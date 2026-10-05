"""API response models. Kept separate from fosas_core's dataclasses so
the API's JSON shape can evolve without changing Core's internal types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from fosas_core.gci import GciResult, GridLevel, compute_gci

from fosas_engine.gci_studies import GciStudy
from fosas_engine.jobs import Job, JobStatus, JobStore
from fosas_engine.polar_progress import aggregate_status
from fosas_engine.polar_studies import PolarStudy
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
    dynamic_pressure: float
    reynolds_number: float
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
                dynamic_pressure=job.result.dynamic_pressure,
                reynolds_number=job.result.reynolds_number,
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


class PolarPointOut(BaseModel):
    aoa_deg: float
    job_id: str
    status: JobStatus
    cl: float | None = None
    cd: float | None = None
    converged: bool | None = None


class PolarStudyOut(BaseModel):
    id: str
    created_at: datetime
    step_filename: str
    status: JobStatus
    archived: bool = False
    points: list[PolarPointOut]

    @classmethod
    def from_study(cls, study: PolarStudy, jobs: JobStore) -> "PolarStudyOut":
        points: list[PolarPointOut] = []
        statuses: list[JobStatus] = []
        for aoa, job_id in zip(study.aoa_values, study.job_ids):
            job = jobs.get(job_id)
            if job is None:
                # Should not normally happen (a constituent job deleted
                # individually without the study knowing): report it as
                # failed rather than crashing the whole study view.
                points.append(PolarPointOut(aoa_deg=aoa, job_id=job_id, status="failed"))
                statuses.append("failed")
                continue
            cl = job.result.cl if job.result is not None else None
            cd = job.result.cd if job.result is not None else None
            converged = job.result.convergence.converged if job.result is not None else None
            points.append(
                PolarPointOut(aoa_deg=aoa, job_id=job_id, status=job.status, cl=cl, cd=cd, converged=converged)
            )
            statuses.append(job.status)
        return cls(
            id=study.id,
            created_at=study.created_at,
            step_filename=study.step_filename,
            status=aggregate_status(statuses),
            archived=study.archived,
            points=points,
        )


class GciLevelOut(BaseModel):
    resolution: str  # "fine" | "medium" | "coarse"
    job_id: str
    status: JobStatus
    element_count: int | None = None
    cl: float | None = None
    cd: float | None = None


class GciMetricOut(BaseModel):
    """Mirrors fosas_core.gci.GciResult, once each for cl and cd."""

    r21: float
    apparent_order_p: float
    extrapolated_value: float
    approximate_relative_error: float
    gci_fine_percent: float
    oscillatory: bool
    message: str

    @classmethod
    def from_result(cls, result: GciResult) -> "GciMetricOut":
        return cls(
            r21=result.r21,
            apparent_order_p=result.apparent_order_p,
            extrapolated_value=result.extrapolated_value,
            approximate_relative_error=result.approximate_relative_error,
            gci_fine_percent=result.gci_fine_percent,
            oscillatory=result.oscillatory,
            message=result.message,
        )


class GciResultOut(BaseModel):
    cl: GciMetricOut
    cd: GciMetricOut


_RESOLUTIONS = ("fine", "medium", "coarse")


class GciStudyOut(BaseModel):
    id: str
    created_at: datetime
    step_filename: str
    status: JobStatus
    archived: bool = False
    refinement_ratio: float
    levels: list[GciLevelOut]
    result: GciResultOut | None = None
    result_error: str | None = None

    @classmethod
    def from_study(cls, study: GciStudy, jobs: JobStore) -> "GciStudyOut":
        levels: list[GciLevelOut] = []
        statuses: list[JobStatus] = []
        grid_levels_cl: list[GridLevel] = []
        grid_levels_cd: list[GridLevel] = []
        for resolution, job_id in zip(_RESOLUTIONS, study.job_ids):
            job = jobs.get(job_id)
            if job is None:
                levels.append(GciLevelOut(resolution=resolution, job_id=job_id, status="failed"))
                statuses.append("failed")
                continue
            element_count = job.result.element_count if job.result is not None else None
            cl = job.result.cl if job.result is not None else None
            cd = job.result.cd if job.result is not None else None
            levels.append(
                GciLevelOut(
                    resolution=resolution, job_id=job_id, status=job.status,
                    element_count=element_count, cl=cl, cd=cd,
                )
            )
            statuses.append(job.status)
            if job.result is not None:
                grid_levels_cl.append(GridLevel(element_count=element_count, value=cl))
                grid_levels_cd.append(GridLevel(element_count=element_count, value=cd))

        status = aggregate_status(statuses)
        result_out = None
        result_error = None
        if status == "done":
            # All three jobs done, in fixed fine/medium/coarse order
            # (see gci_studies.GciStudy.job_ids docstring). compute_gci
            # can still raise (e.g. identical cl/cd between two levels,
            # or - if the background_size_*_factor sweep unexpectedly
            # did not produce strictly decreasing element counts -
            # a GridLevel ordering error): caught here so a GCI study
            # whose three runs all finished successfully never crashes
            # the whole response just because the GCI math itself
            # could not be computed from their particular numbers.
            fine_cl, medium_cl, coarse_cl = grid_levels_cl
            fine_cd, medium_cd, coarse_cd = grid_levels_cd
            try:
                result_out = GciResultOut(
                    cl=GciMetricOut.from_result(compute_gci(fine_cl, medium_cl, coarse_cl)),
                    cd=GciMetricOut.from_result(compute_gci(fine_cd, medium_cd, coarse_cd)),
                )
            except ValueError as exc:
                result_out = None
                result_error = str(exc)

        return cls(
            id=study.id,
            created_at=study.created_at,
            step_filename=study.step_filename,
            status=status,
            archived=study.archived,
            refinement_ratio=study.refinement_ratio,
            levels=levels,
            result=result_out,
            result_error=result_error,
        )
