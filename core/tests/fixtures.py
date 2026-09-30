"""STEP geometry fixtures for tests, generated via build123d. Not part of
the shipped fosas_core package.

All functions here take chord/span in metres, matching how call sites
and assertions read (a 0.6 chord means 0.6 m). Internally they build the
geometry at 1000x that (millimetres), because build123d/OCCT's working
length unit is always millimetres regardless of a STEP file's own
declared unit (confirmed empirically, see the unit-conversion comment in
fosas_core.pipeline.run_case and docs/RISKS.md R15) - so a shape built
with a bare "0.6" would round-trip through STEP as 0.6 mm, not 0.6 m.
"""

from __future__ import annotations

from pathlib import Path

from build123d import BuildLine, BuildPart, BuildSketch, Plane, Spline, export_step, extrude, make_face

from .airfoils import naca4_points


def naca0012_wing_step(path: Path, chord: float = 0.6, span: float = 1.2, n: int = 40) -> Path:
    """A constant-section NACA0012 wing, profile built from two smooth
    splines (not a many-segment polyline), extruded along Y (spanwise),
    matching the SU2/engine axis convention: X chordwise, Y spanwise,
    Z vertical (see docs/ARCHITECTURE.md).
    """
    pts = naca4_points(chord=chord * 1000, n=n)
    mid = len(pts) // 2

    with BuildPart() as wing:
        with BuildSketch(Plane.XZ):
            with BuildLine():
                Spline(*[(x, z) for x, z in pts[: mid + 1]])
                Spline(*([(x, z) for x, z in pts[mid:]] + [pts[0]]))
            make_face()
        extrude(amount=span * 1000)

    export_step(wing.part, str(path))
    return path


def naca0012_wing_step_wrong_axes(path: Path, chord: float = 0.6, span: float = 1.2, n: int = 40) -> Path:
    """Same wing as naca0012_wing_step, but extruded along Z instead of Y,
    i.e. deliberately NOT matching the expected axis convention (span
    ends up along Z, thickness along Y). Reproduces a real incident: a
    customer STEP file with span along Z passed run_case's old bounding-
    box checks (X and Y were both positive) and produced a nonsensical
    lengthwise cross-section that made Gmsh exhaust available memory
    before being killed by the OOM killer, see docs/RISKS.md.
    """
    pts = naca4_points(chord=chord * 1000, n=n)
    mid = len(pts) // 2

    with BuildPart() as wing:
        with BuildSketch(Plane.XY):
            with BuildLine():
                Spline(*[(x, z) for x, z in pts[: mid + 1]])
                Spline(*([(x, z) for x, z in pts[mid:]] + [pts[0]]))
            make_face()
        extrude(amount=span * 1000)

    export_step(wing.part, str(path))
    return path


def naca0012_profile_step(path: Path, chord: float = 0.6, n: int = 40) -> Path:
    """Just the 2D NACA0012 profile curve (two splines, no extrusion,
    no solid), in the X-Z plane matching the SU2 axis convention
    (X chordwise, Z vertical). Used to test whether the meshing adapter's
    boundary layer technique works on a Gmsh-imported STEP curve instead
    of a curve authored directly in the .geo script.

    Deliberately NOT scaled to millimetres like the other fixtures here:
    its only consumer, generate_constant_section_geo_from_step_profile,
    merges this STEP file's raw coordinates straight into the .geo script
    and expects them to already be on the same numeric scale as the
    chord/span arguments passed alongside it (it is not part of the
    fosas_core.pipeline path that now does the mm-to-m conversion, see
    docs/RISKS.md R15), so this fixture's chord argument must still mean
    "chord in whatever unit the geometry is built at", not metres.
    """
    pts = naca4_points(chord=chord, n=n)
    mid = len(pts) // 2

    with BuildLine(Plane.XZ) as profile:
        Spline(*[(x, z) for x, z in pts[: mid + 1]])
        Spline(*([(x, z) for x, z in pts[mid:]] + [pts[0]]))

    export_step(profile.line, str(path))
    return path
