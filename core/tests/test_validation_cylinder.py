"""Phase 2 Milestone 0 gate (see docs/DECISIONS.md ADR-0017): before any
polar-sweep or GCI-study machinery is built, prove that the low-Re
cylinder validation case actually converges. Unlike
test_run_case_end_to_end_on_a_real_step_file (NACA0012), which
deliberately does not assert convergence because that case is known not
to converge (docs/RISKS.md R10), this test's whole point is the
convergence assertion itself: if it fails, that is new, important
information that goes back to the project owner before Milestone 1/2
are built on top of this case, not something to work around quietly.
"""

import dataclasses

import pytest

from fosas_core.pipeline import ExecutablePaths, run_case

from .fixtures import cylinder_step
from .validation_cases import LOW_RE_CYLINDER


@pytest.mark.slow
def test_low_re_cylinder_converges(tmp_path, gmsh_executable, su2_executable, mpirun_executable):
    step_path = cylinder_step(
        tmp_path / "cylinder.step", diameter=LOW_RE_CYLINDER.diameter, span=LOW_RE_CYLINDER.span
    )

    # LOW_RE_CYLINDER.params carries the physical case definition (Re,
    # density, viscosity, AoA); max_iterations/mpi_ranks here are pure
    # test-runtime tuning, not part of the case itself. Confirmed by two
    # real runs: rms[P] was already at -10 (past the -8 default
    # threshold) by iteration ~108 at mpi_ranks=1. A follow-up attempt
    # at mpi_ranks=3 was NOT faster, it was slower (still short of 200
    # iterations after 900s) - this AWS instance only has 2 vCPUs
    # (confirmed via `nproc`), so 3 oversubscribed ranks add MPI
    # communication overhead without adding real parallelism. Staying
    # at mpi_ranks=1 and giving it enough iterations/time instead.
    params = dataclasses.replace(LOW_RE_CYLINDER.params, max_iterations=150, mpi_ranks=1)

    result = run_case(
        step_path,
        params,
        tmp_path / "work",
        executables=ExecutablePaths(gmsh=gmsh_executable, su2=su2_executable, mpirun=mpirun_executable),
        mesh_timeout=300,
        solve_timeout=900,
    )

    # Printed, not just asserted: CLAUDE.md's "kein Schoenreden" rule
    # means a boolean pass must still be inspectable by hand, not just
    # trusted. pytest -s shows this; -v alone does not.
    print(f"converged={result.convergence.converged}, final_residual={result.convergence.final_residual}, "
          f"message={result.convergence.message}")
    print(f"cl={result.cl}, cd={result.cd}, mean_y_plus={result.mean_y_plus}, max_y_plus={result.max_y_plus}")
    print("last 5 history rows (residual column):", result.history.column(params.residual_column)[-5:])

    assert result.chord == pytest.approx(LOW_RE_CYLINDER.diameter, rel=1e-2)
    assert result.span == pytest.approx(LOW_RE_CYLINDER.span, rel=1e-2)
    assert result.node_count > 0
    assert result.convergence.converged is True, (
        f"Low-Re cylinder did not converge: {result.convergence.message}. "
        "This is a real finding (see ADR-0017), not a test bug to paper over."
    )
