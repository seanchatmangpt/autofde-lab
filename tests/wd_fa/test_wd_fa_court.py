from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from autofde_lab.wd_fa.api import create_app
from autofde_lab.wd_fa.automl import train_tpot
from autofde_lab.wd_fa.domain import Standing
from autofde_lab.wd_fa.process import build_ocel, process_evidence, roundtrip_ocel2
from autofde_lab.wd_fa.receipts import issue_receipt, verify_receipt
from autofde_lab.wd_fa.synthetic import (
    RULES,
    feature_frame,
    named_cases,
    training_frame,
)
from autofde_lab.wd_fa.triage import compile_experience, triage


@pytest.fixture(scope="module")
def candidate_model():
    features, labels = training_frame()
    return train_tpot(features, labels)


def test_ocel_is_object_centric_and_roundtrips(tmp_path):
    case = named_cases()["known_a"]
    ocel = build_ocel(case)
    assert {"Drive", "FailureCase", "Lot", "FirmwareRevision", "TestStation"} <= set(
        ocel.objects["ocel:type"]
    )
    assert len(ocel.relations) > len(ocel.events)
    path = tmp_path / "case.jsonocel"
    restored = roundtrip_ocel2(case, path)
    assert len(restored.events) == len(ocel.events)
    assert len(restored.objects) == len(ocel.objects)
    assert len(restored.relations) == len(ocel.relations)
    assert restored.is_ocel20()


def test_pm4py_discovers_object_centric_and_powl_evidence():
    evidence = process_evidence(named_cases()["known_a"])
    assert "Drive" in evidence["object_types"]
    assert evidence["event_count"] >= 4
    assert "test_failed" in evidence["ocdfg_activities"]
    assert evidence["powl_type"]


def test_tpot_is_candidate_not_authority(candidate_model):
    ranking = candidate_model.rank(feature_frame(named_cases()["novel_x"]))
    assert ranking
    assert all(isinstance(score, float) for _, score in ranking)
    result = triage(named_cases()["novel_x"], RULES, candidate_model=candidate_model)
    assert result.standing is Standing.UNKNOWN
    assert result.admitted_mode is None


def test_known_a_is_admitted(candidate_model):
    result = triage(named_cases()["known_a"], RULES, candidate_model=candidate_model)
    assert result.standing is Standing.ALIVE
    assert result.admitted_mode == "MODE-A-FIRMWARE"
    assert result.exploratory_steps == 0


def test_misleading_similarity_cannot_override_applicability(candidate_model):
    result = triage(
        named_cases()["known_b_misleading"], RULES, candidate_model=candidate_model
    )
    assert result.standing is Standing.ALIVE
    assert result.admitted_mode == "MODE-B-SUPPLIER"


def test_incomplete_evidence_is_partial(candidate_model):
    result = triage(
        named_cases()["incomplete_a"], RULES, candidate_model=candidate_model
    )
    assert result.standing is Standing.PARTIAL_ALIVE
    assert result.admitted_mode is None
    assert result.evidence_completeness < 1.0


def test_novel_is_unknown_not_nearest_known(candidate_model):
    result = triage(named_cases()["novel_x"], RULES, candidate_model=candidate_model)
    assert result.standing is Standing.UNKNOWN
    assert result.model_ranking
    assert result.admitted_mode is None


def test_self_certification_is_refused(candidate_model):
    case = named_cases()["known_a"]
    result = triage(case, RULES, candidate_model=candidate_model)
    with pytest.raises(ValueError, match="SELF_CERTIFICATION"):
        issue_receipt(
            case,
            result,
            producer_id="same",
            verifier_id="same",
            observed_disposition="MODE-A-FIRMWARE",
        )


def test_tampered_receipt_fails_replay(candidate_model):
    case = named_cases()["known_a"]
    result = triage(case, RULES, candidate_model=candidate_model)
    receipt = issue_receipt(
        case,
        result,
        producer_id="candidate-producer",
        verifier_id="independent-verifier",
        observed_disposition="MODE-A-FIRMWARE",
    )
    assert verify_receipt(receipt)
    assert receipt.authority_scope == "REPO_LOCAL_FIXTURE"
    assert not verify_receipt(replace(receipt, observed_disposition="TAMPERED"))
    assert not verify_receipt(replace(receipt, authority_scope="EXTERNAL"))


def test_machine_experience_reduces_future_intelligence(candidate_model):
    cases = named_cases()
    first = triage(cases["novel_x"], RULES, candidate_model=candidate_model)
    receipt = issue_receipt(
        cases["novel_x"],
        first,
        producer_id="candidate-producer",
        verifier_id="independent-verifier",
        observed_disposition="MODE-X-NOVEL",
    )
    assert verify_receipt(receipt)
    experience = compile_experience(
        cases["novel_x"],
        first,
        receipt,
        mode_id="MODE-X-NOVEL",
        next_action="repeat_verified_novel_x_procedure",
    )
    replay = triage(
        cases["novel_x_replay"],
        (*RULES, experience.mode),
        candidate_model=candidate_model,
    )
    assert first.standing is Standing.UNKNOWN
    assert replay.standing is Standing.ALIVE
    assert replay.admitted_mode == "MODE-X-NOVEL"
    assert replay.exploratory_steps < first.exploratory_steps


def test_machine_experience_refuses_unbound_receipts(candidate_model):
    cases = named_cases()
    first = triage(cases["novel_x"], RULES, candidate_model=candidate_model)
    receipt = issue_receipt(
        cases["novel_x"],
        first,
        producer_id="candidate-producer",
        verifier_id="independent-verifier",
        observed_disposition="MODE-X-NOVEL",
    )
    with pytest.raises(ValueError, match="INVALID_RECEIPT"):
        compile_experience(
            cases["novel_x"],
            first,
            replace(receipt, receipt_digest="tampered"),
            mode_id="MODE-X-NOVEL",
            next_action="repeat_verified_novel_x_procedure",
        )
    with pytest.raises(ValueError, match="DISPOSITION_BINDING"):
        compile_experience(
            cases["novel_x"],
            first,
            receipt,
            mode_id="MODE-WRONG",
            next_action="repeat_verified_novel_x_procedure",
        )


def test_fastapi_and_sa2a_are_candidate_surfaces_only():
    client = TestClient(create_app())
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["authority"] == "NO_DO"
    triage_response = client.post("/triage", json={"case_name": "known_a"})
    assert triage_response.status_code == 200
    assert triage_response.json()["authority"] == "SELECT_ONLY"
    a2a_response = client.post(
        "/a2a/tasks/analyze_failure", json={"case_name": "novel_x"}
    )
    assert a2a_response.status_code == 200
    assert a2a_response.json()["standing"] == "UNKNOWN"
    assert a2a_response.json()["authority"] == "SELECT_ONLY"
