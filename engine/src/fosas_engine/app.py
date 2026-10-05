"""FastAPI app factory.

Rule from docs/ARCHITECTURE.md: the UI must not be able to do anything
the API cannot. There is no separate internal code path, everything a
future web UI would call goes through these same endpoints, which is
also why FastAPI's own interactive docs (/docs) are treated as a valid
first client, not just a debugging aid (see core/README.md, "Testbarkeit
ueber Webseite").

V1 scope: a single case pipeline (fosas_core.pipeline.run_case) exposed
as an async job. No cache integration yet (see fosas_core.cache), no
WebSocket progress channel yet, both are natural follow-ups once this
shape is validated.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from fosas_core.pipeline import CaseParams, ExecutablePaths, PipelineError, run_case
from fosas_core.report import (
    CombinedReportData,
    GciReportData,
    GciReportLevel,
    GciReportMetric,
    PolarReportData,
    PolarReportPoint,
    ReportError,
    render_combined_report,
    render_gci_report,
    render_polar_report,
)

from fosas_engine.gci_studies import GciStudyStore, new_gci_study_id
from fosas_engine.jobs import Job, JobNotArchivableError, JobNotDeletableError, JobNotResumableError, JobStore, new_job_id
from fosas_engine.models import GciStudyOut, JobOut, PolarStudyOut
from fosas_engine.polar_studies import PolarStudyStore, new_polar_study_id
from fosas_engine.settings import Settings

_WEB_CLIENT_PATH = Path(__file__).resolve().parents[3] / "clients" / "web" / "index.html"
_VIEWER_CLIENT_PATH = Path(__file__).resolve().parents[3] / "clients" / "web" / "viewer.html"


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="FOSAS Engine",
        description=(
            "Local automation engine for FOSAS. Every endpoint requires "
            "the bearer token printed at startup, except /health."
        ),
        version="0.0.1",
    )
    app.state.settings = settings
    settings.work_root.mkdir(parents=True, exist_ok=True)
    app.state.jobs = JobStore.load_from_disk(settings.work_root)
    app.state.polar_studies = PolarStudyStore.load_from_disk(settings.work_root)
    app.state.gci_studies = GciStudyStore.load_from_disk(settings.work_root)
    app.state.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)

    # A job that was still "running" when the engine last stopped (crash
    # or deliberate restart) never got to call mark_done/mark_failed. Its
    # own work is not lost (fosas_core.pipeline.run_case picks up the
    # existing mesh/restart file, see docs/RISKS.md R14), but nothing
    # will resume it unless it is resubmitted here.
    for job in app.state.jobs.list():
        if job.status in ("pending", "running"):
            app.state.executor.submit(_execute_job, app, job.id, job.step_path, job.params, job.work_dir)

    def require_token(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {settings.token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index():
        # No token check here on purpose: the token has to reach the
        # browser somehow, and reaching this route at all already implies
        # network access to the engine (127.0.0.1 plus, for a remote
        # machine, an SSH tunnel), the same trust boundary /docs relies on.
        if not _WEB_CLIENT_PATH.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Web client not found at {_WEB_CLIENT_PATH}. Use /docs instead.",
            )
        html = _WEB_CLIENT_PATH.read_text()
        return html.replace("__FOSAS_TOKEN__", settings.token)

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer():
        # Same trust boundary as "/", see the comment there. Opened in a
        # new tab from the main page's 3D view (?job=<id> in the URL);
        # not linked to a specific job here, it reads that from its own
        # URL like the main page's ?job= resume flow does.
        if not _VIEWER_CLIENT_PATH.exists():
            raise HTTPException(status_code=500, detail=f"Viewer client not found at {_VIEWER_CLIENT_PATH}.")
        html = _VIEWER_CLIENT_PATH.read_text()
        return html.replace("__FOSAS_TOKEN__", settings.token)

    @app.post("/jobs", response_model=JobOut, dependencies=[Depends(require_token)])
    async def create_job(
        step_file: UploadFile,
        velocity: float = Form(..., description="Freestream velocity magnitude, m/s"),
        aoa_deg: float = Form(..., description="Angle of attack, degrees"),
        density: float = Form(1.225, description="Air density, kg/m^3"),
        dynamic_viscosity: float = Form(1.81e-5, description="Dynamic viscosity, Pa*s"),
        temperature: float = Form(288.15, description="Temperature, K"),
        target_y_plus: float = Form(1.0),
        growth_ratio: float = Form(1.2),
        bl_thickness_factor: float = Form(0.05, description="Boundary layer thickness, as a factor of chord"),
        span_layers: int = Form(24),
        n_profile_points: int = Form(60),
        max_iterations: int = Form(500),
        mpi_ranks: int = Form(1),
        time_discretization: str = Form("EULER_IMPLICIT"),
        residual_threshold: float = Form(-8.0),
    ):
        try:
            params = CaseParams(
                velocity=velocity,
                aoa_deg=aoa_deg,
                density=density,
                dynamic_viscosity=dynamic_viscosity,
                temperature=temperature,
                target_y_plus=target_y_plus,
                growth_ratio=growth_ratio,
                bl_thickness_factor=bl_thickness_factor,
                span_layers=span_layers,
                n_profile_points=n_profile_points,
                max_iterations=max_iterations,
                mpi_ranks=mpi_ranks,
                time_discretization=time_discretization,
                residual_threshold=residual_threshold,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        step_bytes = await step_file.read()
        job = _create_and_submit_job(app, params, step_file.filename or "geometry.step", step_bytes)
        return JobOut.from_job(job)

    @app.get("/jobs", response_model=list[JobOut], dependencies=[Depends(require_token)])
    def list_jobs(archived: bool = False):
        # Auto-archive/auto-delete (see docs/DECISIONS.md ADR-0015) is
        # applied lazily inside JobStore.list on every call, not by a
        # background scheduler: cheap at the job counts this tool expects.
        return [JobOut.from_job(job) for job in app.state.jobs.list(include_archived=archived)]

    @app.get("/jobs/{job_id}", response_model=JobOut, dependencies=[Depends(require_token)])
    def get_job(job_id: str):
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No such job")
        return JobOut.from_job(job)

    @app.post("/jobs/{job_id}/resume", response_model=JobOut, dependencies=[Depends(require_token)])
    def resume_job(job_id: str):
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No such job")
        try:
            app.state.jobs.prepare_for_resume(job_id)
        except JobNotResumableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        app.state.executor.submit(_execute_job, app, job.id, job.step_path, job.params, job.work_dir)
        return JobOut.from_job(app.state.jobs.get(job_id))

    @app.post("/jobs/{job_id}/archive", response_model=JobOut, dependencies=[Depends(require_token)])
    def archive_job(job_id: str):
        if app.state.jobs.get(job_id) is None:
            raise HTTPException(status_code=404, detail="No such job")
        try:
            app.state.jobs.archive(job_id)
        except JobNotArchivableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JobOut.from_job(app.state.jobs.get(job_id))

    @app.post("/jobs/{job_id}/unarchive", response_model=JobOut, dependencies=[Depends(require_token)])
    def unarchive_job(job_id: str):
        if app.state.jobs.get(job_id) is None:
            raise HTTPException(status_code=404, detail="No such job")
        app.state.jobs.unarchive(job_id)
        return JobOut.from_job(app.state.jobs.get(job_id))

    @app.delete("/jobs/{job_id}", dependencies=[Depends(require_token)])
    def delete_job(job_id: str):
        if app.state.jobs.get(job_id) is None:
            raise HTTPException(status_code=404, detail="No such job")
        try:
            app.state.jobs.delete(job_id)
        except JobNotDeletableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"deleted": job_id}

    @app.post("/polar-studies", response_model=PolarStudyOut, dependencies=[Depends(require_token)])
    async def create_polar_study(
        step_file: UploadFile,
        aoa_values: list[float] = Form(..., description="Angle of attack values to sweep, degrees"),
        velocity: float = Form(..., description="Freestream velocity magnitude, m/s"),
        density: float = Form(1.225, description="Air density, kg/m^3"),
        dynamic_viscosity: float = Form(1.81e-5, description="Dynamic viscosity, Pa*s"),
        temperature: float = Form(288.15, description="Temperature, K"),
        target_y_plus: float = Form(1.0),
        growth_ratio: float = Form(1.2),
        bl_thickness_factor: float = Form(0.05, description="Boundary layer thickness, as a factor of chord"),
        span_layers: int = Form(24),
        n_profile_points: int = Form(60),
        max_iterations: int = Form(500),
        mpi_ranks: int = Form(1),
        time_discretization: str = Form("EULER_IMPLICIT"),
        residual_threshold: float = Form(-8.0),
    ):
        # Every AoA value becomes its own, fully independent Job (see
        # docs/DECISIONS.md ADR-0017): a polar sweep deliberately reuses
        # 100% of the existing single-case Job machinery (progress,
        # resume, archive, delete) unchanged, rather than teaching
        # Job/JobStore about multiple results per job.
        if not aoa_values:
            raise HTTPException(status_code=422, detail="aoa_values must not be empty")

        step_bytes = await step_file.read()
        step_filename = step_file.filename or "geometry.step"
        job_ids = []
        for aoa in aoa_values:
            try:
                params = CaseParams(
                    velocity=velocity,
                    aoa_deg=aoa,
                    density=density,
                    dynamic_viscosity=dynamic_viscosity,
                    temperature=temperature,
                    target_y_plus=target_y_plus,
                    growth_ratio=growth_ratio,
                    bl_thickness_factor=bl_thickness_factor,
                    span_layers=span_layers,
                    n_profile_points=n_profile_points,
                    max_iterations=max_iterations,
                    mpi_ranks=mpi_ranks,
                    time_discretization=time_discretization,
                    residual_threshold=residual_threshold,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            job = _create_and_submit_job(app, params, step_filename, step_bytes)
            job_ids.append(job.id)

        study = app.state.polar_studies.create(
            new_polar_study_id(), step_filename, tuple(aoa_values), tuple(job_ids), settings.work_root
        )
        return PolarStudyOut.from_study(study, app.state.jobs)

    @app.get("/polar-studies", response_model=list[PolarStudyOut], dependencies=[Depends(require_token)])
    def list_polar_studies(archived: bool = False):
        return [
            PolarStudyOut.from_study(study, app.state.jobs)
            for study in app.state.polar_studies.list(include_archived=archived)
        ]

    @app.get("/polar-studies/{study_id}", response_model=PolarStudyOut, dependencies=[Depends(require_token)])
    def get_polar_study(study_id: str):
        study = app.state.polar_studies.get(study_id)
        if study is None:
            raise HTTPException(status_code=404, detail="No such polar study")
        return PolarStudyOut.from_study(study, app.state.jobs)

    @app.post("/polar-studies/{study_id}/archive", response_model=PolarStudyOut, dependencies=[Depends(require_token)])
    def archive_polar_study(study_id: str):
        if app.state.polar_studies.get(study_id) is None:
            raise HTTPException(status_code=404, detail="No such polar study")
        app.state.polar_studies.archive(study_id)
        return PolarStudyOut.from_study(app.state.polar_studies.get(study_id), app.state.jobs)

    @app.post("/polar-studies/{study_id}/unarchive", response_model=PolarStudyOut, dependencies=[Depends(require_token)])
    def unarchive_polar_study(study_id: str):
        if app.state.polar_studies.get(study_id) is None:
            raise HTTPException(status_code=404, detail="No such polar study")
        app.state.polar_studies.unarchive(study_id)
        return PolarStudyOut.from_study(app.state.polar_studies.get(study_id), app.state.jobs)

    @app.delete("/polar-studies/{study_id}", dependencies=[Depends(require_token)])
    def delete_polar_study(study_id: str):
        # Removes only this study's own small reference record, never
        # the constituent jobs/CFD results it points to - those are
        # deleted individually via DELETE /jobs/{id} if actually wanted,
        # see polar_studies.PolarStudyStore.delete.
        if app.state.polar_studies.get(study_id) is None:
            raise HTTPException(status_code=404, detail="No such polar study")
        app.state.polar_studies.delete(study_id)
        return {"deleted": study_id}

    @app.get("/polar-studies/{study_id}/report", dependencies=[Depends(require_token)])
    def get_polar_study_report(study_id: str):
        # Phase 2, first/narrow report: one polar, no GCI data yet (see
        # docs/DECISIONS.md and the plan this was built from). Pulls
        # straight from PolarStudyOut.points, which already carries
        # cl/cd/status/converged per AoA value - no separate JobStore
        # lookup needed beyond what from_study already did.
        study = app.state.polar_studies.get(study_id)
        if study is None:
            raise HTTPException(status_code=404, detail="No such polar study")
        study_out = PolarStudyOut.from_study(study, app.state.jobs)

        report_data = PolarReportData(
            title=study_out.step_filename,
            generated_at=datetime.now(timezone.utc),
            points=tuple(
                PolarReportPoint(
                    aoa_deg=p.aoa_deg, cl=p.cl, cd=p.cd, status=p.status, converged=p.converged
                )
                for p in study_out.points
            ),
        )
        try:
            pdf_bytes = render_polar_report(report_data)
        except ReportError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="polar_report_{study_id}.pdf"'},
        )

    @app.post("/gci-studies", response_model=GciStudyOut, dependencies=[Depends(require_token)])
    async def create_gci_study(
        step_file: UploadFile,
        velocity: float = Form(..., description="Freestream velocity magnitude, m/s"),
        aoa_deg: float = Form(..., description="Angle of attack, degrees"),
        refinement_ratio: float = Form(1.5, description="Mesh refinement ratio between consecutive levels"),
        density: float = Form(1.225, description="Air density, kg/m^3"),
        dynamic_viscosity: float = Form(1.81e-5, description="Dynamic viscosity, Pa*s"),
        temperature: float = Form(288.15, description="Temperature, K"),
        target_y_plus: float = Form(1.0),
        growth_ratio: float = Form(1.2),
        bl_thickness_factor: float = Form(0.05, description="Boundary layer thickness, as a factor of chord"),
        span_layers: int = Form(24),
        n_profile_points: int = Form(60),
        max_iterations: int = Form(500),
        mpi_ranks: int = Form(1),
        time_discretization: str = Form("EULER_IMPLICIT"),
        residual_threshold: float = Form(-8.0),
    ):
        # Exactly 3 resolutions (fine/medium/coarse, see
        # docs/DECISIONS.md ADR-0017): only background_size_min_factor/
        # max_factor vary between them (far-field/wake density), domain
        # size and near-wall sizing (target_y_plus, growth_ratio,
        # bl_thickness_factor) stay fixed, as the GCI method requires.
        # farfield_factor_* is deliberately not exposed here at all.
        if refinement_ratio <= 1.0:
            raise HTTPException(status_code=422, detail="refinement_ratio must be greater than 1.0")

        step_bytes = await step_file.read()
        step_filename = step_file.filename or "geometry.step"

        base_min_factor = 0.01
        base_max_factor = 0.5
        # fine, medium, coarse order (see GciStudy.job_ids docstring).
        factor_scales = [refinement_ratio**2, refinement_ratio, 1.0]
        job_ids = []
        for scale in factor_scales:
            try:
                params = CaseParams(
                    velocity=velocity,
                    aoa_deg=aoa_deg,
                    density=density,
                    dynamic_viscosity=dynamic_viscosity,
                    temperature=temperature,
                    target_y_plus=target_y_plus,
                    growth_ratio=growth_ratio,
                    bl_thickness_factor=bl_thickness_factor,
                    span_layers=span_layers,
                    n_profile_points=n_profile_points,
                    max_iterations=max_iterations,
                    mpi_ranks=mpi_ranks,
                    time_discretization=time_discretization,
                    residual_threshold=residual_threshold,
                    background_size_min_factor=base_min_factor / scale,
                    background_size_max_factor=base_max_factor / scale,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            job = _create_and_submit_job(app, params, step_filename, step_bytes)
            job_ids.append(job.id)

        study = app.state.gci_studies.create(
            new_gci_study_id(), step_filename, refinement_ratio, tuple(job_ids), settings.work_root
        )
        return GciStudyOut.from_study(study, app.state.jobs)

    @app.get("/gci-studies", response_model=list[GciStudyOut], dependencies=[Depends(require_token)])
    def list_gci_studies(archived: bool = False):
        return [
            GciStudyOut.from_study(study, app.state.jobs)
            for study in app.state.gci_studies.list(include_archived=archived)
        ]

    @app.get("/gci-studies/{study_id}", response_model=GciStudyOut, dependencies=[Depends(require_token)])
    def get_gci_study(study_id: str):
        study = app.state.gci_studies.get(study_id)
        if study is None:
            raise HTTPException(status_code=404, detail="No such GCI study")
        return GciStudyOut.from_study(study, app.state.jobs)

    @app.post("/gci-studies/{study_id}/archive", response_model=GciStudyOut, dependencies=[Depends(require_token)])
    def archive_gci_study(study_id: str):
        if app.state.gci_studies.get(study_id) is None:
            raise HTTPException(status_code=404, detail="No such GCI study")
        app.state.gci_studies.archive(study_id)
        return GciStudyOut.from_study(app.state.gci_studies.get(study_id), app.state.jobs)

    @app.post("/gci-studies/{study_id}/unarchive", response_model=GciStudyOut, dependencies=[Depends(require_token)])
    def unarchive_gci_study(study_id: str):
        if app.state.gci_studies.get(study_id) is None:
            raise HTTPException(status_code=404, detail="No such GCI study")
        app.state.gci_studies.unarchive(study_id)
        return GciStudyOut.from_study(app.state.gci_studies.get(study_id), app.state.jobs)

    @app.delete("/gci-studies/{study_id}", dependencies=[Depends(require_token)])
    def delete_gci_study(study_id: str):
        # Removes only this study's own small reference record, never
        # the constituent jobs/CFD results it points to.
        if app.state.gci_studies.get(study_id) is None:
            raise HTTPException(status_code=404, detail="No such GCI study")
        app.state.gci_studies.delete(study_id)
        return {"deleted": study_id}

    @app.get("/gci-studies/{study_id}/report", dependencies=[Depends(require_token)])
    def get_gci_study_report(study_id: str):
        study = app.state.gci_studies.get(study_id)
        if study is None:
            raise HTTPException(status_code=404, detail="No such GCI study")
        study_out = GciStudyOut.from_study(study, app.state.jobs)

        levels = tuple(
            GciReportLevel(
                resolution=lvl.resolution, element_count=lvl.element_count, cl=lvl.cl, cd=lvl.cd, status=lvl.status
            )
            for lvl in study_out.levels
        )

        def to_metric(metric_out) -> GciReportMetric | None:
            if metric_out is None:
                return None
            return GciReportMetric(
                r21=metric_out.r21,
                apparent_order_p=metric_out.apparent_order_p,
                extrapolated_value=metric_out.extrapolated_value,
                gci_fine_percent=metric_out.gci_fine_percent,
                oscillatory=metric_out.oscillatory,
                message=metric_out.message,
            )

        report_data = GciReportData(
            title=study_out.step_filename,
            generated_at=datetime.now(timezone.utc),
            refinement_ratio=study_out.refinement_ratio,
            levels=levels,
            cl_metric=to_metric(study_out.result.cl if study_out.result else None),
            cd_metric=to_metric(study_out.result.cd if study_out.result else None),
            result_error=study_out.result_error,
        )
        try:
            pdf_bytes = render_gci_report(report_data)
        except ReportError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="gci_report_{study_id}.pdf"'},
        )

    @app.get("/reports/combined", dependencies=[Depends(require_token)])
    def get_combined_report(polar_study_id: str, gci_study_id: str):
        # Explicit two-id choice, no automatic matching: a PolarStudy
        # and a GciStudy have no linkage field (see
        # fosas_core.report.render_combined_report's docstring) -
        # combining them is always something the caller asks for by
        # naming both ids, never inferred from e.g. a matching filename.
        polar_study = app.state.polar_studies.get(polar_study_id)
        if polar_study is None:
            raise HTTPException(status_code=404, detail="No such polar study")
        gci_study = app.state.gci_studies.get(gci_study_id)
        if gci_study is None:
            raise HTTPException(status_code=404, detail="No such GCI study")

        polar_study_out = PolarStudyOut.from_study(polar_study, app.state.jobs)
        gci_study_out = GciStudyOut.from_study(gci_study, app.state.jobs)

        polar_report_data = PolarReportData(
            title=polar_study_out.step_filename,
            generated_at=datetime.now(timezone.utc),
            points=tuple(
                PolarReportPoint(aoa_deg=p.aoa_deg, cl=p.cl, cd=p.cd, status=p.status, converged=p.converged)
                for p in polar_study_out.points
            ),
        )
        gci_levels = tuple(
            GciReportLevel(
                resolution=lvl.resolution, element_count=lvl.element_count, cl=lvl.cl, cd=lvl.cd, status=lvl.status
            )
            for lvl in gci_study_out.levels
        )

        def to_metric(metric_out) -> GciReportMetric | None:
            if metric_out is None:
                return None
            return GciReportMetric(
                r21=metric_out.r21,
                apparent_order_p=metric_out.apparent_order_p,
                extrapolated_value=metric_out.extrapolated_value,
                gci_fine_percent=metric_out.gci_fine_percent,
                oscillatory=metric_out.oscillatory,
                message=metric_out.message,
            )

        gci_report_data = GciReportData(
            title=gci_study_out.step_filename,
            generated_at=datetime.now(timezone.utc),
            refinement_ratio=gci_study_out.refinement_ratio,
            levels=gci_levels,
            cl_metric=to_metric(gci_study_out.result.cl if gci_study_out.result else None),
            cd_metric=to_metric(gci_study_out.result.cd if gci_study_out.result else None),
            result_error=gci_study_out.result_error,
        )

        combined_data = CombinedReportData(
            generated_at=datetime.now(timezone.utc), polar=polar_report_data, gci=gci_report_data
        )
        try:
            pdf_bytes = render_combined_report(combined_data)
        except ReportError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="combined_report_{polar_study_id}_{gci_study_id}.pdf"'
            },
        )

    @app.exception_handler(PipelineError)
    def _unhandled_pipeline_error(request, exc: PipelineError):
        # Should not normally surface here (background jobs catch this
        # themselves), but present if it ever does escape a request path.
        return JSONResponse(status_code=500, content={"stage": exc.stage, "detail": str(exc)})

    return app


# run_case's own default (7200s) is only enough for a few thousand
# iterations at typical per-iteration cost observed so far (roughly 2-3s
# on the reference AWS instance, see docs/RISKS.md R17); a job explicitly
# asking for many more iterations must not be silently held to a ceiling
# sized for the common case. 10s/iteration is a deliberately generous
# per-iteration allowance (several times the observed rate) so this only
# extends the ceiling for genuinely long requests, confirmed the hard way:
# a real 5000-iteration run hit the fixed 7200s default and was killed
# with ~2960 iterations done, recovered only via the resume mechanism.
_SOLVE_SECONDS_PER_ITERATION = 10.0
_SOLVE_TIMEOUT_FLOOR = 7200.0


def _create_and_submit_job(app: FastAPI, params: CaseParams, step_filename: str, step_bytes: bytes) -> Job:
    """Shared by POST /jobs and POST /polar-studies (one call per AoA
    value): builds a fresh job id/work_dir, writes the uploaded STEP
    bytes into it, creates the Job record, and submits it to the
    executor. A pure, behaviour-preserving extraction out of the old
    inline POST /jobs body.
    """
    settings: Settings = app.state.settings
    job_id = new_job_id()
    work_dir = settings.work_root / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    step_path = work_dir / "input.step"
    step_path.write_bytes(step_bytes)

    job = app.state.jobs.create(job_id, params, step_filename, step_path, work_dir)
    app.state.executor.submit(_execute_job, app, job.id, step_path, params, work_dir)
    return job


def _execute_job(app: FastAPI, job_id: str, step_path: Path, params: CaseParams, work_dir: Path) -> None:
    settings: Settings = app.state.settings
    jobs: JobStore = app.state.jobs
    jobs.mark_running(job_id)
    solve_timeout = max(_SOLVE_TIMEOUT_FLOOR, params.max_iterations * _SOLVE_SECONDS_PER_ITERATION)
    try:
        result = run_case(
            step_path,
            params,
            work_dir,
            executables=ExecutablePaths(
                gmsh=settings.gmsh_executable,
                su2=settings.su2_executable,
                mpirun=settings.mpirun_executable,
            ),
            solve_timeout=solve_timeout,
        )
    except PipelineError as exc:
        jobs.mark_failed(job_id, stage=exc.stage, error=str(exc))
    except Exception as exc:  # last resort: a job must never hang as "running" forever
        jobs.mark_failed(job_id, stage="unknown", error=f"Unexpected error: {exc!r}")
    else:
        jobs.mark_done(job_id, result)
