import math

import pytest

from fosas_core.forces import ForceSystem, MomentSystem
from fosas_core.reactions import _aero_force_body_axes, compute_bearing_reaction


def _forces(lift=0.0, drag=0.0, side=0.0):
    resultant = math.sqrt(lift * lift + drag * drag + side * side)
    return ForceSystem(
        reference_area=1.0, lift=lift, drag=drag, side=side,
        resultant=resultant, glide_ratio=None, resultant_angle_deg=0.0,
    )


def _moments(moment_origin, mx=0.0, my=0.0, mz=0.0):
    return MomentSystem(
        reference_length=1.0, moment_origin=moment_origin,
        cmx=0.0, cmy=0.0, cmz=0.0, mx=mx, my=my, mz=mz,
    )


def test_bearing_at_moment_origin_without_material_matches_the_raw_force_and_moment_system():
    # No lever arm (bearing_point == moment_origin), no weight: the
    # reaction must exactly balance the raw aero force/moment, with no
    # cross-product transfer term to get wrong. At AoA=0, beta=0,
    # drag acts along body +X and lift along body +Z (hand-verified:
    # dragDirBody=(1,0,0), liftDirBody=(0,0,1) for aoa_deg=0).
    moment_origin = (0.3, 0.6, 0.0)
    forces = _forces(lift=10.0, drag=5.0, side=0.0)
    moments = _moments(moment_origin, mx=1.0, my=-2.0, mz=0.5)

    reaction = compute_bearing_reaction(
        aoa_deg=0.0, sideslip_deg=0.0, forces=forces, moments=moments,
        center_of_mass=(0.0, 0.0, 0.0), weight=None, bearing_point=moment_origin,
    )

    assert reaction.reaction_force == pytest.approx((-5.0, 0.0, -10.0))
    assert reaction.reaction_moment == pytest.approx((-1.0, 2.0, -0.5))
    assert reaction.reaction_force_magnitude == pytest.approx(math.hypot(5.0, 10.0))
    assert reaction.reaction_moment_magnitude == pytest.approx(math.hypot(1.0, 2.0, 0.5))


def test_bearing_reaction_applies_the_correct_lever_arm_transfer():
    # Same force as above (AoA=0, beta=0: aero_force=(5,0,10)), but now
    # picked 0.3m away from moment_origin along -X, with the raw moment
    # about moment_origin itself zero (isolates the transfer term).
    # Hand-computed: r = moment_origin - bearing_point = (0.3,0,0),
    # M = r x F = (0.3,0,0) x (5,0,10) = (0*10-0*0, 0*5-0.3*10, 0.3*0-0*5)
    #   = (0, -3, 0), so reaction_moment = -M = (0, 3, 0).
    moment_origin = (0.3, 0.6, 0.0)
    bearing_point = (0.0, 0.6, 0.0)
    forces = _forces(lift=10.0, drag=5.0, side=0.0)
    moments = _moments(moment_origin, mx=0.0, my=0.0, mz=0.0)

    reaction = compute_bearing_reaction(
        aoa_deg=0.0, sideslip_deg=0.0, forces=forces, moments=moments,
        center_of_mass=(0.0, 0.0, 0.0), weight=None, bearing_point=bearing_point,
    )

    assert reaction.reaction_force == pytest.approx((-5.0, 0.0, -10.0))
    assert reaction.reaction_moment == pytest.approx((0.0, 3.0, 0.0), abs=1e-9)


def test_weight_contributes_zero_moment_when_the_bearing_point_is_the_center_of_mass():
    # A force contributes zero moment about a point it passes through -
    # physically, a bearing placed exactly at the center of mass must
    # see no moment contribution from gravity, only from the (separate)
    # aerodynamic moment and the aero force's own lever arm.
    center_of_mass = (0.26, 0.5, 0.001)
    moment_origin = (0.25, 0.5, 0.0)
    forces = _forces(lift=0.0, drag=0.0, side=0.0)  # isolate the weight term entirely
    moments = _moments(moment_origin, mx=0.0, my=0.0, mz=0.0)

    reaction = compute_bearing_reaction(
        aoa_deg=0.0, sideslip_deg=0.0, forces=forces, moments=moments,
        center_of_mass=center_of_mass, weight=2.0, bearing_point=center_of_mass,
    )

    assert reaction.reaction_moment == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    # Weight still shows up in the reaction force itself (gravity acts
    # in body -Z): equilibrium needs +2N in Z to hold the weight up.
    assert reaction.reaction_force == pytest.approx((0.0, 0.0, 2.0))


@pytest.mark.parametrize(
    "aoa_deg,sideslip_deg,lift,drag,side",
    [
        (0.0, 0.0, 10.0, 5.0, 0.0),
        (8.0, 0.0, 12.0, 1.5, 0.0),
        (5.0, 3.0, 9.0, 2.0, 0.7),
        (-4.0, -6.0, 6.0, 1.0, -0.3),
    ],
)
def test_aero_force_vector_magnitude_matches_forces_resultant(aoa_deg, sideslip_deg, lift, drag, side):
    # Regression anchor for the orthonormal drag/lift/side basis
    # (already verified once in clients/web/app.js::buildForcesLayer's
    # own comment via dot products) - re-confirmed here for the Python
    # port: the body-axis force vector's magnitude must equal
    # ForceSystem.resultant = hypot(lift, drag, side) for every
    # AoA/sideslip combination, not just the AoA=0/beta=0 special case.
    forces = _forces(lift=lift, drag=drag, side=side)
    vec = _aero_force_body_axes(aoa_deg, sideslip_deg, forces)
    magnitude = math.sqrt(sum(c * c for c in vec))
    assert magnitude == pytest.approx(forces.resultant)


def test_bearing_reaction_without_material_treats_weight_as_zero_not_missing():
    # weight=None must behave exactly like weight=0 for the force/moment
    # math (no silent crash, no NaN) - the "None means no material"
    # distinction matters for API disclosure, not for this calculation.
    forces = _forces(lift=4.0, drag=1.0, side=0.0)
    moments = _moments((0.1, 0.2, 0.0), mx=0.0, my=0.0, mz=0.0)
    reaction = compute_bearing_reaction(
        aoa_deg=0.0, sideslip_deg=0.0, forces=forces, moments=moments,
        center_of_mass=(0.5, 0.5, 0.5), weight=None, bearing_point=(0.1, 0.2, 0.0),
    )
    assert math.isfinite(reaction.reaction_force_magnitude)
    assert math.isfinite(reaction.reaction_moment_magnitude)
