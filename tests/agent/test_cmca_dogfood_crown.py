from __future__ import annotations

from autofde_lab.agent.cmca_dogfood_crown import (
    USE_CASE_TITLES,
    demo_contracts,
    run_cmca_dogfood_crown,
)


def test_demo_contracts_are_the_eight_repo_native_cmca_use_cases() -> None:
    contracts = demo_contracts()
    assert len(contracts) == 8
    assert [contract["case_id"] for contract in contracts] == [
        "UC-1",
        "UC-2",
        "UC-3",
        "UC-4",
        "UC-5",
        "UC-6",
        "UC-7",
        "UC-8",
    ]
    assert {contract["title"] for contract in contracts} == set(
        USE_CASE_TITLES.values()
    )


def test_two_episode_dogfood_crown_compiles_experience_and_replays_without_frontier(
) -> None:
    crown = run_cmca_dogfood_crown()

    assert crown.is_alive is True
    assert crown.frontier_resolution_calls_episode_1 == 8
    assert crown.frontier_resolution_calls_episode_2 == 0
    assert crown.compiled_experience_rules == 8
    assert crown.replay_inference_avoidance_rate == 1.0
    assert len(crown.crown_receipt_hash) == 64

    assert len(crown.cases) == 8
    for case in crown.cases:
        assert case.discovery.verified is True
        assert case.discovery.epistemic_route == "UNKNOWN_FRONTIER"
        assert case.replay.verified is True
        assert case.replay.epistemic_route == "KNOWN_REPLAY"
        assert case.replay_identical is True
        assert case.discovery.contract_digest == case.replay.contract_digest
        assert case.discovery.evidence_digest == case.replay.evidence_digest
        assert len(case.experience_receipt_digest) == 64
