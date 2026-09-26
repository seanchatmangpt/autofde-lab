"""Two-sample log-rank survival court tests."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival_logrank import logrank_survival_test


def episode(
    episode_id: str,
    policy_id: str,
    *,
    failure_step: int | None,
    subject: str = "subject",
) -> dict:
    events = [{"step": 1, "phase": "OBSERVE"}]
    if failure_step is None:
        events.append(
            {
                "step": 3,
                "phase": "DO",
                "authorized": True,
                "receipt_id": f"receipt:{episode_id}",
            }
        )
    else:
        events.append(
            {
                "step": failure_step,
                "phase": "DO",
                "authorized": False,
                "receipt_id": f"receipt:{episode_id}",
            }
        )
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": subject,
        "workload_id": "workload",
        "policy_id": policy_id,
        "episode_id": episode_id,
        "horizon": 3,
        "events": events,
    }


def test_logrank_detects_separated_failure_times_with_known_statistic() -> None:
    left = [
        episode("l1", "left", failure_step=1),
        episode("l2", "left", failure_step=1),
    ]
    right = [
        episode("r1", "right", failure_step=None),
        episode("r2", "right", failure_step=None),
    ]

    report = logrank_survival_test(left, right)

    assert report["left_observed_minus_expected"] == pytest.approx(1.0)
    assert report["variance"] == pytest.approx(1 / 3)
    assert report["chi_square_1df"] == pytest.approx(3.0)
    assert report["p_value"] == pytest.approx(0.0832645167)
    assert report["left_failures"] == 2
    assert report["right_failures"] == 0


def test_identical_failure_allocation_has_zero_logrank_statistic() -> None:
    left = [
        episode("l1", "left", failure_step=2),
        episode("l2", "left", failure_step=None),
    ]
    right = [
        episode("r1", "right", failure_step=2),
        episode("r2", "right", failure_step=None),
    ]

    report = logrank_survival_test(left, right)

    assert report["left_observed_minus_expected"] == pytest.approx(0.0)
    assert report["chi_square_1df"] == pytest.approx(0.0)
    assert report["p_value"] == pytest.approx(1.0)


def test_logrank_refuses_same_policy_or_subject_drift() -> None:
    with pytest.raises(IECRefusal, match="SAME_POLICY"):
        logrank_survival_test(
            [episode("a", "same", failure_step=None)],
            [episode("b", "same", failure_step=None)],
        )

    with pytest.raises(IECRefusal, match="EXACT_SUBJECT_MISMATCH"):
        logrank_survival_test(
            [episode("a", "left", failure_step=None)],
            [episode("b", "right", failure_step=None, subject="other")],
        )


def test_logrank_refuses_policy_drift_within_input_stratum() -> None:
    with pytest.raises(IECRefusal, match="REFUSED_POLICY_MISMATCH"):
        logrank_survival_test(
            [
                episode("a", "left", failure_step=None),
                episode("b", "drift", failure_step=None),
            ],
            [episode("c", "right", failure_step=None)],
        )
