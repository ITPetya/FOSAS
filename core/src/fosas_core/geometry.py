"""STEP geometry import and validation.

Validation deliberately checks more than build123d's own is_valid/
is_manifold in isolation: a shell with a missing face can still report as
"valid" from a pure topology check while not being watertight (confirmed
by a spike test, see docs/RISKS.md ADR-0003 in the FOSAS repository).
This module requires both is_manifold and at least one Solid before
accepting a geometry, and never attempts to silently repair a broken
model, per project policy: any automatic correction must be visible, not
hidden inside an import function.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from build123d import Shape, import_step as _import_step


class GeometryError(Exception):
    """Raised when a STEP file cannot be used as a solid body for meshing."""


@dataclass(frozen=True)
class ImportedGeometry:
    shape: Shape
    source_path: Path
    volume: float


def import_step(path: str | Path) -> ImportedGeometry:
    """Import a STEP file and validate it is a single watertight solid.

    Raises GeometryError with an actionable message if the file is
    missing, not a solid, not manifold, or has non-positive volume.
    """
    path = Path(path)
    if not path.exists():
        raise GeometryError(
            f"STEP file not found: '{path}'. Check the path, and that the "
            "upload completed successfully."
        )

    try:
        shape = _import_step(str(path))
    except Exception as exc:  # build123d/OCCT raise various exception types
        raise GeometryError(
            f"Could not read '{path}' as a STEP file ({exc}). The file may "
            "be corrupted or not a valid STEP file. Try re-exporting it "
            "from the original CAD system."
        ) from exc

    solids = shape.solids()
    if len(solids) == 0:
        raise GeometryError(
            f"'{path}' contains no solid body, only surfaces or curves. "
            "FOSAS needs a closed solid to mesh. Check that the source "
            "model is exported as a solid, not a surface model."
        )
    if len(solids) > 1:
        raise GeometryError(
            f"'{path}' contains {len(solids)} separate solid bodies. FOSAS "
            "expects a single solid body for the outer aerodynamic shape. "
            "Combine the bodies into one solid, or remove unrelated parts, "
            "before importing."
        )

    if not shape.is_manifold:
        raise GeometryError(
            f"'{path}' is not watertight (not manifold): it has gaps or "
            "open edges. This cannot be meshed as a solid body. Repair "
            "the geometry in the source CAD system and re-export it. "
            "FOSAS does not attempt automatic hole-filling, because that "
            "would silently change the shape being simulated."
        )

    volume = shape.volume
    if volume <= 0:
        raise GeometryError(
            f"'{path}' has non-positive volume ({volume:.6g}). This "
            "usually means the solid's face orientations are inconsistent. "
            "Re-export the geometry from the source CAD system."
        )

    return ImportedGeometry(shape=shape, source_path=path, volume=volume)
