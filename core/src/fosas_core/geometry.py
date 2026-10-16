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

from build123d import Axis, BRepBuilderAPI_Sewing, Edge, Shape, Shell, Solid, import_step as _import_step


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


# Axis-orientation detection (point 3 of the original requirements,
# docs/ARCHITECTURE.md "Koordinatenkonvention"; docs/RISKS.md R13
# explicitly deferred automatic correction in favour of a user-
# confirmed 3D preview, never built - this finally adds the automatic
# half, for the unambiguous case only, see below).
#
# Threshold confirmed against two real STEP files that actually failed
# in production (docs/RISKS.md R13, 2026-10-16): a correctly-oriented
# wing, once rotated into the right axes, measured thickness/chord =
# 10% (chord=100mm, span=500mm, thickness=10.2mm) - a clean, confident
# match. A second, structurally more complex file (not a simple single
# wing) had its best candidate at thickness/chord = 49% even after
# trying every possible axis assignment - nowhere near as confident,
# and real airfoils are typically 6-18% thick. 0.3 sits between the
# two observed real cases; still an Annahme/Richtwert, not a physical
# law, since a genuinely unusual but correctly-oriented thick body
# could exceed it.
_PLAUSIBLE_THICKNESS_RATIO = 0.3
# The best candidate must beat the next-best plausible one by at least
# this factor, or the choice is not confident enough to apply silently
# (the real ambiguous file above had 4 of 6 candidates "plausible" by
# the loose chord/span/thickness bound alone - thickness_ratio alone
# is the real discriminator, this margin guards against two candidates
# scoring close enough that picking either would be a guess).
_CONFIDENCE_MARGIN = 2.0


@dataclass(frozen=True)
class OrientationCandidate:
    """One of the 6 possible ways to assign a shape's own three
    bounding-box extents to FOSAS's (chord=X, span=Y, thickness=Z)
    convention. Confirmed exhaustive by direct test against the two
    real files mentioned above: every possible axis assignment is
    reachable via the identity, a single 90-degree rotation about one
    of the three axes, or one of the two genuine 3-axis-cycle
    combinations - there is no 7th distinct assignment.
    """

    label: str
    chord: float
    span: float
    thickness: float
    plausible: bool  # same bounds as pipeline.run_case's own sanity check
    thickness_ratio: float  # thickness / chord; lower = more airfoil-like


@dataclass(frozen=True)
class OrientationResult:
    shape: Shape
    applied_label: str | None  # None: used as given, either because it already fit or because no candidate was confident
    confident: bool
    candidates: tuple[OrientationCandidate, ...]  # all 6, for diagnostics/error messages/the manual preview tool


# The 6 possible 90-degree axis-permutation labels, shared between
# detect_axis_orientation (automatic case) and apply_named_rotation
# (manual preview case, pipeline.py's CaseParams.manual_rotation_label) so
# both always mean exactly the same physical rotation - the label is the
# single source of truth, never a separately re-derived (x, y, z) angle
# triple on either side (rotations do not commute, so a fixed-order
# x-then-y-then-z composition cannot reproduce every one of the 6 cases,
# "rot_z90_then_x90" in particular - see geometry preview endpoint).
ROTATION_LABELS: tuple[str, ...] = (
    "identity",
    "rot_x90",
    "rot_y90",
    "rot_z90",
    "rot_x90_then_z90",
    "rot_z90_then_x90",
)


def _named_rotations(shape: Shape) -> dict[str, Shape]:
    return {
        "identity": shape,
        "rot_x90": shape.rotate(Axis.X, 90),
        "rot_y90": shape.rotate(Axis.Y, 90),
        "rot_z90": shape.rotate(Axis.Z, 90),
        "rot_x90_then_z90": shape.rotate(Axis.X, 90).rotate(Axis.Z, 90),
        "rot_z90_then_x90": shape.rotate(Axis.Z, 90).rotate(Axis.X, 90),
    }


def apply_named_rotation(shape: Shape, label: str) -> Shape:
    """Applies one of ROTATION_LABELS by name. Used for a manually chosen
    orientation (geometry preview tool) - the automatic detector below
    uses the exact same recipes, so a label means the same thing either
    way.
    """
    rotations = _named_rotations(shape)
    if label not in rotations:
        raise GeometryError(f"Unknown rotation label '{label}', expected one of {ROTATION_LABELS}")
    return rotations[label]


def detect_axis_orientation(shape: Shape) -> OrientationResult:
    """Looks for a confident 90-degree-multiple rotation that fixes a
    chord/span/thickness axis mix-up, without ever second-guessing a
    shape that is already plausibly oriented: if the shape as given
    already satisfies the same bounds pipeline.run_case checks itself,
    it is always returned unchanged, regardless of whether some other
    rotation would score "better" by the thickness-ratio heuristic -
    that heuristic is a best-effort guess for the case where the shape
    as given does NOT already pass, not a replacement for an
    already-working orientation.

    Does not replace pipeline.run_case's own sanity checks - those
    still run afterwards on whatever shape comes back from here, this
    only decides which (if any) rotation to try first.
    """
    rotations = _named_rotations(shape)

    def make_candidate(label: str, candidate_shape: Shape) -> OrientationCandidate:
        bbox = candidate_shape.bounding_box()
        chord = bbox.max.X - bbox.min.X
        span = bbox.max.Y - bbox.min.Y
        thickness = bbox.max.Z - bbox.min.Z
        plausible = chord > 0 and span > 0 and span >= 0.5 * chord and thickness <= 2 * span
        thickness_ratio = thickness / chord if chord > 0 else float("inf")
        return OrientationCandidate(
            label=label, chord=chord, span=span, thickness=thickness,
            plausible=plausible, thickness_ratio=thickness_ratio,
        )

    candidates = tuple(make_candidate(label, s) for label, s in rotations.items())

    identity_candidate = candidates[0]
    if identity_candidate.plausible:
        return OrientationResult(shape=shape, applied_label=None, confident=True, candidates=candidates)

    alternatives = sorted((c for c in candidates[1:] if c.plausible), key=lambda c: c.thickness_ratio)
    confident = (
        len(alternatives) >= 1
        and alternatives[0].thickness_ratio <= _PLAUSIBLE_THICKNESS_RATIO
        and (len(alternatives) == 1 or alternatives[1].thickness_ratio >= _CONFIDENCE_MARGIN * alternatives[0].thickness_ratio)
    )
    if confident:
        best = alternatives[0]
        return OrientationResult(shape=rotations[best.label], applied_label=best.label, confident=True, candidates=candidates)

    return OrientationResult(shape=shape, applied_label=None, confident=False, candidates=candidates)
