"""Category, type-confusion and frontier-replay falsifiers for the ABB -> SBB court.

Chicago style: every test drives the real ``qualify``/``frontier``/``replay_refusals``/
``verify_receipt``/``prior_art_disposition`` functions with real frozen dataclasses and
asserts on returned receipts. No test double is used; the court has no collaborators.

Holes guarded here were observed by the PR #203 audit at head 0dcf14c9:

* vendor-as-ABB / Pack-as-EA: a candidate whose exact subject IS the ABB or the
  contract qualified, and no kind model existed (charter DoD 4);
* equivalence laundering: one exact subject submitted under two candidate ids;
* type confusion: evidence="e:1" qualified as three characters; unhashable evidence,
  non-mapping dimensions, unhashable authority and object() values raised TypeError;
* a frontier-issued DUPLICATE_CANDIDATE_ID receipt could never replay;
* prior-art receipts ignored the findings that chose the route;
* verify_receipt's confers_authority check had no killing test (mutant M08).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from autofde_lab.enterprise_architecture import (
    DIMENSIONS,
    ArchitectureContract,
    CandidateSBB,
    Standing,
    digest,
    frontier,
    prior_art_disposition,
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


def test_default_kind_is_sbb_and_still_qualifies():
    receipt = qualify(contract(), candidate())
    assert candidate().kind == "SBB"
    assert receipt.standing is Standing.QUALIFIED
    assert receipt.frontier_refusals == ()


# --- vendor-as-ABB ---------------------------------------------------------------


def test_subject_equal_to_the_abb_is_vendor_as_abb():
    receipt = qualify(contract(), candidate(exact_subject_digest=ABB))
    assert refused_with(receipt, "VENDOR_AS_ABB")


@pytest.mark.parametrize("kind", ["VENDOR", "PRODUCT", "ABB"])
def test_vendor_kinds_are_vendor_as_abb(kind):
    receipt = qualify(contract(), candidate(kind=kind))
    assert refused_with(receipt, "VENDOR_AS_ABB")
    assert "UNKNOWN_KIND" not in receipt.refusal_codes


# --- Pack-as-EA ------------------------------------------------------------------


def test_subject_equal_to_the_contract_is_pack_as_ea():
    receipt = qualify(contract(), candidate(exact_subject_digest=CONTRACT))
    assert refused_with(receipt, "PACK_AS_EA")


@pytest.mark.parametrize("kind", ["PACK", "CONTRACT", "EA"])
def test_pack_kinds_are_pack_as_ea(kind):
    receipt = qualify(contract(), candidate(kind=kind))
    assert refused_with(receipt, "PACK_AS_EA")


def test_contract_that_is_its_own_abb_is_pack_as_ea():
    conflated = contract(contract_digest=ABB)
    receipt = qualify(conflated, candidate(contract_digest=ABB))
    assert refused_with(receipt, "PACK_AS_EA")


@pytest.mark.parametrize("kind", ["sbb", "", None, ["SBB"], 1])
def test_unknown_kind_fails_closed(kind):
    receipt = qualify(contract(), candidate(kind=kind))
    assert refused_with(receipt, "UNKNOWN_KIND")


# --- equivalence laundering --------------------------------------------------------


def test_one_subject_under_two_ids_is_refused_as_aliased():
    alias = candidate(candidate_id="sbb:alias")
    receipts = frontier(contract(), (candidate(), alias))
    assert len(receipts) == 2
    assert all(refused_with(r, "SUBJECT_ALIASED") for r in receipts)
    assert all(r.frontier_refusals == ("SUBJECT_ALIASED",) for r in receipts)


def test_distinct_subjects_under_distinct_ids_are_not_aliased():
    b = candidate(candidate_id="sbb:b", exact_subject_digest=SUBJECT_B)
    receipts = frontier(contract(), (candidate(), b))
    assert [r.standing for r in receipts] == [Standing.QUALIFIED] * 2


# --- type confusion never raises and never qualifies --------------------------------


@pytest.mark.parametrize("evidence", ["e:1", "aa", b"e:1", 7, {"e:1"}])
def test_non_sequence_evidence_is_malformed_not_split(evidence):
    receipt = qualify(contract(), candidate(evidence=evidence))
    assert refused_with(receipt, "MALFORMED_EVIDENCE")
    assert "DUPLICATE_EVIDENCE" not in receipt.refusal_codes


def test_none_evidence_is_missing():
    assert refused_with(
        qualify(contract(), candidate(evidence=None)), "MISSING_EVIDENCE"
    )


@pytest.mark.parametrize("evidence", [(["x"],), ({"x": 1},), (1,), ("ok", None)])
def test_unhashable_or_non_string_evidence_entry_is_malformed(evidence):
    receipt = qualify(contract(), candidate(evidence=evidence))
    assert refused_with(receipt, "MALFORMED_EVIDENCE")


@pytest.mark.parametrize("dimensions", [None, list(DIMENSIONS), "semantic", 3])
def test_non_mapping_dimensions_is_malformed(dimensions):
    receipt = qualify(contract(), candidate(dimensions=dimensions))
    assert refused_with(receipt, "MALFORMED_DIMENSION")
    assert all(r.verdict == "UNKNOWN" for r in receipt.dimensions)


def test_mixed_type_dimension_keys_are_undeclared():
    dimensions = {dimension: True for dimension in DIMENSIONS}
    dimensions[1] = True
    receipt = qualify(contract(), candidate(dimensions=dimensions))
    assert refused_with(receipt, "UNDECLARED_DIMENSION")


def test_object_dimension_value_is_malformed_and_digestible():
    dimensions = {dimension: True for dimension in DIMENSIONS}
    dimensions["effect"] = object()
    first = qualify(contract(), candidate(dimensions=dimensions))
    dimensions["effect"] = object()
    second = qualify(contract(), candidate(dimensions=dimensions))
    assert refused_with(first, "MALFORMED_DIMENSION")
    # Digest is by type name, never by memory address: deterministic.
    assert first.receipt_digest == second.receipt_digest


def test_unhashable_candidate_authority_is_unknown():
    receipt = qualify(contract(), candidate(authority=["DO"]))
    assert refused_with(receipt, "UNKNOWN_AUTHORITY")


def test_unhashable_contract_ceiling_is_invalid():
    receipt = qualify(contract(authority_ceiling=["DO"]), candidate(authority="NONE"))
    assert refused_with(receipt, "CONTRACT_CEILING_INVALID")


def test_non_string_digest_is_malformed():
    receipt = qualify(contract(), candidate(exact_subject_digest=12345))
    assert refused_with(receipt, "MALFORMED_DIGEST")


# --- frontier receipts replay -------------------------------------------------------


def test_duplicate_candidate_id_receipt_replays_from_its_own_record():
    impostor = candidate(exact_subject_digest=SUBJECT_B)
    receipts = frontier(contract(), (candidate(), impostor))
    by_subject = {r.exact_subject_digest: r for r in receipts}
    base_receipt = by_subject[SUBJECT_A]
    assert base_receipt.frontier_refusals == ("DUPLICATE_CANDIDATE_ID",)
    assert replay_refusals(contract(), candidate(), base_receipt) == ()
    assert replay_refusals(contract(), impostor, by_subject[SUBJECT_B]) == ()


def test_frontier_receipt_replays_against_the_full_frontier_set():
    impostor = candidate(exact_subject_digest=SUBJECT_B)
    frontier_set = (candidate(), impostor)
    receipt = {r.exact_subject_digest: r for r in frontier(contract(), frontier_set)}[
        SUBJECT_A
    ]
    assert replay_refusals(contract(), candidate(), receipt, frontier_set) == ()
    # Against a frontier where the conflict is gone the receipt no longer replays.
    assert replay_refusals(contract(), candidate(), receipt, (candidate(),)) == (
        "REPLAY_MISMATCH",
    )


def test_stripping_frontier_codes_from_a_receipt_is_detected():
    impostor = candidate(exact_subject_digest=SUBJECT_B)
    receipt = {
        r.exact_subject_digest: r for r in frontier(contract(), (candidate(), impostor))
    }[SUBJECT_A]
    stripped = replace(receipt, frontier_refusals=())
    assert not verify_receipt(stripped)
    assert "RECEIPT_TAMPERED" in replay_refusals(contract(), candidate(), stripped)


def test_frontier_codes_outside_the_vocabulary_fail_integrity():
    receipt = qualify(contract(), candidate())
    injected = replace(receipt, frontier_refusals=("ANYTHING",), receipt_digest="")
    injected = replace(injected, receipt_digest=digest(injected))
    assert not verify_receipt(injected)


# --- verify_receipt: authority and integrity-vs-authenticity ------------------------


def test_recomputed_digest_cannot_make_a_receipt_confer_authority():
    # Kills mutant M08 (verify_receipt ignoring confers_authority): the widened
    # receipt's digest is recomputed, so only the explicit check refuses it.
    receipt = qualify(contract(), candidate())
    widened = replace(receipt, confers_authority=True, receipt_digest="")
    widened = replace(widened, receipt_digest=digest(widened))
    assert not verify_receipt(widened)
    assert "RECEIPT_TAMPERED" in replay_refusals(contract(), candidate(), widened)


def test_integrity_is_not_authenticity_replay_catches_recomputed_forgery():
    refused = qualify(contract(), candidate(mutable=True))
    forged = replace(
        refused, standing=Standing.QUALIFIED, refusal_codes=(), receipt_digest=""
    )
    forged = replace(forged, receipt_digest=digest(forged))
    assert verify_receipt(forged)  # unkeyed digest: integrity only, documented
    assert replay_refusals(contract(), candidate(mutable=True), forged) == (
        "REPLAY_MISMATCH",
    )


# --- prior-art decision receipt ----------------------------------------------------


def test_prior_art_receipt_binds_the_findings_not_only_the_route():
    narrow = prior_art_disposition(reusable=True, composable=False, extendable=False)
    wide = prior_art_disposition(reusable=True, composable=True, extendable=True)
    assert narrow[0] == wide[0] == "REUSE"
    assert narrow[1] != wide[1]
    assert narrow == prior_art_disposition(
        reusable=True, composable=False, extendable=False
    )


@pytest.mark.parametrize("value", [1, "yes", None])
def test_non_bool_prior_art_finding_is_unknown_not_invent(value):
    route, _ = prior_art_disposition(reusable=value, composable=False, extendable=False)
    assert route == "UNKNOWN"
