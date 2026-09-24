"""Gmsh meshing adapter.

Gmsh is invoked exclusively as an external process (never `import gmsh`),
per ADR-0002: Gmsh is GPL-licensed, and loading it in-process could pull
our own code into that license's scope. All communication happens through
a generated .geo script and the resulting .su2 mesh file on disk.

The meshing technique implemented here (2D profile with a boundary layer,
then translational extrusion along the span) only applies to bodies with
a constant cross-section along one axis, see ADR-0007. It works both with
a profile authored directly as Gmsh commands
(generate_constant_section_geo) and with one imported from a STEP file
via Gmsh's own OCC import (generate_constant_section_geo_from_step_profile),
both confirmed by end-to-end tests with real graded near-wall spacing.
Still open: bodies without a constant cross-section (taper, sweep, wing
tips), see docs/OPEN_QUESTIONS.md.

Every run's full output log is scanned for the literal string "Error"
before the result is considered successful. Gmsh has been observed to
log an invalid-option error and then continue running to completion
anyway (see docs/RISKS.md R1), so checking the process exit code alone,
or only the tail of the log, is not sufficient.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class MeshingError(Exception):
    """Raised when Gmsh reports an error, or fails to produce a mesh."""


@dataclass(frozen=True)
class BoundaryLayerMeshParams:
    first_cell_height: float
    growth_ratio: float
    thickness: float

    def __post_init__(self):
        if self.first_cell_height <= 0:
            raise ValueError("first_cell_height must be positive")
        if self.growth_ratio <= 1.0:
            raise ValueError("growth_ratio must be greater than 1.0")
        if self.thickness <= self.first_cell_height:
            raise ValueError("thickness must be greater than first_cell_height")


@dataclass(frozen=True)
class ConstantSectionMeshParams:
    """Meshing parameters for a body with a constant cross-section swept
    along the span (Y) axis, matching the SU2 axis convention (X
    chordwise/downstream, Y spanwise, Z vertical), see docs/ARCHITECTURE.md.
    """

    profile_points_xz: tuple[tuple[float, float], ...]
    span: float
    chord: float
    boundary_layer: BoundaryLayerMeshParams
    span_layers: int = 24
    farfield_factor_upstream: float = 5.0
    farfield_factor_downstream: float = 10.0
    farfield_factor_side: float = 6.0
    background_size_min_factor: float = 0.01
    background_size_max_factor: float = 0.5

    def __post_init__(self):
        if len(self.profile_points_xz) < 3:
            raise ValueError("profile_points_xz needs at least 3 points")
        if self.span <= 0:
            raise ValueError("span must be positive")
        if self.chord <= 0:
            raise ValueError("chord must be positive")


@dataclass(frozen=True)
class MeshInfo:
    su2_path: Path
    node_count: int
    element_count: int
    markers: tuple[str, ...]


def generate_constant_section_geo(params: ConstantSectionMeshParams, output_su2_path: Path) -> str:
    """Build the .geo script text for a constant-cross-section body,
    with the profile authored directly as Gmsh Point/Spline commands.
    """
    pts = list(params.profile_points_xz)
    if pts[0] == pts[-1]:
        pts = pts[:-1]  # de-duplicate; the loop is closed explicitly below

    # Gmsh/OCCT reliably builds a closed loop from two splines meeting at
    # shared end points, but a single spline that returns exactly to its
    # own start point failed in testing ("Could not create spline"). Split
    # the profile into two arcs at roughly the halfway point instead.
    mid = len(pts) // 2

    point_lines = []
    point_ids = []
    for i, (x, z) in enumerate(pts):
        pid = f"p{i}"
        point_ids.append(pid)
        point_lines.append(f"{pid} = newp; Point({pid}) = {{{x!r}, 0, {z!r}, 1}};")
    arc1_ids = point_ids[: mid + 1]
    arc2_ids = point_ids[mid:] + [point_ids[0]]

    profile_setup = (
        "\n".join(point_lines)
        + f"\nprofile_arc1 = newl; Spline(profile_arc1) = {{{', '.join(arc1_ids)}}};"
        + f"\nprofile_arc2 = newl; Spline(profile_arc2) = {{{', '.join(arc2_ids)}}};"
    )
    return _constant_section_geo_body(
        profile_setup=profile_setup,
        profile_curves_expr="profile_arc1, profile_arc2",
        chord=params.chord,
        span=params.span,
        bl=params.boundary_layer,
        span_layers=params.span_layers,
        farfield_factor_upstream=params.farfield_factor_upstream,
        farfield_factor_downstream=params.farfield_factor_downstream,
        farfield_factor_side=params.farfield_factor_side,
        background_size_min_factor=params.background_size_min_factor,
        background_size_max_factor=params.background_size_max_factor,
        output_su2_path=output_su2_path,
    )


def generate_constant_section_geo_from_step_profile(
    profile_step_path: str | Path,
    chord: float,
    span: float,
    boundary_layer: BoundaryLayerMeshParams,
    output_su2_path: Path,
    span_layers: int = 24,
    farfield_factor_upstream: float = 5.0,
    farfield_factor_downstream: float = 10.0,
    farfield_factor_side: float = 6.0,
    background_size_min_factor: float = 0.01,
    background_size_max_factor: float = 0.5,
) -> str:
    """Same as generate_constant_section_geo, but the profile curve is
    imported from a STEP file (via Gmsh's own OCC import) instead of
    being authored as Python-side points. This is the technique that was
    still untested as of ADR-0007; see docs/OPEN_QUESTIONS.md.

    The STEP file must contain only the profile curve(s) in the X-Z
    plane (X chordwise, Z vertical), nothing else, since all curves
    present immediately after the Merge are taken to be the profile.
    """
    profile_setup = f'Merge "{profile_step_path}";\nprofileCurves() = Curve{{:}};'
    return _constant_section_geo_body(
        profile_setup=profile_setup,
        profile_curves_expr="profileCurves()",
        chord=chord,
        span=span,
        bl=boundary_layer,
        span_layers=span_layers,
        farfield_factor_upstream=farfield_factor_upstream,
        farfield_factor_downstream=farfield_factor_downstream,
        farfield_factor_side=farfield_factor_side,
        background_size_min_factor=background_size_min_factor,
        background_size_max_factor=background_size_max_factor,
        output_su2_path=output_su2_path,
    )


def _constant_section_geo_body(
    *,
    profile_setup: str,
    profile_curves_expr: str,
    chord: float,
    span: float,
    bl: BoundaryLayerMeshParams,
    span_layers: int,
    farfield_factor_upstream: float,
    farfield_factor_downstream: float,
    farfield_factor_side: float,
    background_size_min_factor: float,
    background_size_max_factor: float,
    output_su2_path: Path,
) -> str:
    margin_up = farfield_factor_upstream * chord
    margin_down = farfield_factor_downstream * chord
    margin_side = farfield_factor_side * chord
    size_min = background_size_min_factor * chord
    size_max = background_size_max_factor * chord

    return f"""SetFactory("OpenCASCADE");

{profile_setup}

margin_up = {margin_up!r};
margin_down = {margin_down!r};
margin_side = {margin_side!r};
chord = {chord!r};
span = {span!r};

r_p1 = newp; Point(r_p1) = {{-margin_up, 0, -margin_side, 1}};
r_p2 = newp; Point(r_p2) = {{chord+margin_down, 0, -margin_side, 1}};
r_p3 = newp; Point(r_p3) = {{chord+margin_down, 0, margin_side, 1}};
r_p4 = newp; Point(r_p4) = {{-margin_up, 0, margin_side, 1}};
r_l1 = newl; Line(r_l1) = {{r_p1, r_p2}};
r_l2 = newl; Line(r_l2) = {{r_p2, r_p3}};
r_l3 = newl; Line(r_l3) = {{r_p3, r_p4}};
r_l4 = newl; Line(r_l4) = {{r_p4, r_p1}};
cl_far = newcl; Curve Loop(cl_far) = {{r_l1, r_l2, r_l3, r_l4}};
cl_profile = newcl; Curve Loop(cl_profile) = {{{profile_curves_expr}}};

s_fluid2d = news; Plane Surface(s_fluid2d) = {{cl_far, cl_profile}};

Mesh.MeshSizeMax = {size_max!r};
Mesh.MeshSizeMin = {size_min!r};

Field[1] = Distance;
Field[1].CurvesList = {{{profile_curves_expr}}};
Field[1].Sampling = 300;
Field[2] = Threshold;
Field[2].InField = 1;
Field[2].SizeMin = {size_min!r};
Field[2].SizeMax = {size_max!r};
Field[2].DistMin = {0.05 * chord!r};
Field[2].DistMax = {3.0 * chord!r};

Field[3] = BoundaryLayer;
Field[3].CurvesList = {{{profile_curves_expr}}};
Field[3].Size = {bl.first_cell_height!r};
Field[3].Ratio = {bl.growth_ratio!r};
Field[3].SizeFar = {size_max!r};
Field[3].Thickness = {bl.thickness!r};
Field[3].Quads = 0;
BoundaryLayer Field = 3;

Background Field = 2;

Mesh 2;

ext[] = Extrude {{0, span, 0}} {{ Surface{{s_fluid2d}}; Layers{{{span_layers}}}; }};

allVols() = Volume{{:}};
fluid_vol = allVols(0);

allBoundarySigned() = Boundary{{ Volume{{fluid_vol}}; }};
allBoundary() = {{}};
For i In {{0:#allBoundarySigned()-1}}
  allBoundary() += {{Abs(allBoundarySigned(i))}};
EndFor

wingSurfs() = Surface In BoundingBox{{{-0.05*chord!r}, {-0.01*span!r}, {-0.5*chord!r}, {1.05*chord!r}, {1.01*span!r}, {0.5*chord!r}}};

farfieldSurfs() = {{}};
For i In {{0:#allBoundary()-1}}
  isWing = 0;
  For j In {{0:#wingSurfs()-1}}
    If (allBoundary(i) == wingSurfs(j))
      isWing = 1;
    EndIf
  EndFor
  If (isWing == 0)
    farfieldSurfs() += {{allBoundary(i)}};
  EndIf
EndFor

Physical Surface("airfoil") = wingSurfs();
Physical Surface("farfield") = farfieldSurfs();
Physical Volume("fluid") = {{fluid_vol}};

Mesh 3;

Save "{str(output_su2_path)}";
"""


def run_gmsh(
    geo_script: str,
    output_su2_path: Path,
    gmsh_executable: str = "gmsh",
    timeout: float = 900.0,
) -> MeshInfo:
    """Write geo_script to a temp .geo file next to the output, run Gmsh,
    and validate the result. Raises MeshingError if Gmsh reports any
    error anywhere in its output, if the process fails to start, if it
    times out, or if the expected output file was not produced.
    """
    output_su2_path = Path(output_su2_path)
    geo_path = output_su2_path.with_suffix(".geo")
    geo_path.write_text(geo_script)

    try:
        result = subprocess.run(
            [gmsh_executable, str(geo_path), "-3", "-v", "3"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise MeshingError(
            f"Gmsh executable '{gmsh_executable}' was not found. Install "
            "Gmsh or pass the correct path via gmsh_executable."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise MeshingError(
            f"Gmsh did not finish within {timeout} seconds. Increase the "
            "timeout, or reduce mesh resolution."
        ) from exc

    full_log = (result.stdout or "") + (result.stderr or "")
    if "Error" in full_log:
        error_lines = [line for line in full_log.splitlines() if "Error" in line]
        raise MeshingError(
            "Gmsh reported at least one error (checked the full log, not "
            "just the exit code or the tail, see docs/RISKS.md R1):\n"
            + "\n".join(error_lines)
        )
    if result.returncode != 0:
        raise MeshingError(
            f"Gmsh exited with code {result.returncode} without a recognized "
            f"'Error' line. Full output:\n{full_log[-4000:]}"
        )
    if not output_su2_path.exists():
        raise MeshingError(
            f"Gmsh finished without reporting an error, but the expected "
            f"output file '{output_su2_path}' was not created."
        )

    node_count, element_count, markers = _read_su2_header(output_su2_path)
    return MeshInfo(
        su2_path=output_su2_path,
        node_count=node_count,
        element_count=element_count,
        markers=markers,
    )


def _read_su2_header(su2_path: Path) -> tuple[int, int, tuple[str, ...]]:
    node_count = -1
    element_count = -1
    markers: list[str] = []
    with open(su2_path) as f:
        for line in f:
            if line.startswith("NELEM="):
                element_count = int(line.split("=")[1])
            elif line.startswith("NPOIN="):
                node_count = int(line.split("=")[1])
            elif line.startswith("MARKER_TAG="):
                markers.append(line.split("=")[1].strip())
    return node_count, element_count, tuple(markers)
