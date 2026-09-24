"""STEP geometry fixtures for tests, generated via build123d. Not part of
the shipped fosas_core package.
"""

from __future__ import annotations

from pathlib import Path

from build123d import BuildLine, BuildPart, BuildSketch, Plane, Spline, export_step, extrude, make_face

from .airfoils import naca4_points


def naca0012_wing_step(path: Path, chord: float = 0.6, span: float = 1.2, n: int = 40) -> Path:
    """A constant-section NACA0012 wing, profile built from two smooth
    splines (not a many-segment polyline), extruded along Z.
    """
    pts = naca4_points(chord=chord, n=n)
    mid = len(pts) // 2

    with BuildPart() as wing:
        with BuildSketch(Plane.XY):
            with BuildLine():
                Spline(*[(x, z) for x, z in pts[: mid + 1]])
                Spline(*([(x, z) for x, z in pts[mid:]] + [pts[0]]))
            make_face()
        extrude(amount=span)

    export_step(wing.part, str(path))
    return path


def naca0012_profile_step(path: Path, chord: float = 0.6, n: int = 40) -> Path:
    """Just the 2D NACA0012 profile curve (two splines, no extrusion,
    no solid), in the X-Z plane matching the SU2 axis convention
    (X chordwise, Z vertical). Used to test whether the meshing adapter's
    boundary layer technique works on a Gmsh-imported STEP curve instead
    of a curve authored directly in the .geo script.
    """
    pts = naca4_points(chord=chord, n=n)
    mid = len(pts) // 2

    with BuildLine(Plane.XZ) as profile:
        Spline(*[(x, z) for x, z in pts[: mid + 1]])
        Spline(*([(x, z) for x, z in pts[mid:]] + [pts[0]]))

    export_step(profile.line, str(path))
    return path
