import math

import pytest

from fosas_core.boundary_layer import (
    first_cell_height,
    flat_plate_skin_friction_coefficient,
    reynolds_number,
)


def test_reynolds_number_matches_known_case():
    # NACA0012 Phase 1 spike case: chord 0.6 m, air properties from the
    # SU2 Inc_Turbulent_NACA0012 tutorial, tuned to hit Re=6e6.
    re = reynolds_number(
        density=2.13163, velocity=86.933, reference_length=0.6, dynamic_viscosity=1.853e-5
    )
    assert re == pytest.approx(6.0e6, rel=1e-3)


@pytest.mark.parametrize(
    "field,value",
    [("density", -1.0), ("reference_length", 0.0), ("dynamic_viscosity", -1e-5), ("velocity", 0.0)],
)
def test_reynolds_number_rejects_invalid_input(field, value):
    kwargs = dict(density=1.2, velocity=10.0, reference_length=1.0, dynamic_viscosity=1.8e-5)
    kwargs[field] = value
    with pytest.raises(ValueError):
        reynolds_number(**kwargs)


def test_skin_friction_decreases_with_reynolds():
    cf_low = flat_plate_skin_friction_coefficient(1e6)
    cf_high = flat_plate_skin_friction_coefficient(1e8)
    assert cf_high < cf_low


def test_skin_friction_rejects_low_reynolds():
    with pytest.raises(ValueError):
        flat_plate_skin_friction_coefficient(1e3)


def test_first_cell_height_naca0012_case_is_far_below_spike_test_value():
    # This is the concrete, tested confirmation of the R10 hypothesis:
    # the spike's guessed first cell height (0.0003 m) was about two
    # orders of magnitude too coarse for y+=1 at this Reynolds number.
    y1 = first_cell_height(
        density=2.13163,
        velocity=86.933,
        reference_length=0.6,
        dynamic_viscosity=1.853e-5,
        target_y_plus=1.0,
    )
    assert y1 == pytest.approx(2.67e-6, rel=0.05)
    spike_test_value = 0.0003
    assert spike_test_value / y1 > 50


def test_first_cell_height_scales_linearly_with_target_y_plus():
    y1 = first_cell_height(density=1.2, velocity=50.0, reference_length=1.0, dynamic_viscosity=1.8e-5, target_y_plus=1.0)
    y30 = first_cell_height(density=1.2, velocity=50.0, reference_length=1.0, dynamic_viscosity=1.8e-5, target_y_plus=30.0)
    assert y30 == pytest.approx(30 * y1)


def test_first_cell_height_rejects_non_positive_target_y_plus():
    with pytest.raises(ValueError):
        first_cell_height(density=1.2, velocity=50.0, reference_length=1.0, dynamic_viscosity=1.8e-5, target_y_plus=0)
