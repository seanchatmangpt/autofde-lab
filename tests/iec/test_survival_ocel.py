from __future__ import annotations

from autofde_lab.iec.crowns.survival_ocel import (
    episode_to_ocel2_json,
    episode_to_ocel_log,
)


def episode() -> dict:
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "git:survival/example@0123456789abcdef",
        "workload_id": "sha256:ocel",
        "policy_id": "policy:formal",
        "episode_id": "ep-1",
        "horizon": 3,
        "events": [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 2,
                "phase": "DO",
                "authorized": False,
                "receipt_id": "receipt:2",
                "terminal_ready": True,
            },
            {"step": 3, "phase": "VERIFY"},
        ],
    }


def test_survival_episode_projects_to_valid_replay_stable_ocel() -> None:
    first = episode_to_ocel_log(episode())
    second = episode_to_ocel_log(episode())

    assert first.validate(strict_qualifiers=True) is first
    assert first.digest() == second.digest()
    assert [event.activity for event in first.events] == [
        "survival.observe",
        "survival.do",
        "survival.verify",
    ]
    assert any(obj.object_type == "SurvivalFailure" for obj in first.objects)
    assert any(obj.object_type == "Receipt" for obj in first.objects)


def test_literal_ocel_projection_contains_qualified_failure_and_receipt_links() -> None:
    document = episode_to_ocel2_json(episode())
    do_event = next(event for event in document["events"] if event["type"] == "survival.do")
    qualifiers = {relationship["qualifier"] for relationship in do_event["relationships"]}

    assert {"subject", "policy", "episode", "receipt", "failure"} <= qualifiers
    assert document["objects"]
    assert document["eventTypes"]
    assert document["objectTypes"]
