"""Finite-sample survival uncertainty tests."""

from __future__ import annotations

import math

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival_uncertainty import survival_uncertainty_report


def episode(episode_id: str, *, failure_step: int | None) -> dict:
    events = [{"step": 1, "phase": "OBSERVE"}]
    if failure_step is None:
        events.append(
            {
                "step": 3,
                "phase": "DO",
                "authorized": True,
                "admitted": True,
                "receipt_id": f"receipt:{episode_id}",
                "terminal_ready": True,
            }
        )
    else:
        events.append(
            {
                "step": failure_step,
                "phase": "DO",
                "authorized": False,
                "admitted": True,
                "receipt_id": f"receipt:{episode_id}",
                "terminal_ready": True,
            }
        )
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "subject",
        "workload_id": "workload",
        "policy_id": "policy",
        "episode_id": episode_id,
        "horizon": 3,
        "events": events,
    }


def test_greenwood_variance_tracks_discrete_km_risk_set() -> None:
    report = survival_uncertainty_report(
        [
            episode("failed", failure_step=2),
            episode("censored", failure_step=None),
        ]
    )

    step2 = report["survival_curve"][1]
    assert step2["at_risk"] == 2
    assert step2["failures"] == 1
    assert step2["survival"] == pytest.approx(0.5)
    assert step2["greenwood_sum"] == pytest.approx(0.5)
    assert step2["survival_variance"] == pytest.approx(0.125)
    assert step2["survival_standard_error"] == pytest.approx(math.sqrt(0.125))
    assert 0.0 <= step2["confidence_lower"] < 0.5
    assert 0.5 < step2["confidence_upper"] <= 1.0


def test_all_survive_has_exact_km_band_but_nonzero_wilson_uncertainty() -> None:
    report = survival_uncertainty_report(
        [
            episode("a", failure_step=None),
            episode("b", failure_step=None),
            episode("c", failure_step=None),
        ]
    )

    assert all(point["confidence_lower"] == 1.0 for point in report["survival_curve"])
    assert all(point["confidence_upper"] == 1.0 for point in report["survival_curve"])
    assert report["failure_probability_observed"] == 0.0
    assert report["failure_probability_wilson"]["lower"] == pytest.approx(0.0)
    assert report["failure_probability_wilson"]["upper"] > 0.0


def test_terminal_failure_has_zero_survival_interval() -> None:
    report = survival_uncertainty_report(
        [
            episode("a", failure_step=2),
            episode("b", failure_step=2),
        ]
    )

    step2 = report["survival_curve"][1]
    assert step2["survival"] == 0.0
    assert step2["confidence_lower"] == 0.0
    assert step2["confidence_upper"] == 0.0


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.1, 1.1])
def test_invalid_confidence_is_typed_refusal(confidence: float) -> None:
    with pytest.raises(IECRefusal, match="REFUSED_SURVIVAL_CONFIDENCE"):
        survival_uncertainty_report(
            [episode("a", failure_step=None)],
            confidence=confidence,
        )
