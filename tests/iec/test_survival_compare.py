"""Cross-policy survival comparison falsifiers."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival import EPISODE_SCHEMA
from autofde_lab.iec.crowns.survival_compare import (
    compare_survival_policies,
    observed_pareto_frontier,
    PolicyMetrics,
)

SUBJECT = "git:seanchatmangpt/autofde-lab@0123456789abcdef"
WORKLOAD = "sha256:comparison-workload"


def episode(
    episode_id: str,
    policy_id: str,
    events: list[dict],
    *,
    horizon: int = 4,
    subject: str = SUBJECT,
    workload_id: str = WORKLOAD,
) -> dict:
    return {
        "schema": EPISODE_SCHEMA,
        "subject": subject,
        "workload_id": workload_id,
        "policy_id": policy_id,
        "episode_id": episode_id,
        "horizon": horizon,
        "events": events,
    }


def clean_do(step: int = 4, *, llm_tokens: int = 0) -> list[dict]:
    return [
        {"step": 1, "phase": "OBSERVE", "llm_tokens": llm_tokens},
        {
            "step": step,
            "phase": "DO",
            "authorized": True,
            "admitted": True,
            "receipt_id": f"receipt:{step}",
            "replay_verified": True,
            "terminal_ready": True,
        },
    ]


def failed_do(step: int = 2, *, llm_tokens: int = 10) -> list[dict]:
    return [
        {"step": 1, "phase": "OBSERVE", "llm_tokens": llm_tokens},
        {
            "step": step,
            "phase": "DO",
            "authorized": False,
            "admitted": True,
            "receipt_id": f"receipt:{step}",
            "replay_verified": True,
            "terminal_ready": True,
        },
    ]


def test_comparison_keeps_policy_strata_separate_and_reports_observed_deltas() -> None:
    report = compare_survival_policies(
        {
            "formal": [
                episode("formal-1", "formal", clean_do()),
                episode("formal-2", "formal", clean_do()),
            ],
            "llm": [
                episode("llm-1", "llm", failed_do()),
                episode("llm-2", "llm", clean_do(llm_tokens=20)),
            ],
        }
    )

    rows = {row["policy_id"]: row for row in report["policies"]}
    assert rows["formal"]["failures"] == 0
    assert rows["formal"]["terminal_survival"] == 1.0
    assert rows["formal"]["receipt_coverage"] == 1.0
    assert rows["formal"]["replay_coverage"] == 1.0
    assert rows["formal"]["llm_dependency_fraction"] == 0.0

    assert rows["llm"]["failures"] == 1
    assert rows["llm"]["terminal_survival"] == pytest.approx(0.5)
    assert rows["llm"]["llm_dependency_fraction"] == pytest.approx(0.5)

    pair = report["pairwise"][0]
    assert {pair["left_policy_id"], pair["right_policy_id"]} == {"formal", "llm"}
    assert pair["left_observed_dominates_right"] is True
    assert pair["right_observed_dominates_left"] is False
    assert report["observed_pareto_frontier"] == ["formal"]


def test_comparison_refuses_subject_workload_or_horizon_drift() -> None:
    base = episode("a", "formal", clean_do())

    with pytest.raises(IECRefusal, match="REFUSED_EXACT_SUBJECT_MISMATCH"):
        compare_survival_policies(
            {
                "formal": [base],
                "llm": [
                    episode(
                        "b",
                        "llm",
                        clean_do(),
                        subject="git:other/repo@deadbeef",
                    )
                ],
            }
        )

    with pytest.raises(IECRefusal, match="REFUSED_WORKLOAD_MISMATCH"):
        compare_survival_policies(
            {
                "formal": [base],
                "llm": [
                    episode(
                        "b",
                        "llm",
                        clean_do(),
                        workload_id="sha256:other-workload",
                    )
                ],
            }
        )

    with pytest.raises(IECRefusal, match="REFUSED_HORIZON_MISMATCH"):
        compare_survival_policies(
            {
                "formal": [base],
                "llm": [episode("b", "llm", clean_do(), horizon=5)],
            }
        )


def test_comparison_refuses_policy_key_mismatch_or_single_stratum() -> None:
    with pytest.raises(IECRefusal, match="UNDERPOWERED"):
        compare_survival_policies(
            {"formal": [episode("a", "formal", clean_do())]}
        )

    with pytest.raises(IECRefusal, match="REFUSED_POLICY_MISMATCH"):
        compare_survival_policies(
            {
                "formal": [episode("a", "formal", clean_do())],
                "llm": [episode("b", "selective", clean_do())],
            }
        )


def test_pareto_frontier_preserves_tradeoff_instead_of_forcing_scalar_winner() -> None:
    safer_more_llm = PolicyMetrics(
        policy_id="safe",
        episodes=10,
        failures=0,
        failure_probability_observed=0.0,
        rmst_steps=10.0,
        terminal_survival=1.0,
        receipt_coverage=1.0,
        replay_coverage=1.0,
        llm_dependency_fraction=0.8,
        llm_tokens=1000,
    )
    riskier_no_llm = PolicyMetrics(
        policy_id="cheap",
        episodes=10,
        failures=1,
        failure_probability_observed=0.1,
        rmst_steps=9.5,
        terminal_survival=0.9,
        receipt_coverage=1.0,
        replay_coverage=1.0,
        llm_dependency_fraction=0.0,
        llm_tokens=0,
    )

    assert observed_pareto_frontier((safer_more_llm, riskier_no_llm)) == (
        "cheap",
        "safe",
    )
