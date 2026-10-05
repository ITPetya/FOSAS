"""GCI study store: a thin record referencing exactly 3 ordinary Jobs
(fine/medium/coarse mesh resolution), the same reuse pattern as
polar_studies.py (see its module docstring and docs/DECISIONS.md
ADR-0017) - status is always derived live from the referenced jobs,
never stored here, and deleting a study record never touches its
constituent jobs' own independent lifecycle.
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

_META_FILENAME = "gci_study_meta.json"
_STUDIES_SUBDIR = "gci_studies"


def new_gci_study_id() -> str:
    return uuid.uuid4().hex


@dataclass
class GciStudy:
    id: str
    created_at: datetime
    step_filename: str
    refinement_ratio: float
    # Fixed order: fine, medium, coarse.
    job_ids: tuple[str, str, str]
    work_dir: Path
    archived: bool = False


def _study_to_dict(study: GciStudy) -> dict[str, Any]:
    return {
        "id": study.id,
        "created_at": study.created_at.isoformat(),
        "step_filename": study.step_filename,
        "refinement_ratio": study.refinement_ratio,
        "job_ids": list(study.job_ids),
        "work_dir": str(study.work_dir),
        "archived": study.archived,
    }


def _study_from_dict(data: dict[str, Any]) -> GciStudy:
    job_ids = tuple(data["job_ids"])
    return GciStudy(
        id=data["id"],
        created_at=datetime.fromisoformat(data["created_at"]),
        step_filename=data["step_filename"],
        refinement_ratio=data["refinement_ratio"],
        job_ids=job_ids,
        work_dir=Path(data["work_dir"]),
        archived=data.get("archived", False),
    )


def _write_study_meta(study: GciStudy) -> None:
    meta_path = study.work_dir / _META_FILENAME
    tmp_path = meta_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(_study_to_dict(study), indent=2))
    tmp_path.replace(meta_path)


class GciStudyStore:
    def __init__(self):
        self._studies: dict[str, GciStudy] = {}
        self._lock = threading.Lock()

    @classmethod
    def load_from_disk(cls, work_root: Path) -> "GciStudyStore":
        store = cls()
        base = work_root / _STUDIES_SUBDIR
        if not base.exists():
            return store
        for meta_path in sorted(base.glob(f"*/{_META_FILENAME}")):
            try:
                data = json.loads(meta_path.read_text())
                study = _study_from_dict(data)
            except Exception as exc:
                print(f"Warning: could not load GCI study metadata from {meta_path}: {exc!r}", flush=True)
                continue
            store._studies[study.id] = study
        return store

    def create(
        self,
        study_id: str,
        step_filename: str,
        refinement_ratio: float,
        job_ids: tuple[str, str, str],
        work_root: Path,
    ) -> GciStudy:
        work_dir = work_root / _STUDIES_SUBDIR / study_id
        work_dir.mkdir(parents=True, exist_ok=True)
        study = GciStudy(
            id=study_id,
            created_at=datetime.now(timezone.utc),
            step_filename=step_filename,
            refinement_ratio=refinement_ratio,
            job_ids=job_ids,
            work_dir=work_dir,
        )
        with self._lock:
            self._studies[study.id] = study
            _write_study_meta(study)
        return study

    def get(self, study_id: str) -> GciStudy | None:
        with self._lock:
            return self._studies.get(study_id)

    def list(self, include_archived: bool = False) -> list[GciStudy]:
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
        Never touches the constituent jobs it references."""
        with self._lock:
            study = self._studies[study_id]
            if study.work_dir.exists():
                shutil.rmtree(study.work_dir)
            del self._studies[study_id]
