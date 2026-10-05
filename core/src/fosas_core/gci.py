"""Grid Convergence Index (GCI): the three-grid Richardson-extrapolation
procedure for estimating discretization uncertainty in CFD results, per
Roache 1994 (ASME J. Fluids Eng. 116, pp. 405-413) as refined by Celik,
Ghia, Roache, Freitas, Coleman, Raad 2008 ("Procedure for Estimation and
Reporting of Uncertainty Due to Discretization in CFD Applications",
ASME J. Fluids Eng. 130(7), 078001), the paper the ASME V&V 20 committee
adopted. Formulas cross-checked against a second, independent source
(NASA's own GCI tutorial, grc.nasa.gov/www/wind/valid/tutorial/spatconv.html),
both agreeing on the formulas implemented here.

Precondition this module does not and cannot check itself: the three
GridLevel values being compared must come from runs on the SAME
underlying domain/geometry, differing only in element density (not
domain size), so that the mesh-size ratio can be computed exactly from
element counts alone (r = (N_coarse/N_fine)^(1/3) for a fixed-volume
domain), without needing a separately tracked domain-volume field. See
docs/DECISIONS.md ADR-0017 for how Phase 2's GCI study constructs its
three levels this way (varying only
CaseParams.background_size_min_factor/max_factor).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GridLevel:
    element_count: int
    value: float  # e.g. cl or cd from that resolution's CaseResult

    def __post_init__(self):
        if self.element_count <= 0:
            raise ValueError("element_count must be positive")


@dataclass(frozen=True)
class GciResult:
    r21: float
    apparent_order_p: float
    extrapolated_value: float
    approximate_relative_error: float
    gci_fine_percent: float
    oscillatory: bool
    message: str


def _mesh_size_ratio(coarser: GridLevel, finer: GridLevel) -> float:
    """r = h_coarser / h_finer (always >= 1, coarser grids have bigger
    cells), computed from element counts alone via h ~ (1/N)^(1/3) for
    a fixed-volume domain (see module docstring): h_coarser/h_finer =
    (1/N_coarser)^(1/3) / (1/N_finer)^(1/3) = (N_finer/N_coarser)^(1/3).
    Confirmed the hard way: an earlier version of this had the ratio
    inverted (coarser/finer instead of finer/coarser), which produced a
    ratio < 1 and, propagated through _solve_apparent_order, a
    nonsensical negative apparent order from an otherwise-correct
    synthetic test case.
    """
    return (finer.element_count / coarser.element_count) ** (1.0 / 3.0)


def _solve_apparent_order(r21: float, r32: float, e21: float, e32: float) -> float:
    """Apparent order of convergence p, per Celik et al. 2008 eq. 3-5 /
    the equivalent NASA tutorial formula. For the general case (possibly
    r21 != r32), p is defined implicitly and found by fixed-point
    iteration starting from the q=0 initial guess; this collapses to the
    closed form p = ln|e32/e21| / ln(r21) exactly when r21 == r32 (the
    case Phase 2's GCI study actually produces), confirmed by
    test_gci.py's cross-check between the two code paths.
    """
    s = 1.0 if (e32 / e21) > 0 else -1.0
    ratio = abs(e32 / e21)
    # Initial guess uses q=0 (Celik et al.'s own starting point): the
    # formula's absolute-value bars are explicit in the literature,
    # not optional, since the apparent order p is always reported as a
    # positive magnitude even when ln(ratio) itself is negative (e.g.
    # super-convergent or noisy data where ratio < 1).
    p = abs(math.log(ratio)) / math.log(r21)
    for _ in range(100):
        q = math.log((r21**p - s) / (r32**p - s)) if r32 != r21 else 0.0
        new_p = abs(math.log(ratio) + q) / math.log(r21)
        if math.isclose(new_p, p, rel_tol=1e-12, abs_tol=1e-12):
            p = new_p
            break
        p = new_p
    return p


def compute_gci(fine: GridLevel, medium: GridLevel, coarse: GridLevel, safety_factor: float = 1.25) -> GciResult:
    """Three-grid GCI for the fine grid. `safety_factor=1.25` is Celik et
    al.'s recommended value for a 3-grid study with a calculated
    apparent order p (NOT Roache's older Fs=3.0, which applies to a
    2-grid study with an assumed p - using 3.0 here would be wrong).
    """
    if not (fine.element_count > medium.element_count > coarse.element_count):
        raise ValueError(
            "fine/medium/coarse must have strictly decreasing element_count "
            f"(got fine={fine.element_count}, medium={medium.element_count}, coarse={coarse.element_count})"
        )

    r21 = _mesh_size_ratio(medium, fine)
    r32 = _mesh_size_ratio(coarse, medium)
    e21 = medium.value - fine.value
    e32 = coarse.value - medium.value

    if e21 == 0:
        raise ValueError("fine and medium grid values are identical; cannot estimate a convergence order from this")

    oscillatory = (e32 / e21) < 0 if e32 != 0 else False
    p = _solve_apparent_order(r21, r32, e21, e32)

    extrapolated_value = (r21**p * fine.value - medium.value) / (r21**p - 1)
    approximate_relative_error = abs(e21 / fine.value) if fine.value != 0 else abs(e21)
    gci_fine_percent = safety_factor * approximate_relative_error / (r21**p - 1) * 100

    if oscillatory:
        message = (
            f"Oszillierende Konvergenz (e32/e21 < 0): die scheinbare Ordnung p={p:.3g} und die "
            "daraus abgeleitete GCI sind unter diesen Umstaenden kein verlaessliches Mass fuer den "
            "Diskretisierungsfehler, siehe Celik et al. 2008."
        )
    else:
        message = (
            f"Scheinbare Konvergenzordnung p={p:.3g}, extrapolierter Wert {extrapolated_value:.6g}, "
            f"GCI (feines Netz) {gci_fine_percent:.3g}%."
        )

    return GciResult(
        r21=r21,
        apparent_order_p=p,
        extrapolated_value=extrapolated_value,
        approximate_relative_error=approximate_relative_error,
        gci_fine_percent=gci_fine_percent,
        oscillatory=oscillatory,
        message=message,
    )
