from pathlib import Path

from fosas_core.pipeline import CaseParams, CaseResult
from fosas_core.quality import ConvergenceAssessment
from fosas_core.solver import IterationHistory, SurfaceData

from fosas_engine.jobs import JobStore


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
