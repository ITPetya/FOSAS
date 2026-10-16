"""Short-lived storage for the geometry preview tool (docs/ARCHITECTURE.md
"Koordinatenkonvention", ADR-0020 Teil B).

Deliberately much simpler than JobStore: a preview is not a result worth
keeping, only a STEP file waiting to be either used by a real submission
(within a short window) or discarded. In-memory only, no job_meta.json-
style disk mirroring, no survival across an engine restart - the project
owner already has to re-upload the file anyway if that happens, same as
if they had never opened the preview tool at all.
"""

from __future__ import annotations

import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# An abandoned preview (uploaded, never submitted) is cleaned up after
# this long - generous enough for a person to look at a 3D view and
# decide, short enough that a crash-only engine does not accumulate
# uploaded STEP files forever in previews_root.
_PREVIEW_MAX_AGE = timedelta(hours=2)


@dataclass
class GeometryPreview:
    id: str
    step_path: Path
    created_at: datetime


class GeometryPreviewStore:
    def __init__(self, previews_root: Path):
        self.previews_root = previews_root
        self.previews_root.mkdir(parents=True, exist_ok=True)
        self._previews: dict[str, GeometryPreview] = {}
        self._lock = threading.Lock()

    def create(self, step_bytes: bytes) -> GeometryPreview:
        self._cleanup_expired()
        preview_id = uuid.uuid4().hex
        preview_dir = self.previews_root / preview_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        step_path = preview_dir / "input.step"
        step_path.write_bytes(step_bytes)
        preview = GeometryPreview(id=preview_id, step_path=step_path, created_at=datetime.now(timezone.utc))
        with self._lock:
            self._previews[preview_id] = preview
        return preview

    def get(self, preview_id: str) -> GeometryPreview | None:
        self._cleanup_expired()
        with self._lock:
            return self._previews.get(preview_id)

    def _cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [p for p in self._previews.values() if now - p.created_at > _PREVIEW_MAX_AGE]
            for preview in expired:
                del self._previews[preview.id]
        for preview in expired:
            shutil.rmtree(preview.step_path.parent, ignore_errors=True)
