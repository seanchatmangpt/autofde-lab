"""Competing-risk and recurrent-event survival court tests."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.recurrent_survival import (
    cause_specific_survival_report,
    recurrent_episode_report,
    recurrent_survival_report,
)
from autofde_lab.iec.crowns.survival import EPISODE_SCHEMA

SUBJECT = "git:seanchatmangpt/autofde-lab@0123456789abcdef"
WORKLOAD = "sha256:survival-recurrence-workload"


def episode(episode_id: str, events: list[dict], *, horizon: int = 6) -> dict:
    return {
        "schema": EPISODE_SCHEMA,
        "subject": SUBJECT,
        "workload_id": WORKLOAD,
        "policy_id": "policy:formal",
        "episode_id": episode_id,
        "horizon": horizon,
        "events": events,
    }


def test_competing_risk_uses_stable_primary_cause_without_erasing_other_failures() -> None:
    multi = episode(
        "ep-multi",
        [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 2,
                "phase": "DO",
                "exact_subject": False,
                "authorized": False,
                "admitted": False,
                "terminal_ready": False,
            },
        ],
    )
    receipt_only = episode(
        "ep-receipt",
        [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 4,
                "phase": "DO",
                "authorized": True,
                "admitted": True,
                "terminal_ready": True,
            },
        ],
    )

    report = cause_specific_survival_report([multi, receipt_only])

    step2 = report["curve"][1]
    assert step2["at_risk"] == 2
    assert step2["failures"] == {"WRONG_SUBJECT_DO": 1}
    assert step2["hazards"]["WRONG_SUBJECT_DO"] == pytest.approx(0.5)
    assert step2["all_cause_hazard"] == pytest.approx(0.5)

    step4 = report["curve"][3]
    assert step4["at_risk"] == 1
    assert step4["failures"] == {"UNRECEIPTED_DO": 1}
    assert step4["hazards"]["UNRECEIPTED_DO"] == 1.0
    assert step4["survival"] == 0.0


def test_recurrent_episode_measures_guard_suppression_and_replay_coverage() -> None:
    report = recurrent_episode_report(
        episode(
            "ep-guarded",
            [
                {"step": 1, "phase": "OBSERVE", "llm_tokens": 12},
                {
                    "step": 2,
                    "phase": "DO",
                    "authorized": False,
                    "admitted": True,
                    "receipt_id": "receipt:2",
                    "replay_verified": True,
                },
                {
                    "step": 3,
                    "phase": "VERIFY",
                    "guards_installed": ["UNAUTHORIZED_DO"],
                },
                {
                    "step": 5,
                    "phase": "DO",
                    "authorized": True,
                    "admitted": True,
                    "receipt_id": "receipt:5",
                    "replay_verified": True,
                },
            ],
        )
    )

    edge = report["failure_edges"]["UNAUTHORIZED_DO"]
    assert edge["failure_steps"] == [2]
    assert edge["guard_installed_step"] == 3
    assert edge["guard_install_latency_steps"] == 1
    assert edge["post_guard_failures"] == 0
    assert edge["guard_effective_observed"] is True
    assert report["receipt_coverage"] == 1.0
    assert report["replay_coverage"] == 1.0
    assert report["llm_tokens"] == 12
    assert report["llm_dependency_fraction"] == pytest.approx(0.25)


def test_recurrence_after_guard_is_not_hidden_by_guard_declaration() -> None:
    report = recurrent_episode_report(
        episode(
            "ep-recur",
            [
                {
                    "step": 1,
                    "phase": "DO",
                    "authorized": False,
                    "receipt_id": "receipt:1",
                },
                {
                    "step": 2,
                    "phase": "VERIFY",
                    "guards_installed": ["UNAUTHORIZED_DO"],
                },
                {
                    "step": 4,
                    "phase": "DO",
                    "authorized": False,
                    "receipt_id": "receipt:4",
                },
            ],
        )
    )

    edge = report["failure_edges"]["UNAUTHORIZED_DO"]
    assert edge["occurrences"] == 2
    assert edge["recurrences"] == 1
    assert edge["inter_failure_steps"] == [3]
    assert edge["post_guard_failure_steps"] == [4]
    assert edge["guard_effective_observed"] is False


def test_aggregate_reports_failure_rate_delta_only_from_guarded_exposure() -> None:
    suppressed = episode(
        "ep-suppressed",
        [
            {
                "step": 2,
                "phase": "DO",
                "authorized": False,
                "receipt_id": "receipt:2",
            },
            {
                "step": 3,
                "phase": "VERIFY",
                "guards_installed": ["UNAUTHORIZED_DO"],
            },
            {
                "step": 6,
                "phase": "DO",
                "authorized": True,
                "receipt_id": "receipt:6",
                "replay_verified": True,
            },
        ],
    )
    recurred = episode(
        "ep-recurred",
        [
            {
                "step": 1,
                "phase": "DO",
                "authorized": False,
                "receipt_id": "receipt:1",
            },
            {
                "step": 2,
                "phase": "VERIFY",
                "guards_installed": ["UNAUTHORIZED_DO"],
            },
            {
                "step": 5,
                "phase": "DO",
                "authorized": False,
                "receipt_id": "receipt:5",
            },
        ],
    )

    report = recurrent_survival_report([suppressed, recurred])
    edge = report["failure_edges"]["UNAUTHORIZED_DO"]

    assert edge["occurrences"] == 3
    assert edge["recurrences"] == 1
    assert edge["guarded_episodes"] == 2
    assert edge["post_guard_failures"] == 1
    assert edge["pre_guard_failure_rate_per_step"] == pytest.approx(2 / 5)
    assert edge["post_guard_failure_rate_per_step"] == pytest.approx(1 / 7)
    assert edge["failure_rate_delta_per_step"] == pytest.approx(9 / 35)


def test_replay_coverage_requires_receipt_and_verified_replay() -> None:
    report = recurrent_episode_report(
        episode(
            "ep-replay",
            [
                {
                    "step": 1,
                    "phase": "DO",
                    "authorized": True,
                    "receipt_id": "receipt:1",
                    "replay_verified": True,
                },
                {
                    "step": 2,
                    "phase": "DO",
                    "authorized": True,
                    "receipt_id": "receipt:2",
                    "replay_verified": False,
                },
                {
                    "step": 3,
                    "phase": "DO",
                    "authorized": True,
                    "receipt_id": None,
                    "replay_verified": True,
                },
            ],
        )
    )

    assert report["do_count"] == 3
    assert report["receipted_do_count"] == 2
    assert report["replay_verified_do_count"] == 1
    assert report["receipt_coverage"] == pytest.approx(2 / 3)
    assert report["replay_coverage"] == pytest.approx(1 / 2)
