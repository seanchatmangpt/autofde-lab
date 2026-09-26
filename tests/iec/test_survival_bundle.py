from __future__ import annotations

import json

from autofde_lab.iec.crowns.survival_bundle import (
    build_survival_bundle,
    main,
    replay_survival_bundle,
)


def episode(episode_id: str, policy: str, *, unauthorized: bool = False) -> dict:
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "git:survival/example@0123456789abcdef",
        "workload_id": "sha256:bundle",
        "policy_id": policy,
        "episode_id": episode_id,
        "horizon": 3,
        "events": [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 3,
                "phase": "DO",
                "authorized": not unauthorized,
                "receipt_id": f"receipt:{episode_id}",
                "terminal_ready": True,
            },
        ],
    }


def corpus() -> list[dict]:
    return [
        episode("a", "formal"),
        episode("b", "formal"),
        episode("c", "llm", unauthorized=True),
        episode("d", "llm", unauthorized=True),
    ]


def test_bundle_is_deterministic_and_binds_cohort_recurrence_and_ocel() -> None:
    first = build_survival_bundle(corpus(), min_occurrences=2)
    second = build_survival_bundle(corpus(), min_occurrences=2)

    assert first == second
    assert first["standing"] == "STRUCTURAL"
    assert first["authority"] == "none"
    assert first["actuation_performed"] is False
    assert first["cohort_id"]
    assert first["recurrence_id"]
    assert len(first["episode_evidence"]) == 4
    assert all(row["ocel_digest"] for row in first["episode_evidence"])


def test_replay_receipt_detects_observation_mutation() -> None:
    expected = build_survival_bundle(corpus(), min_occurrences=2)

    matched = replay_survival_bundle(corpus(), expected)
    assert matched["matched"] is True
    assert matched["mismatches"] == ()

    changed = corpus()
    changed[2]["events"][1]["authorized"] = True
    replay = replay_survival_bundle(changed, expected)

    assert replay["matched"] is False
    assert "COHORT_MISMATCH" in replay["mismatches"]
    assert "RECURRENCE_MISMATCH" in replay["mismatches"]
    assert "OCEL_OR_EPISODE_EVIDENCE_MISMATCH" in replay["mismatches"]


def test_cli_writes_bundle_then_replays_exact_bytes(tmp_path) -> None:
    episodes = tmp_path / "episodes.json"
    bundle = tmp_path / "bundle.json"
    receipt = tmp_path / "replay.json"
    episodes.write_text(json.dumps(corpus()), encoding="utf-8")

    assert main([str(episodes), str(bundle), "--min-occurrences", "2"]) == 0
    assert (
        main(
            [
                str(episodes),
                str(receipt),
                "--replay",
                str(bundle),
            ]
        )
        == 0
    )
    replay = json.loads(receipt.read_text(encoding="utf-8"))
    assert replay["matched"] is True
