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


class CaseResultOut(BaseModel):
    chord: float
    span: float
    node_count: int
    element_count: int
    markers: list[str]
    cl: float
    cd: float
    convergence: ConvergenceOut


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
