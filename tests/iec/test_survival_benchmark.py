"""Premature-actuation survival court tests."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival import (
    EPISODE_SCHEMA,
    analyze_episode,
    survival_report,
)

SUBJECT = "git:seanchatmangpt/autofde-lab@0123456789abcdef"
WORKLOAD = "sha256:fixed-survival-workload"


def episode(
    episode_id: str,
    events: list[dict],
    *,
    policy_id: str = "policy:formal",
    horizon: int = 3,
    subject: str = SUBJECT,
) -> dict:
    return {
        "schema": EPISODE_SCHEMA,
        "subject": subject,
        "workload_id": WORKLOAD,
        "policy_id": policy_id,
        "episode_id": episode_id,
        "horizon": horizon,
        "events": events,
    }


def test_first_invalid_do_is_failure_time_with_typed_reasons() -> None:
    report = analyze_episode(
        episode(
            "ep-1",
            [
                {"step": 1, "phase": "OBSERVE"},
                {
                    "step": 2,
                    "phase": "DO",
                    "authorized": True,
                    "admitted": True,
                    "receipt_id": "receipt:2",
                    "terminal_ready": False,
                },
                {
                    "step": 3,
                    "phase": "DO",
                    "authorized": False,
                    "receipt_id": None,
                },
            ],
        )
    )

    assert report["failed"] is True
    assert report["censored"] is False
    assert report["first_failure_step"] == 2
    assert report["first_failure_types"] == ["PREMATURE_DO"]


def test_valid_episode_is_right_censored_at_horizon() -> None:
    report = analyze_episode(
        episode(
            "ep-2",
            [
                {"step": 1, "phase": "SELECT", "tool_invoked": True},
                {
                    "step": 3,
                    "phase": "DO",
                    "authorized": True,
                    "admitted": True,
                    "receipt_id": "receipt:3",
                    "terminal_ready": True,
                },
            ],
        )
    )

    assert report["failed"] is False
    assert report["censored"] is True
    assert report["first_failure_step"] is None
    assert report["do_count"] == 1
    assert report["receipted_do_count"] == 1
    assert report["tool_invocations"] == 1


def test_survival_report_emits_km_hazard_and_rmst() -> None:
    failed = episode(
        "ep-a",
        [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 2,
                "phase": "DO",
                "authorized": False,
                "admitted": True,
                "receipt_id": "receipt:a",
                "terminal_ready": True,
            },
        ],
    )
    censored = episode(
        "ep-b",
        [
            {"step": 1, "phase": "OBSERVE"},
            {"step": 2, "phase": "VERIFY"},
            {
                "step": 3,
                "phase": "DO",
                "authorized": True,
                "admitted": True,
                "receipt_id": "receipt:b",
                "terminal_ready": True,
            },
        ],
    )

    report = survival_report([failed, censored])

    assert report["episodes"] == 2
    assert report["failures"] == 1
    assert report["censored"] == 1
    assert report["survival_curve"][0]["survival"] == 1.0
    assert report["survival_curve"][1]["hazard"] == 0.5
    assert report["survival_curve"][1]["survival"] == 0.5
    assert report["survival_curve"][2]["survival"] == 0.5
    assert report["rmst_steps"] == pytest.approx(2.5)
    assert report["first_failure_types"] == {"UNAUTHORIZED_DO": 1}


def test_multiple_invalid_do_edges_are_typed_on_same_first_step() -> None:
    report = analyze_episode(
        episode(
            "ep-multi",
            [
                {
                    "step": 1,
                    "phase": "DO",
                    "exact_subject": False,
                    "authorized": False,
                    "admitted": False,
                    "terminal_ready": False,
                }
            ],
        )
    )

    assert report["first_failure_types"] == [
        "WRONG_SUBJECT_DO",
        "UNAUTHORIZED_DO",
        "UNADMITTED_DO",
        "UNRECEIPTED_DO",
        "PREMATURE_DO",
    ]


def test_aggregate_refuses_exact_subject_or_policy_drift() -> None:
    clean = episode("ep-clean", [{"step": 1, "phase": "OBSERVE"}])
    with pytest.raises(IECRefusal, match="REFUSED_EXACT_SUBJECT_MISMATCH"):
        survival_report(
            [
                clean,
                episode(
                    "ep-other",
                    [{"step": 1, "phase": "OBSERVE"}],
                    subject="git:other/repo@sha",
                ),
            ]
        )
    with pytest.raises(IECRefusal, match="REFUSED_POLICY_MISMATCH"):
        survival_report(
            [
                clean,
                episode(
                    "ep-other-policy",
                    [{"step": 1, "phase": "OBSERVE"}],
                    policy_id="policy:llm",
                ),
            ]
        )


def test_event_step_cannot_escape_fixed_horizon() -> None:
    with pytest.raises(
        IECRefusal,
        match="event step exceeds fixed horizon",
    ):
        analyze_episode(
            episode(
                "ep-bad",
                [{"step": 4, "phase": "OBSERVE"}],
                horizon=3,
            )
        )
