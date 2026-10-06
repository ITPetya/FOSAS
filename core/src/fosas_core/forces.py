"""Aerodynamic force and moment decomposition in mechanical-engineering units.

CL and CD, as read from the solver (see pipeline.run_case), are already
wind-axis coefficients: lift perpendicular to the freestream, drag
parallel to it, independent of angle of attack (SU2 computes them that
way directly, verified against this project's own cylinder test case,
see docs/ARCHITECTURE.md, "Technische-Mechanik-Visualisierung"). This
module turns those plus the already-known dynamic pressure and reference
area/length into actual forces (Newtons) and moments (Newton-metres), the
standard mechanical-engineering form F = c * q * A and M = cm * q * A * L.

CMx/CMy/CMz already come out of SU2's own AERO_COEFF history group
(confirmed by reading the actual history CSV columns, see
ARCHITECTURE.md), about the fixed reference point `solver.ReferenceValues
.moment_origin` (currently always mid-chord/mid-span/Z=0, not yet
user-selectable). Moment-reference-point transfer (the Schwerpunkt/
Ursprung/frei choice from the original requirement) is not implemented
here: it needs the actual geometry position of that choice, which is a
UI/pipeline concern, not something this purely numeric module can do on
its own.

Deliberately narrow: only the resultant force system and the raw moment
system about the solver's existing fixed reference point, not yet
center-of-pressure markers or body-axis (Fx/Fy/Fz, needs a sideslip
angle this project does not model yet) decomposition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ForceSystem:
    reference_area: float
    lift: float
    drag: float
    resultant: float
    # None when drag is exactly zero (glide ratio undefined), not a
    # silently wrong number: a real body always has some drag, this
    # only happens for a synthetic/degenerate test input.
    glide_ratio: float | None
    # Angle between the resultant and the drag (freestream) direction,
    # degrees. atan2, not atan(lift/drag): stays correct (and finite)
    # even if drag is zero or either component is negative.
    resultant_angle_deg: float


@dataclass(frozen=True)
class MomentSystem:
    reference_length: float
    moment_origin: tuple[float, float, float]
    # Raw coefficients kept alongside the scaled values (not just
    # derivable by dividing mx/my/mz back out) so a "show your work"
    # display (M = cm * q * A * L) can show the actual coefficient that
    # was substituted, not a value reconstructed by inverting the scale
    # factor.
    cmx: float
    cmy: float
    cmz: float
    mx: float
    my: float
    mz: float


def compute_moment_system(
    cmx: float,
    cmy: float,
    cmz: float,
    dynamic_pressure: float,
    reference_area: float,
    reference_length: float,
    moment_origin: tuple[float, float, float],
) -> MomentSystem:
    if dynamic_pressure < 0:
        raise ValueError("dynamic_pressure must not be negative (Pa)")
    if reference_area <= 0:
        raise ValueError("reference_area must be positive (m^2)")
    if reference_length <= 0:
        raise ValueError("reference_length must be positive (m)")
    scale = dynamic_pressure * reference_area * reference_length
    return MomentSystem(
        reference_length=reference_length,
        moment_origin=moment_origin,
        cmx=cmx,
        cmy=cmy,
        cmz=cmz,
        mx=cmx * scale,
        my=cmy * scale,
        mz=cmz * scale,
    )


def compute_force_system(cl: float, cd: float, dynamic_pressure: float, reference_area: float) -> ForceSystem:
    if dynamic_pressure < 0:
        raise ValueError("dynamic_pressure must not be negative (Pa)")
    if reference_area <= 0:
        raise ValueError("reference_area must be positive (m^2)")
    lift = cl * dynamic_pressure * reference_area
    drag = cd * dynamic_pressure * reference_area
    resultant = math.hypot(lift, drag)
    glide_ratio = lift / drag if drag != 0 else None
    resultant_angle_deg = math.degrees(math.atan2(lift, drag))
    return ForceSystem(
        reference_area=reference_area,
        lift=lift,
        drag=drag,
        resultant=resultant,
        glide_ratio=glide_ratio,
        resultant_angle_deg=resultant_angle_deg,
    )
