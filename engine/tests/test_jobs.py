from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fosas_core.pipeline import CaseParams, CaseResult
from fosas_core.quality import ConvergenceAssessment
from fosas_core.solver import IterationHistory, SurfaceData

from fosas_engine.jobs import JobNotArchivableError, JobNotDeletableError, JobNotResumableError, JobStore


def _fake_result(work_dir: Path) -> CaseResult:
    return CaseResult(
        chord=0.6,
        span=1.2,
        node_count=1234,
        element_count=5678,
        markers=("airfoil", "farfield"),
        cl=1.29,
        cd=0.08,
        convergence=ConvergenceAssessment(
            converged=False,
            final_residual=-3.5,
            residual_threshold=-8.0,
            is_plateaued=True,
            message="did not converge in the allotted iterations",
        ),
        history=IterationHistory(columns={"rms[P]": (-1.0, -2.0, -3.5)}),
        surface=SurfaceData(columns={"x": (0.0, 0.6), "Pressure_Coefficient": (0.5, -0.3)}),
        mean_y_plus=0.9,
        max_y_plus=1.4,
        dynamic_pressure=450.6,
        reynolds_number=2.1e6,
        mesh_path=work_dir / "mesh.su2",
        solve_dir=work_dir / "solve",
    )


def test_job_metadata_survives_a_store_reload(tmp_path):
    work_root = tmp_path / "cases"
    params = CaseParams(velocity=50, aoa_deg=5)
    work_dir = work_root / "job1"
    work_dir.mkdir(parents=True)
    step_path = work_dir / "input.step"
    step_path.write_bytes(b"dummy step content")

    store = JobStore()
    job = store.create("job1", params, "wing.step", step_path, work_dir)
    store.mark_running(job.id)
    store.mark_done(job.id, _fake_result(work_dir))

    assert (work_dir / "job_meta.json").exists()

    reloaded = JobStore.load_from_disk(work_root)
    reloaded_job = reloaded.get("job1")
    assert reloaded_job is not None
    assert reloaded_job.status == "done"
    assert reloaded_job.params == params
    assert reloaded_job.step_path == step_path
    assert reloaded_job.work_dir == work_dir
    assert reloaded_job.result.cl == 1.29
    assert reloaded_job.result.markers == ("airfoil", "farfield")
    assert reloaded_job.result.history.column("rms[P]") == (-1.0, -2.0, -3.5)
    assert reloaded_job.result.surface.column("Pressure_Coefficient") == (0.5, -0.3)
    assert reloaded_job.result.mesh_path == work_dir / "mesh.su2"


def test_load_from_disk_skips_unreadable_job_dirs_instead_of_crashing(tmp_path):
    work_root = tmp_path / "cases"
    broken_dir = work_root / "broken"
    broken_dir.mkdir(parents=True)
    (broken_dir / "job_meta.json").write_text("{not valid json")

    store = JobStore.load_from_disk(work_root)
    assert store.list() == []


def test_load_from_disk_with_missing_work_root_returns_empty_store(tmp_path):
    store = JobStore.load_from_disk(tmp_path / "does_not_exist")
    assert store.list() == []


def _make_finished_job(tmp_path, name, status, hours_ago):
    work_dir = tmp_path / "cases" / name
    work_dir.mkdir(parents=True)
    (work_dir / "input.step").write_bytes(b"dummy")
    store = JobStore()
    job = store.create(name, CaseParams(velocity=50, aoa_deg=5), "wing.step", work_dir / "input.step", work_dir)
    store.mark_running(job.id)
    if status == "done":
        store.mark_done(job.id, _fake_result(work_dir))
    else:
        store.mark_failed(job.id, stage="solving", error="boom")
    store._jobs[job.id].finished_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return store, job.id, work_dir


def test_manual_archive_and_unarchive(tmp_path):
    store, job_id, _ = _make_finished_job(tmp_path, "job1", "done", hours_ago=0)
    assert job_id in [j.id for j in store.list()]

    store.archive(job_id)
    assert job_id not in [j.id for j in store.list()]
    assert job_id in [j.id for j in store.list(include_archived=True)]

    store.unarchive(job_id)
    assert job_id in [j.id for j in store.list()]
    assert job_id not in [j.id for j in store.list(include_archived=True)]


def test_done_job_auto_archives_after_5_hours_not_before(tmp_path):
    store, job_id, _ = _make_finished_job(tmp_path, "job1", "done", hours_ago=4.9)
    assert job_id in [j.id for j in store.list()]  # not yet

    store._jobs[job_id].finished_at = datetime.now(timezone.utc) - timedelta(hours=5.1)
    assert job_id not in [j.id for j in store.list()]
    assert job_id in [j.id for j in store.list(include_archived=True)]


def test_failed_job_auto_archives_after_1_5_hours_sooner_than_done(tmp_path):
    store, job_id, _ = _make_finished_job(tmp_path, "job1", "failed", hours_ago=1.6)
    assert job_id not in [j.id for j in store.list()]
    assert job_id in [j.id for j in store.list(include_archived=True)]


def test_failed_job_auto_deletes_after_24_hours(tmp_path):
    store, job_id, work_dir = _make_finished_job(tmp_path, "job1", "failed", hours_ago=24.1)
    assert work_dir.exists()

    store.list()  # triggers the sweep

    assert store.get(job_id) is None
    assert not work_dir.exists()  # files actually removed, not just hidden


def test_done_job_never_auto_deletes(tmp_path):
    store, job_id, work_dir = _make_finished_job(tmp_path, "job1", "done", hours_ago=1000)
    store.list()
    assert store.get(job_id) is not None  # archived, but never deleted on its own
    assert work_dir.exists()


def test_delete_refuses_a_running_job(tmp_path):
    work_dir = tmp_path / "cases" / "job1"
    work_dir.mkdir(parents=True)
    store = JobStore()
    job = store.create("job1", CaseParams(velocity=50, aoa_deg=5), "wing.step", work_dir / "input.step", work_dir)
    store.mark_running(job.id)
    with pytest.raises(JobNotDeletableError):
        store.delete(job.id)
    assert work_dir.exists()


def test_manual_delete_removes_files_and_record(tmp_path):
    store, job_id, work_dir = _make_finished_job(tmp_path, "job1", "done", hours_ago=0)
    store.delete(job_id)
    assert store.get(job_id) is None
    assert not work_dir.exists()


def test_prepare_for_resume_resets_a_failed_job(tmp_path):
    store, job_id, work_dir = _make_finished_job(tmp_path, "job1", "failed", hours_ago=0)
    store._jobs[job_id].archived = True

    resumed = store.prepare_for_resume(job_id)

    assert resumed.status == "pending"
    assert resumed.stage is None
    assert resumed.error is None
    assert resumed.finished_at is None
    assert resumed.archived is False
    assert work_dir.exists()  # nothing deleted, same work_dir reused


def test_prepare_for_resume_refuses_a_done_job(tmp_path):
    store, job_id, _ = _make_finished_job(tmp_path, "job1", "done", hours_ago=0)
    with pytest.raises(JobNotResumableError):
        store.prepare_for_resume(job_id)


def test_prepare_for_resume_refuses_a_running_job(tmp_path):
    work_dir = tmp_path / "cases" / "job1"
    work_dir.mkdir(parents=True)
    store = JobStore()
    job = store.create("job1", CaseParams(velocity=50, aoa_deg=5), "wing.step", work_dir / "input.step", work_dir)
    store.mark_running(job.id)
    with pytest.raises(JobNotResumableError):
        store.prepare_for_resume(job.id)


def test_archive_refuses_a_pending_or_running_job(tmp_path):
    work_dir = tmp_path / "cases" / "job1"
    work_dir.mkdir(parents=True)
    store = JobStore()
    job = store.create("job1", CaseParams(velocity=50, aoa_deg=5), "wing.step", work_dir / "input.step", work_dir)
    with pytest.raises(JobNotArchivableError):
        store.archive(job.id)
    store.mark_running(job.id)
    with pytest.raises(JobNotArchivableError):
        store.archive(job.id)
    assert job.archived is False
