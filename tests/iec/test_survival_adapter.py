"""Strict survival projection adapter tests."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival import analyze_episode
from autofde_lab.iec.crowns.survival_adapter import project_event_trace


def test_projection_is_sorted_receipted_and_consumable_by_survival_court() -> None:
    document, receipt = project_event_trace(
        [
            {
                "step": 3,
                "phase": "DO",
                "authorized": True,
                "admitted": True,
                "receipt_id": "receipt:3",
                "terminal_ready": True,
                "replay_verified": True,
            },
            {
                "step": 1,
                "phase": "OBSERVE",
                "tool_invoked": True,
                "llm_tokens": 9,
            },
        ],
        source_identity="ocel:sha256:abc",
        subject="git:seanchatmangpt/autofde-lab@abc",
        workload_id="sha256:workload",
        policy_id="formal",
        episode_id="episode-1",
        horizon=3,
    )

    assert [event["step"] for event in document["events"]] == [1, 3]
    assert receipt["authority"] == "none"
    assert receipt["actuation_performed"] is False
    assert receipt["projected_events"] == 2
    assert receipt["receipt_id"].startswith("sha256:")

    analyzed = analyze_episode(document)
    assert analyzed["failed"] is False
    assert analyzed["llm_tokens"] == 9
    assert analyzed["tool_invocations"] == 1


def test_projection_never_infers_phase_from_activity_name() -> None:
    with pytest.raises(IECRefusal, match="phase"):
        project_event_trace(
            [{"step": 1, "activity": "kubectl apply"}],
            source_identity="trace:1",
            subject="subject",
            workload_id="workload",
            policy_id="policy",
            episode_id="episode",
            horizon=1,
        )


def test_projection_refuses_duplicate_or_out_of_horizon_steps() -> None:
    with pytest.raises(IECRefusal, match="duplicate source event step"):
        project_event_trace(
            [
                {"step": 1, "phase": "OBSERVE"},
                {"step": 1, "phase": "VERIFY"},
            ],
            source_identity="trace:dup",
            subject="subject",
            workload_id="workload",
            policy_id="policy",
            episode_id="episode",
            horizon=2,
        )

    with pytest.raises(IECRefusal, match="exceeds horizon"):
        project_event_trace(
            [{"step": 3, "phase": "OBSERVE"}],
            source_identity="trace:horizon",
            subject="subject",
            workload_id="workload",
            policy_id="policy",
            episode_id="episode",
            horizon=2,
        )


def test_projection_refuses_implicit_truthiness_for_bools() -> None:
    with pytest.raises(IECRefusal, match="authorized.*boolean"):
        project_event_trace(
            [{"step": 1, "phase": "DO", "authorized": 1}],
            source_identity="trace:bool",
            subject="subject",
            workload_id="workload",
            policy_id="policy",
            episode_id="episode",
            horizon=1,
        )


def test_projection_preserves_guard_and_replay_evidence_without_interpreting_it() -> None:
    document, _ = project_event_trace(
        [
            {
                "step": 1,
                "phase": "DO",
                "authorized": False,
                "receipt_id": "r1",
            },
            {
                "step": 2,
                "phase": "VERIFY",
                "guards_installed": ["UNAUTHORIZED_DO"],
                "replay_verified": True,
            },
        ],
        source_identity="trace:guard",
        subject="subject",
        workload_id="workload",
        policy_id="policy",
        episode_id="episode",
        horizon=2,
    )

    assert document["events"][1]["guards_installed"] == ["UNAUTHORIZED_DO"]
    assert document["events"][1]["replay_verified"] is True
