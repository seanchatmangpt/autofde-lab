"""AASEE-derived delegation/admission calculus tests."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.delegation_admission import (
    compare_delegation,
    evaluate_delegation,
    main,
)
from autofde_lab.iec.crowns.model import IECRefusal

SUBJECT = "git:seanchatmangpt/autofde-lab@0123456789abcdef"


def artifact(
    *,
    units: int = 3,
    scope: int = 3,
    independent: bool = True,
    modify_verdict: str = "PASS",
) -> dict:
    return {
        "schema": "autofde-lab.delegation-admission/1",
        "subject": SUBJECT,
        "delegation": {
            "units": units,
            "boundary_id": "sha256:boundary",
            "authority_scope_id": "sha256:authority-scope",
            "producer_id": "urn:producer:subject",
        },
        "obligations": {
            "explain": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "provenance_id": "sha256:provenance",
                "ontology_id": "sha256:ontology",
                "rationale_id": "sha256:rationale",
            },
            "verify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "verifier_id": "urn:verifier:independent",
                "verifier_set_id": "sha256:verifiers",
                "receipt_id": "sha256:verify-receipt",
                "independent": independent,
            },
            "modify": {
                "subject": SUBJECT,
                "verdict": modify_verdict,
                "scope_units": scope,
                "change_id": "sha256:changed-requirement",
                "result_id": "sha256:changed-result",
                "replay_id": "sha256:changed-replay",
            },
            "account": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "authority_id": "sha256:authority",
                "consequence_id": "sha256:consequence",
                "receipt_id": "sha256:receipt",
                "replay_id": "sha256:replay",
                "standing": "PARTIAL_ALIVE",
            },
        },
    }


def test_full_evidence_admits_delegation_without_debt() -> None:
    result = evaluate_delegation(artifact())
    assert result["gate"] == "PASS"
    assert result["admission_capacity_units"] == 3
    assert result["admission_debt"]["units"] == 0
    assert result["falsifiers"] == []


def test_verifier_must_be_independent() -> None:
    result = evaluate_delegation(artifact(independent=False))
    assert result["gate"] == "COUNTEREXAMPLE"
    assert "VERIFY_NOT_INDEPENDENT" in result["falsifiers"]
    assert result["admission_capacity_units"] == 0


def test_verifier_identity_must_differ_from_producer_identity() -> None:
    candidate = artifact()
    candidate["obligations"]["verify"]["verifier_id"] = candidate["delegation"][
        "producer_id"
    ]
    result = evaluate_delegation(candidate)
    assert result["gate"] == "COUNTEREXAMPLE"
    assert "VERIFY_PRODUCER_EQUALS_VERIFIER" in result["falsifiers"]
    assert result["admission_capacity_units"] == 0


def test_changed_requirement_probe_is_a_required_obligation() -> None:
    candidate = artifact(modify_verdict="COUNTEREXAMPLE")
    result = evaluate_delegation(candidate)
    assert result["gate"] == "COUNTEREXAMPLE"
    assert "MODIFY_NOT_PASS" in result["falsifiers"]
    assert result["admission_debt"]["modification"] is True


def test_delegation_beyond_minimum_evidenced_scope_creates_admission_debt() -> None:
    result = evaluate_delegation(artifact(units=5, scope=3))
    assert result["gate"] == "COUNTEREXAMPLE"
    assert result["admission_capacity_units"] == 3
    assert result["admission_debt"]["units"] == 2
    assert "DELEGATION_EXCEEDS_ADMISSION_CAPACITY" in result["falsifiers"]


def test_growth_law_requires_admission_capacity_to_keep_up() -> None:
    reference = artifact(units=2, scope=2)
    candidate = artifact(units=3, scope=2)
    result = compare_delegation(reference, candidate)
    assert result["growth_law"]["verdict"] == "COUNTEREXAMPLE"
    assert result["delta"]["delegation_units"] == 1
    assert result["delta"]["admission_capacity_units"] == 0
    assert "DELEGATION_GROWTH_OUTRUNS_ADMISSION_GROWTH" in result["falsifiers"]


def test_growth_law_passes_when_capacity_grows_with_delegation() -> None:
    result = compare_delegation(
        artifact(units=2, scope=2),
        artifact(units=4, scope=4),
    )
    assert result["gate"] == "PASS"
    assert result["growth_law"]["verdict"] == "PASS"




def test_growth_law_allows_safe_contraction_after_evidence_revocation() -> None:
    # Reference carries surplus evidence. The candidate loses most of that
    # evidence but also contracts delegation back inside the new boundary.
    # No positive delegation growth occurred, so the growth law must not
    # manufacture a failure from negative deltas.
    result = compare_delegation(
        artifact(units=2, scope=5),
        artifact(units=1, scope=1),
    )
    assert result["gate"] == "PASS"
    assert result["delta"]["delegation_units"] == -1
    assert result["delta"]["admission_capacity_units"] == -4
    assert result["growth_law"]["verdict"] == "PASS"

def test_compare_refuses_boundary_drift() -> None:
    candidate = artifact()
    candidate["delegation"]["boundary_id"] = "sha256:other-boundary"
    with pytest.raises(IECRefusal, match="REFUSED_BOUNDARY_MISMATCH"):
        compare_delegation(artifact(), candidate)


def test_cli_receipt_is_byte_replayable(tmp_path) -> None:
    candidate = tmp_path / "candidate.json"
    receipt = tmp_path / "receipt.json"
    candidate.write_text(json.dumps(artifact()), encoding="utf-8")

    assert main([str(candidate), str(receipt), "--gate"]) == 0
    first = receipt.read_bytes()
    assert main([str(candidate), str(receipt)]) == 0
    assert receipt.read_bytes() == first
