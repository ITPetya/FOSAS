"""Content-addressed cache for expensive pipeline steps (meshing, solving).

The cache key is a hash of everything that affects the result: geometry
file content plus the exact parameters used. Same inputs always produce
the same key, so a cache hit is safe to reuse without re-checking
anything else. There is no "best effort" or time-based invalidation:
either the hash matches, or the result is not reused.

Every cache entry stores a metadata.json recording exactly what inputs
produced it (paths, parameter values, a timestamp), so a cached result
stays traceable to what created it, matching the project's
reproducibility rule (see CLAUDE.md).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def hash_file(path: str | Path) -> str:
    """SHA-256 of a file's content, read in chunks (safe for large files)."""
    path = Path(path)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot hash value of type {type(value).__name__}: not JSON-serializable")


def hash_value(value) -> str:
    """Stable SHA-256 of any JSON-serializable-ish value. Dict key order
    does not affect the result; dataclasses and Path are supported.
    """
    encoded = json.dumps(value, sort_keys=True, default=_json_default).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def combined_hash(*values) -> str:
    """Stable SHA-256 combining several values (e.g. a geometry file hash
    plus mesh parameters plus solver parameters) into one cache key.
    """
    digest = hashlib.sha256()
    for value in values:
        digest.update(hash_value(value).encode("utf-8"))
    return digest.hexdigest()


class CacheStore:
    """A directory-based cache: one subdirectory per key, under root."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def entry_dir(self, key: str) -> Path:
        return self.root / key

    def has(self, key: str) -> bool:
        return (self.entry_dir(key) / "metadata.json").exists()

    def reserve(self, key: str) -> Path:
        """Return the directory for this key, creating it if needed. Does
        not mark the entry as complete; call write_metadata when the
        computation actually succeeded.
        """
        entry = self.entry_dir(key)
        entry.mkdir(parents=True, exist_ok=True)
        return entry

    def write_metadata(self, key: str, inputs: dict) -> None:
        metadata = {
            "key": key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inputs": json.loads(json.dumps(inputs, sort_keys=True, default=_json_default)),
        }
        (self.entry_dir(key) / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True))

    def read_metadata(self, key: str) -> dict | None:
        path = self.entry_dir(key) / "metadata.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())
