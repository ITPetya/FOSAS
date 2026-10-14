from pathlib import Path

import pytest

from fosas_core.meshing import BoundaryLayerMeshParams, ConstantSectionMeshParams, generate_constant_section_geo, run_gmsh
from fosas_core.solver import (
    FreestreamConditions,
    IterationHistory,
    ReferenceValues,
    SolverError,
    SolverParams,
    _parse_forces_breakdown,
    count_completed_iterations,
    generate_config,
    run_su2,
)

from .airfoils import naca4_points


def _naca0012_freestream():
    # Same conditions used in the Phase 1 spike: Mach 0.15, Re=6e6 for a
    # 0.6 m chord, air properties from the SU2 Inc_Turbulent_NACA0012
    # tutorial, AoA 10 deg with X chordwise, Z vertical.
    return FreestreamConditions(
        density=2.13163,
        velocity=(85.6124, 0.0, 15.0952),
        temperature=288.15,
        dynamic_viscosity=1.853e-5,
    )


def test_freestream_conditions_reject_invalid_input():
    with pytest.raises(ValueError, match="density"):
        FreestreamConditions(density=0, velocity=(1, 0, 0), temperature=288, dynamic_viscosity=1e-5)
    with pytest.raises(ValueError, match="dynamic_viscosity"):
        FreestreamConditions(density=1.2, velocity=(1, 0, 0), temperature=288, dynamic_viscosity=0)


def test_reference_values_reject_invalid_input():
    with pytest.raises(ValueError, match="area"):
        ReferenceValues(length=1.0, area=0)


def test_solver_params_reject_invalid_input():
    with pytest.raises(ValueError, match="max_iterations"):
        SolverParams(
            mesh_su2_path=Path("mesh.su2"),
            freestream=_naca0012_freestream(),
            reference=ReferenceValues(length=0.6, area=0.72),
            max_iterations=0,
        )


def test_generate_config_contains_expected_markers_and_conditions():
    params = SolverParams(
        mesh_su2_path=Path("/tmp/naca0012.su2"),
        freestream=_naca0012_freestream(),
        reference=ReferenceValues(length=0.6, area=0.72),
        max_iterations=50,
    )
    cfg = generate_config(params, output_dir=Path("/tmp/out"))
    assert "SOLVER= INC_RANS" in cfg
    assert "MARKER_HEATFLUX= ( airfoil, 0.0 )" in cfg
    assert "MARKER_FAR= ( farfield )" in cfg
    assert "85.6124" in cfg
    assert "ITER= 50" in cfg
    assert "RESTART_SOL= NO" in cfg


def test_generate_config_with_restart():
    params = SolverParams(
        mesh_su2_path=Path("/tmp/naca0012.su2"),
        freestream=_naca0012_freestream(),
        reference=ReferenceValues(length=0.6, area=0.72),
        restart_solution_path=Path("/tmp/out/restart_flow.dat"),
    )
    cfg = generate_config(params, output_dir=Path("/tmp/out"))
    assert "RESTART_SOL= YES" in cfg
    assert "SOLUTION_FILENAME= /tmp/out/restart_flow.dat" in cfg


def test_run_su2_rejects_missing_executable(tmp_path):
    with pytest.raises(SolverError, match="Could not start"):
        run_su2("SOLVER= INC_RANS", tmp_path, su2_executable="not-a-real-su2-binary")


def test_run_su2_reports_config_error_with_detail(tmp_path, su2_executable):
    # Regression guard: confirms a broken config reliably produces a
    # non-zero exit code with an extractable "Error in ..." block, the
    # basis for treating the exit code as the primary failure signal for
    # SU2 (unlike Gmsh, see meshing.py).
    broken_config = "SOLVER= INC_RANS\nNONSENSE_OPTION_THAT_DOES_NOT_EXIST= YES\n"
    with pytest.raises(SolverError, match="invalid option name"):
        run_su2(broken_config, tmp_path, su2_executable=su2_executable)


def test_iteration_history_column_access():
    history = IterationHistory(columns={"CL": (0.1, 0.2, 0.3), "CD": (0.01, 0.02, 0.03)})
    assert history.column("CL") == (0.1, 0.2, 0.3)
    assert history.num_iterations == 3
    with pytest.raises(KeyError):
        history.column("does_not_exist")


@pytest.mark.slow
def test_end_to_end_mesh_and_solve_produces_parseable_history(tmp_path, gmsh_executable, su2_executable, mpirun_executable):
    """Full vertical slice: mesh a NACA0012 section, run a handful of SU2
    iterations, and confirm the pipeline produces a readable history with
    the expected columns. Does NOT assert on converged cl/cd values, see
    docs/RISKS.md R10: this mesh and iteration count are not expected to
    converge, only to run without error and produce parseable output.
    """
    chord, span = 0.6, 1.2
    mesh_params = ConstantSectionMeshParams(
        profile_points_xz=naca4_points(chord=chord, n=25),
        span=span,
        chord=chord,
        boundary_layer=BoundaryLayerMeshParams(first_cell_height=2.7e-6, growth_ratio=1.25, thickness=0.02),
        span_layers=10,
    )
    mesh_path = tmp_path / "mesh.su2"
    geo = generate_constant_section_geo(mesh_params, mesh_path)
    run_gmsh(geo, mesh_path, gmsh_executable=gmsh_executable, timeout=180)

    solver_params = SolverParams(
        mesh_su2_path=mesh_path,
        freestream=_naca0012_freestream(),
        reference=ReferenceValues(length=chord, area=chord * span),
        max_iterations=15,
        time_discretization="RUNGE-KUTTA_EXPLICIT",  # avoids the single-rank implicit OOM from R10
    )
    output_dir = tmp_path / "solve"
    config_text = generate_config(solver_params, output_dir)
    result = run_su2(
        config_text, output_dir, su2_executable=su2_executable, mpi_ranks=3, mpirun_executable=mpirun_executable, timeout=300
    )

    assert result.history.num_iterations == 15
    assert "CL" in result.history.columns
    assert "CD" in result.history.columns
    assert abs(result.final("CL")) < 50  # would be in the millions if the run diverged
    assert abs(result.final("CD")) < 50
    assert result.surface.num_points > 0
    assert "Pressure_Coefficient" in result.surface.columns
    assert "Y_Plus" in result.surface.columns
    # Pressure/friction drag split (point 6, docs/ARCHITECTURE.md): must
    # sum exactly to the breakdown file's own total, and that total
    # should be close to the history CD (not exact: the breakdown file
    # prints fewer decimal digits, same tolerance as pipeline.run_case's
    # own cross-check).
    breakdown = result.forces_breakdown
    # Real run, not the hand-picked excerpt below: the file only prints 6
    # decimal digits, so pressure+friction can be off from the printed
    # total by a rounding unit in the last digit (observed directly:
    # 0.627198 vs printed total 0.627197), not a parsing bug.
    assert breakdown.cd_pressure + breakdown.cd_friction == pytest.approx(breakdown.cd_total, abs=1e-5)
    assert abs(breakdown.cd_total - result.final("CD")) < max(1e-6, abs(result.final("CD")) * 0.01)


# Trimmed excerpt of a real SU2 8.5.0 forces_breakdown.dat (captured
# 2026-10-14, cylinder test case), with the per-surface section's own
# numbers deliberately changed from the real file so this test actually
# proves the global ("Forces breakdown:") section's "Total CD:" line is
# the one parsed, not the later per-surface repeat further down.
_REAL_BREAKDOWN_EXCERPT = """
Forces breakdown:

Center of Pressure: X=-9984.297651Z-0.005943.

 m.

NOTE: Multiply forces by the non-dimensional factor: 0.049000, and the reference factor: 1.000000
to obtain the dimensional force.

Total CL:      -0.000627 | Pressure (  242%):   -0.001520 | Friction ( -142%):    0.000892 | Momentum (    0%):    0.000000
Total CD:       6.263383 | Pressure (   98%):    6.142443 | Friction (    1%):    0.120940 | Momentum (    0%):    0.000000
Total CSF:      0.000070 | Pressure (    0%):   -0.000000 | Friction (   99%):    0.000070 | Momentum (    0%):    0.000000


Surface name: airfoil

Total CD    (  100%):    1.000000 | Pressure (   50%):    0.500000 | Friction (   50%):    0.500000 | Momentum (    0%):    0.000000
"""


def test_parse_forces_breakdown_reads_the_global_section_not_the_per_surface_repeat(tmp_path):
    path = tmp_path / "forces_breakdown.dat"
    path.write_text(_REAL_BREAKDOWN_EXCERPT)
    breakdown = _parse_forces_breakdown(path)
    assert breakdown.cd_total == pytest.approx(6.263383)
    assert breakdown.cd_pressure == pytest.approx(6.142443)
    assert breakdown.cd_friction == pytest.approx(0.120940)
    # Pressure + friction must reproduce the total to within the file's
    # own printed precision (6 decimals; see the real end-to-end test
    # below for a case where this is off by one unit in the last digit,
    # not exact for every run).
    assert breakdown.cd_pressure + breakdown.cd_friction == pytest.approx(breakdown.cd_total, abs=1e-5)


def test_parse_forces_breakdown_rejects_a_file_without_the_expected_line(tmp_path):
    path = tmp_path / "forces_breakdown.dat"
    path.write_text("Some unrelated SU2 output with no Total CD line at all.\n")
    with pytest.raises(SolverError, match="Total CD"):
        _parse_forces_breakdown(path)


def test_count_completed_iterations_reports_zero_when_nothing_exists_yet(tmp_path):
    assert count_completed_iterations(tmp_path / "does_not_exist") == 0
    empty_dir = tmp_path / "solve"
    empty_dir.mkdir()
    assert count_completed_iterations(empty_dir) == 0  # SU2 started but has not written history.csv yet


def test_count_completed_iterations_counts_only_complete_rows(tmp_path):
    output_dir = tmp_path / "solve"
    output_dir.mkdir()
    history = output_dir / "history.csv"
    header = '"Time_Iter","Inner_Iter","rms[P]"\n'
    complete_rows = "0,0,-1.0\n0,1,-1.5\n0,2,-1.8\n"
    history.write_text(header + complete_rows)
    assert count_completed_iterations(output_dir) == 3

    # A live SU2 process can be caught mid-write of its next line: fewer
    # fields than the header (the write was cut off before finishing).
    history.write_text(header + complete_rows + "0,3")
    assert count_completed_iterations(output_dir) == 3
