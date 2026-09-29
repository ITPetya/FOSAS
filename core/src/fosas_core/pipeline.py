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

from .boundary_layer import first_cell_height
from .geometry import GeometryError, import_step
from .meshing import (
    BoundaryLayerMeshParams,
    ConstantSectionMeshParams,
    MeshingError,
    generate_constant_section_geo,
    run_gmsh,
)
from .quality import ConvergenceAssessment, assess_convergence
from .solver import (
    FreestreamConditions,
    ReferenceValues,
    SolverError,
    SolverParams,
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

    def __post_init__(self):
        if self.velocity <= 0:
            raise ValueError("velocity must be positive")
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")


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
    mesh_path: Path
    solve_dir: Path


def _sample_wire_points(wire) -> tuple[tuple[float, float], ...]:
    edges = wire.edges()
    points = []
    for edge in edges:
        n = 40
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
    if chord <= 0 or span <= 0:
        raise PipelineError(
            "geometry",
            f"Bounding box gives chord={chord:.4g}, span={span:.4g}. FOSAS V1 "
            "assumes the geometry already uses X chordwise, Y spanwise, Z "
            "vertical (see docs/ARCHITECTURE.md); check the input orientation.",
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

    profile_points = _sample_wire_points(section[0].outer_wire())

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
    )
    mesh_path = work_dir / "mesh.su2"
    try:
        geo = generate_constant_section_geo(mesh_params, mesh_path)
        mesh_info = run_gmsh(geo, mesh_path, gmsh_executable=executables.gmsh, timeout=mesh_timeout)
    except MeshingError as exc:
        raise PipelineError("meshing", str(exc)) from exc

    vx = params.velocity * math.cos(math.radians(params.aoa_deg))
    vz = params.velocity * math.sin(math.radians(params.aoa_deg))
    solver_params = SolverParams(
        mesh_su2_path=mesh_path,
        freestream=FreestreamConditions(
            density=params.density,
            velocity=(vx, 0.0, vz),
            temperature=params.temperature,
            dynamic_viscosity=params.dynamic_viscosity,
        ),
        reference=ReferenceValues(length=chord, area=chord * span, moment_origin=(chord / 2, mid_y, 0.0)),
        max_iterations=params.max_iterations,
        time_discretization=params.time_discretization,
    )
    solve_dir = work_dir / "solve"
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

    return CaseResult(
        chord=chord,
        span=span,
        node_count=mesh_info.node_count,
        element_count=mesh_info.element_count,
        markers=mesh_info.markers,
        cl=result.final("CL"),
        cd=result.final("CD"),
        convergence=convergence,
        mesh_path=mesh_path,
        solve_dir=solve_dir,
    )
