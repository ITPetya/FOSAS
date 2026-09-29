from pathlib import Path

import pytest

from fosas_core.pipeline import CaseParams, ExecutablePaths, PipelineError, run_case

from .fixtures import naca0012_wing_step


def test_case_params_reject_invalid_input():
    with pytest.raises(ValueError, match="velocity"):
        CaseParams(velocity=0, aoa_deg=0)
    with pytest.raises(ValueError, match="max_iterations"):
        CaseParams(velocity=10, aoa_deg=0, max_iterations=0)


def test_run_case_reports_geometry_error_for_missing_file(tmp_path):
    params = CaseParams(velocity=50, aoa_deg=5)
    with pytest.raises(PipelineError) as exc_info:
        run_case(tmp_path / "does_not_exist.step", params, tmp_path / "work")
    assert exc_info.value.stage == "geometry"


@pytest.mark.slow
def test_run_case_end_to_end_on_a_real_step_file(tmp_path, gmsh_executable, su2_executable, mpirun_executable):
    """Full pipeline exactly as the engine will call it: real STEP file
    in (built with the axis convention the pipeline assumes), real
    non-zero cl/cd out, honest convergence assessment. Deliberately does
    not assert convergence=True, since this coarse/short case is known
    not to converge (see docs/RISKS.md R10); it asserts the assessment
    is present and consistent instead.
    """
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=25)
    params = CaseParams(
        velocity=86.933,
        aoa_deg=10.0,
        density=2.13163,
        dynamic_viscosity=1.853e-5,
        span_layers=8,
        max_iterations=15,
        mpi_ranks=1,
        time_discretization="RUNGE-KUTTA_EXPLICIT",
    )
    result = run_case(
        step_path,
        params,
        tmp_path / "work",
        executables=ExecutablePaths(gmsh=gmsh_executable, su2=su2_executable, mpirun=mpirun_executable),
        mesh_timeout=180,
        solve_timeout=300,
    )

    assert result.chord == pytest.approx(0.6, rel=1e-3)
    assert result.span == pytest.approx(1.2, rel=1e-3)
    assert set(result.markers) == {"airfoil", "farfield"}
    assert result.node_count > 0
    assert result.cl != 0.0  # would be exactly 0 if the axis convention were wrong again, see ARCHITECTURE.md
    assert result.convergence.converged is False  # known for this short/coarse case
    assert result.surface.num_points > 0
    assert "Pressure_Coefficient" in result.surface.columns
    assert result.mean_y_plus > 0
    assert result.max_y_plus >= result.mean_y_plus
    assert isinstance(result.convergence.message, str) and result.convergence.message
