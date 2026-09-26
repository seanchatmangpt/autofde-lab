"""OCEL projection court for autonomic-survival evidence."""

from __future__ import annotations

from autofde_lab.iec.crowns.survival_ocel import survival_episode_to_ocel


def episode() -> dict:
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "git:seanchatmangpt/autofde-lab@0123456789abcdef",
        "workload_id": "sha256:ocel-survival-workload",
        "policy_id": "formal",
        "episode_id": "episode-ocel-1",
        "horizon": 4,
        "events": [
            {
                "step": 1,
                "phase": "OBSERVE",
                "tool_invoked": True,
                "llm_tokens": 3,
            },
            {
                "step": 2,
                "phase": "DO",
                "authorized": False,
                "admitted": True,
                "receipt_id": "receipt:2",
                "replay_verified": True,
                "terminal_ready": True,
            },
            {
                "step": 3,
                "phase": "VERIFY",
                "guards_installed": ["UNAUTHORIZED_DO"],
            },
            {
                "step": 4,
                "phase": "DO",
                "authorized": True,
                "admitted": True,
                "receipt_id": "receipt:4",
                "replay_verified": True,
                "terminal_ready": True,
            },
        ],
    }


def attrs(event) -> dict:
    return {attribute.key: attribute.value.value for attribute in event.attributes}


def test_survival_projection_is_strictly_qualified_and_deterministic() -> None:
    first = survival_episode_to_ocel(episode())
    second = survival_episode_to_ocel(episode())

    assert first == second
    assert len(first.objects) == 3
    assert {obj.object_type for obj in first.objects} == {
        "SurvivalEpisode",
        "Subject",
        "Policy",
    }
    assert len(first.events) == 4
    assert len(first.event_object_links) == 12
    assert all(link.qualifier for link in first.event_object_links)
    assert [event.timestamp_ns for event in first.events] == [
        1_000_000_000,
        2_000_000_000,
        3_000_000_000,
        4_000_000_000,
    ]


def test_survival_projection_preserves_failure_replay_and_guard_evidence() -> None:
    log = survival_episode_to_ocel(episode())

    do_failure = attrs(log.events[1])
    verify = attrs(log.events[2])
    repaired_do = attrs(log.events[3])

    assert log.events[1].activity == "survival.do"
    assert do_failure["authorized"] is False
    assert do_failure["receiptId"] == "receipt:2"
    assert do_failure["replayVerified"] is True
    assert verify["guardsInstalled"] == '["UNAUTHORIZED_DO"]'
    assert repaired_do["authorized"] is True
    assert repaired_do["receiptId"] == "receipt:4"


def test_survival_projection_keeps_exact_subject_as_object_attribute() -> None:
    log = survival_episode_to_ocel(episode())
    subject = next(obj for obj in log.objects if obj.object_type == "Subject")

    projected = {attribute.key: attribute.value.value for attribute in subject.attributes}

    assert projected["exactSubject"] == episode()["subject"]
