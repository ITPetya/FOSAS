"""Live progress for a running job.

Computed on demand from the filesystem on every poll, never stored:
storing it would mean keeping a second, derivable copy of state that
fosas_core already writes (mesh.su2's existence, history.csv's growing
row count), risking the two drifting apart. See docs/ARCHITECTURE.md,
job progress tracking, and docs/RISKS.md R14 for why job state lives in
files at all.

Two phases only, matching what fosas_core.pipeline.run_case actually
does: "meshing" (Gmsh has not produced mesh.su2 yet) and "solving" (SU2
is writing history.csv). Meshing has no usable progress signal: Gmsh
reports no percentage FOSAS can read while it runs (confirmed: its
progress-relevant log lines only appear per completed operation, not on
a fixed schedule usable for extrapolation), so `current_iteration`,
`max_iterations`, `percent` and `eta_seconds` are honestly reported as
unknown (None) for that phase rather than guessed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fosas_core.solver import count_completed_iterations

from fosas_engine.jobs import Job


@dataclass
class Progress:
    phase: str  # "meshing" or "solving"
    current_iteration: int | None
    max_iterations: int | None
    percent: float | None
    elapsed_seconds: float
    eta_seconds: float | None


def compute_progress(job: Job) -> Progress | None:
    """None when there is nothing in-progress to report (job is not
    currently running): a finished or failed job has its final result
    instead, a pending job has not started any phase yet.
    """
    if job.status != "running":
        return None

    mesh_path = job.work_dir / "mesh.su2"
    if not mesh_path.exists():
        return Progress(
            phase="meshing",
            current_iteration=None,
            max_iterations=None,
            percent=None,
            elapsed_seconds=time.time() - job.created_at.timestamp(),
            eta_seconds=None,
        )

    solve_dir = job.work_dir / "solve"
    config_path = solve_dir / "config.cfg"
    max_iterations = job.params.max_iterations
    if not config_path.exists():
        # Mesh is done, but run_su2 has not written its own config.cfg
        # yet (brief window right at the phase transition).
        return Progress(
            phase="solving",
            current_iteration=0,
            max_iterations=max_iterations,
            percent=0.0,
            elapsed_seconds=time.time() - mesh_path.stat().st_mtime,
            eta_seconds=None,
        )

    # config.cfg is (re)written by generate_config immediately before
    # every SU2 invocation, including a resumed one, so its mtime marks
    # the start of THIS solve attempt even when mesh.su2 is much older
    # (reused from a previous, interrupted attempt, see RISKS.md R14) -
    # unlike mesh.su2's own mtime, which would not be.
    elapsed = time.time() - config_path.stat().st_mtime
    current_iteration = count_completed_iterations(solve_dir)
    percent = (current_iteration / max_iterations * 100) if max_iterations else None
    eta_seconds = None
    if current_iteration > 0:
        seconds_per_iteration = elapsed / current_iteration
        eta_seconds = seconds_per_iteration * max(max_iterations - current_iteration, 0)

    return Progress(
        phase="solving",
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        percent=percent,
        elapsed_seconds=elapsed,
        eta_seconds=eta_seconds,
    )
