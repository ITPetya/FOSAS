import time

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import naca0012_wing_step

from fosas_engine.app import create_app
from fosas_engine.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(token="test-token-123", work_root=tmp_path / "cases")


@pytest.fixture
def client(settings):
    app = create_app(settings)
    return TestClient(app)


def test_viewer_route_serves_html_with_token_injected(client, settings):
    response = client.get("/viewer")
    assert response.status_code == 200
    assert settings.token in response.text
    assert "__FOSAS_TOKEN__" not in response.text


def test_index_and_app_js_serve_token_without_a_password_set(client, settings):
    # Default behaviour (settings.public_password is None): no change
    # from before the login gate existed. index.html itself references
    # app.js as an external file (no inline script, see ARCHITECTURE.md
    # Phase 3 step 1), so the token is only embedded in /app.js's
    # response, not /'s - same as /viewer, which IS a single file.
    assert client.get("/").status_code == 200

    js_response = client.get("/app.js")
    assert js_response.status_code == 200
    assert settings.token in js_response.text
    assert "__FOSAS_TOKEN__" not in js_response.text


def test_login_route_404s_when_no_password_is_set(client):
    assert client.get("/login").status_code == 404
    assert client.post("/login", data={"password": "whatever"}).status_code == 404


def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_jobs_endpoint_rejects_missing_token(client):
    response = client.get("/jobs")
    assert response.status_code == 401


def test_jobs_endpoint_rejects_wrong_token(client):
    response = client.get("/jobs", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_unknown_job_is_404(client, settings):
    response = client.get("/jobs/does-not-exist", headers={"Authorization": f"Bearer {settings.token}"})
    assert response.status_code == 404


def _fake_case_result(work_dir):
    from fosas_core.forces import ForceSystem, MomentSystem
    from fosas_core.pipeline import CaseResult
    from fosas_core.quality import ConvergenceAssessment
    from fosas_core.solver import IterationHistory, SurfaceData

    return CaseResult(
        chord=0.6,
        span=1.2,
        node_count=1234,
        element_count=5678,
        markers=("airfoil", "farfield"),
        aoa_deg=5.0,
        sideslip_deg=0.0,
        cl=1.29,
        cd=0.08,
        cs=0.0,
        cd_pressure=0.075,
        cd_friction=0.005,
        drag_pressure=1.5,
        drag_friction=0.1,
        frontal_area=0.06,
        cl_frontal=12.9,
        cd_frontal=0.8,
        convergence=ConvergenceAssessment(
            converged=False, final_residual=-3.5, residual_threshold=-8.0,
            is_plateaued=True, message="did not converge",
        ),
        history=IterationHistory(columns={"rms[P]": (-1.0, -2.0, -3.5)}),
        surface=SurfaceData(columns={
            "x": (0.0, 0.6), "y": (0.0, 0.0), "z": (0.0, 0.01),
            "Pressure_Coefficient": (0.5, -0.3), "Y_Plus": (1.0, 1.2),
            "Skin_Friction_Coefficient_x": (0.01, 0.02),
            "Skin_Friction_Coefficient_y": (0.0, 0.0),
            "Skin_Friction_Coefficient_z": (0.001, -0.001),
        }),
        mean_y_plus=0.9,
        max_y_plus=1.4,
        mean_wall_shear_stress=3.2,
        max_wall_shear_stress=8.7,
        dynamic_pressure=450.6,
        reynolds_number=2.1e6,
        forces=ForceSystem(
            reference_area=0.72, lift=334.8, drag=20.8, side=0.0, resultant=335.4,
            glide_ratio=16.1, resultant_angle_deg=86.4,
        ),
        moments=MomentSystem(
            reference_length=0.6, moment_origin=(0.3, 0.6, 0.0),
            cmx=0.001, cmy=-0.08, cmz=0.0002,
            mx=0.1, my=-12.5, mz=0.02,
        ),
        center_of_mass=(0.3, 0.6, 0.0),
        volume=0.00012,
        material="aluminium",
        material_density=2700.0,
        mass=0.324,
        weight=3.177,
        mesh_path=work_dir / "mesh.su2",
        solve_dir=work_dir / "solve",
    )


def _create_finished_job(app, work_root, job_id, status="done"):
    from fosas_core.pipeline import CaseParams

    work_dir = work_root / job_id
    work_dir.mkdir(parents=True)
    (work_dir / "input.step").write_bytes(b"dummy")
    job = app.state.jobs.create(job_id, CaseParams(velocity=30, aoa_deg=5), "wing.step", work_dir / "input.step", work_dir)
    app.state.jobs.mark_running(job.id)
    if status == "done":
        app.state.jobs.mark_done(job.id, _fake_case_result(work_dir))
    else:
        app.state.jobs.mark_failed(job.id, stage="solving", error="boom")
    return work_dir


def test_archive_unarchive_and_list_filtering(client, settings, tmp_path):
    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    _create_finished_job(app, settings.work_root, "job1")
    headers = {"Authorization": f"Bearer {settings.token}"}

    assert [j["id"] for j in client.get("/jobs", headers=headers).json()] == ["job1"]

    resp = client.post("/jobs/job1/archive", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["archived"] is True
    assert client.get("/jobs", headers=headers).json() == []
    assert [j["id"] for j in client.get("/jobs?archived=true", headers=headers).json()] == ["job1"]

    resp = client.post("/jobs/job1/unarchive", headers=headers)
    assert resp.json()["archived"] is False
    assert [j["id"] for j in client.get("/jobs", headers=headers).json()] == ["job1"]


def test_resume_resubmits_a_failed_job(client, settings, tmp_path, monkeypatch):
    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    _create_finished_job(app, settings.work_root, "job1", status="failed")
    headers = {"Authorization": f"Bearer {settings.token}"}

    import fosas_engine.app as app_module

    captured = {}

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        captured["called"] = True
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    resp = client.post("/jobs/job1/resume", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running", "failed")  # race with the background thread

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and "called" not in captured:
        time.sleep(0.05)
    assert captured.get("called") is True


def test_resume_refuses_a_done_job(client, settings, tmp_path):
    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    _create_finished_job(app, settings.work_root, "job1", status="done")
    headers = {"Authorization": f"Bearer {settings.token}"}

    resp = client.post("/jobs/job1/resume", headers=headers)
    assert resp.status_code == 409


def test_resume_unknown_job_is_404(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.post("/jobs/does-not-exist/resume", headers=headers).status_code == 404


def test_archive_unknown_job_is_404(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.post("/jobs/does-not-exist/archive", headers=headers).status_code == 404
    assert client.post("/jobs/does-not-exist/unarchive", headers=headers).status_code == 404
    assert client.delete("/jobs/does-not-exist", headers=headers).status_code == 404


def test_delete_job_removes_it(client, settings, tmp_path):
    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    work_dir = _create_finished_job(app, settings.work_root, "job1", status="failed")
    headers = {"Authorization": f"Bearer {settings.token}"}

    resp = client.delete("/jobs/job1", headers=headers)
    assert resp.status_code == 200
    assert client.get("/jobs/job1", headers=headers).status_code == 404
    assert not work_dir.exists()


def test_delete_running_job_is_rejected(client, settings, tmp_path):
    from fosas_core.pipeline import CaseParams

    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    work_dir = settings.work_root / "job1"
    work_dir.mkdir(parents=True)
    app.state.jobs.create("job1", CaseParams(velocity=30, aoa_deg=5), "wing.step", work_dir / "input.step", work_dir)
    app.state.jobs.mark_running("job1")
    headers = {"Authorization": f"Bearer {settings.token}"}

    resp = client.delete("/jobs/job1", headers=headers)
    assert resp.status_code == 409
    assert work_dir.exists()


def test_execute_job_scales_solve_timeout_with_max_iterations(client, settings, tmp_path, monkeypatch):
    """Regression test for a real incident (docs/RISKS.md R17): a job
    explicitly asking for 5000 iterations was killed by run_case's fixed
    7200s default solve_timeout after completing only ~2960 of them.
    _execute_job must scale the timeout it passes to run_case with the
    job's own max_iterations instead of relying on that fixed default.
    """
    import fosas_engine.app as app_module

    captured = {}

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        captured["solve_timeout"] = solve_timeout
        captured["max_iterations"] = params.max_iterations
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    with open(step_path, "rb") as f:
        response = client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_deg": "5", "max_iterations": "5000"},
        )
    assert response.status_code == 200
    job_id = response.json()["id"]

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "solve_timeout" not in captured:
        time.sleep(0.05)

    assert captured["max_iterations"] == 5000
    assert captured["solve_timeout"] >= 5000 * 10.0  # generous per-iteration allowance, not the fixed 7200s default

    job = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {settings.token}"}).json()
    assert job["status"] == "failed"


def test_get_job_reports_solving_progress(client, settings, tmp_path):
    from fosas_core.pipeline import CaseParams

    work_dir = tmp_path / "cases" / "fake-job"
    solve_dir = work_dir / "solve"
    solve_dir.mkdir(parents=True)
    (work_dir / "mesh.su2").write_text("fake mesh")
    (solve_dir / "config.cfg").write_text("fake config")
    header = '"Time_Iter","Inner_Iter","rms[P]"\n'
    rows = "\n".join(f"0,{i},-1.0" for i in range(30)) + "\n"
    (solve_dir / "history.csv").write_text(header + rows)

    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    app.state.jobs.create(
        "fake-job",
        CaseParams(velocity=30, aoa_deg=5, max_iterations=100),
        "wing.step",
        work_dir / "input.step",
        work_dir,
    )
    app.state.jobs.mark_running("fake-job")

    response = client.get("/jobs/fake-job", headers={"Authorization": f"Bearer {settings.token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["progress"]["phase"] == "solving"
    assert body["progress"]["current_iteration"] == 30
    assert body["progress"]["max_iterations"] == 100
    assert body["progress"]["percent"] == 30.0
    assert body["progress"]["eta_seconds"] is not None


def test_create_job_rejects_invalid_params(client, settings, tmp_path):
    step_path = naca0012_wing_step(tmp_path / "wing.step")
    with open(step_path, "rb") as f:
        response = client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "0", "aoa_deg": "5"},  # velocity must be positive
        )
    assert response.status_code == 422


@pytest.mark.slow
def test_create_and_poll_a_real_job(client, settings, tmp_path, gmsh_executable, su2_executable, mpirun_executable, monkeypatch):
    monkeypatch.setenv("FOSAS_GMSH_EXECUTABLE", gmsh_executable)
    monkeypatch.setenv("FOSAS_SU2_EXECUTABLE", su2_executable)
    monkeypatch.setenv("FOSAS_MPIRUN_EXECUTABLE", mpirun_executable)
    # Settings reads the executables from the environment at construction
    # time, so build a fresh app after setting the env vars above.
    settings = Settings(token="test-token-123", work_root=tmp_path / "cases")
    app = create_app(settings)
    client = TestClient(app)

    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=25)
    with open(step_path, "rb") as f:
        response = client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={
                "velocity": "86.933",
                "aoa_deg": "10.0",
                "density": "2.13163",
                "dynamic_viscosity": "1.853e-5",
                "span_layers": "8",
                "max_iterations": "15",
                "mpi_ranks": "1",
                "time_discretization": "RUNGE-KUTTA_EXPLICIT",
            },
        )
    assert response.status_code == 200
    job_id = response.json()["id"]

    deadline = time.monotonic() + 180
    job = None
    while time.monotonic() < deadline:
        job = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {settings.token}"}).json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(2)

    assert job is not None
    assert job["status"] == "done", job


def test_create_polar_study_rejects_empty_aoa_values(client, settings, tmp_path):
    step_path = naca0012_wing_step(tmp_path / "wing.step")
    with open(step_path, "rb") as f:
        response = client.post(
            "/polar-studies",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30"},
        )
    assert response.status_code == 422


def test_create_polar_study_creates_one_job_per_aoa_value(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/polar-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_values": ["0", "5", "10"]},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["points"]) == 3
    assert [p["aoa_deg"] for p in body["points"]] == [0.0, 5.0, 10.0]
    job_ids = [p["job_id"] for p in body["points"]]
    assert len(set(job_ids)) == 3  # three distinct, fully independent jobs

    # Each AoA value's job is an ordinary job, independently visible and
    # manageable via the existing /jobs routes (see docs/DECISIONS.md
    # ADR-0017: reuse, not a new parallel job concept).
    jobs_list = client.get("/jobs", headers=headers).json()
    assert {j["id"] for j in jobs_list} == set(job_ids)


def test_create_polar_study_rejects_invalid_params(client, settings, tmp_path):
    step_path = naca0012_wing_step(tmp_path / "wing.step")
    with open(step_path, "rb") as f:
        response = client.post(
            "/polar-studies",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "0", "aoa_values": ["0"]},  # velocity must be positive
        )
    assert response.status_code == 422


def test_polar_study_status_aggregates_from_constituent_jobs(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/polar-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_values": ["0", "5"]},
        )
    study_id = response.json()["id"]

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/polar-studies/{study_id}", headers=headers).json()
        if body["status"] == "failed":
            break
        time.sleep(0.05)

    assert body["status"] == "failed"  # both constituent jobs fail (fake_run_case), so the study aggregates to failed
    assert all(p["status"] == "failed" for p in body["points"])


def test_polar_study_not_found(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.get("/polar-studies/does-not-exist", headers=headers).status_code == 404
    assert client.post("/polar-studies/does-not-exist/archive", headers=headers).status_code == 404
    assert client.post("/polar-studies/does-not-exist/unarchive", headers=headers).status_code == 404
    assert client.delete("/polar-studies/does-not-exist", headers=headers).status_code == 404


def test_delete_polar_study_does_not_delete_constituent_jobs(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/polar-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_values": ["0"]},
        )
    study_id = response.json()["id"]
    job_id = response.json()["points"][0]["job_id"]

    assert client.delete(f"/polar-studies/{study_id}", headers=headers).status_code == 200
    assert client.get(f"/polar-studies/{study_id}", headers=headers).status_code == 404
    # The job itself is untouched, still independently visible.
    assert client.get(f"/jobs/{job_id}", headers=headers).status_code == 200


def test_create_gci_study_rejects_invalid_refinement_ratio(client, settings, tmp_path):
    step_path = naca0012_wing_step(tmp_path / "wing.step")
    with open(step_path, "rb") as f:
        response = client.post(
            "/gci-studies",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_deg": "5", "refinement_ratio": "1.0"},  # must be > 1.0
        )
    assert response.status_code == 422


def test_create_gci_study_rejects_invalid_params(client, settings, tmp_path):
    step_path = naca0012_wing_step(tmp_path / "wing.step")
    with open(step_path, "rb") as f:
        response = client.post(
            "/gci-studies",
            headers={"Authorization": f"Bearer {settings.token}"},
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "0", "aoa_deg": "5"},  # velocity must be positive
        )
    assert response.status_code == 422


def test_create_gci_study_creates_three_jobs_with_decreasing_background_size_factors(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    captured_params = []

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        captured_params.append(params)
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/gci-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_deg": "5", "refinement_ratio": "1.5"},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["levels"]) == 3
    assert [lvl["resolution"] for lvl in body["levels"]] == ["fine", "medium", "coarse"]
    job_ids = [lvl["job_id"] for lvl in body["levels"]]
    assert len(set(job_ids)) == 3

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and len(captured_params) < 3:
        time.sleep(0.05)
    assert len(captured_params) == 3

    # fine has the SMALLEST background_size factors (smallest cells,
    # most elements), coarse the LARGEST (base defaults), confirmed
    # directly on the actual CaseParams each job was given, not just on
    # the refinement_ratio input.
    fine_params, medium_params, coarse_params = captured_params
    assert fine_params.background_size_min_factor < medium_params.background_size_min_factor < coarse_params.background_size_min_factor
    assert fine_params.background_size_max_factor < medium_params.background_size_max_factor < coarse_params.background_size_max_factor
    assert coarse_params.background_size_min_factor == pytest.approx(0.01)
    assert coarse_params.background_size_max_factor == pytest.approx(0.5)
    # Everything else about the three cases must be identical (same
    # domain size, near-wall sizing): only far-field/wake density
    # varies, as the GCI method requires.
    assert fine_params.target_y_plus == medium_params.target_y_plus == coarse_params.target_y_plus
    assert fine_params.growth_ratio == medium_params.growth_ratio == coarse_params.growth_ratio


def test_gci_study_not_found(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.get("/gci-studies/does-not-exist", headers=headers).status_code == 404
    assert client.post("/gci-studies/does-not-exist/archive", headers=headers).status_code == 404
    assert client.post("/gci-studies/does-not-exist/unarchive", headers=headers).status_code == 404
    assert client.delete("/gci-studies/does-not-exist", headers=headers).status_code == 404


def test_delete_gci_study_does_not_delete_constituent_jobs(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/gci-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_deg": "5"},
        )
    study_id = response.json()["id"]
    job_id = response.json()["levels"][0]["job_id"]

    assert client.delete(f"/gci-studies/{study_id}", headers=headers).status_code == 200
    assert client.get(f"/gci-studies/{study_id}", headers=headers).status_code == 404
    assert client.get(f"/jobs/{job_id}", headers=headers).status_code == 200


def test_polar_study_report_not_found(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.get("/polar-studies/does-not-exist/report", headers=headers).status_code == 404


def test_polar_study_report_returns_a_real_pdf_even_when_every_point_failed(client, settings, tmp_path, monkeypatch):
    # Exercises the real route -> PolarStudyOut -> PolarReportData ->
    # fosas_core.report.render_polar_report -> real typst.compile
    # chain end to end (no mocking of the report-rendering itself,
    # only of the CFD solve, which isn't what this route tests). Uses
    # the all-points-failed case specifically, since
    # core/tests/test_report.py already proves render_polar_report
    # handles a real "done" point correctly, and a full CaseResult
    # fixture is not worth constructing again just for route wiring.
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/polar-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_values": ["0", "5"]},
        )
    study_id = response.json()["id"]

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/polar-studies/{study_id}", headers=headers).json()
        if body["status"] == "failed":
            break
        time.sleep(0.05)
    assert body["status"] == "failed"

    report_response = client.get(f"/polar-studies/{study_id}/report", headers=headers)
    assert report_response.status_code == 200
    assert report_response.headers["content-type"] == "application/pdf"
    assert report_response.content.startswith(b"%PDF")


def test_gci_study_report_not_found(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.get("/gci-studies/does-not-exist/report", headers=headers).status_code == 404


def test_gci_study_report_returns_a_real_pdf_even_when_every_level_failed(client, settings, tmp_path, monkeypatch):
    # Same reasoning as the polar report's equivalent test: exercises
    # the real route -> GciStudyOut -> GciReportData ->
    # fosas_core.report.render_gci_report -> real typst.compile chain,
    # using the all-failed case since core/tests/test_report.py already
    # proves the full-result and result-error paths work.
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        response = client.post(
            "/gci-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_deg": "5"},
        )
    study_id = response.json()["id"]

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/gci-studies/{study_id}", headers=headers).json()
        if body["status"] == "failed":
            break
        time.sleep(0.05)
    assert body["status"] == "failed"

    report_response = client.get(f"/gci-studies/{study_id}/report", headers=headers)
    assert report_response.status_code == 200
    assert report_response.headers["content-type"] == "application/pdf"
    assert report_response.content.startswith(b"%PDF")


def test_combined_report_not_found(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        polar_response = client.post(
            "/polar-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_values": ["0"]},
        )
    polar_study_id = polar_response.json()["id"]

    assert client.get(
        f"/reports/combined?polar_study_id=does-not-exist&gci_study_id=does-not-exist", headers=headers
    ).status_code == 404
    assert client.get(
        f"/reports/combined?polar_study_id={polar_study_id}&gci_study_id=does-not-exist", headers=headers
    ).status_code == 404


def test_combined_report_returns_a_real_pdf_combining_both_studies(client, settings, tmp_path, monkeypatch):
    import fosas_engine.app as app_module

    def fake_run_case(step_path, params, work_dir, executables, solve_timeout=None, **kwargs):
        raise app_module.PipelineError("solving", "stop before actually running SU2")

    monkeypatch.setattr(app_module, "run_case", fake_run_case)

    step_path = naca0012_wing_step(tmp_path / "wing.step")
    headers = {"Authorization": f"Bearer {settings.token}"}
    with open(step_path, "rb") as f:
        polar_response = client.post(
            "/polar-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_values": ["0", "5"]},
        )
    polar_study_id = polar_response.json()["id"]

    with open(step_path, "rb") as f:
        gci_response = client.post(
            "/gci-studies",
            headers=headers,
            files={"step_file": ("wing.step", f, "application/octet-stream")},
            data={"velocity": "30", "aoa_deg": "5"},
        )
    gci_study_id = gci_response.json()["id"]

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        polar_body = client.get(f"/polar-studies/{polar_study_id}", headers=headers).json()
        gci_body = client.get(f"/gci-studies/{gci_study_id}", headers=headers).json()
        if polar_body["status"] == "failed" and gci_body["status"] == "failed":
            break
        time.sleep(0.05)
    assert polar_body["status"] == "failed"
    assert gci_body["status"] == "failed"

    report_response = client.get(
        f"/reports/combined?polar_study_id={polar_study_id}&gci_study_id={gci_study_id}", headers=headers
    )
    assert report_response.status_code == 200
    assert report_response.headers["content-type"] == "application/pdf"
    assert report_response.content.startswith(b"%PDF")


def test_job_report_not_found(client, settings):
    headers = {"Authorization": f"Bearer {settings.token}"}
    assert client.get("/jobs/does-not-exist/report", headers=headers).status_code == 404


def test_job_report_conflict_when_not_done(client, settings, tmp_path):
    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    _create_finished_job(app, settings.work_root, "job1", status="failed")
    headers = {"Authorization": f"Bearer {settings.token}"}

    response = client.get("/jobs/job1/report", headers=headers)
    assert response.status_code == 409


def test_job_report_returns_a_real_pdf(client, settings, tmp_path):
    # Exercises the real route -> JobReportData -> fosas_core.report.
    # render_job_report -> real typst.compile chain end to end, same
    # pattern as the polar/GCI/combined report route tests above.
    # core/tests/test_report.py already proves render_job_report itself
    # handles the various field edge cases (None glide ratio, etc.), so
    # this only needs to prove the route wiring.
    from fosas_engine.app import create_app

    app = create_app(settings)
    client = TestClient(app)
    _create_finished_job(app, settings.work_root, "job1", status="done")
    headers = {"Authorization": f"Bearer {settings.token}"}

    response = client.get("/jobs/job1/report", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


# --- Login gate (settings.public_password), see docs/RISKS.md R23 and
# fosas_engine.app's module docstring: required before exposing the
# engine beyond the tailnet (e.g. via "tailscale funnel"), since "/",
# "/viewer", "/app.js" and the docs routes normally hand the real
# bearer token to anyone who can load them at all.

@pytest.fixture
def gated_settings(tmp_path):
    return Settings(token="test-token-123", work_root=tmp_path / "cases", public_password="s3cr3t")


@pytest.fixture
def gated_client(gated_settings):
    app = create_app(gated_settings)
    return TestClient(app)


def test_index_redirects_to_login_without_a_session(gated_client):
    response = gated_client.get("/", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith("/login")


def test_app_js_redirects_to_login_without_a_session(gated_client):
    response = gated_client.get("/app.js", follow_redirects=False)
    assert response.status_code in (302, 303, 307)


def test_docs_redirects_to_login_without_a_session(gated_client):
    response = gated_client.get("/docs", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith("/login")


def test_api_routes_are_unaffected_by_the_login_gate(gated_client):
    # The login gate only ever guards the token-revealing/docs routes
    # above - every actual API route keeps using require_token exactly
    # as before, completely independent of settings.public_password.
    assert gated_client.get("/jobs").status_code == 401  # still needs the bearer token, not a session
    assert gated_client.get("/health").status_code == 200  # still ungated


def test_wrong_password_is_rejected_and_grants_no_session(gated_client):
    response = gated_client.post("/login", data={"password": "wrong", "next": "/"})
    assert response.status_code == 401
    assert "fosas_session" not in response.cookies
    # Still redirected to login afterwards, not granted access.
    assert gated_client.get("/", follow_redirects=False).status_code in (302, 303, 307)


def test_correct_password_grants_a_session_that_unlocks_everything(gated_client, gated_settings):
    login_response = gated_client.post(
        "/login", data={"password": "s3cr3t", "next": "/"}, follow_redirects=False
    )
    assert login_response.status_code == 303
    assert "fosas_session" in login_response.cookies

    # The TestClient keeps cookies across requests on the same instance
    # (same as a real browser), so subsequent requests should now see
    # the real content instead of being redirected.
    assert gated_client.get("/").status_code == 200

    js_response = gated_client.get("/app.js")
    assert js_response.status_code == 200
    assert gated_settings.token in js_response.text

    assert gated_client.get("/docs").status_code == 200


def test_too_many_wrong_passwords_are_rate_limited(gated_client):
    for _ in range(5):
        response = gated_client.post("/login", data={"password": "wrong", "next": "/"})
        assert response.status_code == 401
    locked_out_response = gated_client.post("/login", data={"password": "wrong", "next": "/"})
    assert locked_out_response.status_code == 429
    # Even the correct password is refused while locked out - a correct
    # guess during a brute-force burst must not bypass the lockout.
    still_locked_response = gated_client.post("/login", data={"password": "s3cr3t", "next": "/"})
    assert still_locked_response.status_code == 429
