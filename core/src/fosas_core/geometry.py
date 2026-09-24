"""STEP geometry import and validation.

Validation deliberately checks more than build123d's own is_valid/
is_manifold in isolation: a shell with a missing face can still report as
"valid" from a pure topology check while not being watertight (confirmed
by a spike test, see ADR-0003 in docs/DECISIONS.md). This module requires
both is_manifold and at least one Solid before accepting a geometry.

Automatic repair (stitching disconnected surface patches back together)
is only performed when explicitly requested via sewing_tolerance, and the
result always discloses exactly what was done (input face count, whether
it became a solid, remaining open edges) rather than silently accepting a
repaired shape as if it were the original. Confirmed on a real customer
STEP file (a car rear spoiler, 182 disconnected single-face shells, 0
solids as exported): sewing at a few tenths of a millimeter connects
everything into a single shell, but 6 to 8 edges remained open across a
range of tested tolerances (0.05 mm to 0.7 mm), so that particular file
still needs a fix in the source CAD tool, automatic repair could not
close a genuine modelling gap. See docs/RISKS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from build123d import BRepBuilderAPI_Sewing, Edge, Shape, Shell, Solid, import_step as _import_step


class GeometryError(Exception):
    """Raised when a STEP file cannot be used as a solid body for meshing."""


@dataclass(frozen=True)
class FreeEdgeInfo:
    center: tuple[float, float, float]
    length: float


@dataclass(frozen=True)
class SewingReport:
    tolerance: float
    input_face_count: int
    became_solid: bool
    free_edge_count: int
    free_edges_sample: tuple[FreeEdgeInfo, ...]


@dataclass(frozen=True)
class ImportedGeometry:
    shape: Shape
    source_path: Path
    volume: float
    repair_report: SewingReport | None = None


def import_step(path: str | Path, sewing_tolerance: float | None = None) -> ImportedGeometry:
    """Import a STEP file and validate it is a single watertight solid.

    If sewing_tolerance is given and the raw import is not already a
    valid solid, an explicit, disclosed sewing repair is attempted at
    that tolerance (see module docstring). Without sewing_tolerance, no
    repair is attempted, matching the previous strict behaviour.

    Raises GeometryError with an actionable message if the file is
    missing, not readable as STEP, or (after any requested repair
    attempt) still not a single watertight solid with positive volume.
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

    try:
        return _validate_solid(shape, path)
    except GeometryError:
        if sewing_tolerance is None:
            raise
        return _repair_and_validate(shape, path, sewing_tolerance)


def _validate_solid(shape: Shape, path: Path, repair_report: SewingReport | None = None) -> ImportedGeometry:
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
            "the geometry in the source CAD system and re-export it, or "
            "retry with a sewing_tolerance to attempt automatic repair."
        )

    volume = shape.volume
    if volume <= 0:
        raise GeometryError(
            f"'{path}' has non-positive volume ({volume:.6g}). This "
            "usually means the solid's face orientations are inconsistent. "
            "Re-export the geometry from the source CAD system."
        )

    return ImportedGeometry(shape=shape, source_path=path, volume=volume, repair_report=repair_report)


def _repair_and_validate(shape: Shape, path: Path, tolerance: float) -> ImportedGeometry:
    faces = shape.faces()
    sewing = BRepBuilderAPI_Sewing(tolerance)
    for face in faces:
        sewing.Add(face.wrapped)
    sewing.Perform()

    free_edge_count = sewing.NbFreeEdges()
    free_edges_sample = tuple(
        FreeEdgeInfo(center=tuple(Edge(sewing.FreeEdge(i)).center()), length=Edge(sewing.FreeEdge(i)).length)
        for i in range(1, min(free_edge_count, 10) + 1)
    )

    sewn_solid: Solid | None = None
    if free_edge_count == 0:
        sewn_shell = Shell(sewing.SewedShape())
        try:
            sewn_solid = Solid(Solid._make_solid(sewn_shell))
        except Exception:
            sewn_solid = None
    became_solid = sewn_solid is not None

    report = SewingReport(
        tolerance=tolerance,
        input_face_count=len(faces),
        became_solid=became_solid,
        free_edge_count=free_edge_count,
        free_edges_sample=free_edges_sample,
    )

    if not became_solid:
        sample_text = "\n".join(
            f"  - near {e.center}, length {e.length:.4g}" for e in free_edges_sample
        )
        raise GeometryError(
            f"'{path}' has {report.input_face_count} disconnected surface "
            f"patches. Sewing at tolerance {tolerance:g} connected most of "
            f"them, but {free_edge_count} edge(s) remain open, so this is "
            "not a closed solid. This is a genuine gap in the source model, "
            "not something automatic repair can safely close. Open the "
            "model in the source CAD system and check near these "
            f"locations:\n{sample_text}"
        )

    return _validate_solid(sewn_solid, path, repair_report=report)
