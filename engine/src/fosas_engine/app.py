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

Optional login gate (settings.public_password, see docs/RISKS.md R23):
"/", "/viewer" and "/app.js" embed the real bearer token directly into
the page for ANY client that loads them - by design, see the comment on
"/" below - which is fine as long as the engine is only ever reachable
through an already-trusted network (loopback, or Tailscale). The moment
that stops being true (e.g. "tailscale funnel" exposing the port to the
public internet), those three routes - plus /docs/openapi.json, which do
not leak the token but do reveal the API's shape - hand out full control
to anyone who finds the URL. When settings.public_password is set, all
of them instead require a session cookie obtained by POSTing the
password to /login first; when it is None (the default), nothing changes
from before. This is a second, independent secret from the bearer token
itself, deliberately: the token still has to reach the browser somehow,
and now a password-gated login page is that path instead of "anyone who
can load the route at all".
"""

from __future__ import annotations

import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from fosas_core.geometry import GeometryError, ROTATION_LABELS, apply_named_rotation, detect_axis_orientation, import_step
from fosas_core.pipeline import CaseParams, ExecutablePaths, PipelineError, run_case
from fosas_core.report import (
    CombinedReportData,
    GciReportData,
    GciReportLevel,
    GciReportMetric,
    JobReportData,
    JobReportSurfacePoint,
    PolarReportData,
    PolarReportPoint,
    ReportError,
    render_combined_report,
    render_gci_report,
    render_job_report,
    render_polar_report,
)

from fosas_engine.gci_studies import GciStudyStore, new_gci_study_id
from fosas_engine.geometry_previews import GeometryPreviewStore
from fosas_engine.jobs import Job, JobNotArchivableError, JobNotDeletableError, JobNotResumableError, JobStore, new_job_id
from fosas_engine.models import GciStudyOut, GeometryPreviewOut, GeometryVariantOut, JobOut, PolarStudyOut
from fosas_engine.polar_studies import PolarStudyStore, new_polar_study_id
from fosas_engine.settings import Settings

_WEB_CLIENT_PATH = Path(__file__).resolve().parents[3] / "clients" / "web" / "index.html"
_VIEWER_CLIENT_PATH = Path(__file__).resolve().parents[3] / "clients" / "web" / "viewer.html"
_APP_JS_PATH = Path(__file__).resolve().parents[3] / "clients" / "web" / "app.js"


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="FOSAS Engine",
        description=(
            "Local automation engine for FOSAS. Every endpoint requires "
            "the bearer token printed at startup, except /health. If "
            "settings.public_password is set, '/', '/viewer', '/app.js', "
            "and the docs routes additionally require a /login session "
            "cookie first (see module docstring)."
        ),
        version="0.0.1",
    )
    app.state.settings = settings
    settings.work_root.mkdir(parents=True, exist_ok=True)
    app.state.jobs = JobStore.load_from_disk(settings.work_root)
    app.state.polar_studies = PolarStudyStore.load_from_disk(settings.work_root)
    app.state.gci_studies = GciStudyStore.load_from_disk(settings.work_root)
    app.state.geometry_previews = GeometryPreviewStore(settings.work_root / "previews")
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

    # --- Optional login gate (settings.public_password), see module
    # docstring and docs/RISKS.md R23. Session tokens and failed-login
    # counters are in-memory only, same lifetime as the bearer token
    # itself (lost on restart) - no new persistence layer for this.
    app.state.sessions = set()
    app.state.login_attempts = {}
    _LOGIN_MAX_ATTEMPTS = 5
    _LOGIN_WINDOW_SECONDS = 300.0

    def _client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def _has_valid_session(request: Request) -> bool:
        if settings.public_password is None:
            return True  # gate disabled entirely, nothing changes from before
        token = request.cookies.get("fosas_session")
        return token is not None and token in app.state.sessions

    def _login_page(next_path: str, error: str | None = None) -> str:
        error_html = f'<p class="error">{error}</p>' if error else ""
        return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>FOSAS Login</title>
<style>
body {{ font-family: sans-serif; background: #1a1d23; color: #eee; display: flex;
  align-items: center; justify-content: center; height: 100vh; margin: 0; }}
form {{ background: #242830; padding: 24px 32px; border-radius: 8px; min-width: 260px; }}
input {{ padding: 8px; margin: 8px 0; width: 100%; box-sizing: border-box; }}
button {{ padding: 8px 16px; cursor: pointer; }}
.error {{ color: #ff6b6b; }}
</style></head>
<body>
<form method="post" action="/login">
<h2>FOSAS</h2>
<input type="hidden" name="next" value="{next_path}">
<label for="password">Passwort</label>
<input type="password" id="password" name="password" autofocus>
<button type="submit">Anmelden</button>
{error_html}
</form>
</body></html>"""

    def _login_redirect(request: Request) -> RedirectResponse:
        next_path = request.url.path
        if request.url.query:
            next_path += "?" + request.url.query
        return RedirectResponse(url=f"/login?next={next_path}")

    @app.middleware("http")
    async def _gate_docs_routes(request: Request, call_next):
        # /docs, /redoc, /openapi.json are FastAPI/Starlette's own
        # auto-registered routes - there is no Depends() injection point
        # for them, hence a middleware instead of a route-level check
        # like the other gated paths below. They do not leak the bearer
        # token, only the API's shape, but that is still real
        # information disclosure once this engine is reachable from
        # outside the tailnet.
        if settings.public_password is not None and request.url.path in ("/docs", "/redoc", "/openapi.json"):
            if not _has_valid_session(request):
                return _login_redirect(request)
        return await call_next(request)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(next: str = "/"):
        if settings.public_password is None:
            raise HTTPException(status_code=404)
        return _login_page(next)

    @app.post("/login")
    def login_submit(request: Request, password: str = Form(...), next: str = Form("/")):
        if settings.public_password is None:
            raise HTTPException(status_code=404)
        ip = _client_ip(request)
        now = time.monotonic()
        recent_failures = [t for t in app.state.login_attempts.get(ip, []) if now - t < _LOGIN_WINDOW_SECONDS]
        if len(recent_failures) >= _LOGIN_MAX_ATTEMPTS:
            return HTMLResponse(
                _login_page(next, "Zu viele Fehlversuche. Bitte einige Minuten warten."),
                status_code=429,
            )
        if not secrets.compare_digest(password, settings.public_password):
            recent_failures.append(now)
            app.state.login_attempts[ip] = recent_failures
            return HTMLResponse(_login_page(next, "Falsches Passwort."), status_code=401)
        app.state.login_attempts.pop(ip, None)
        session_token = secrets.token_urlsafe(32)
        app.state.sessions.add(session_token)
        response = RedirectResponse(url=next or "/", status_code=303)
        response.set_cookie(
            "fosas_session", session_token, httponly=True, samesite="lax", max_age=30 * 24 * 3600
        )
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        # No bearer-token check here on purpose: the token has to reach
        # the browser somehow, and reaching this route at all already
        # implies network access to the engine (127.0.0.1 plus, for a
        # remote machine, an SSH tunnel), the same trust boundary /docs
        # relies on - UNLESS settings.public_password is set, meaning
        # that assumption no longer holds (see module docstring), in
        # which case a valid /login session is required instead.
        if not _has_valid_session(request):
            return _login_redirect(request)
        if not _WEB_CLIENT_PATH.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Web client not found at {_WEB_CLIENT_PATH}. Use /docs instead.",
            )
        html = _WEB_CLIENT_PATH.read_text()
        return html.replace("__FOSAS_TOKEN__", settings.token)

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer(request: Request):
        # Same trust boundary as "/", see the comment there. Opened in a
        # new tab from the main page's 3D view (?job=<id> in the URL);
        # not linked to a specific job here, it reads that from its own
        # URL like the main page's ?job= resume flow does.
        if not _has_valid_session(request):
            return _login_redirect(request)
        if not _VIEWER_CLIENT_PATH.exists():
            raise HTTPException(status_code=500, detail=f"Viewer client not found at {_VIEWER_CLIENT_PATH}.")
        html = _VIEWER_CLIENT_PATH.read_text()
        return html.replace("__FOSAS_TOKEN__", settings.token)

    @app.get("/app.js")
    def app_js(request: Request):
        # Same trust boundary as "/" and "/viewer", see the comment on
        # "/": no bearer-token check, the token itself has to reach the
        # browser through this exact file (it embeds __FOSAS_TOKEN__,
        # replaced below, same as the two HTML routes) - gated by the
        # login session instead when settings.public_password is set.
        if not _has_valid_session(request):
            return _login_redirect(request)
        if not _APP_JS_PATH.exists():
            raise HTTPException(status_code=500, detail=f"app.js not found at {_APP_JS_PATH}.")
        js = _APP_JS_PATH.read_text()
        return Response(content=js.replace("__FOSAS_TOKEN__", settings.token), media_type="application/javascript")

    @app.post("/geometry/preview", response_model=GeometryPreviewOut, dependencies=[Depends(require_token)])
    async def create_geometry_preview(step_file: UploadFile):
        # Manual rotation preview (docs/ARCHITECTURE.md
        # "Koordinatenkonvention", ADR-0020 Teil B): deliberately
        # synchronous, inline in the request handler, not submitted to
        # app.state.executor - import_step and tessellate are both cheap
        # (no Gmsh/SU2 involved at all here, confirmed ~0.1s combined on
        # a real wing file in the approved plan), so a background job
        # would only add latency for no benefit.
        step_bytes = await step_file.read()
        preview = app.state.geometry_previews.create(step_bytes)
        try:
            geometry = import_step(preview.step_path)
        except GeometryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        orientation = detect_axis_orientation(geometry.shape)

        bbox = geometry.shape.bounding_box()
        diagonal = (
            (bbox.max.X - bbox.min.X) ** 2 + (bbox.max.Y - bbox.min.Y) ** 2 + (bbox.max.Z - bbox.min.Z) ** 2
        ) ** 0.5
        # A fixed absolute tessellation tolerance (e.g. the 0.1mm used
        # ad-hoc while verifying the plan) only looks reasonable for a
        # ~100mm-chord wing; scaling it to the actual geometry's own
        # size keeps triangle counts (and thus response size) similar
        # regardless of whether the part is 10mm or 10m across. This is
        # for a visual preview only, nowhere near as strict as a meshing
        # tolerance would need to be.
        tessellate_tolerance = max(diagonal * 0.001, 1e-4)

        variants = []
        for label in ROTATION_LABELS:
            shape = geometry.shape if label == "identity" else apply_named_rotation(geometry.shape, label)
            vertices, triangles = shape.tessellate(tessellate_tolerance, 0.3)
            variants.append(
                GeometryVariantOut(
                    label=label,
                    vertices=[(v.X, v.Y, v.Z) for v in vertices],
                    triangles=list(triangles),
                )
            )

        return GeometryPreviewOut.from_orientation(preview.id, orientation, variants)

    @app.post("/jobs", response_model=JobOut, dependencies=[Depends(require_token)])
    async def create_job(
        step_file: UploadFile | None = None,
        preview_id: str | None = Form(
            None, description="Use an already-uploaded geometry from POST /geometry/preview instead of step_file"
        ),
        manual_rotation_label: str | None = Form(
            None,
            description=(
                "Explicit axis orientation chosen in the geometry preview tool, one of "
                f"{ROTATION_LABELS}; overrides automatic detection when set"
            ),
        ),
        velocity: float = Form(..., description="Freestream velocity magnitude, m/s"),
        aoa_deg: float = Form(..., description="Angle of attack, degrees"),
        sideslip_deg: float = Form(0.0, description="Sideslip angle (crosswind), degrees"),
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
        material: str | None = Form(
            None, description="Optional material for a weight-force estimate, see fosas_core.materials"
        ),
    ):
        try:
            params = CaseParams(
                velocity=velocity,
                aoa_deg=aoa_deg,
                sideslip_deg=sideslip_deg,
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
                material=material or None,
                manual_rotation_label=manual_rotation_label or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        step_bytes, step_filename = await _resolve_step_bytes(app, step_file, preview_id)
        job = _create_and_submit_job(app, params, step_filename, step_bytes)
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

    @app.get("/jobs/{job_id}/report", dependencies=[Depends(require_token)])
    def get_job_report(job_id: str):
        # Phase 3, point 11 of the technical-mechanics requirement
        # (docs/ARCHITECTURE.md): the single-job counterpart of the
        # polar/GCI/combined reports above, mirroring the browser's own
        # result panel on paper. Built straight from job.result
        # (fosas_core.pipeline.CaseResult), not JobOut, since this stays
        # inside the engine process and does not need the Pydantic
        # round-trip the HTTP response layer uses.
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No such job")
        if job.result is None:
            raise HTTPException(status_code=409, detail="Job has no result yet (not done or failed)")

        surface = job.result.surface
        xs = surface.column("x")
        zs = surface.column("z")
        cps = surface.column("Pressure_Coefficient")
        report_data = JobReportData(
            step_filename=job.step_filename,
            generated_at=datetime.now(timezone.utc),
            aoa_deg=job.result.aoa_deg,
            sideslip_deg=job.result.sideslip_deg,
            cl=job.result.cl,
            cd=job.result.cd,
            cs=job.result.cs,
            cd_pressure=job.result.cd_pressure,
            cd_friction=job.result.cd_friction,
            drag_pressure=job.result.drag_pressure,
            drag_friction=job.result.drag_friction,
            converged=job.result.convergence.converged,
            convergence_message=job.result.convergence.message,
            mean_y_plus=job.result.mean_y_plus,
            max_y_plus=job.result.max_y_plus,
            mean_wall_shear_stress=job.result.mean_wall_shear_stress,
            max_wall_shear_stress=job.result.max_wall_shear_stress,
            dynamic_pressure=job.result.dynamic_pressure,
            reynolds_number=job.result.reynolds_number,
            reference_area=job.result.forces.reference_area,
            lift=job.result.forces.lift,
            drag=job.result.forces.drag,
            side=job.result.forces.side,
            resultant=job.result.forces.resultant,
            glide_ratio=job.result.forces.glide_ratio,
            resultant_angle_deg=job.result.forces.resultant_angle_deg,
            reference_length=job.result.moments.reference_length,
            moment_origin=job.result.moments.moment_origin,
            cmx=job.result.moments.cmx,
            cmy=job.result.moments.cmy,
            cmz=job.result.moments.cmz,
            mx=job.result.moments.mx,
            my=job.result.moments.my,
            mz=job.result.moments.mz,
            center_of_mass=job.result.center_of_mass,
            volume=job.result.volume,
            material=job.result.material,
            material_density=job.result.material_density,
            mass=job.result.mass,
            weight=job.result.weight,
            surface_points=tuple(
                JobReportSurfacePoint(x=xs[i], z=zs[i], cp=cps[i]) for i in range(surface.num_points)
            ),
        )
        try:
            pdf_bytes = render_job_report(report_data)
        except ReportError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="job_report_{job_id}.pdf"'},
        )

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
        step_file: UploadFile | None = None,
        preview_id: str | None = Form(
            None, description="Use an already-uploaded geometry from POST /geometry/preview instead of step_file"
        ),
        manual_rotation_label: str | None = Form(
            None,
            description=(
                "Explicit axis orientation chosen in the geometry preview tool, one of "
                f"{ROTATION_LABELS}; overrides automatic detection when set"
            ),
        ),
        aoa_values: list[float] = Form(..., description="Angle of attack values to sweep, degrees"),
        velocity: float = Form(..., description="Freestream velocity magnitude, m/s"),
        sideslip_deg: float = Form(0.0, description="Sideslip angle (crosswind), degrees, fixed across the sweep"),
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
        material: str | None = Form(
            None, description="Optional material for a weight-force estimate, see fosas_core.materials"
        ),
    ):
        # Every AoA value becomes its own, fully independent Job (see
        # docs/DECISIONS.md ADR-0017): a polar sweep deliberately reuses
        # 100% of the existing single-case Job machinery (progress,
        # resume, archive, delete) unchanged, rather than teaching
        # Job/JobStore about multiple results per job.
        if not aoa_values:
            raise HTTPException(status_code=422, detail="aoa_values must not be empty")

        step_bytes, step_filename = await _resolve_step_bytes(app, step_file, preview_id)
        job_ids = []
        for aoa in aoa_values:
            try:
                params = CaseParams(
                    velocity=velocity,
                    aoa_deg=aoa,
                    sideslip_deg=sideslip_deg,
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
                    material=material or None,
                    manual_rotation_label=manual_rotation_label or None,
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
        step_file: UploadFile | None = None,
        preview_id: str | None = Form(
            None, description="Use an already-uploaded geometry from POST /geometry/preview instead of step_file"
        ),
        manual_rotation_label: str | None = Form(
            None,
            description=(
                "Explicit axis orientation chosen in the geometry preview tool, one of "
                f"{ROTATION_LABELS}; overrides automatic detection when set"
            ),
        ),
        velocity: float = Form(..., description="Freestream velocity magnitude, m/s"),
        aoa_deg: float = Form(..., description="Angle of attack, degrees"),
        sideslip_deg: float = Form(0.0, description="Sideslip angle (crosswind), degrees"),
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
        material: str | None = Form(
            None, description="Optional material for a weight-force estimate, see fosas_core.materials"
        ),
    ):
        # Exactly 3 resolutions (fine/medium/coarse, see
        # docs/DECISIONS.md ADR-0017): only background_size_min_factor/
        # max_factor vary between them (far-field/wake density), domain
        # size and near-wall sizing (target_y_plus, growth_ratio,
        # bl_thickness_factor) stay fixed, as the GCI method requires.
        # farfield_factor_* is deliberately not exposed here at all.
        if refinement_ratio <= 1.0:
            raise HTTPException(status_code=422, detail="refinement_ratio must be greater than 1.0")

        step_bytes, step_filename = await _resolve_step_bytes(app, step_file, preview_id)

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
                    sideslip_deg=sideslip_deg,
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
                    material=material or None,
                    manual_rotation_label=manual_rotation_label or None,
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


async def _resolve_step_bytes(
    app: FastAPI, step_file: UploadFile | None, preview_id: str | None
) -> tuple[bytes, str]:
    """Shared by POST /jobs, /polar-studies, /gci-studies: a submission
    either uploads a fresh STEP file, or references one already
    uploaded to the geometry preview tool (see geometry_previews.py,
    ADR-0020 Teil B) - exactly one of the two, never both and never
    neither, so a submission never silently runs on the wrong file.
    """
    if step_file is not None and preview_id is not None:
        raise HTTPException(status_code=422, detail="Provide either step_file or preview_id, not both")
    if step_file is not None:
        return await step_file.read(), step_file.filename or "geometry.step"
    if preview_id is not None:
        preview = app.state.geometry_previews.get(preview_id)
        if preview is None:
            raise HTTPException(
                status_code=404, detail="No such geometry preview (expired after 2 hours, or never existed)"
            )
        return preview.step_path.read_bytes(), preview.step_path.name
    raise HTTPException(status_code=422, detail="Provide either step_file or preview_id")


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
