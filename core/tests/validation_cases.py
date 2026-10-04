"""Bundled geometry + reference-condition definitions for Phase 2's
validation cases, so the same single source of truth can be reused by
a one-off verification run, the regression test suite, and later
engine-level polar/GCI tests (see docs/DECISIONS.md ADR-0017). Not part
of the shipped fosas_core package, same convention as fixtures.py/airfoils.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from fosas_core.pipeline import CaseParams


@dataclass(frozen=True)
class CylinderCase:
    diameter: float
    span: float
    reynolds_number: float
    params: CaseParams


def _velocity_for_reynolds(reynolds: float, density: float, dynamic_viscosity: float, diameter: float) -> float:
    return reynolds * dynamic_viscosity / (density * diameter)


# Low-Reynolds-number (laminar, steady, attached) circular cylinder: no
# sharp trailing edge (unlike NACA0012, avoids ADR-0007's boundary-layer-
# at-a-sharp-corner complications), and deliberately kept below the
# textbook vortex-shedding onset (roughly Re < 40-47 for a 2D cylinder,
# Annahme: this classification is not re-verified against a primary
# source this session, see docs/DECISIONS.md ADR-0017), so a steady
# solver is not fighting a genuinely unsteady flow (RISKS.md R8).
_DIAMETER = 0.01
_SPAN = 2.0 * _DIAMETER  # satisfies pipeline.run_case's span >= 0.5*chord check
_REYNOLDS = 20.0
_DENSITY = 1.225
_DYNAMIC_VISCOSITY = 1.81e-5

LOW_RE_CYLINDER = CylinderCase(
    diameter=_DIAMETER,
    span=_SPAN,
    reynolds_number=_REYNOLDS,
    params=CaseParams(
        velocity=_velocity_for_reynolds(_REYNOLDS, _DENSITY, _DYNAMIC_VISCOSITY, _DIAMETER),
        aoa_deg=0.0,
        density=_DENSITY,
        dynamic_viscosity=_DYNAMIC_VISCOSITY,
    ),
)
