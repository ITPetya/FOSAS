"""API response models. Kept separate from fosas_core's dataclasses so
the API's JSON shape can evolve without changing Core's internal types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from fosas_engine.jobs import Job, JobStatus


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


class JobOut(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    step_filename: str
    stage: str | None = None
    error: str | None = None
    result: CaseResultOut | None = None

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
        return cls(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            step_filename=job.step_filename,
            stage=job.stage,
            error=job.error,
            result=result_out,
        )
