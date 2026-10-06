"""Aerodynamic force decomposition in wind axes.

CL and CD, as read from the solver (see pipeline.run_case), are already
wind-axis coefficients: lift perpendicular to the freestream, drag
parallel to it, independent of angle of attack (SU2 computes them that
way directly). This module turns those two dimensionless coefficients
plus the already-known dynamic pressure and reference area into actual
forces in Newtons, the standard mechanical-engineering form F = c * q * A
(see docs/ARCHITECTURE.md, "Technische-Mechanik-Visualisierung").

Deliberately narrow first slice: only the resultant force system (lift,
drag, resultant magnitude, glide ratio, resultant angle), not yet the
full body-axis/moment system (Mx/My/Mz, moment reference point), which
needs data fosas_core does not read from the solver yet, see the same
ARCHITECTURE.md section for what is still missing.
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
