"""API response models. Kept separate from fosas_core's dataclasses so
the API's JSON shape can evolve without changing Core's internal types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from fosas_engine.jobs import Job, JobStatus
from fosas_engine.progress import compute_progress


class ConvergenceOut(BaseModel):
    converged: bool
    final_residual: float
    residual_threshold: float
    is_plateaued: bool
    message: str


class SurfacePointOut(BaseModel):
    x: float
    y: float
    z: float
    cp: float
    y_plus: float


class CaseResultOut(BaseModel):
    chord: float
    span: float
    node_count: int
    element_count: int
    markers: list[str]
    cl: float
    cd: float
    convergence: ConvergenceOut
    mean_y_plus: float
    max_y_plus: float
    surface: list[SurfacePointOut]


class ProgressOut(BaseModel):
    phase: str
    current_iteration: int | None
    max_iterations: int | None
    percent: float | None
    elapsed_seconds: float
    eta_seconds: float | None


class JobOut(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    finished_at: datetime | None = None
    archived: bool = False
    step_filename: str
    stage: str | None = None
    error: str | None = None
    result: CaseResultOut | None = None
    progress: ProgressOut | None = None

    @classmethod
    def from_job(cls, job: Job) -> "JobOut":
        result_out = None
        if job.result is not None:
            surface = job.result.surface
            xs = surface.column("x")
            ys = surface.column("y")
            zs = surface.column("z")
            cps = surface.column("Pressure_Coefficient")
            y_pluses = surface.column("Y_Plus")
            surface_out = [
                SurfacePointOut(x=xs[i], y=ys[i], z=zs[i], cp=cps[i], y_plus=y_pluses[i])
                for i in range(surface.num_points)
            ]
            result_out = CaseResultOut(
                chord=job.result.chord,
                span=job.result.span,
                node_count=job.result.node_count,
                element_count=job.result.element_count,
                markers=list(job.result.markers),
                cl=job.result.cl,
                cd=job.result.cd,
                convergence=ConvergenceOut(
                    converged=job.result.convergence.converged,
                    final_residual=job.result.convergence.final_residual,
                    residual_threshold=job.result.convergence.residual_threshold,
                    is_plateaued=job.result.convergence.is_plateaued,
                    message=job.result.convergence.message,
                ),
                mean_y_plus=job.result.mean_y_plus,
                max_y_plus=job.result.max_y_plus,
                surface=surface_out,
            )
        progress = compute_progress(job)
        progress_out = (
            ProgressOut(
                phase=progress.phase,
                current_iteration=progress.current_iteration,
                max_iterations=progress.max_iterations,
                percent=progress.percent,
                elapsed_seconds=progress.elapsed_seconds,
                eta_seconds=progress.eta_seconds,
            )
            if progress is not None
            else None
        )
        return cls(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            finished_at=job.finished_at,
            archived=job.archived,
            step_filename=job.step_filename,
            stage=job.stage,
            error=job.error,
            result=result_out,
            progress=progress_out,
        )
