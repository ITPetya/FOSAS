"""Tests for the GCI/Richardson extrapolation module, see
fosas_core.gci's own docstring for the exact formulas and sources
(Celik et al. 2008 / NASA's independent GCI tutorial, cross-checked).
Pure math, no Gmsh/SU2 needed.
"""

import math

import pytest

from fosas_core.gci import GciResult, GridLevel, compute_gci


def _synthetic_levels(f_exact: float, c: float, p: float, h_fine: float, r: float):
    """Three grid levels whose values exactly follow the textbook
    asymptotic error model f(h) = f_exact + C*h^p, so compute_gci must
    recover both p and f_exact (within floating-point tolerance) from
    them. element_count ~ 1/h^3 (3D, fixed-volume domain, see module
    docstring), so h_fine corresponds to the largest element_count.
    """
    h_medium = h_fine * r
    h_coarse = h_medium * r

    def level(h: float) -> GridLevel:
        value = f_exact + c * h**p
        element_count = round(1.0 / h**3)
        return GridLevel(element_count=element_count, value=value)

    return level(h_fine), level(h_medium), level(h_coarse)


def test_compute_gci_recovers_known_order_and_extrapolated_value():
    f_exact, c, true_p = 10.0, 2.0, 1.5
    fine, medium, coarse = _synthetic_levels(f_exact, c, true_p, h_fine=0.01, r=1.5)

    result = compute_gci(fine, medium, coarse)

    assert result.apparent_order_p == pytest.approx(true_p, rel=1e-3)
    assert result.extrapolated_value == pytest.approx(f_exact, rel=1e-3)
    assert result.oscillatory is False
    assert result.gci_fine_percent > 0


def test_compute_gci_recovers_known_order_for_first_order_convergence():
    # A second, independent (p, r) combination, so the recovery is not
    # just coincidentally right for one specific exponent.
    f_exact, c, true_p = -3.5, 0.8, 1.0
    fine, medium, coarse = _synthetic_levels(f_exact, c, true_p, h_fine=0.02, r=1.3)

    result = compute_gci(fine, medium, coarse)

    assert result.apparent_order_p == pytest.approx(true_p, rel=1e-3)
    assert result.extrapolated_value == pytest.approx(f_exact, rel=1e-3)


def test_compute_gci_flags_oscillatory_convergence():
    # e21 and e32 with opposite signs: the value overshoots and comes
    # back, not a monotonic approach to a limit.
    fine = GridLevel(element_count=8_000_000, value=1.0)
    medium = GridLevel(element_count=1_000_000, value=1.2)
    coarse = GridLevel(element_count=125_000, value=1.1)

    result = compute_gci(fine, medium, coarse)

    assert result.oscillatory is True
    assert "Oszillier" in result.message


def test_compute_gci_constant_ratio_matches_closed_form_order():
    # When r21 == r32 (Phase 2's GCI study always produces this, see
    # ADR-0017: a fixed refinement_ratio applied twice), the general
    # iterative formula must agree with the simple closed form
    # p = ln|e32/e21| / ln(r). element_counts are chosen so r21 and r32
    # both come out to exactly 1.5 (27e6 -> 8e6 -> 2_370_370 is three
    # steps of /1.5**3, confirmed numerically), not just "plausible"
    # numbers that happen to have different ratios.
    fine = GridLevel(element_count=27_000_000, value=5.0)
    medium = GridLevel(element_count=8_000_000, value=5.3)
    coarse = GridLevel(element_count=2_370_370, value=6.1)

    result = compute_gci(fine, medium, coarse)

    r = (fine.element_count / medium.element_count) ** (1.0 / 3.0)
    e21 = medium.value - fine.value
    e32 = coarse.value - medium.value
    closed_form_p = math.log(abs(e32 / e21)) / math.log(r)

    assert result.apparent_order_p == pytest.approx(closed_form_p, rel=1e-6)


def test_compute_gci_rejects_non_decreasing_element_counts():
    fine = GridLevel(element_count=1000, value=1.0)
    medium = GridLevel(element_count=2000, value=1.1)  # wrong order: must be < fine
    coarse = GridLevel(element_count=500, value=1.2)
    with pytest.raises(ValueError):
        compute_gci(fine, medium, coarse)


def test_grid_level_rejects_non_positive_element_count():
    with pytest.raises(ValueError):
        GridLevel(element_count=0, value=1.0)
