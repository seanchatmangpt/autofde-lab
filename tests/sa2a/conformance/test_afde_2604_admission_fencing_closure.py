# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composed admission-fencing closure fixture for AFDE-2604 (RFC-SA2A-001/002 v26.9.16).

Local instantiation of the remote `ash_a2a` ticket A2A-2604 ("wire semantic admission
into the live consequence path"), scoped per
`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md` and
`.claude/rules/ecosystem-boundary.md`: this exercises only this repo's in-repo
`sa2a/` RFC-SA2A-001/002 conformance testbed (a local, self-contained implementation
of admission/authority/BRCE used to falsify this repo's own laws). It is not `mfw`'s
ecosystem admission/broker, and nothing here is a cross-repo/ecosystem standing claim.

This is a genuine END-TO-END composition -- not one court exercised in isolation. A
single test drives the real `AdmissionCourt` (wrapping the real `AdmissionPipeline`),
the real `AuthorityCourt` (wrapping the real `AuthorityBroker`), and the real
`ConsequenceBoundary` (the same primitive the real `ConsequenceCourt`'s own gates are
built on -- see `consequence_court.py`'s `audit_*` methods, each of which constructs a
fresh `ConsequenceBoundary` the same way this file does) together, and asserts the
COMPOSED law directly, per the task:

    (a) an admitted-but-not-yet-authorized candidate is refused before it can reach
        `ConsequenceBoundary.execute()`'s actuation step;
    (b) an authorized-but-never-admitted candidate is refused before DO;
    (c) a valid AuthorityGrant for the same actuation identity must not repair or
        bypass a REFUSED admission outcome (AFDE-2604 Required Change #4).

ORIGINAL RESULT (this session's earlier pass, before the fix below): the composed law
did NOT hold. `law_held = False`. Part (a) closed under real composition
(`ConsequenceBoundary.execute()` unconditionally evaluates `AuthorityBroker.evaluate()`
before any actuation, for every envelope). Part (b) did NOT close, and this file
established -- as a real state-based fact, not narration -- that `ExecutionEnvelope`,
the sole input type `ConsequenceBoundary.execute()` accepted, carried no field able to
bind an actuation attempt to any `AdmissionResult` produced by
`AdmissionPipeline.admit()`: the gap was at the INTERFACE level, not a call this test
could route around.

FIXED (AFDE-2604 local closure, THIS session) -- `law_held = True` now:

  - `ExecutionEnvelope` gained a new, additive, optional
    `admission_result: Optional[AdmissionResult] = None` field
    (`src/autofde_lab/sa2a/brce/boundary.py`). Existing callers that never pass it are
    completely unaffected.
  - A new, strict, opt-in entry point, `ConsequenceBoundary.execute_admitted(envelope)`,
    refuses (typed `REFUSED_NOT_ADMITTED`, never a bare exception) any envelope whose
    `admission_result` is missing or not `Standing.ADMITTED`, BEFORE
    `AuthorityBroker.evaluate()` or actuation are ever reached. `execute()` itself is
    completely unchanged -- `execute_admitted()` is a new wrapper, not a modification of
    its contract.
  - Part (b) below now drives the real, refused `AdmissionResult` from
    `AdmissionCourt.pipeline.admit()` onto the envelope and calls
    `execute_admitted()` instead of `execute()`: the composed system now genuinely
    REFUSES the authorized-but-never-admitted candidate before DO, with zero
    actuation and zero disk mutation -- closing AFDE-2604 Laws #1 and #3 and Chicago
    falsifier #2 in their correct (refusing) form, under the same genuine
    three-court composition this file always used.
  - Part (c) (new) proves Required Change #4 directly: presenting the SAME valid,
    independently-authorized `AuthorityGrant` a second time for the SAME refused
    candidate does not repair or bypass the refusal -- the admission gate in
    `execute_admitted()` is checked unconditionally, before authority is ever
    consulted, so a grant has no code path that can route around it.

Per the task's own instruction: `src/autofde_lab/sa2a/brce/boundary.py` (the
`ExecutionEnvelope`/`ConsequenceBoundary.execute()` surface this ticket names) WAS
modified this session to close this gap -- additively, per the fields/entry-point
design above. No other court/boundary source in `src/autofde_lab/sa2a/` was touched by
this specific fix.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AdmissionCourt` (real `AdmissionPipeline`, real ShEx/SHACL/SPARQL-falsifier
  validators as configured by that court's own constructor).
- Real `AuthorityCourt` (real `AuthorityBroker`, real `AuthorityGrant` registration
  and evaluation via the court's own public `verify_legitimate_grant_authorized`
  gate -- not a reimplementation of its logic).
- Real `ConsequenceBoundary` with real `RealDiskJournalActuator` /
  `IndependentDiskJournalVerifier` (genuine physical disk I/O, the same real
  collaborators `test_mutation_consequence.py` and `test_mutation_cross_court_identity.py`
  use) and a real `DurableDiskReceiptStore`.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
  this file.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from autofde_lab.sa2a.admission import REFUSED_PARSE_FAILURE
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    REFUSED_NO_GRANT,
    AuthorityBroker,
    AuthorityGrant,
)
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_NOT_ADMITTED,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.admission_court import AdmissionCourt
from autofde_lab.sa2a.conformance.courts.authority_court import AuthorityCourt
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)

# The exact interface-level field set `ConsequenceBoundary.execute()`'s sole input
# type accepts, per `src/autofde_lab/sa2a/brce/boundary.py`, confirmed by reading that
# source this session. UPDATED (AFDE-2604 fix, this session): `admission_result` is now
# present -- the additive field that closes the interface-level gap this constant
# originally documented the ABSENCE of.
_EXECUTION_ENVELOPE_FIELD_NAMES = frozenset(
    {
        "idempotency_token",
        "action_iri",
        "target_resource",
        "actor_id",
        "parameters",
        "consequence_class",
        "grant_id",
        "plan_digest",
        "artifact",
        "construction_receipt",
        "admitted_semantics",
        "admission_result",
    }
)


def test_composed_admission_authority_consequence_fence(tmp_path: Path) -> None:
    """Compose admission_court + authority_court + ConsequenceBoundary end to end.

    See module docstring for the full result (law_held = True, post-fix). Three
    independent scenarios below share no idempotency token, actor, action, target,
    broker, or disk path -- each is a fully isolated, self-contained composed episode.
    """
    admission_court = AdmissionCourt()
    authority_court = AuthorityCourt()

    # =================================================================================
    # Part (a): admitted-but-not-yet-authorized is refused before ConsequenceBoundary
    # can reach actuation. Uses the exact "legit_ttl" shape already proven to reach
    # Standing.ADMITTED under AdmissionCourt's real, default identity/ShEx/SHACL
    # policy in test_court_admission.py::test_admission_court_zero_mock_consequence_gating.
    # =================================================================================
    admitted_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:afde_2604_part_a a afl:Action ;
        afl:actionId "afde-2604-part-a"^^xsd:string ;
        afl:targetResource afl:disk_target .
    """
    admitted_result = admission_court.pipeline.admit(
        admitted_ttl,
        provenance_record={
            "issuer": "urn:issuer:trusted-authority",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )
    assert admitted_result.is_admitted is True
    assert admitted_result.standing == Standing.ADMITTED
    assert admitted_result.receipt.standing == Standing.ADMITTED

    # Deliberately empty broker: zero grants, zero policies registered anywhere.
    unauthorized_broker = AuthorityBroker()

    a_journal = tmp_path / "part_a" / "journal.json"
    a_actuator = RealDiskJournalActuator(a_journal)
    a_verifier = IndependentDiskJournalVerifier(a_journal)
    a_receipt_store = DurableDiskReceiptStore(tmp_path / "part_a" / "receipts")
    a_boundary = ConsequenceBoundary(
        authority_broker=unauthorized_broker,
        actuator=a_actuator,
        verifier=a_verifier,
        receipt_store=a_receipt_store,
    )

    a_actor = "urn:agent:afde-2604-unauthorized-worker"
    a_action = "urn:action:afde-2604:admitted-no-authority"
    a_target = "urn:resource:afde-2604:admitted-no-authority-target"
    a_envelope = ExecutionEnvelope(
        idempotency_token="idemp-afde-2604-part-a",
        action_iri=a_action,
        target_resource=a_target,
        actor_id=a_actor,
        parameters={"admitted_graph_digest": admitted_result.digest or ""},
    )
    a_result = a_boundary.execute(a_envelope)

    assert a_result.success is False, (
        "Part (a) composed-law check: an admitted-but-unauthorized actuation attempt "
        "must be refused before DO."
    )
    assert a_result.state == TerminalReceiptState.REFUSED
    assert a_result.refusal_code == REFUSED_NO_GRANT
    assert a_actuator.call_count == 0, "Actuator must never be invoked for an unauthorized request."
    assert a_journal.exists() is False, "Zero disk mutation for an unauthorized request."
    assert a_result.final_receipt is not None
    assert a_result.final_receipt.state == TerminalReceiptState.REFUSED

    # =================================================================================
    # Part (b): authorized-but-never-admitted. The candidate content below is the
    # exact non-RDF payload from this session's earlier repro
    # (scratchpad/afde2604_repro.py, cited in AFDE-2604-admission-fencing-local-
    # closure.md), driven here through the real AdmissionCourt/AdmissionPipeline
    # instead of a standalone script.
    # =================================================================================
    never_admitted_candidate = "the sky is blue and this sentence is not RDF in any serialization"
    refused_result = admission_court.pipeline.admit(never_admitted_candidate)

    assert refused_result.is_admitted is False
    assert refused_result.standing == Standing.REFUSED
    assert refused_result.refusal_code == REFUSED_PARSE_FAILURE
    assert refused_result.receipt.standing == Standing.REFUSED

    b_actor = "urn:agent:afde-2604-authorized-worker"
    b_action = "urn:action:afde-2604:authorized-never-admitted"
    b_target = "urn:resource:afde-2604:authorized-never-admitted-target"
    grant = AuthorityGrant(
        grant_id="grant-afde-2604-part-b",
        subject_id=b_actor,
        action_iri=b_action,
        target_resource_iri=b_target,
    )

    # Compose the real AuthorityCourt (not the raw broker) as the task instructs:
    # this is the court's own public positive-control gate, confirming this exact
    # actuation identity really is authorized -- a genuine, independent result, not
    # a reimplementation of AuthorityBroker.evaluate()'s logic.
    authorized_broker = AuthorityBroker()
    grant_check = authority_court.verify_legitimate_grant_authorized(
        authorized_broker, grant, fail_closed=True
    )
    assert grant_check.passed is True
    assert grant_check.decision is not None
    assert grant_check.decision.authorized is True
    assert grant_check.decision.grant_id == grant.grant_id

    # Interface-level state check: the sole input type ConsequenceBoundary.execute()
    # accepts now DOES carry a field that binds this actuation attempt to
    # refused_result. UPDATED: `admission_result` exists (AFDE-2604 fix, additive).
    envelope_field_names = frozenset(f.name for f in dataclasses.fields(ExecutionEnvelope))
    assert envelope_field_names == _EXECUTION_ENVELOPE_FIELD_NAMES
    assert "admission_result" in envelope_field_names, (
        "AFDE-2604 fix: ExecutionEnvelope must carry a field able to bind a real "
        "admission.pipeline.AdmissionResult to this actuation attempt."
    )

    b_journal = tmp_path / "part_b" / "journal.json"
    b_actuator = RealDiskJournalActuator(b_journal)
    b_verifier = IndependentDiskJournalVerifier(b_journal)
    b_receipt_store = DurableDiskReceiptStore(tmp_path / "part_b" / "receipts")
    b_boundary = ConsequenceBoundary(
        authority_broker=authorized_broker,
        actuator=b_actuator,
        verifier=b_verifier,
        receipt_store=b_receipt_store,
    )
    b_envelope = ExecutionEnvelope(
        idempotency_token="idemp-afde-2604-part-b",
        action_iri=b_action,
        target_resource=b_target,
        actor_id=b_actor,
        parameters={"never_admitted_candidate_digest": refused_result.receipt.candidate_digest},
        # AFDE-2604 fix: the real, REFUSED AdmissionResult for this exact candidate is
        # bound directly onto the envelope -- the fix under test.
        admission_result=refused_result,
    )
    # AFDE-2604 fix: the new strict entry point, not the original execute(). This is
    # the composed law's actual enforcement point.
    b_result = b_boundary.execute_admitted(b_envelope)

    # =================================================================================
    # FIXED behavior, asserted as the real, current (correct) composed outcome.
    # Composing admission_court + authority_court + ConsequenceBoundary.execute_admitted
    # together now DOES refuse this request before DO.
    # =================================================================================
    assert b_result.success is False, (
        "AFDE-2604 fix: the composed system must REFUSE an authorized-but-never-"
        "admitted actuation attempt before DO."
    )
    assert b_result.state == TerminalReceiptState.REFUSED, (
        "AFDE-2604 fix: a typed non-EXECUTED/refusal terminal state is required for a "
        "candidate the real AdmissionCourt independently refused."
    )
    assert b_result.refusal_code == REFUSED_NOT_ADMITTED, (
        "AFDE-2604 fix: the typed refusal code must name exactly why -- the bound "
        "AdmissionResult was not Standing.ADMITTED."
    )
    assert b_actuator.call_count == 0, (
        "AFDE-2604 fix: the real actuator must NEVER be invoked for a candidate "
        "admission independently refused."
    )
    assert b_journal.exists() is False, (
        "AFDE-2604 fix: zero disk mutation for a never-admitted candidate."
    )
    assert b_result.final_receipt is not None
    assert b_result.final_receipt.state == TerminalReceiptState.REFUSED
    assert b_result.final_receipt.refusal_code == REFUSED_NOT_ADMITTED
    assert b_result.final_receipt.postcondition_verified is False, (
        "No postcondition can be verified for an actuation that never happened."
    )

    # =================================================================================
    # Part (c): Required Change #4 -- a valid AuthorityGrant must not repair or bypass
    # a REFUSED admission outcome for the same candidate. Present the SAME grant_check
    # -confirmed authority a second time, for the SAME refused candidate, through a
    # fresh boundary sharing the same authorized_broker -- proving the admission gate
    # is unconditional, not merely "not yet routed around."
    # =================================================================================
    c_journal = tmp_path / "part_c" / "journal.json"
    c_actuator = RealDiskJournalActuator(c_journal)
    c_verifier = IndependentDiskJournalVerifier(c_journal)
    c_receipt_store = DurableDiskReceiptStore(tmp_path / "part_c" / "receipts")
    c_boundary = ConsequenceBoundary(
        authority_broker=authorized_broker,  # the SAME real, independently-authorized broker
        actuator=c_actuator,
        verifier=c_verifier,
        receipt_store=c_receipt_store,
    )
    c_envelope = ExecutionEnvelope(
        idempotency_token="idemp-afde-2604-part-c-grant-cannot-repair-refusal",
        action_iri=b_action,
        target_resource=b_target,
        actor_id=b_actor,
        grant_id=grant.grant_id,  # explicitly presenting the valid grant_id this time
        admission_result=refused_result,  # the SAME REFUSED admission outcome
    )
    c_result = c_boundary.execute_admitted(c_envelope)

    assert c_result.success is False, (
        "AFDE-2604 Required Change #4: a valid AuthorityGrant for the same actuation "
        "identity must not repair or bypass a REFUSED admission outcome."
    )
    assert c_result.refusal_code == REFUSED_NOT_ADMITTED, (
        "The refusal must remain the admission fence's own code -- proving the gate "
        "was checked (and refused) BEFORE authority/grant_id was ever consulted, not "
        "that authority itself happened to also refuse."
    )
    assert c_actuator.call_count == 0
    assert c_journal.exists() is False

    # =================================================================================
    # Composed-law verdict, stated as a single explicit fact this test establishes:
    # law_held = True. Both halves of the composed law now hold under a genuine
    # three-court composition, and a valid grant cannot repair a refused admission.
    # =================================================================================
    law_held = (a_result.success is False) and (b_result.success is False) and (c_result.success is False)
    assert law_held is True, (
        "AFDE-2604 composed law now holds: part (a) admitted-but-unauthorized IS "
        "refused before DO, part (b) authorized-but-never-admitted IS refused before "
        "DO, and part (c) a valid grant cannot repair/bypass a refused admission -- "
        "all three under a genuine three-court composition, not merely a single-"
        "boundary repro."
    )
