"""Job store with on-disk persistence.

Jobs run in a background thread pool since fosas_core.pipeline.run_case
is a long-running, blocking sequence of subprocess calls (Gmsh, SU2),
not something to await inline in a request handler. State is mirrored to
a `job_meta.json` file inside each job's own work_dir on every state
change, so an engine restart (crash or deliberate, e.g. to deploy a fix)
does not lose job history or force a user to re-upload and restart from
iteration 0, see docs/RISKS.md R14. This is still a single-process,
single-machine store: it is not safe for multiple engine instances
writing the same work_root concurrently, which is fine for V1's
single-user, single-server scope (see docs/ARCHITECTURE.md).
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fosas_core.pipeline import CaseParams, CaseResult
from fosas_core.quality import ConvergenceAssessment
from fosas_core.solver import IterationHistory, SurfaceData

JobStatus = Literal["pending", "running", "done", "failed"]

_META_FILENAME = "job_meta.json"


def new_job_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Job:
    id: str
    status: JobStatus
    created_at: datetime
    params: CaseParams
    step_filename: str
    step_path: Path
    work_dir: Path
    stage: str | None = None
    error: str | None = None
    result: CaseResult | None = None


def _case_result_to_dict(result: CaseResult) -> dict[str, Any]:
    data = asdict(result)
    data["mesh_path"] = str(result.mesh_path)
    data["solve_dir"] = str(result.solve_dir)
    return data


def _columns_from_dict(data: dict[str, list[float]]) -> dict[str, tuple[float, ...]]:
    return {name: tuple(values) for name, values in data.items()}


def _case_result_from_dict(data: dict[str, Any]) -> CaseResult:
    data = dict(data)
    data["mesh_path"] = Path(data["mesh_path"])
    data["solve_dir"] = Path(data["solve_dir"])
    data["markers"] = tuple(data["markers"])
    data["convergence"] = ConvergenceAssessment(**data["convergence"])
    data["history"] = IterationHistory(columns=_columns_from_dict(data["history"]["columns"]))
    data["surface"] = SurfaceData(columns=_columns_from_dict(data["surface"]["columns"]))
    return CaseResult(**data)


def _job_to_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "params": asdict(job.params),
        "step_filename": job.step_filename,
        "step_path": str(job.step_path),
        "work_dir": str(job.work_dir),
        "stage": job.stage,
        "error": job.error,
        "result": _case_result_to_dict(job.result) if job.result is not None else None,
    }


def _job_from_dict(data: dict[str, Any]) -> Job:
    return Job(
        id=data["id"],
        status=data["status"],
        created_at=datetime.fromisoformat(data["created_at"]),
        params=CaseParams(**data["params"]),
        step_filename=data["step_filename"],
        step_path=Path(data["step_path"]),
        work_dir=Path(data["work_dir"]),
        stage=data.get("stage"),
        error=data.get("error"),
        result=_case_result_from_dict(data["result"]) if data.get("result") is not None else None,
    )


def _write_job_meta(job: Job) -> None:
    meta_path = job.work_dir / _META_FILENAME
    # Written after every state change so a crash mid-write leaves at
    # worst the previous, still-consistent state on disk, not a torn
    # file: write to a temp file in the same directory, then atomically
    # replace, so a reader never sees a half-written JSON document.
    tmp_path = meta_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(_job_to_dict(job), indent=2))
    tmp_path.replace(meta_path)


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    @classmethod
    def load_from_disk(cls, work_root: Path) -> JobStore:
        store = cls()
        if not work_root.exists():
            return store
        for meta_path in sorted(work_root.glob(f"*/{_META_FILENAME}")):
            try:
                data = json.loads(meta_path.read_text())
                job = _job_from_dict(data)
            except Exception as exc:
                # A job directory with unreadable metadata must not stop
                # the whole engine from starting up; skip it and let the
                # user see the gap rather than crash-looping on startup.
                print(f"Warning: could not load job metadata from {meta_path}: {exc!r}", flush=True)
                continue
            store._jobs[job.id] = job
        return store

    def create(self, job_id: str, params: CaseParams, step_filename: str, step_path: Path, work_dir: Path) -> Job:
        job = Job(
            id=job_id,
            status="pending",
            created_at=datetime.now(timezone.utc),
            params=params,
            step_filename=step_filename,
            step_path=step_path,
            work_dir=work_dir,
        )
        with self._lock:
            self._jobs[job.id] = job
            _write_job_meta(job)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            _write_job_meta(job)

    def mark_done(self, job_id: str, result: CaseResult) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "done"
            job.result = result
            _write_job_meta(job)

    def mark_failed(self, job_id: str, stage: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.stage = stage
            job.error = error
            _write_job_meta(job)
