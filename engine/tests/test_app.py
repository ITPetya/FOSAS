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
    assert job["result"]["cl"] != 0.0
    assert abs(job["result"]["cl"]) < 50  # catches a diverged run, not just an unrotated one
    assert abs(job["result"]["cd"]) < 50
    assert job["result"]["convergence"]["converged"] is False  # known for this short/coarse case
    assert len(job["result"]["surface"]) > 0
    assert "cp" in job["result"]["surface"][0]
    assert job["result"]["mean_y_plus"] > 0
