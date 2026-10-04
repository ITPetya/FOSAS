"""Aggregate status for a polar study's constituent jobs. Deliberately
never stored on the PolarStudy record itself: it is always derived live
from each referenced job's own current status (see jobs.JobStatus), so
there is only ever one source of truth for "is this job done", the same
reasoning as progress.py's own live-computed-not-stored approach.
"""

from __future__ import annotations

from fosas_engine.jobs import JobStatus


def aggregate_status(job_statuses: list[JobStatus]) -> JobStatus:
    if all(s == "pending" for s in job_statuses):
        return "pending"
    if all(s == "done" for s in job_statuses):
        return "done"
    if all(s in ("done", "failed") for s in job_statuses) and any(s == "failed" for s in job_statuses):
        return "failed"
    return "running"
