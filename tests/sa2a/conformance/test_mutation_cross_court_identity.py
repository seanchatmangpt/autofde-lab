# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Cross-court identity mutation tests: Authority Court x Consequence Court
(RFC-SA2A-002 v26.9.16).

Per `.claude/rules/no-dual-bookkeeping.md`'s "Identity is explicit or it does not
exist" and "Object-centric conformance": a `PreparedReceipt`/`FinalReceipt`'s
`grant_id` field is a claim that a named `AuthorityGrant` authorized THIS EXACT
actuation identity (this `action_iri` + `target_resource` + `actor_id`). That claim
is a *relation*, not a label match -- carrying the same grant_id string on two
receipts whose action/target differ is a same-label-different-identity mismatch,
the exact class of defect `no-dual-bookkeeping.md` names: "Two artifacts... joined
only by explicit identity... Never reconstruct a relation afterwards... a relation
inferred post hoc is a guess wearing the costume of a join."

This file constructs exactly that scenario, spanning both courts read for this
task:

- `authority_court.py`'s `AuthorityCourt.verify_legitimate_grant_authorized` and a
  real `AuthorityBroker.evaluate()` call establish, as a positive control, that a
  registered `AuthorityGrant` G is scoped to ONE exact actuation identity
  (actor, action_iri, target_resource) -- and that the broker itself correctly
  REFUSES the same grant_id for a different actuation identity when asked
  honestly.
- `consequence_court.py`'s real `ConsequenceCourt` and BRCE receipt-layer
  collaborators (`PreparedReceipt`, `FinalReceipt`, `DurableDiskReceiptStore`,
  `ConsequenceBoundary`) are then used to show that a receipt CAN still be handed
  to the consequence side of the system claiming grant G authorized a *different*
  actuation identity than the one the broker actually authorized at the STORE
  layer (Test 1, unchanged) -- but that presenting that forged claim through the
  real `ConsequenceBoundary.execute()` path (Test 2, exercised via the Consequence
  Court's own public `audit_idempotency_replay_refusal` gate, plus a direct
  boundary call) is now independently re-evaluated against the real broker and
  refused, closing the gap this file originally found.

ORIGINAL GAP FINDING (this session's earlier pass, before the fix below):

    Neither `AuthorityCourt` nor `ConsequenceCourt` (nor the `ReceiptStore` /
    `PreparedReceipt` / `FinalReceipt` machinery `ConsequenceCourt` is built on)
    verifies that a receipt's self-asserted `grant_id` field is bound, via an
    explicit typed edge to a real `AuthorityDecision`, to THIS receipt's own
    `action_iri` + `target_resource` + `actor_id`. `ReceiptStore.save_prepared` /
    `save_final` accept and durably persist a receipt whose `grant_id` cites a
    grant that never authorized that receipt's actual action/target pair. And
    `ConsequenceBoundary.execute()`'s idempotency replay check (Step 1) keys
    *only* on `idempotency_token` -- once such a forged receipt sits in the store
    under a token, a real `boundary.execute()` call for that same token returns
    the forged receipt as a trusted cached success, with zero re-verification.

FIXED (AFDE-2604 local closure, this session) -- what changed and what did not:

    `ReceiptStore.save_prepared`/`save_final` (Test 1, below) are UNCHANGED and
    STILL accept the forged receipt with no cross-check -- that finding stands,
    deliberately: the store is an intentionally dumb, append-only persistence
    layer, and adding an authority-verification responsibility to it would be a
    much larger, non-additive redesign than this task's scope. What closes the
    gap is `ConsequenceBoundary.execute()` (Test 2, below): its Step 1
    idempotency-replay path no longer trusts a cached `EXECUTED` receipt (forged
    or genuine) at face value. Before returning it, the boundary now performs a
    FRESH `AuthorityBroker.evaluate()` call for the exact actuation identity of
    the REQUEST under audit (never the receipt's own self-asserted fields), and
    refuses (`REFUSED_REPLAY_NOT_REAUTHORIZED`) if that fresh check does not
    confirm authorization. So a forged receipt sitting in the store no longer
    grants its bearer anything: presenting it (via a request naming the forged
    identity) is now independently re-evaluated and, for this exact forged
    identity, correctly refused. `ConsequenceCourt.audit_idempotency_replay_refusal`
    (the court's own real public gate) still reports `GateVerdict.PASSED` for
    this scenario -- Test 2 keeps that assertion and explains precisely why it
    is correct, not a residual gap: that gate checks replay STABILITY (same
    call count, same digest across two identical replay attempts), which now
    holds because the boundary consistently and deterministically REFUSES the
    forged identity on every attempt, not because the forged claim is accepted.
    A new, direct assertion (added to Test 2) exercises `ConsequenceBoundary
    .execute()` itself to prove the underlying refusal, since `CourtGateResult`
    alone does not expose the underlying terminal state/refusal code.

Chicago Zero-Mock Standard:
- Real `AuthorityBroker` / `AuthorityGrant` / `ConsequenceRequest` instances (the
  same collaborators `test_court_authority.py` and `test_mutation_authority.py`
  use).
- Real `DurableDiskReceiptStore` performing genuine disk I/O under `tmp_path` (the
  same collaborator `test_court_consequence.py` uses).
- Real `AuthorityCourt` / `ConsequenceCourt` public methods -- the actual
  conformance-gate entry points, not reimplementations of their logic.
- The one adversarial step -- directly constructing a `PreparedReceipt` /
  `FinalReceipt` with a self-asserted `grant_id` and calling
  `ReceiptStore.save_prepared` / `save_final` on it -- is not a mock. It is the
  exact same construction path `ConsequenceBoundary.execute()` itself uses
  internally (see `src/autofde_lab/sa2a/brce/boundary.py`); this file simply
  performs it directly, the way a compromised or buggy upstream caller of the
  receipt store legitimately could, to test whether anything downstream catches
  the mismatch. No `unittest.mock`, `Mock`, `MagicMock`, `patch`, or
  `monkeypatch` appears anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    REFUSED_NO_GRANT,
    AuthorityBroker,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    TerminalReceiptState,
)
from autofde_lab.sa2a.conformance.courts.authority_court import AuthorityCourt
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
    ConsequenceCourt,
    DurableDiskReceiptStore,
    GateVerdict,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)

GENESIS = "genesis:0" * 4

# The exact actuation identity grant G is legitimately issued for.
LEGIT_ACTOR = "urn:agent:cluster-ops"
LEGIT_ACTION = "urn:action:quarantine_node"
LEGIT_TARGET = "urn:resource:cluster:node-1"

# A DIFFERENT actuation identity -- same actor, different action + target -- that
# the receipt evidence will falsely claim grant G authorized.
FORGED_ACTION = "urn:action:delete_all_data"
FORGED_TARGET = "urn:resource:cluster:node-99"


def _make_grant() -> AuthorityGrant:
    return AuthorityGrant(
        grant_id="grant-cross-court-001",
        subject_id=LEGIT_ACTOR,
        action_iri=LEGIT_ACTION,
        target_resource_iri=LEGIT_TARGET,
    )


# ---------------------------------------------------------------------------
# Test 1: the receipt store durably accepts a grant_id claim for an actuation
# identity the broker never authorized under that grant (unit-level).
# ---------------------------------------------------------------------------


def test_receipt_store_accepts_grant_id_claim_for_never_authorized_actuation_identity(
    tmp_path: Path,
) -> None:
    """`PreparedReceipt.grant_id` is accepted by the store with no cross-check
    against a real `AuthorityDecision` for that receipt's own action/target.

    Baseline (spans AuthorityCourt + real broker):
    1. Register grant G scoped to exactly (LEGIT_ACTOR, LEGIT_ACTION, LEGIT_TARGET).
    2. `AuthorityCourt.verify_legitimate_grant_authorized` confirms G really
       authorizes that one exact actuation identity (positive control).
    3. A direct `broker.evaluate()` call presenting grant_id=G for the DIFFERENT
       (FORGED_ACTION, FORGED_TARGET) identity is REFUSED with REFUSED_NO_GRANT --
       the broker itself correctly scopes G to one actuation identity when asked
       honestly.

    Attack (spans the BRCE receipt layer ConsequenceCourt is built on):
    4. A `PreparedReceipt` is constructed directly, citing grant_id=G.grant_id but
       action_iri/target_resource = FORGED_ACTION/FORGED_TARGET -- the identity
       the broker just refused for this grant.
    5. `receipt_store.save_prepared(...)` succeeds with no exception and no
       validation against the broker/grant registry.

    GAP (STORE-LAYER, still real and unchanged by the AFDE-2604 fix in this
    session -- see Test 2 below for what DID change): the durable receipt now
    stands as evidence that grant G authorized FORGED_ACTION/FORGED_TARGET,
    contradicting the real `AuthorityDecision` obtained in step 3, and nothing
    in `ReceiptStore.save_prepared` or `PreparedReceipt` construction rejects
    it. This remains true after the fix -- deliberately: `ReceiptStore` is an
    intentionally dumb, append-only persistence layer, and the fix instead
    closes the gap at the point of USE (`ConsequenceBoundary.execute()`, see
    Test 2), which is where an authority re-check actually belongs and where
    it makes a forged receipt inert regardless of whether the store itself
    ever validates what it is handed.
    """
    court = AuthorityCourt()
    broker = AuthorityBroker()
    grant = _make_grant()

    # 1 + 2: positive control -- G really authorizes its own exact identity.
    baseline = court.verify_legitimate_grant_authorized(broker, grant, fail_closed=True)
    assert baseline.passed is True
    assert baseline.decision is not None
    assert baseline.decision.authorized is True
    assert baseline.decision.grant_id == grant.grant_id

    # 3: the broker itself refuses grant G for the FORGED (different) identity.
    forged_request = ConsequenceRequest(
        actor_id=LEGIT_ACTOR,
        action_iri=FORGED_ACTION,
        target_resource=FORGED_TARGET,
        grant_id=grant.grant_id,
    )
    forged_decision = broker.evaluate(forged_request)
    assert forged_decision.authorized is False
    assert forged_decision.refusal_code == REFUSED_NO_GRANT

    # 4 + 5: directly construct and persist a receipt claiming grant G authorized
    # the FORGED identity anyway -- bypassing the broker entirely.
    store = DurableDiskReceiptStore(tmp_path / "receipts")
    token = "idemp-cross-court-forged-001"
    forged_prepared = PreparedReceipt(
        prepared_id="prep-forged-001",
        idempotency_token=token,
        action_iri=FORGED_ACTION,
        target_resource=FORGED_TARGET,
        actor_id=LEGIT_ACTOR,
        grant_id=grant.grant_id,  # <-- same-label-different-identity claim
        plan_digest=GENESIS,
        artifact_digest="none",
        admitted_input_digest=GENESIS,
        consequence_class="LOCAL_EFFECT",
        previous_receipt_digest=store.last_receipt_digest(),
    )
    store.save_prepared(forged_prepared)  # No exception: no cross-check performed.

    persisted = store.get_prepared(token)
    assert persisted is not None
    assert persisted.grant_id == grant.grant_id
    assert persisted.action_iri == FORGED_ACTION
    assert persisted.target_resource == FORGED_TARGET
    # The store durably holds a receipt whose grant_id claims authorization the
    # broker just refused for this exact (action, target) pair. This is the gap:
    # the receipt layer performs no join back to a real AuthorityDecision.


# ---------------------------------------------------------------------------
# Test 2: the Consequence Court's own real public gate, PLUS a direct boundary
# call proving the underlying fix (court-level and boundary-level, executable
# falsifiers).
# ---------------------------------------------------------------------------


def test_consequence_court_replay_gate_reports_conformant_for_mismatched_grant_claim(
    tmp_path: Path,
) -> None:
    """`ConsequenceCourt.audit_idempotency_replay_refusal` -- the real, public
    CHI-BRCE-04 gate -- against a forged receipt whose grant_id claim was, moments
    earlier in this same test, independently REFUSED by the real broker for that
    exact actuation identity.

    This is the decisive falsifier: it calls the actual court API named in the
    task (not a reimplementation of its checks), and the court's own verdict is
    the artifact under test -- PLUS a direct `ConsequenceBoundary.execute()` call
    (added this session) that exercises the underlying primitive `audit_*` gates
    are all built on, since `CourtGateResult` alone does not expose the terminal
    state/refusal code needed to see the fix directly.

    UPDATED (AFDE-2604 local closure, this session): `gate_result.verdict ==
    GateVerdict.PASSED` is UNCHANGED from the original pinning -- and that is
    correct, not a residual gap. `audit_idempotency_replay_refusal`'s PASSED
    verdict means "replaying this token is idempotent" (same actuator call count,
    same receipt digest across two identical replay attempts) -- it has never
    meant "the underlying claim was accepted as authorized," and
    `CourtGateResult` does not expose the underlying `state`/`refusal_code` at
    all. Pre-fix, PASSED reflected two IDENTICAL trusted-cache reads of the
    forged EXECUTED receipt (both attempts silently succeeded, so they were
    trivially stable). Post-fix, PASSED reflects two IDENTICAL, independently
    re-verified REFUSALS of the forged identity (both attempts are now correctly
    refused, and refused deterministically, so they are still stable) -- the gate
    stays PASSED throughout, for the opposite, now-correct, underlying reason.
    The new assertions below call `ConsequenceBoundary.execute()` directly to
    make that underlying reason -- REFUSED, not EXECUTED -- an explicit,
    verified fact rather than leaving it implicit in the gate's own scope.
    """
    court = AuthorityCourt()
    broker = AuthorityBroker()
    grant = _make_grant()
    court.verify_legitimate_grant_authorized(broker, grant, fail_closed=True)

    # Honest broker evaluation for the FORGED identity under grant G: REFUSED.
    honest_decision = broker.evaluate(
        ConsequenceRequest(
            actor_id=LEGIT_ACTOR,
            action_iri=FORGED_ACTION,
            target_resource=FORGED_TARGET,
            grant_id=grant.grant_id,
        )
    )
    assert honest_decision.authorized is False
    assert honest_decision.refusal_code == REFUSED_NO_GRANT

    # Construct a self-consistent forged Prepared+Final receipt pair -- internally
    # correct (FinalReceipt.prepared_receipt_digest really does bind the exact
    # PreparedReceipt.digest, isolating the one axis under test: the grant_id ->
    # actuation-identity binding, not receipt-chain integrity) -- claiming grant G
    # authorized the FORGED identity and that it EXECUTED successfully.
    store = DurableDiskReceiptStore(tmp_path / "receipts")
    token = "idemp-cross-court-forged-002"
    forged_prepared = PreparedReceipt(
        prepared_id="prep-forged-002",
        idempotency_token=token,
        action_iri=FORGED_ACTION,
        target_resource=FORGED_TARGET,
        actor_id=LEGIT_ACTOR,
        grant_id=grant.grant_id,
        plan_digest=GENESIS,
        artifact_digest="none",
        admitted_input_digest=GENESIS,
        consequence_class="LOCAL_EFFECT",
        previous_receipt_digest=store.last_receipt_digest(),
    )
    store.save_prepared(forged_prepared)

    forged_final = FinalReceipt(
        receipt_id="rec-forged-002",
        prepared_receipt_digest=forged_prepared.digest,
        idempotency_token=token,
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
        evidence={"claim": "grant authorized this actuation"},
    )
    store.save_final(forged_final)

    # Hand this evidence to the real, public ConsequenceCourt gate, naming the
    # SAME (grant-refused) FORGED actuation identity as the request under audit.
    consequence_court = ConsequenceCourt()
    gate_result = consequence_court.audit_idempotency_replay_refusal(
        broker=broker,
        receipt_store=store,
        journal_path=tmp_path / "journal.json",
        actor_id=LEGIT_ACTOR,
        action_iri=FORGED_ACTION,
        target_resource=FORGED_TARGET,
        parameters={},
        idempotency_token=token,
    )

    # --- The gate stays PASSED -- for the correct reason now (see docstring). ---
    # ConsequenceBoundary.execute()'s Step 1 idempotency-replay path still finds the
    # forged EXECUTED receipt under `token`, but no longer trusts it: it now performs
    # a fresh AuthorityBroker.evaluate() for the request's own actor/action/target
    # (ignoring the receipt's self-asserted grant_id) on EVERY call the gate makes,
    # deterministically refusing the forged identity both times -- so the replay is
    # still stable (same refusal, same digest, zero new actuation), which is exactly
    # what this gate checks.
    assert gate_result.gate_id == CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL
    assert gate_result.verdict == GateVerdict.PASSED, (
        f"Expected the gate to report PASSED (stable, idempotent REFUSAL of the "
        f"forged identity): {gate_result.reason}"
    )
    assert gate_result.passed is True
    assert gate_result.evidence.get("replayed_flag") is True

    # --- Direct proof of the underlying fix: a fresh ConsequenceBoundary.execute()
    # call for this exact forged identity is REFUSED, not EXECUTED. This is what
    # `CourtGateResult` alone cannot show. ---
    #
    # AFDE-2604 fail-secure closure (unrelated later session, this repo):
    # `ConsequenceBoundary.__init__`'s `require_admission` default flipped from
    # `False` to `True`, so `execute()` itself now applies the same admission
    # gate `execute_admitted()` always has (`_enforce_admission_gate()`), BEFORE
    # Step 1's idempotency-replay re-authorization check below is ever reached.
    # This test's own concern -- whether a forged, self-asserted `grant_id`
    # claim on a cached EXECUTED receipt can smuggle a never-authorized
    # actuation identity back out through a replay -- is orthogonal to the
    # admission fence: closing the admission-default gap does not, by itself,
    # close (or even touch) the receipt-forgery/replay-reauthorization gap this
    # file exists to falsify. So a real, valid, `Standing.ADMITTED`
    # `AdmissionResult` -- explicitly bound, via the real RDF triple
    # `<FORGED_ACTION> afl:targetResource <FORGED_TARGET> .`, to the EXACT
    # forged identity under audit -- is constructed and wired onto the
    # envelope below, so this call reaches the SAME `REFUSED_REPLAY_
    # NOT_REAUTHORIZED` code path it always tested, rather than being
    # short-circuited earlier by `REFUSED_NOT_ADMITTED`. Verified below: the
    # original finding (a fresh boundary call for the forged identity is
    # refused, not executed) still reproduces once admission is honestly
    # satisfied -- the admission fence and the replay-reauthorization fence are
    # two independent, additive gates, not substitutes for one another.
    forged_identity_admission = AdmissionPipeline().admit(
        "@prefix afl: <urn:autofde-lab:> .\n"
        f"<{FORGED_ACTION}> afl:targetResource <{FORGED_TARGET}> .",
        provenance_record={
            "issuer": "urn:issuer:test-mutation-cross-court-identity",
            "timestamp": "2026-09-17T00:00:00Z",
        },
    )
    assert forged_identity_admission.standing == Standing.ADMITTED, (
        "Precondition: the admission itself must genuinely succeed so that any "
        "subsequent refusal below is attributable to the replay-reauthorization "
        "gate under test, never to a failed admission precondition."
    )

    direct_boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=RealDiskJournalActuator(tmp_path / "direct_journal.json"),
        verifier=IndependentDiskJournalVerifier(tmp_path / "direct_journal.json"),
        receipt_store=store,  # the SAME store already holding the forged receipt
    )
    direct_result = direct_boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=FORGED_ACTION,
            target_resource=FORGED_TARGET,
            actor_id=LEGIT_ACTOR,
            parameters={},
            admission_result=forged_identity_admission,
        )
    )
    assert direct_result.success is False, (
        "AFDE-2604 fix: a fresh ConsequenceBoundary.execute() call for the forged "
        "identity must be refused, not report success -- the durably-stored forged "
        "EXECUTED receipt must never be handed back as a trusted result."
    )
    assert direct_result.state == TerminalReceiptState.REFUSED
    assert direct_result.refusal_code == "REFUSED_REPLAY_NOT_REAUTHORIZED"
    assert direct_result.final_receipt is not None
    assert direct_result.final_receipt.digest != forged_final.digest, (
        "The refusal must never reuse the forged receipt's own digest as if it were "
        "a legitimate cached response."
    )

    # The combined evidence (forged receipt + grant claim) IS now rejected the moment
    # anything asks the real ConsequenceBoundary about this actuation identity again --
    # closing the gap this file originally found. The durably-persisted forged receipt
    # itself is unchanged (Test 1's finding stands at the store layer), but it is
    # inert: presenting it never again yields a trusted EXECUTED outcome.
