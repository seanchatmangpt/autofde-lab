import pytest

from autofde_lab.ptd.metrics import (
    generative_leverage,
    knowledge_depreciation,
    knowledge_retention,
    ptd_advantage,
    ptd_efficiency,
    regeneration_advantage,
    strong_phase_regime,
)


def test_cross_phase_retention_uses_fresh_phase_baseline() -> None:
    assert knowledge_retention(0.2, 0.8) == pytest.approx(0.25)
    assert knowledge_depreciation(0.2, 0.8) == pytest.approx(0.75)


def test_retention_is_not_clamped_when_prior_knowledge_is_more_useful() -> None:
    assert knowledge_retention(0.9, 0.6) == pytest.approx(1.5)
    assert knowledge_depreciation(0.9, 0.6) == pytest.approx(-0.5)


def test_zero_fresh_phase_baseline_is_not_a_defined_ratio() -> None:
    with pytest.raises(ValueError, match="fresh_phase_performance"):
        knowledge_retention(0.0, 0.0)


def test_economic_metrics() -> None:
    assert regeneration_advantage(50.0, 5.0) == pytest.approx(10.0)
    assert generative_leverage(100.0, 5.0) == pytest.approx(20.0)
    assert ptd_efficiency(0.75, 5.0) == pytest.approx(0.15)
    assert ptd_advantage(0.75, 50.0, 5.0) == pytest.approx(7.5)


def test_strong_phase_regime_is_strict() -> None:
    assert strong_phase_regime(11.0, 10.0)
    assert not strong_phase_regime(10.0, 10.0)
