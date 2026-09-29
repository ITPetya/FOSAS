import pytest

from fosas_core.quality import assess_convergence


def test_rejects_empty_history():
    with pytest.raises(ValueError):
        assess_convergence(())


def test_converged_case():
    history = tuple(-1.0 - 0.5 * i for i in range(20))  # reaches -10.5
    result = assess_convergence(history, residual_threshold=-8.0, plateau_window=5)
    assert result.converged is True
    assert result.final_residual == pytest.approx(-10.5)
    assert "konvergiert" in result.message


def test_plateaued_case_matches_the_r10_pattern():
    # Same shape as the real Phase 1 spike history: fast initial drop,
    # then a flat plateau far from the -8 target (see docs/RISKS.md R10).
    dropping = [-0.5 - 0.3 * i for i in range(10)]  # down to about -3.2
    plateau = [-3.4 + 0.001 * (i % 3) for i in range(150)]  # tiny wobble, no real progress
    history = tuple(dropping + plateau)
    result = assess_convergence(history, residual_threshold=-8.0, plateau_window=100)
    assert result.converged is False
    assert result.is_plateaued is True
    assert "Plateau" in result.message


def test_still_converging_case_is_not_flagged_as_plateaued():
    history = tuple(-0.1 * i for i in range(50))  # steadily falling, not yet at -8
    result = assess_convergence(history, residual_threshold=-8.0, plateau_window=20)
    assert result.converged is False
    assert result.is_plateaued is False
    assert "koennten helfen" in result.message


def test_single_point_history_is_not_falsely_plateaued():
    result = assess_convergence((-1.0,), residual_threshold=-8.0)
    assert result.converged is False
    assert result.is_plateaued is False
