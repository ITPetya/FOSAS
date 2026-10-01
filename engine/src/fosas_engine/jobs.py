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

Retention policy (see docs/DECISIONS.md ADR-0015): a finished job (done
or failed) is auto-archived some time after it *finished*, not after it
was created, so a long-running job is never archived out from under
itself while still active. Archiving only changes visibility (it moves
out of the default job list into the archive view); the underlying files
and the job's own record stay untouched and restorable. Only failed jobs
are ever auto-deleted (their files actually removed from disk); a
successful job's result is kept until a person explicitly deletes it.
"""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fosas_core.pipeline import CaseParams, CaseResult
from fosas_core.quality import ConvergenceAssessment
from fosas_core.solver import IterationHistory, SurfaceData

JobStatus = Literal["pending", "running", "done", "failed"]

_META_FILENAME = "job_meta.json"

# Measured from finished_at (when a job left "running"), never from
# created_at: a job that legitimately runs for many hours must not be
# archived mid-run just because it is "old". A failed job is archived
# sooner than a successful one on the assumption that a failure is
# usually looked at quickly and then no longer needs to sit in the main
# list, while a successful result is more likely to still be wanted.
_ARCHIVE_AFTER_DONE = timedelta(hours=5)
_ARCHIVE_AFTER_FAILED = timedelta(hours=1.5)
_DELETE_FAILED_AFTER = timedelta(hours=24)


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
    finished_at: datetime | None = None
    archived: bool = False


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
        "finished_at": job.finished_at.isoformat() if job.finished_at is not None else None,
        "archived": job.archived,
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
        finished_at=datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None,
        archived=data.get("archived", False),
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


class JobNotDeletableError(Exception):
    """Raised when trying to delete a job that is still pending/running:
    its work_dir may still be written to by a subprocess."""


class JobNotResumableError(Exception):
    """Raised when trying to resume a job that is not currently failed:
    "done" has nothing to resume, "pending"/"running" is already active."""


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
        self._sweep()
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, include_archived: bool = False) -> list[Job]:
        self._sweep()
        with self._lock:
            jobs = list(self._jobs.values())
        if include_archived:
            return [j for j in jobs if j.archived]
        return [j for j in jobs if not j.archived]

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            # Clears a previous failure's stage/error: relevant when this
            # is a resume of a job that failed before (see `resume`
            # below), so a since-fixed run does not keep showing the old
            # error message after it succeeds.
            job.stage = None
            job.error = None
            _write_job_meta(job)

    def mark_done(self, job_id: str, result: CaseResult) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "done"
            job.result = result
            job.finished_at = datetime.now(timezone.utc)
            _write_job_meta(job)

    def mark_failed(self, job_id: str, stage: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.stage = stage
            job.error = error
            job.finished_at = datetime.now(timezone.utc)
            _write_job_meta(job)

    def prepare_for_resume(self, job_id: str) -> Job:
        """Resets a failed job back to "pending" so the caller can
        resubmit it to the executor (see POST /jobs/{id}/resume in
        app.py; this method only touches state, it does not itself run
        anything). fosas_core.pipeline.run_case picks up whatever mesh/
        restart file already exists in the unchanged work_dir on its
        own, see docs/RISKS.md R14/R17 for the real incidents this is
        for. Un-archives, since a resumed job is active again.
        """
        with self._lock:
            job = self._jobs[job_id]
            if job.status != "failed":
                raise JobNotResumableError(f"Job {job_id} is {job.status}, only a failed job can be resumed")
            job.status = "pending"
            job.stage = None
            job.error = None
            job.finished_at = None
            job.archived = False
            _write_job_meta(job)
            return job

    def archive(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.archived = True
            _write_job_meta(job)

    def unarchive(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.archived = False
            _write_job_meta(job)

    def delete(self, job_id: str) -> None:
        """Permanently removes a finished job's files and its record.
        Refuses a pending/running job: a subprocess may still be writing
        into its work_dir, see docs/RISKS.md R14 for why that directory
        is trusted as the source of truth for job state.

        Filesystem deletion happens before the in-memory record is
        dropped, and any failure to remove the directory aborts here
        instead of silently dropping the record: an un-removed directory
        still has a job_meta.json, which load_from_disk would otherwise
        resurrect on the next engine restart, letting a "deleted" job
        come back from the dead.
        """
        with self._lock:
            job = self._jobs[job_id]
            if job.status in ("pending", "running"):
                raise JobNotDeletableError(f"Job {job_id} is still {job.status}, cannot be deleted")
            shutil.rmtree(job.work_dir)
            del self._jobs[job_id]

    def _sweep(self) -> None:
        """Applies the retention policy (see module docstring and
        docs/DECISIONS.md ADR-0015): auto-archive a finished job once it
        has sat long enough, auto-delete a failed job once it is old
        enough. Called on every read so no background thread/scheduler
        is needed; cheap for the job counts this tool expects.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            if job.finished_at is None:
                continue
            age = now - job.finished_at
            if job.status == "failed" and age >= _DELETE_FAILED_AFTER:
                try:
                    self.delete(job.id)
                except (JobNotDeletableError, FileNotFoundError, KeyError):
                    pass
                continue
            if not job.archived:
                threshold = _ARCHIVE_AFTER_FAILED if job.status == "failed" else _ARCHIVE_AFTER_DONE
                if age >= threshold:
                    with self._lock:
                        current = self._jobs.get(job.id)
                        if current is not None and not current.archived:
                            current.archived = True
                            _write_job_meta(current)
