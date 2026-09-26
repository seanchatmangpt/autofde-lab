from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival_compare import cohort_report

SUBJECT = "git:survival/example@0123456789abcdef"
WORKLOAD = "sha256:cohort"


def episode(episode_id: str, policy: str, fail_step: int | None) -> dict:
    events = [{"step": 1, "phase": "OBSERVE"}]
    if fail_step is None:
        events.append(
            {
                "step": 4,
                "phase": "DO",
                "receipt_id": f"receipt:{episode_id}",
                "terminal_ready": True,
            }
        )
    else:
        events.append(
            {
                "step": fail_step,
                "phase": "DO",
                "receipt_id": f"receipt:{episode_id}",
                "terminal_ready": False,
                "tool_invoked": policy == "tool",
                "llm_tokens": 10 if policy == "llm" else 0,
            }
        )
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": SUBJECT,
        "workload_id": WORKLOAD,
        "policy_id": policy,
        "episode_id": episode_id,
        "horizon": 4,
        "events": events,
    }


def test_cohort_preserves_single_policy_courts_and_pairwise_deltas() -> None:
    report = cohort_report(
        [
            episode("llm-1", "llm", 2),
            episode("llm-2", "llm", 2),
            episode("formal-1", "formal", None),
            episode("formal-2", "formal", None),
        ]
    )

    assert report["policy_count"] == 2
    assert report["episodes"] == 4
    assert set(report["policies"]) == {"formal", "llm"}
    comparison = report["pairwise"][0]
    assert comparison["left_policy_id"] == "formal"
    assert comparison["right_policy_id"] == "llm"
    assert comparison["delta"]["failure_probability_observed"] == 1.0
    assert comparison["delta"]["rmst_steps"] < 0
    assert "causal" in comparison["claim_ceiling"]


def test_cohort_refuses_subject_or_horizon_drift() -> None:
    clean = episode("a", "formal", None)
    other_subject = episode("b", "llm", None)
    other_subject["subject"] = "git:other/repo@sha"
    with pytest.raises(IECRefusal, match="REFUSED_EXACT_SUBJECT_MISMATCH"):
        cohort_report([clean, other_subject])

    other_horizon = episode("c", "llm", None)
    other_horizon["horizon"] = 5
    with pytest.raises(IECRefusal, match="REFUSED_HORIZON_MISMATCH"):
        cohort_report([clean, other_horizon])
