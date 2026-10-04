"""Polar study store: a thin record referencing a group of ordinary
Jobs (see jobs.py), one per angle-of-attack value, plus the AoA value
each one corresponds to. Deliberately does not duplicate Job/JobStore's
own lifecycle or persistence of CFD results: status is always derived
live from the referenced jobs (see polar_progress.aggregate_status),
never stored here, and deleting a study record never touches its
constituent jobs' own independent lifecycle (archive/unarchive/delete
via /jobs/{id}) - a user is never surprised by CFD results disappearing
just because they deleted a study wrapper around them. See
docs/DECISIONS.md ADR-0017 for why a polar sweep is modelled this way
(reusing the existing single-case Job machinery unchanged) instead of
teaching Job/JobStore about multiple results per job.
"""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_META_FILENAME = "polar_study_meta.json"
_STUDIES_SUBDIR = "polar_studies"


def new_polar_study_id() -> str:
    return uuid.uuid4().hex


@dataclass
class PolarStudy:
    id: str
    created_at: datetime
    step_filename: str
    aoa_values: tuple[float, ...]
    job_ids: tuple[str, ...]
    work_dir: Path
    archived: bool = False


def _study_to_dict(study: PolarStudy) -> dict[str, Any]:
    return {
        "id": study.id,
        "created_at": study.created_at.isoformat(),
        "step_filename": study.step_filename,
        "aoa_values": list(study.aoa_values),
        "job_ids": list(study.job_ids),
        "work_dir": str(study.work_dir),
        "archived": study.archived,
    }


def _study_from_dict(data: dict[str, Any]) -> PolarStudy:
    return PolarStudy(
        id=data["id"],
        created_at=datetime.fromisoformat(data["created_at"]),
        step_filename=data["step_filename"],
        aoa_values=tuple(data["aoa_values"]),
        job_ids=tuple(data["job_ids"]),
        work_dir=Path(data["work_dir"]),
        archived=data.get("archived", False),
    )


def _write_study_meta(study: PolarStudy) -> None:
    meta_path = study.work_dir / _META_FILENAME
    tmp_path = meta_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(_study_to_dict(study), indent=2))
    tmp_path.replace(meta_path)


class PolarStudyStore:
    def __init__(self):
        self._studies: dict[str, PolarStudy] = {}
        self._lock = threading.Lock()

    @classmethod
    def load_from_disk(cls, work_root: Path) -> "PolarStudyStore":
        store = cls()
        base = work_root / _STUDIES_SUBDIR
        if not base.exists():
            return store
        for meta_path in sorted(base.glob(f"*/{_META_FILENAME}")):
            try:
                data = json.loads(meta_path.read_text())
                study = _study_from_dict(data)
            except Exception as exc:
                # Same policy as JobStore.load_from_disk: one unreadable
                # study record must not stop the whole engine starting.
                print(f"Warning: could not load polar study metadata from {meta_path}: {exc!r}", flush=True)
                continue
            store._studies[study.id] = study
        return store

    def create(
        self,
        study_id: str,
        step_filename: str,
        aoa_values: tuple[float, ...],
        job_ids: tuple[str, ...],
        work_root: Path,
    ) -> PolarStudy:
        work_dir = work_root / _STUDIES_SUBDIR / study_id
        work_dir.mkdir(parents=True, exist_ok=True)
        study = PolarStudy(
            id=study_id,
            created_at=datetime.now(timezone.utc),
            step_filename=step_filename,
            aoa_values=aoa_values,
            job_ids=job_ids,
            work_dir=work_dir,
        )
        with self._lock:
            self._studies[study.id] = study
            _write_study_meta(study)
        return study

    def get(self, study_id: str) -> PolarStudy | None:
        with self._lock:
            return self._studies.get(study_id)

    def list(self, include_archived: bool = False) -> list[PolarStudy]:
        with self._lock:
            studies = list(self._studies.values())
        if include_archived:
            return [s for s in studies if s.archived]
        return [s for s in studies if not s.archived]

    def archive(self, study_id: str) -> None:
        with self._lock:
            study = self._studies[study_id]
            study.archived = True
            _write_study_meta(study)

    def unarchive(self, study_id: str) -> None:
        with self._lock:
            study = self._studies[study_id]
            study.archived = False
            _write_study_meta(study)

    def delete(self, study_id: str) -> None:
        """Removes only this study's own small meta-record directory.
        Never touches the constituent jobs it references - those are
        deleted individually via DELETE /jobs/{id} if actually wanted.
        """
        with self._lock:
            study = self._studies[study_id]
            if study.work_dir.exists():
                shutil.rmtree(study.work_dir)
            del self._studies[study_id]
