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
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from fosas_core.pipeline import CaseParams, ExecutablePaths, PipelineError, run_case

from fosas_engine.jobs import JobNotDeletableError, JobNotResumableError, JobStore, new_job_id
from fosas_engine.models import JobOut
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

        job_id = new_job_id()
        work_dir = settings.work_root / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        step_path = work_dir / "input.step"
        step_path.write_bytes(await step_file.read())

        job = app.state.jobs.create(job_id, params, step_file.filename or "geometry.step", step_path, work_dir)
        app.state.executor.submit(_execute_job, app, job.id, step_path, params, work_dir)
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
        app.state.jobs.archive(job_id)
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
