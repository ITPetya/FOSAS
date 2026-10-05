from datetime import datetime, timezone
from pathlib import Path

from fosas_engine.polar_studies import PolarStudyStore


def test_polar_study_metadata_survives_a_store_reload(tmp_path):
    work_root = tmp_path / "cases"
    store = PolarStudyStore()
    study = store.create("study1", "wing.step", (0.0, 5.0, 10.0), ("job1", "job2", "job3"), work_root)

    assert (study.work_dir / "polar_study_meta.json").exists()

    reloaded = PolarStudyStore.load_from_disk(work_root)
    reloaded_study = reloaded.get("study1")
    assert reloaded_study is not None
    assert reloaded_study.step_filename == "wing.step"
    assert reloaded_study.aoa_values == (0.0, 5.0, 10.0)
    assert reloaded_study.job_ids == ("job1", "job2", "job3")
    assert reloaded_study.archived is False


def test_list_filters_by_archived(tmp_path):
    store = PolarStudyStore()
    study = store.create("study1", "wing.step", (0.0,), ("job1",), tmp_path / "cases")

    assert [s.id for s in store.list()] == ["study1"]
    assert store.list(include_archived=True) == []

    store.archive(study.id)
    assert store.list() == []
    assert [s.id for s in store.list(include_archived=True)] == ["study1"]

    store.unarchive(study.id)
    assert [s.id for s in store.list()] == ["study1"]


def test_delete_removes_only_the_study_record_not_referenced_jobs(tmp_path):
    # The study's own work_dir (where its meta file lives) is separate
    # from any job's work_dir - deleting a study must never touch job
    # directories, since those are a referenced job's own, independently
    # owned lifecycle (see docs/DECISIONS.md ADR-0017).
    work_root = tmp_path / "cases"
    job_work_dir = work_root / "job1"
    job_work_dir.mkdir(parents=True)
    (job_work_dir / "input.step").write_bytes(b"dummy")

    store = PolarStudyStore()
    study = store.create("study1", "wing.step", (0.0,), ("job1",), work_root)
    assert study.work_dir.exists()

    store.delete("study1")
    assert store.get("study1") is None
    assert not study.work_dir.exists()
    assert job_work_dir.exists()  # untouched
    assert (job_work_dir / "input.step").exists()
