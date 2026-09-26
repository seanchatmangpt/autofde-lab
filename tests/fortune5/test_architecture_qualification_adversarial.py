"""Adversarial falsifiers for the ABB -> SBB architecture qualification court.

Chicago style: every test drives the real ``qualify``/``frontier``/``replay_refusals``
functions with real frozen dataclasses and asserts on the returned receipts. No test
double is used anywhere; the court has no external collaborators.

Each test names the hole it guards. The holes were observed on PR #203 head
66fae260 (see the harden commit message) and are now permanent regression guards.
"""

from __future__ import annotations

import itertools
from dataclasses import replace

import pytest

from autofde_lab.enterprise_architecture import (
    DIMENSIONS,
    ArchitectureContract,
    CandidateSBB,
    Standing,
    digest,
    frontier,
    qualify,
    replay_refusals,
    verify_receipt,
)

ABB = digest({"abb": "capability:order-to-cash"})
CONTRACT = digest({"contract": "order-to-cash/v1"})
SUBJECT_A = digest({"subject": "sbb:a@1"})
SUBJECT_B = digest({"subject": "sbb:b@1"})


def contract(**overrides) -> ArchitectureContract:
    values = {
        "abb_digest": ABB,
        "contract_digest": CONTRACT,
        "authority_ceiling": "CONSTRUCT",
    }
    values.update(overrides)
    return ArchitectureContract(**values)


def candidate(**overrides) -> CandidateSBB:
    values = {
        "candidate_id": "sbb:a",
        "abb_digest": ABB,
        "contract_digest": CONTRACT,
        "exact_subject_digest": SUBJECT_A,
        "mutable": False,
        "authority": "CONSTRUCT",
        "evidence": ("evidence:independent-run",),
        "dimensions": {dimension: True for dimension in DIMENSIONS},
    }
    values.update(overrides)
    return CandidateSBB(**values)


def refused_with(receipt, code: str) -> bool:
    return receipt.standing is Standing.REFUSED and code in receipt.refusal_codes


# --- authority: the court never confers or admits DO -------------------------


def test_do_candidate_is_refused_even_under_a_do_ceiling():
    # Hole on 66fae260: ceiling="DO" + authority="DO" qualified, i.e. a qualification
    # receipt certified an actuating SBB although the RFC says no result confers BRCE.
    receipt = qualify(contract(authority_ceiling="DO"), candidate(authority="DO"))
    assert refused_with(receipt, "AUTHORITY_WIDENING")
    assert refused_with(receipt, "CONTRACT_CEILING_INVALID")
    assert receipt.confers_authority is False


@pytest.mark.parametrize("ceiling", ["DO", "ROOT", "", "construct"])
def test_contract_ceiling_above_construct_or_unknown_is_refused(ceiling):
    receipt = qualify(contract(authority_ceiling=ceiling), candidate(authority="NONE"))
    assert refused_with(receipt, "CONTRACT_CEILING_INVALID")


@pytest.mark.parametrize("authority", ["do", "ADMIN", "", "CONSTRUCT "])
def test_unknown_candidate_authority_fails_closed(authority):
    receipt = qualify(contract(), candidate(authority=authority))
    assert refused_with(receipt, "UNKNOWN_AUTHORITY")


def test_lower_authority_than_ceiling_still_qualifies():
    for authority in ("NONE", "OBSERVE", "SELECT", "CONSTRUCT"):
        assert qualify(contract(), candidate(authority=authority)).standing is (
            Standing.QUALIFIED
        )


# --- malformed / wrong digests ------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("exact_subject_digest", "sha256:subject-a"),
        ("exact_subject_digest", "SHA256:" + "a" * 64),
        ("exact_subject_digest", "sha256:" + "a" * 63),
        ("exact_subject_digest", "sha512:" + "a" * 64),
        ("exact_subject_digest", "sha256:" + "g" * 64),
        ("abb_digest", "sha256:abb"),
        ("contract_digest", "latest"),
    ],
)
def test_malformed_digest_is_refused(field, value):
    # Hole on 66fae260: any non-empty string was accepted as an exact subject, so a
    # branch name or tag ("latest") could stand in for an immutable digest.
    receipt = qualify(contract(), candidate(**{field: value}))
    assert refused_with(receipt, "MALFORMED_DIGEST")


def test_malformed_contract_side_digest_is_refused():
    receipt = qualify(contract(abb_digest="abb"), candidate(abb_digest="abb"))
    assert refused_with(receipt, "MALFORMED_DIGEST")


def test_missing_exact_subject_is_typed_separately_from_malformed():
    receipt = qualify(contract(), candidate(exact_subject_digest=""))
    assert refused_with(receipt, "MISSING_EXACT_SUBJECT")
    assert "MALFORMED_DIGEST" not in receipt.refusal_codes


def test_wrong_but_well_formed_digest_is_stale_not_malformed():
    stale = digest({"contract": "order-to-cash/v0"})
    receipt = qualify(contract(), candidate(contract_digest=stale))
    assert refused_with(receipt, "STALE_CONTRACT")
    assert "MALFORMED_DIGEST" not in receipt.refusal_codes


# --- evidence and subject identity --------------------------------------------


@pytest.mark.parametrize("evidence", [("",), ("   ",), ("evidence:x", "")])
def test_blank_evidence_is_refused(evidence):
    # Hole on 66fae260: evidence=("",) was non-empty so it qualified.
    receipt = qualify(contract(), candidate(evidence=evidence))
    assert refused_with(receipt, "MALFORMED_EVIDENCE")


def test_duplicate_evidence_delivery_is_refused():
    receipt = qualify(contract(), candidate(evidence=("evidence:x", "evidence:x")))
    assert refused_with(receipt, "DUPLICATE_EVIDENCE")


@pytest.mark.parametrize("mutable", ["false", 0, None, 1])
def test_non_bool_mutable_flag_fails_closed(mutable):
    # Only the literal False admits immutability; "false"/0/None are not proof.
    receipt = qualify(contract(), candidate(mutable=mutable))
    assert refused_with(receipt, "MUTABLE_SUBJECT")


def test_blank_candidate_id_is_refused():
    receipt = qualify(contract(), candidate(candidate_id="  "))
    assert refused_with(receipt, "MISSING_CANDIDATE_ID")


# --- dimensions: no laundering through typos or truthy values ------------------


@pytest.mark.parametrize("value", [1, "yes", "true", 1.0])
def test_truthy_non_bool_dimension_is_malformed_not_pass(value):
    dimensions = {dimension: True for dimension in DIMENSIONS}
    dimensions["effect"] = value
    receipt = qualify(contract(), candidate(dimensions=dimensions))
    assert refused_with(receipt, "MALFORMED_DIMENSION")
    verdicts = {r.dimension: r.verdict for r in receipt.dimensions}
    assert verdicts["effect"] == "UNKNOWN"


def test_undeclared_dimension_key_is_refused():
    # A typo ("semantics") must not silently leave "semantic" UNKNOWN while the
    # submitter believes it passed; it is a typed refusal.
    dimensions = {dimension: True for dimension in DIMENSIONS}
    dimensions["semantics"] = True
    receipt = qualify(contract(), candidate(dimensions=dimensions))
    assert refused_with(receipt, "UNDECLARED_DIMENSION")


def test_every_dimension_failure_is_individually_typed():
    for dimension in DIMENSIONS:
        dimensions = {d: True for d in DIMENSIONS}
        dimensions[dimension] = False
        receipt = qualify(contract(), candidate(dimensions=dimensions))
        assert receipt.refusal_codes == (f"{dimension.upper()}_INCOMPATIBLE",)
        passes = [r for r in receipt.dimensions if r.verdict == "PASS"]
        assert len(passes) == len(DIMENSIONS) - 1


def test_missing_dimension_stays_unknown_for_each_dimension():
    for dimension in DIMENSIONS:
        dimensions = {d: True for d in DIMENSIONS if d != dimension}
        receipt = qualify(contract(), candidate(dimensions=dimensions))
        assert receipt.standing is Standing.UNKNOWN
        assert receipt.refusal_codes == ()


# --- receipts: binding, tamper, stale subject, replay ---------------------------


def test_receipt_binds_evidence_so_swapped_evidence_changes_digest():
    # Hole on 66fae260: the receipt digest ignored evidence/authority/dimensions,
    # so two different submissions produced byte-identical receipts.
    first = qualify(contract(), candidate(evidence=("evidence:run-1",)))
    second = qualify(contract(), candidate(evidence=("evidence:run-2",)))
    assert first.standing is second.standing is Standing.QUALIFIED
    assert first.input_digest != second.input_digest
    assert first.receipt_digest != second.receipt_digest


def test_verify_receipt_detects_tamper():
    receipt = qualify(contract(), candidate())
    assert verify_receipt(receipt)
    forged = replace(receipt, standing=Standing.QUALIFIED, refusal_codes=())
    assert verify_receipt(forged)  # unchanged content: still valid
    refused = qualify(contract(), candidate(mutable=True))
    laundered = replace(refused, standing=Standing.QUALIFIED, refusal_codes=())
    assert not verify_receipt(laundered)
    widened = replace(receipt, confers_authority=True)
    assert not verify_receipt(widened)


def test_replay_of_same_subject_is_byte_identical():
    receipt = qualify(contract(), candidate())
    assert replay_refusals(contract(), candidate(), receipt) == ()


def test_replay_against_moved_subject_is_stale():
    receipt = qualify(contract(), candidate())
    moved = candidate(exact_subject_digest=SUBJECT_B)
    assert "STALE_SUBJECT" in replay_refusals(contract(), moved, receipt)


def test_replay_against_changed_evidence_is_mismatch():
    receipt = qualify(contract(), candidate())
    changed = candidate(evidence=("evidence:other-run",))
    assert replay_refusals(contract(), changed, receipt) == ("REPLAY_MISMATCH",)


def test_replay_of_tampered_receipt_is_refused_first():
    refused = qualify(contract(), candidate(mutable=True))
    laundered = replace(refused, standing=Standing.QUALIFIED, refusal_codes=())
    assert "RECEIPT_TAMPERED" in replay_refusals(
        contract(), candidate(mutable=True), laundered
    )


def test_replay_under_moved_contract_is_mismatch():
    receipt = qualify(contract(), candidate())
    moved_contract = contract(contract_digest=digest({"contract": "v2"}))
    codes = replay_refusals(moved_contract, candidate(), receipt)
    assert "REPLAY_MISMATCH" in codes


# --- frontier: reordering, duplicate delivery, conflicting ids -----------------


def test_frontier_is_invariant_under_every_reordering():
    candidates = (
        candidate(),
        candidate(candidate_id="sbb:b", exact_subject_digest=SUBJECT_B),
        candidate(candidate_id="sbb:c", exact_subject_digest=digest("c"), mutable=True),
    )
    baseline = frontier(contract(), candidates)
    for permutation in itertools.permutations(candidates):
        assert frontier(contract(), permutation) == baseline


def test_duplicate_delivery_of_identical_candidate_is_idempotent():
    once = frontier(contract(), (candidate(),))
    thrice = frontier(contract(), (candidate(), candidate(), candidate()))
    assert thrice == once


def test_conflicting_candidates_sharing_an_id_are_both_refused():
    impostor = candidate(exact_subject_digest=SUBJECT_B)
    receipts = frontier(contract(), (candidate(), impostor))
    assert len(receipts) == 2
    assert all(refused_with(r, "DUPLICATE_CANDIDATE_ID") for r in receipts)
    assert {r.exact_subject_digest for r in receipts} == {SUBJECT_A, SUBJECT_B}
    assert frontier(contract(), (impostor, candidate())) == receipts


def test_frontier_does_not_select():
    receipts = frontier(
        contract(),
        (candidate(), candidate(candidate_id="sbb:b", exact_subject_digest=SUBJECT_B)),
    )
    assert [r.standing for r in receipts] == [Standing.QUALIFIED, Standing.QUALIFIED]
    assert not any(r.confers_authority for r in receipts)
