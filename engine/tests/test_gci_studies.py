from fosas_engine.gci_studies import GciStudyStore


def test_gci_study_metadata_survives_a_store_reload(tmp_path):
    work_root = tmp_path / "cases"
    store = GciStudyStore()
    study = store.create("study1", "wing.step", 1.5, ("fine_job", "medium_job", "coarse_job"), work_root)

    assert (study.work_dir / "gci_study_meta.json").exists()

    reloaded = GciStudyStore.load_from_disk(work_root)
    reloaded_study = reloaded.get("study1")
    assert reloaded_study is not None
    assert reloaded_study.step_filename == "wing.step"
    assert reloaded_study.refinement_ratio == 1.5
    assert reloaded_study.job_ids == ("fine_job", "medium_job", "coarse_job")
    assert reloaded_study.archived is False


def test_list_filters_by_archived(tmp_path):
    store = GciStudyStore()
    study = store.create("study1", "wing.step", 1.5, ("j1", "j2", "j3"), tmp_path / "cases")

    assert [s.id for s in store.list()] == ["study1"]
    assert store.list(include_archived=True) == []

    store.archive(study.id)
    assert store.list() == []
    assert [s.id for s in store.list(include_archived=True)] == ["study1"]

    store.unarchive(study.id)
    assert [s.id for s in store.list()] == ["study1"]


def test_delete_removes_only_the_study_record_not_referenced_jobs(tmp_path):
    work_root = tmp_path / "cases"
    job_work_dir = work_root / "job1"
    job_work_dir.mkdir(parents=True)
    (job_work_dir / "input.step").write_bytes(b"dummy")

    store = GciStudyStore()
    study = store.create("study1", "wing.step", 1.5, ("job1", "job2", "job3"), work_root)
    assert study.work_dir.exists()

    store.delete("study1")
    assert store.get("study1") is None
    assert not study.work_dir.exists()
    assert job_work_dir.exists()  # untouched
