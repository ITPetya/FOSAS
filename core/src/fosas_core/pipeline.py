"""End-to-end case pipeline: STEP file in, cl/cd and convergence out.

V1 scope, explicit assumptions (see docs/ARCHITECTURE.md and
docs/OPEN_QUESTIONS.md):

- The geometry must already use the axis convention X chordwise
  (downstream), Y spanwise, Z vertical. FOSAS does not yet reorient
  arbitrary geometry (that needs the user-confirmed orientation step
  from the original requirements, not implemented yet).
- The body must have a constant cross-section along Y (ADR-0007). A
  single cross-section is taken at mid-span; tapered/swept bodies are
  out of scope for now (see docs/RISKS.md R12).
- Reference length/area/moment origin are derived from the geometry's
  bounding box, not user-overridable yet.

This intentionally does not hide the still-open convergence question
from docs/RISKS.md R10: assess_convergence is always run and reported,
and a case that does not converge is still returned as a result, not
raised as an error, with converged=False and an honest message.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from build123d import Plane

from .boundary_layer import dynamic_pressure, first_cell_height, reynolds_number
from .forces import ForceSystem, MomentSystem, compute_force_system, compute_moment_system
from .geometry import GeometryError, import_step
from .meshing import (
    BoundaryLayerMeshParams,
    ConstantSectionMeshParams,
    MeshingError,
    generate_constant_section_geo,
    read_mesh_info,
    run_gmsh,
)
from .quality import ConvergenceAssessment, assess_convergence
from .solver import (
    FreestreamConditions,
    IterationHistory,
    ReferenceValues,
    SolverError,
    SolverParams,
    SurfaceData,
    generate_config,
    run_su2,
)


class PipelineError(Exception):
    """A case failed at a specific stage. `stage` names it so a caller
    (e.g. the API) can report which part of the pipeline broke.
    """

    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"[{stage}] {message}")


@dataclass(frozen=True)
class ExecutablePaths:
    gmsh: str = "gmsh"
    su2: str = "SU2_CFD"
    mpirun: str = "mpirun"


def aoa_to_velocity_components(velocity: float, aoa_deg: float) -> tuple[float, float, float]:
    """Freestream velocity vector (X, Y, Z) for a given angle of attack,
    matching the project's axis convention (X chordwise/downstream, Y
    spanwise, Z vertical, see docs/ARCHITECTURE.md): the inflow rotates
    in the X-Z plane, Y stays zero. Extracted out of run_case so a
    polar sweep (Phase 2) can reuse the exact same conversion per AoA
    value without duplicating it.
    """
    vx = velocity * math.cos(math.radians(aoa_deg))
    vz = velocity * math.sin(math.radians(aoa_deg))
    return vx, 0.0, vz


@dataclass(frozen=True)
class CaseParams:
    velocity: float
    aoa_deg: float
    density: float = 1.225
    dynamic_viscosity: float = 1.81e-5
    temperature: float = 288.15
    target_y_plus: float = 1.0
    growth_ratio: float = 1.2
    bl_thickness_factor: float = 0.05
    span_layers: int = 24
    n_profile_points: int = 60
    max_iterations: int = 500
    mpi_ranks: int = 1
    residual_column: str = "rms[P]"
    residual_threshold: float = -8.0
    time_discretization: str = "EULER_IMPLICIT"
    # Background mesh density, as a factor of chord (see
    # meshing.ConstantSectionMeshParams); previously always silently
    # fixed at ConstantSectionMeshParams's own class defaults, since
    # run_case never passed anything else through. Exposed here
    # specifically so a GCI mesh-independence study (Phase 2, see
    # docs/DECISIONS.md ADR-0017) can vary ONLY the far-field/wake
    # element density across 3 runs while holding domain size and
    # near-wall sizing (target_y_plus, growth_ratio, bl_thickness_factor)
    # fixed, as the GCI method requires.
    background_size_min_factor: float = 0.01
    background_size_max_factor: float = 0.5

    def __post_init__(self):
        if self.velocity <= 0:
            raise ValueError("velocity must be positive")
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.n_profile_points < 3:
            raise ValueError("n_profile_points must be at least 3")


@dataclass(frozen=True)
class CaseResult:
    chord: float
    span: float
    node_count: int
    element_count: int
    markers: tuple[str, ...]
    cl: float
    cd: float
    convergence: ConvergenceAssessment
    history: IterationHistory
    surface: SurfaceData
    mean_y_plus: float
    max_y_plus: float
    # Derived purely from already-known inputs (freestream density/
    # velocity, chord, viscosity), computed here rather than in the UI
    # per the project's rule that all physics lives in the logic layer,
    # see docs/ARCHITECTURE.md "Technische-Mechanik-Visualisierung".
    dynamic_pressure: float
    reynolds_number: float
    forces: ForceSystem
    moments: MomentSystem
    mesh_path: Path
    solve_dir: Path


def _sample_wire_points(wire, n: int) -> tuple[tuple[float, float], ...]:
    """Sample n points per edge of the wire (not n total): a wire coming
    from a real, external STEP file can have more than the two edges a
    synthetic upper/lower-surface split assumes (confirmed on a real
    customer file, see docs/RISKS.md R12/R15: three edges, not two), and
    n is the resolution along each of them, not a total budget to divide
    up. n was hardcoded to 40 here regardless of CaseParams.n_profile_points
    until this was noticed: the GUI's "Profilpunkte" field had no effect
    on the actual mesh at all.
    """
    edges = wire.edges()
    points = []
    for edge in edges:
        for i in range(n):
            p = edge.position_at(i / n)
            points.append((p.X, p.Z))
    return tuple(points)


def run_case(
    step_path: str | Path,
    params: CaseParams,
    work_dir: str | Path,
    executables: ExecutablePaths = ExecutablePaths(),
    mesh_timeout: float = 900.0,
    solve_timeout: float = 7200.0,
) -> CaseResult:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        geometry = import_step(step_path)
    except GeometryError as exc:
        raise PipelineError("geometry", str(exc)) from exc

    bbox = geometry.shape.bounding_box()
    chord = bbox.max.X - bbox.min.X
    span = bbox.max.Y - bbox.min.Y
    thickness = bbox.max.Z - bbox.min.Z
    if chord <= 0 or span <= 0:
        raise PipelineError(
            "geometry",
            f"Bounding box gives chord={chord:.4g}, span={span:.4g}. FOSAS V1 "
            "assumes the geometry already uses X chordwise, Y spanwise, Z "
            "vertical (see docs/ARCHITECTURE.md); check the input orientation.",
        )
    # Sanity check, added after a real incident: a STEP file with the
    # actual span along Z (not Y) passed the check above (Y and X were
    # both positive, just the wrong physical quantities) and produced a
    # nonsensical lengthwise cross-section, which made Gmsh consume
    # essentially all available RAM before the OOM killer stepped in.
    # A real wing's span is essentially always larger than its chord,
    # and its Y-extent (assumed thickness-free span) should not be
    # dramatically smaller than its Z-extent if Z really is vertical.
    if span < 0.5 * chord or thickness > 2 * span:
        raise PipelineError(
            "geometry",
            f"Bounding box looks implausible for the assumed axis convention "
            f"(X chordwise={chord:.4g}, Y spanwise={span:.4g}, Z vertical="
            f"{thickness:.4g}). A real wing's span is normally larger than its "
            "chord, and clearly larger than its thickness. This usually means "
            "the geometry's span is actually along a different axis (often Z). "
            "Re-export or rotate the geometry so X is chordwise, Y is "
            "spanwise, and Z is vertical, see docs/ARCHITECTURE.md.",
        )
    mid_y = (bbox.min.Y + bbox.max.Y) / 2

    try:
        # Plane.XZ's normal points along -Y (confirmed empirically: an
        # offset of +d lands the plane at global Y=-d, not +d), so the
        # offset sign has to be flipped to actually reach Y=mid_y.
        section = geometry.shape.intersect(Plane.XZ.offset(-mid_y))
    except Exception as exc:
        raise PipelineError("geometry", f"Could not cut a cross-section at mid-span: {exc}") from exc
    if not section:
        raise PipelineError("geometry", "Cross-section at mid-span is empty.")

    profile_points_native = _sample_wire_points(section[0].outer_wire(), params.n_profile_points)

    # build123d/OCCT's internal working length unit is millimeters,
    # regardless of what unit a source STEP file declares in its own
    # header: confirmed directly by round-tripping two synthetic STEP
    # files through import_step, one declaring SI_UNIT(.MILLI.,.METRE.)
    # and one declaring SI_UNIT($,.METRE.) for the same nominal size,
    # which came back as bounding boxes of 1.0 and 1000.0 respectively.
    # Every physics formula from here on (Reynolds number, y+ sizing,
    # SU2's freestream/viscosity) is SI (density kg/m^3, velocity m/s,
    # viscosity Pa*s), so every length pulled out of the geometry must
    # be converted to meters here, once, before any of it is used. This
    # was missing until a real customer file (chord really 100 mm) got
    # its 100 treated as 100 meters, inflating the Reynolds number by
    # 1000x and, through the resulting boundary-layer/background mesh
    # size ratio, crashing Gmsh with an OOM kill, see docs/RISKS.md R15.
    # Synthetic test fixtures never exposed this: they are also built
    # and re-imported via build123d, so a "0.6" chosen to mean "0.6 m"
    # round-tripped as "0.6" again before this fix, i.e. two separate
    # unit mistakes (mm meant as m in the fixture, then treated as m
    # again here) canceled out numerically. Fixed at the source instead
    # of patching fixtures to match the bug: fixtures.py now builds
    # geometry at 1000x the intended metre dimensions.
    _MM_TO_M = 0.001
    chord *= _MM_TO_M
    span *= _MM_TO_M
    thickness *= _MM_TO_M
    mid_y *= _MM_TO_M
    profile_points = tuple((x * _MM_TO_M, z * _MM_TO_M) for x, z in profile_points_native)

    y1 = first_cell_height(
        density=params.density,
        velocity=params.velocity,
        reference_length=chord,
        dynamic_viscosity=params.dynamic_viscosity,
        target_y_plus=params.target_y_plus,
    )
    mesh_params = ConstantSectionMeshParams(
        profile_points_xz=profile_points,
        span=span,
        chord=chord,
        boundary_layer=BoundaryLayerMeshParams(
            first_cell_height=y1,
            growth_ratio=params.growth_ratio,
            thickness=params.bl_thickness_factor * chord,
        ),
        span_layers=params.span_layers,
        background_size_min_factor=params.background_size_min_factor,
        background_size_max_factor=params.background_size_max_factor,
    )
    mesh_path = work_dir / "mesh.su2"
    if mesh_path.exists():
        # Resuming a job that got this far before (crash, engine restart,
        # see docs/ARCHITECTURE.md job persistence): re-meshing an
        # unchanged geometry with the same parameters would just
        # reproduce the same file, so reuse it instead of redoing
        # potentially expensive work.
        mesh_info = read_mesh_info(mesh_path)
    else:
        try:
            geo = generate_constant_section_geo(mesh_params, mesh_path)
            mesh_info = run_gmsh(geo, mesh_path, gmsh_executable=executables.gmsh, timeout=mesh_timeout)
        except MeshingError as exc:
            raise PipelineError("meshing", str(exc)) from exc

    vx, _, vz = aoa_to_velocity_components(params.velocity, params.aoa_deg)
    solve_dir = work_dir / "solve"
    # If a previous attempt got partway through solving before being
    # interrupted (crash, engine restart), SU2 will have written its own
    # periodic restart file; picking it up here means a retry continues
    # from there instead of losing that work and starting at iteration 0.
    previous_restart = solve_dir / "restart_flow.dat"
    moment_origin = (chord / 2, mid_y, 0.0)
    solver_params = SolverParams(
        mesh_su2_path=mesh_path,
        freestream=FreestreamConditions(
            density=params.density,
            velocity=(vx, 0.0, vz),
            temperature=params.temperature,
            dynamic_viscosity=params.dynamic_viscosity,
        ),
        reference=ReferenceValues(length=chord, area=chord * span, moment_origin=moment_origin),
        max_iterations=params.max_iterations,
        time_discretization=params.time_discretization,
        restart_solution_path=previous_restart if previous_restart.exists() else None,
    )
    try:
        config_text = generate_config(solver_params, solve_dir)
        result = run_su2(
            config_text,
            solve_dir,
            su2_executable=executables.su2,
            mpi_ranks=params.mpi_ranks,
            mpirun_executable=executables.mpirun,
            timeout=solve_timeout,
        )
    except SolverError as exc:
        raise PipelineError("solving", str(exc)) from exc

    convergence = assess_convergence(
        result.history.column(params.residual_column),
        residual_threshold=params.residual_threshold,
    )

    y_plus_values = result.surface.column("Y_Plus")
    mean_y_plus = sum(y_plus_values) / len(y_plus_values)
    max_y_plus = max(y_plus_values)
    final_cl = result.final("CL")
    final_cd = result.final("CD")
    q = dynamic_pressure(params.density, params.velocity)

    return CaseResult(
        chord=chord,
        span=span,
        node_count=mesh_info.node_count,
        element_count=mesh_info.element_count,
        markers=mesh_info.markers,
        cl=final_cl,
        cd=final_cd,
        convergence=convergence,
        history=result.history,
        surface=result.surface,
        mean_y_plus=mean_y_plus,
        max_y_plus=max_y_plus,
        dynamic_pressure=q,
        reynolds_number=reynolds_number(params.density, params.velocity, chord, params.dynamic_viscosity),
        forces=compute_force_system(cl=final_cl, cd=final_cd, dynamic_pressure=q, reference_area=chord * span),
        moments=compute_moment_system(
            cmx=result.final("CMx"),
            cmy=result.final("CMy"),
            cmz=result.final("CMz"),
            dynamic_pressure=q,
            reference_area=chord * span,
            reference_length=chord,
            moment_origin=moment_origin,
        ),
        mesh_path=mesh_path,
        solve_dir=solve_dir,
    )
