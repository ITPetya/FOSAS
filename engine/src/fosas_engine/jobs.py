"""In-memory job store.

Jobs run in a background thread pool since fosas_core.pipeline.run_case
is a long-running, blocking sequence of subprocess calls (Gmsh, SU2),
not something to await inline in a request handler. State lives only in
memory: restarting the engine loses job history, which is acceptable for
a local, single-user V1 (see docs/ARCHITECTURE.md); a server mode would
need a persistent store, not built yet.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from fosas_core.pipeline import CaseParams, CaseResult

JobStatus = Literal["pending", "running", "done", "failed"]


@dataclass
class Job:
    id: str
    status: JobStatus
    created_at: datetime
    params: CaseParams
    step_filename: str
    stage: str | None = None
    error: str | None = None
    result: CaseResult | None = None


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, params: CaseParams, step_filename: str) -> Job:
        job = Job(
            id=uuid.uuid4().hex,
            status="pending",
            created_at=datetime.now(timezone.utc),
            params=params,
            step_filename=step_filename,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id].status = "running"

    def mark_done(self, job_id: str, result: CaseResult) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "done"
            job.result = result

    def mark_failed(self, job_id: str, stage: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.stage = stage
            job.error = error
