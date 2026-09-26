from __future__ import annotations

from dataclasses import replace

from autofde_lab.enterprise_architecture import (
    ArchitectureContract,
    CandidateSBB,
    Standing,
    digest,
    frontier,
    prior_art_disposition,
    qualify,
)

ABB = digest({"abb": "sha256:abb"})
CONTRACT = digest({"contract": "sha256:contract"})
SUBJECT_A = digest({"subject": "sbb:a"})
SUBJECT_B = digest({"subject": "sbb:b"})


def contract() -> ArchitectureContract:
    return ArchitectureContract(
        abb_digest=ABB,
        contract_digest=CONTRACT,
        authority_ceiling="CONSTRUCT",
    )


def candidate(**overrides) -> CandidateSBB:
    values = {
        "candidate_id": "sbb:a",
        "abb_digest": ABB,
        "contract_digest": CONTRACT,
        "exact_subject_digest": SUBJECT_A,
        "mutable": False,
        "authority": "CONSTRUCT",
        "evidence": ("evidence:independent",),
        "dimensions": {
            "semantic": True,
            "functional": True,
            "effect": True,
            "failure": True,
            "authority": True,
            "resource": True,
            "evidence": True,
            "lifecycle": True,
        },
    }
    values.update(overrides)
    return CandidateSBB(**values)


def test_positive_qualification_is_deterministic_and_non_authoritative():
    first = qualify(contract(), candidate())
    second = qualify(contract(), candidate())
    assert first == second
    assert first.standing is Standing.QUALIFIED
    assert first.confers_authority is False


def test_unknown_remains_unknown_and_does_not_collapse_to_qualified():
    dimensions = dict(candidate().dimensions)
    dimensions["failure"] = None
    receipt = qualify(contract(), candidate(dimensions=dimensions))
    assert receipt.standing is Standing.UNKNOWN
    assert not receipt.refusal_codes


def test_adversarial_refusals_are_typed():
    cases = (
        (candidate(mutable=True), "MUTABLE_SUBJECT"),
        (candidate(evidence=()), "MISSING_EVIDENCE"),
        (candidate(authority="DO"), "AUTHORITY_WIDENING"),
        (candidate(contract_digest=digest({"contract": "old"})), "STALE_CONTRACT"),
        (candidate(abb_digest=digest({"abb": "other"})), "ABB_MISMATCH"),
    )
    for subject, code in cases:
        receipt = qualify(contract(), subject)
        assert receipt.standing is Standing.REFUSED
        assert code in receipt.refusal_codes


def test_equivalence_laundering_fails_one_dimension_without_poisoning_others():
    dimensions = dict(candidate().dimensions)
    dimensions["semantic"] = False
    receipt = qualify(contract(), candidate(dimensions=dimensions))
    assert receipt.standing is Standing.REFUSED
    assert "SEMANTIC_INCOMPATIBLE" in receipt.refusal_codes
    assert {r.dimension: r.verdict for r in receipt.dimensions}["functional"] == "PASS"


def test_dfcm_frontier_preserves_multiple_qualified_candidates():
    b = replace(candidate(), candidate_id="sbb:b", exact_subject_digest=SUBJECT_B)
    receipts = frontier(contract(), (b, candidate()))
    assert [receipt.candidate_id for receipt in receipts] == ["sbb:a", "sbb:b"]
    assert all(receipt.standing is Standing.QUALIFIED for receipt in receipts)


def test_prior_art_order_is_reuse_compose_extend_invent():
    assert (
        prior_art_disposition(reusable=True, composable=True, extendable=True)[0]
        == "REUSE"
    )
    assert (
        prior_art_disposition(reusable=False, composable=True, extendable=True)[0]
        == "COMPOSE"
    )
    assert (
        prior_art_disposition(reusable=False, composable=False, extendable=True)[0]
        == "EXTEND"
    )
    assert (
        prior_art_disposition(reusable=False, composable=False, extendable=False)[0]
        == "INVENT"
    )
