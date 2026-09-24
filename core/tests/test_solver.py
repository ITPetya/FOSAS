from pathlib import Path

import pytest

from fosas_core.meshing import BoundaryLayerMeshParams, ConstantSectionMeshParams, generate_constant_section_geo, run_gmsh
from fosas_core.solver import (
    FreestreamConditions,
    IterationHistory,
    ReferenceValues,
    SolverError,
    SolverParams,
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
