"""Bearing/attachment-point reaction force and moment (point 7 of the
"Technische-Mechanik-Visualisierung" requirement, docs/ARCHITECTURE.md).

A pure rigid-body statics follow-up on an already-finished CaseResult -
no new Gmsh/SU2 run is needed, since everything this depends on
(forces, moments, center_of_mass, weight) is already computed by
pipeline.run_case. Given a single chosen bearing point, this answers
"what force and moment would a single, fully rigid support at this
point need to provide to hold the body in equilibrium?" - a strong
simplification (one point, fully fixed, not e.g. a hinge that cannot
react moment, not a multi-point/statically-indeterminate system), kept
deliberately narrow for this first version and disclosed as such in
BearingReaction itself rather than silently assumed.

The wind-axis-to-body-axis force directions (drag/lift/side) used here
are the exact same recipe already verified in
clients/web/app.js::buildForcesLayer (orthonormality confirmed there by
dot product) - duplicated here in Python rather than re-derived, so
the physics agrees with what the 3D viewer already draws.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .forces import ForceSystem, MomentSystem


@dataclass(frozen=True)
class BearingReaction:
    bearing_point: tuple[float, float, float]  # m, body axes - echoed back, not recomputed
    reaction_force: tuple[float, float, float]  # N, body axes
    reaction_force_magnitude: float  # N
    reaction_moment: tuple[float, float, float]  # N*m, body axes
    reaction_moment_magnitude: float  # N*m


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (a[0] * s, a[1] * s, a[2] * s)


def _aero_force_body_axes(aoa_deg: float, sideslip_deg: float, forces: ForceSystem) -> tuple[float, float, float]:
    """Wind-axis lift/drag/side -> body-axis force vector, same recipe as
    clients/web/app.js::buildForcesLayer's dragDirBody/liftDirBody/
    sideDirBody (verified orthonormal there). Duplicated here
    deliberately, not imported from JS, since this is a different
    language/layer - keep both in sync if either ever changes.
    """
    aoa_rad = math.radians(aoa_deg)
    beta_rad = math.radians(sideslip_deg)
    cos_a, sin_a = math.cos(aoa_rad), math.sin(aoa_rad)
    cos_b, sin_b = math.cos(beta_rad), math.sin(beta_rad)
    drag_dir = (cos_a * cos_b, sin_b, sin_a * cos_b)
    lift_dir = (-sin_a, 0.0, cos_a)
    side_dir = (-cos_a * sin_b, cos_b, -sin_a * sin_b)
    drag, lift, side = forces.drag, forces.lift, forces.side
    return (
        drag_dir[0] * drag + lift_dir[0] * lift + side_dir[0] * side,
        drag_dir[1] * drag + lift_dir[1] * lift + side_dir[1] * side,
        drag_dir[2] * drag + lift_dir[2] * lift + side_dir[2] * side,
    )


def compute_bearing_reaction(
    aoa_deg: float,
    sideslip_deg: float,
    forces: ForceSystem,
    moments: MomentSystem,
    center_of_mass: tuple[float, float, float],
    weight: float | None,
    bearing_point: tuple[float, float, float],
) -> BearingReaction:
    """Only depends on these 6 values, not the full CaseResult they
    usually come from (e.g. Job.result in fosas_engine) - deliberately
    narrow: decouples this pure-statics calculation from the much
    larger CaseResult shape (which keeps gaining unrelated fields), and
    keeps it trivially testable without constructing a full fake
    CaseResult.
    """
    aero_force = _aero_force_body_axes(aoa_deg, sideslip_deg, forces)
    # Gravity always acts in body -Z (docs/ARCHITECTURE.md), regardless
    # of AoA/sideslip - None when no material was selected, same "both
    # or neither" rule as CaseResult.weight itself (no silent zero).
    weight_force = (0.0, 0.0, -weight) if weight is not None else (0.0, 0.0, 0.0)

    total_force = _add(aero_force, weight_force)
    reaction_force = _scale(total_force, -1.0)

    moment_origin = moments.moment_origin
    aero_moment_at_origin = (moments.mx, moments.my, moments.mz)
    # Moment transfer: M_about_P = M_about_O + (O - P) x F, for the same
    # force F applied at the same (unknown) point of application -
    # standard rigid-body statics, derived from M_about_X = r_{X->Q} x F
    # for the force's actual application point Q.
    aero_moment_at_point = _add(aero_moment_at_origin, _cross(_sub(moment_origin, bearing_point), aero_force))

    if weight is not None:
        weight_moment_at_point = _cross(_sub(center_of_mass, bearing_point), weight_force)
    else:
        weight_moment_at_point = (0.0, 0.0, 0.0)

    total_moment_at_point = _add(aero_moment_at_point, weight_moment_at_point)
    reaction_moment = _scale(total_moment_at_point, -1.0)

    return BearingReaction(
        bearing_point=bearing_point,
        reaction_force=reaction_force,
        reaction_force_magnitude=math.sqrt(sum(c * c for c in reaction_force)),
        reaction_moment=reaction_moment,
        reaction_moment_magnitude=math.sqrt(sum(c * c for c in reaction_moment)),
    )
