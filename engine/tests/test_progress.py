import time
from datetime import datetime, timedelta, timezone

from fosas_core.pipeline import CaseParams

from fosas_engine.jobs import Job
from fosas_engine.progress import compute_progress


def _job(tmp_path, status="running", max_iterations=500, created_at=None):
    work_dir = tmp_path / "job1"
    work_dir.mkdir(parents=True, exist_ok=True)
    return Job(
        id="job1",
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
        params=CaseParams(velocity=30, aoa_deg=5, max_iterations=max_iterations),
        step_filename="wing.step",
        step_path=work_dir / "input.step",
        work_dir=work_dir,
    )


def test_compute_progress_is_none_for_a_non_running_job(tmp_path):
    for status in ["pending", "done", "failed"]:
        assert compute_progress(_job(tmp_path, status=status)) is None


def test_compute_progress_reports_meshing_phase_before_mesh_exists(tmp_path):
    created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    job = _job(tmp_path, created_at=created_at)

    progress = compute_progress(job)

    assert progress.phase == "meshing"
    assert progress.current_iteration is None
    assert progress.max_iterations is None
    assert progress.percent is None
    assert progress.eta_seconds is None
    assert progress.elapsed_seconds >= 5


def test_compute_progress_reports_zero_percent_right_after_mesh_is_done(tmp_path):
    job = _job(tmp_path, max_iterations=200)
    (job.work_dir / "mesh.su2").write_text("fake mesh")

    progress = compute_progress(job)

    assert progress.phase == "solving"
    assert progress.current_iteration == 0
    assert progress.max_iterations == 200
    assert progress.percent == 0.0
    assert progress.eta_seconds is None


def test_compute_progress_reports_percent_and_eta_during_solving(tmp_path):
    job = _job(tmp_path, max_iterations=200)
    (job.work_dir / "mesh.su2").write_text("fake mesh")
    solve_dir = job.work_dir / "solve"
    solve_dir.mkdir()
    (solve_dir / "config.cfg").write_text("fake config")
    time.sleep(0.05)
    header = '"Time_Iter","Inner_Iter","rms[P]"\n'
    rows = "\n".join(f"0,{i},-1.0" for i in range(50)) + "\n"
    (solve_dir / "history.csv").write_text(header + rows)

    progress = compute_progress(job)

    assert progress.phase == "solving"
    assert progress.current_iteration == 50
    assert progress.max_iterations == 200
    assert progress.percent == 25.0
    assert progress.elapsed_seconds > 0
    assert progress.eta_seconds is not None
    assert progress.eta_seconds > 0


def test_compute_progress_uses_config_mtime_not_mesh_mtime_for_a_resumed_job(tmp_path):
    # A resumed job reuses a mesh.su2 from a much earlier, interrupted
    # attempt (see docs/RISKS.md R14): its mtime must not be mistaken for
    # when THIS solve attempt started, only config.cfg (rewritten by
    # generate_config on every call, including a resumed one) marks that.
    job = _job(tmp_path, max_iterations=200)
    mesh_path = job.work_dir / "mesh.su2"
    mesh_path.write_text("fake mesh")
    old_time = time.time() - 3600
    import os

    os.utime(mesh_path, (old_time, old_time))

    solve_dir = job.work_dir / "solve"
    solve_dir.mkdir()
    (solve_dir / "config.cfg").write_text("fake config")

    progress = compute_progress(job)

    assert progress.phase == "solving"
    assert progress.elapsed_seconds < 5  # not ~3600s, which mesh.su2's mtime would give
