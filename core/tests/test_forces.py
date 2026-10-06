import math

import pytest

from fosas_core.forces import compute_force_system, compute_moment_system, rescale_coefficient_to_frontal_area


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


def test_moment_system_scales_coefficients_by_q_a_l():
    # cmy=0.5, q=100 Pa, A=2 m^2, L=0.5 m -> My = 0.5*100*2*0.5 = 50 Nm
    result = compute_moment_system(
        cmx=0.0, cmy=0.5, cmz=-0.2,
        dynamic_pressure=100.0, reference_area=2.0, reference_length=0.5,
        moment_origin=(0.25, 1.0, 0.0),
    )
    assert result.mx == pytest.approx(0.0)
    assert result.my == pytest.approx(50.0)
    assert result.mz == pytest.approx(-20.0)
    assert result.moment_origin == (0.25, 1.0, 0.0)


def test_moment_system_rejects_non_positive_reference_length():
    with pytest.raises(ValueError):
        compute_moment_system(
            cmx=0.0, cmy=0.0, cmz=0.0,
            dynamic_pressure=10.0, reference_area=1.0, reference_length=0.0,
            moment_origin=(0.0, 0.0, 0.0),
        )


def test_rescale_coefficient_to_frontal_area_same_force_same_coefficient_times_area():
    # The underlying force F = c_planform * q * A_planform must equal
    # c_frontal * q * A_frontal for the same F: check that identity
    # directly, not just the rescaling formula in isolation.
    cd_planform, planform_area, frontal_area = 0.02, 0.6, 0.05
    cd_frontal = rescale_coefficient_to_frontal_area(cd_planform, planform_area, frontal_area)
    assert cd_frontal == pytest.approx(cd_planform * planform_area / frontal_area)
    q = 100.0
    assert cd_planform * q * planform_area == pytest.approx(cd_frontal * q * frontal_area)


def test_rescale_coefficient_to_frontal_area_returns_none_for_near_zero_area():
    # A true flat plate (no meaningful thickness): frontal-area
    # coefficient would blow up to +/-infinity, must be None, not a
    # silently huge or infinite number.
    assert rescale_coefficient_to_frontal_area(1.0, planform_area=1.0, frontal_area=0.0) is None
    assert rescale_coefficient_to_frontal_area(1.0, planform_area=1.0, frontal_area=1e-12) is None


def test_rescale_coefficient_to_frontal_area_handles_negative_coefficient():
    result = rescale_coefficient_to_frontal_area(-0.5, planform_area=2.0, frontal_area=1.0)
    assert result == pytest.approx(-1.0)
