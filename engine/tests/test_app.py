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
