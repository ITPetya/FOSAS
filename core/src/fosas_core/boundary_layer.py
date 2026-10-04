"""Boundary layer sizing helpers.

Provides a first-cell-height estimate for a target y+ value, based on the
flat-plate turbulent skin friction correlation Cf = 0.026 * Re_L^(-1/7).
This is a standard engineering approximation used by common CFD
preprocessing tools to get a meshing starting point; it is not a
substitute for checking the actual y+ after solving (the true wall shear
stress depends on the real 3D flow, not a flat plate).
"""

from __future__ import annotations

import math


def reynolds_number(
    density: float, velocity: float, reference_length: float, dynamic_viscosity: float
) -> float:
    """Reynolds number Re = rho * V * L / mu."""
    if density <= 0:
        raise ValueError("density must be positive (kg/m^3)")
    if reference_length <= 0:
        raise ValueError("reference_length must be positive (m)")
    if dynamic_viscosity <= 0:
        raise ValueError("dynamic_viscosity must be positive (Pa*s)")
    if velocity <= 0:
        raise ValueError("velocity must be positive (m/s)")
    return density * velocity * reference_length / dynamic_viscosity


def flat_plate_skin_friction_coefficient(reynolds: float) -> float:
    """Turbulent flat-plate skin friction estimate, Cf = 0.026 * Re^(-1/7).

    Valid as a rough estimate for Re roughly above 1e5 (fully turbulent
    boundary layer assumed, no transition modelling). Below that the
    correlation is not meaningful and this raises instead of silently
    returning a number that would not represent turbulent flow.
    """
    if reynolds < 1e5:
        raise ValueError(
            f"reynolds={reynolds:.3g} is below the range this turbulent "
            "flat-plate correlation is valid for (roughly >= 1e5). Use a "
            "transition-aware estimate instead, or confirm the flow is "
            "actually turbulent at this Reynolds number."
        )
    return 0.026 * reynolds ** (-1.0 / 7.0)


_LAMINAR_REGIME_REYNOLDS_THRESHOLD = 1e5
_LAMINAR_REGIME_FALLBACK_FACTOR = 1.0 / 1000.0


def first_cell_height(
    density: float,
    velocity: float,
    reference_length: float,
    dynamic_viscosity: float,
    target_y_plus: float = 1.0,
) -> float:
    """Wall-normal height of the first mesh cell to hit target_y_plus.

    Uses the flat-plate turbulent skin friction estimate to get a wall
    shear stress and friction velocity, then inverts the y+ definition
    y+ = y * u_tau * rho / mu for y. This is a preprocessing estimate,
    the actual y+ must still be checked from the converged solution.

    Below the turbulent correlation's own validity floor (Re < 1e5, see
    flat_plate_skin_friction_coefficient), target_y_plus has no physical
    meaning: there is no thin turbulent near-wall layer for a wall-unit
    target to describe (at the low Reynolds numbers this project uses
    for a validation case meant to stay laminar/steady, the viscous
    region around a small body is comparable to the body's own size,
    not a thin boundary layer). Rather than reach for a second
    correlation (e.g. the laminar flat-plate Blasius estimate) that
    would look rigorous but is equally inapplicable in that regime (it
    also assumes a thin attached boundary layer), this returns an
    explicit, clearly-labelled placeholder cell height instead of
    raising, so meshing can still proceed. Callers must not interpret
    the resulting mesh as y+-controlled when this branch is used.
    """
    if target_y_plus <= 0:
        raise ValueError("target_y_plus must be positive")
    reynolds = reynolds_number(density, velocity, reference_length, dynamic_viscosity)
    if reynolds < _LAMINAR_REGIME_REYNOLDS_THRESHOLD:
        return reference_length * _LAMINAR_REGIME_FALLBACK_FACTOR
    cf = flat_plate_skin_friction_coefficient(reynolds)
    wall_shear_stress = cf * 0.5 * density * velocity**2
    friction_velocity = math.sqrt(wall_shear_stress / density)
    return target_y_plus * dynamic_viscosity / (density * friction_velocity)
