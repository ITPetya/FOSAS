import math

import pytest

from fosas_core.forces import compute_force_system


def test_lift_and_drag_from_coefficients():
    # cl=1.0, cd=0.1, q=100 Pa, A=2 m^2 -> lift=200 N, drag=20 N
    result = compute_force_system(cl=1.0, cd=0.1, dynamic_pressure=100.0, reference_area=2.0)
    assert result.lift == pytest.approx(200.0)
    assert result.drag == pytest.approx(20.0)
    assert result.resultant == pytest.approx(math.hypot(200.0, 20.0))
    assert result.glide_ratio == pytest.approx(10.0)
    assert result.resultant_angle_deg == pytest.approx(math.degrees(math.atan2(200.0, 20.0)))


def test_zero_drag_gives_none_glide_ratio_not_a_crash():
    result = compute_force_system(cl=1.0, cd=0.0, dynamic_pressure=50.0, reference_area=1.0)
    assert result.glide_ratio is None
    assert result.resultant_angle_deg == pytest.approx(90.0)


def test_negative_lift_handled_via_atan2():
    # A symmetric body at negative AoA: lift can be negative, drag stays positive.
    result = compute_force_system(cl=-0.5, cd=0.2, dynamic_pressure=10.0, reference_area=1.0)
    assert result.lift == pytest.approx(-5.0)
    assert result.drag == pytest.approx(2.0)
    assert result.resultant_angle_deg < 0


def test_rejects_non_positive_reference_area():
    with pytest.raises(ValueError):
        compute_force_system(cl=1.0, cd=0.1, dynamic_pressure=10.0, reference_area=0.0)


def test_rejects_negative_dynamic_pressure():
    with pytest.raises(ValueError):
        compute_force_system(cl=1.0, cd=0.1, dynamic_pressure=-1.0, reference_area=1.0)
