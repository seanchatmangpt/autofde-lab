# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fresh adversarial falsifiers against `ConsequenceBoundary`'s replay/idempotency path
(`src/autofde_lab/sa2a/brce/boundary.py`), written by an independent qualification pass
under the lens: REPLAY AND IDEMPOTENCY, per `.claude/rules/level4-completion-law.md`'s
Mutation law -- for each named relation/identity, construct an otherwise-complete,
currently-valid episode and mutate exactly one identity, expecting refusal (or, where
actuation genuinely proceeds, expecting the resulting receipt chain to correctly
identify what was actually actuated).

These are DELIBERATELY DIFFERENT mutations from the ones already exercised elsewhere in
this repo:

  - `test_afde_2604_fresh_mutations_qualification.py` Mutation A (content-unbound
    admission reuse -- an admission-content-binding concern, not replay/idempotency),
    Mutation B (SAME actor substitutes a DIFFERENT action/target on a shared token --
    now defeated by the `REFUSED_TOKEN_ACTION_MISMATCH` check), and Mutation C
    (admission-gate bypass on `execute_admitted()` replay -- an admission-fencing
    concern, not a base `execute()` replay/idempotency concern).
  - `test_mutation_cross_court_identity.py` (grant_id/receipt cross-actor forgery via
    directly-constructed receipts bypassing the boundary entirely -- not a token-replay
    scenario through `ConsequenceBoundary.execute()` itself).

MUTATION D -- cross-actor idempotency-token reuse (receipt-reuse-across-actors):
  actor_a executes action/target under shared token T (real actuation, real receipt).
  actor_b -- a COMPLETELY DIFFERENT actor, holding their OWN, independent, validly
  registered `AuthorityGrant` for the EXACT SAME action/target -- then presents the SAME
  token T. `ConsequenceBoundary.execute()` Step 1's Mutation-B fix compares only
  `action_iri`/`target_resource` between the token's bound `PreparedReceipt` and the
  replaying envelope; it never compares `PreparedReceipt.actor_id` (a field that is
  recorded on every `PreparedReceipt` but is not read anywhere in the Step-1 replay
  path). The subsequent reauthorization call also independently succeeds, because
  actor_b really does hold a valid grant for this exact action/target. Nothing then
  stops actor_a's original cached `FinalReceipt` -- minted for actor_a's own
  actuation -- from being handed back to actor_b as `success=True`, without actor_b's
  own request ever being independently actuated or receipted under actor_b's own
  identity.

MUTATION E -- stale-PreparedReceipt action substitution across the prepared-but-not-yet-
  finalized window (timing-based): models a real crash/interruption between BRCE Step 4
  (`PreparedReceipt` durably committed) and Step 7 (`FinalReceipt` durably committed) --
  a state reachable in production whenever a process dies mid-actuation, and reproduced
  here, Chicago-style, by depositing a genuine `PreparedReceipt` directly onto the SAME
  real `DurableDiskReceiptStore` the boundary uses (exactly the durable artifact Step 4
  of a since-interrupted call would have left behind), with no `FinalReceipt` recorded.
  A second caller then replays the SAME token with a COMPLETELY DIFFERENT, independently
  authorized action2/target2. Because `existing_final is None` for this token,
  `execute()`'s ENTIRE Step-1 replay block (including the Mutation-B action-mismatch
  check) is skipped outright -- that check only runs when a FinalReceipt already
  exists. Step 4 then finds `existing_prep is not None` (the stale action1/target1
  receipt) and reuses it verbatim as `prepared_receipt`, while Step 5 actuates using the
  CURRENT envelope's `action_iri`/`target_resource` (action2/target2) -- so real,
  physical actuation of action2 proceeds, but the resulting `FinalReceipt`'s
  `prepared_receipt_digest` references a `PreparedReceipt` whose own content describes a
  DIFFERENT action (action1/target1). Zero Unreceipted Actuation is nominally satisfied
  (SOME durable receipt predates the call), but its CONTENT does not describe the
  actuation that occurred -- exactly the object-identity violation
  `.claude/rules/no-dual-bookkeeping.md` names ("ActuationClosed must reference the SAME
  Actuation that was opened"; "identity is explicit or it does not exist").

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant`.
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (genuine physical
  disk I/O) and a real `DurableDiskReceiptStore` -- the same real collaborators the
  fixing session's and the sibling qualification session's own tests use.
- A real `PreparedReceipt` dataclass instance (not a mock) is deposited directly onto
  the real store for Mutation E, modeling a genuine crash-recovery state -- this is a
  real durable artifact, not an interaction-verifying double.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
  file.

Each test asserts the SECURE/expected outcome. A PASS means the real code already
defeats that mutation. A FAIL is the real, verified gap -- the assertion failure
message and the real disk/receipt state are the falsifying evidence; this file does not
weaken any assertion to force a green result, and no fix is applied here (fresh
mutations are reported, not patched, per this qualification pass's own scope).
"""

from __future__ import annotations

import json
from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_TOKEN_ACTION_MISMATCH,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import PreparedReceipt, TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)


def _boundary(tmp_path: Path, name: str, broker: AuthorityBroker):
    journal = tmp_path / name / "journal.json"
    store = DurableDiskReceiptStore(tmp_path / name / "receipts")
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store
    )
    return boundary, actuator, store, journal


def _journal_records(journal: Path) -> list[dict]:
    if not journal.exists():
        return []
    return json.loads(journal.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Mutation D: cross-actor idempotency-token reuse (receipt-reuse-across-actors).
# ---------------------------------------------------------------------------


def test_mutation_d_cross_actor_token_reuse_hands_actor_a_receipt_to_actor_b(
    tmp_path: Path,
) -> None:
    """A token bound to actor_a's own executed actuation must never be honored for a
    DIFFERENT actor_b, even when actor_b is independently, validly granted for the
    exact same action/target -- actor_b presenting actor_a's token is not actor_b's own
    actuation, and handing back actor_a's receipt misrepresents whose consequence it is.

    AFDE-2604 fail-secure closure (this session): `ConsequenceBoundary.__init__`'s
    `require_admission` default flipped `False -> True`, so `_boundary()`'s bare-default
    construction now makes every `execute()` call here enforce the same admission gate
    `execute_admitted()` always has (`_enforce_admission_gate()`). Admission is
    INCIDENTAL to what Mutation D actually probes (cross-actor idempotency-token
    identity binding on the replay path, not the admission fence itself), so a real,
    valid, `Standing.ADMITTED` `AdmissionResult` -- explicitly binding `action` to
    `target` via the real `afl:targetResource` triple -- is wired onto BOTH envelopes
    below (same action/target for actor_a and actor_b, so the SAME admission applies to
    both), reaching the exact same actor-identity-binding code path this test has
    always exercised, rather than disabling the gate via `require_admission=False`.
    """
    actor_a = "urn:agent:fresh-mut-d-actor-a"
    actor_b = "urn:agent:fresh-mut-d-actor-b"
    action = "urn:action:fresh-mut-d:read-secret"
    target = "urn:resource:fresh-mut-d:secret-vault"
    token = "idemp-fresh-mut-d-shared-token"

    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        f"""
@prefix afl: <urn:autofde-lab:> .
<{action}> a afl:Action ;
    afl:targetResource <{target}> .
""",
        provenance_record={
            "issuer": "urn:issuer:fresh-mut-d",
            "timestamp": "2026-09-17T00:00:00Z",
        },
    )
    assert admitted.standing == Standing.ADMITTED

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-d-a",
            subject_id=actor_a,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-d-b",
            subject_id=actor_b,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_d", broker)

    first = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=action,
            target_resource=target,
            actor_id=actor_a,
            admission_result=admitted,
        )
    )
    assert first.success is True
    assert first.state == TerminalReceiptState.EXECUTED
    assert actuator.call_count == 1

    prepared = boundary.receipt_store.get_prepared(token)
    assert prepared is not None and prepared.actor_id == actor_a

    # MUTATION: a COMPLETELY DIFFERENT actor, independently and validly granted for the
    # exact SAME action/target, presents the SAME shared token. The SAME admission
    # (bound to the same action/target) is presented again -- admission is a property
    # of the candidate content, not of which actor is replaying the token, so a
    # legitimate replay from any actor for this exact action/target satisfies the same
    # admission gate; the actor-identity mismatch below is the check under test.
    second = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=action,
            target_resource=target,
            actor_id=actor_b,
            admission_result=admitted,
        )
    )

    assert second.success is False, (
        "MUTATION D SURVIVED: idempotency token "
        f"{token!r} -- bound at its first EXECUTED write to actor_id={actor_a!r} "
        f"(PreparedReceipt.actor_id={prepared.actor_id!r}) -- was replayed by a "
        f"COMPLETELY DIFFERENT actor_id={actor_b!r} for the exact same action/target, "
        f"and ConsequenceBoundary.execute() returned success={second.success!r} "
        f"state={second.state!r} handing back "
        f"final_receipt_digest={second.final_receipt.digest if second.final_receipt else None!r} "
        f"(identical to actor_a's original receipt digest "
        f"{first.final_receipt.digest!r}: "
        f"{second.final_receipt is not None and second.final_receipt.digest == first.final_receipt.digest}). "
        "actuator.call_count stayed at "
        f"{actuator.call_count} -- actor_b's own request was never independently "
        "actuated or receipted; actor_a's cached receipt was handed to actor_b solely "
        "because actor_b happens to hold an independent grant for the SAME "
        "action/target as the token's original bound identity. "
        "ConsequenceBoundary.execute() Step 1's Mutation-B fix "
        f"(REFUSED_TOKEN_ACTION_MISMATCH={REFUSED_TOKEN_ACTION_MISMATCH!r}) compares "
        "only action_iri/target_resource between the token's bound PreparedReceipt and "
        "the replaying envelope -- PreparedReceipt.actor_id is recorded on every "
        "PreparedReceipt but is never read anywhere in the Step-1 replay path, so no "
        "actor-identity binding is enforced on token replay at all."
    )


# ---------------------------------------------------------------------------
# Mutation E: stale-PreparedReceipt action substitution across the
# prepared-but-not-yet-finalized window (timing-based).
# ---------------------------------------------------------------------------


def test_mutation_e_stale_prepared_receipt_reused_across_action_substitution(
    tmp_path: Path,
) -> None:
    """Models a real crash/interruption between BRCE Step 4 (PreparedReceipt durably
    committed) and Step 7 (FinalReceipt durably committed): a genuine PreparedReceipt
    for action1/target1 is deposited directly onto the real DurableDiskReceiptStore
    (exactly the durable artifact a since-interrupted execute() call's own Step 4 would
    have left behind), with NO FinalReceipt recorded under that token. A caller then
    replays the SAME token with a COMPLETELY DIFFERENT, independently authorized
    action2/target2.

    A secure boundary must never actuate action2 while attaching it to a FinalReceipt
    whose prepared_receipt_digest references a PreparedReceipt describing a DIFFERENT
    action -- either the replay should be refused outright (no existing-final-receipt
    identity to compare against, so a secure implementation would need a DIFFERENT gate
    than the Mutation-B one to catch this), or, if actuation is allowed to proceed for
    the new action, the resulting FinalReceipt's referenced PreparedReceipt must
    actually describe THAT action/target.
    """
    actor = "urn:agent:fresh-mut-e-actor"
    action1 = "urn:action:fresh-mut-e:noop-log-rotate"
    target1 = "urn:resource:fresh-mut-e:log-archive"
    action2 = "urn:action:fresh-mut-e:wire-transfer"
    target2 = "urn:resource:fresh-mut-e:treasury"
    token = "idemp-fresh-mut-e-shared-token"

    broker = AuthorityBroker()
    # actor is independently, validly granted for action2/target2 only -- action1/target1
    # is never granted to this actor at all in THIS call graph, modeling that the stale
    # PreparedReceipt for action1 was durably committed by some PRIOR, since-interrupted
    # call whose own Step 2 authority check already ran and passed before the simulated
    # crash (irrelevant to reproduce here -- what matters is the STALE DURABLE ARTIFACT
    # left behind, not re-deriving how it got there).
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-e-action2",
            subject_id=actor,
            action_iri=action2,
            target_resource_iri=target2,
        )
    )
    boundary, actuator, store, journal = _boundary(tmp_path, "mut_e", broker)

    # Simulate the crash: a real, genuine PreparedReceipt for action1/target1 is already
    # durably committed under this token (Step 4 of a since-interrupted call), but no
    # FinalReceipt exists yet (Steps 5-7 never completed).
    stale_prepared = PreparedReceipt(
        prepared_id="prep-fresh-mut-e-stale",
        idempotency_token=token,
        action_iri=action1,
        target_resource=target1,
        actor_id=actor,
        grant_id="grant-fresh-mut-e-stale-action1",
        plan_digest="genesis:0" * 4,
        artifact_digest="none",
        admitted_input_digest="genesis:0" * 4,
        consequence_class="LOCAL_EFFECT",
    )
    store.save_prepared(stale_prepared)
    assert store.get_prepared(token) is not None
    assert store.get_final(token) is None, (
        "Precondition: this token must be in the real 'prepared, not yet finalized' "
        "crash-window state -- a durable PreparedReceipt exists, no FinalReceipt does."
    )

    # MUTATION: replay the SAME token, but this call presents a COMPLETELY DIFFERENT,
    # independently authorized action2/target2 (not action1/target1 the stale receipt
    # describes).
    result = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token, action_iri=action2, target_resource=target2, actor_id=actor
        )
    )

    records = _journal_records(journal)
    action2_actually_actuated = any(r.get("action") == action2 for r in records)
    action1_actually_actuated = any(r.get("action") == action1 for r in records)

    assert not action1_actually_actuated, (
        "action1 (the stale receipt's own action) must never be actuated by this call -- "
        f"it was never presented in this call's envelope. Journal records: {records!r}"
    )

    if not (result.success and action2_actually_actuated):
        # Refused outright, or actuated-but-not-observed-on-disk: not the mutation this
        # test targets (no receipt/actuation-identity mismatch to check). Record the
        # observed outcome for the record and stop here.
        return

    referenced_prepared = boundary.receipt_store.get_by_digest(
        result.final_receipt.prepared_receipt_digest
    )
    assert referenced_prepared is not None, (
        "MUTATION E SURVIVED (worse form): the FinalReceipt for a REAL, physically "
        f"actuated action2={action2!r} on target2={target2!r} references "
        f"prepared_receipt_digest={result.final_receipt.prepared_receipt_digest!r}, which "
        "does not resolve to ANY PreparedReceipt in the durable store at all."
    )
    assert (
        referenced_prepared.action_iri == action2
        and referenced_prepared.target_resource == target2
    ), (
        "MUTATION E SURVIVED: idempotency token "
        f"{token!r} had a stale, durably-committed PreparedReceipt for "
        f"action_iri={stale_prepared.action_iri!r}, target_resource="
        f"{stale_prepared.target_resource!r} (modeling a crash between BRCE Step 4 and "
        "Step 7), with NO FinalReceipt yet recorded. A replay of this SAME token with a "
        f"COMPLETELY DIFFERENT action_iri={action2!r}, target_resource={target2!r} "
        f"resulted in REAL physical actuation of action2 (journal record present: "
        f"{action2_actually_actuated!r}), yet the resulting FinalReceipt's "
        f"prepared_receipt_digest={result.final_receipt.prepared_receipt_digest!r} "
        "resolves back to the STALE PreparedReceipt describing "
        f"action_iri={referenced_prepared.action_iri!r}, target_resource="
        f"{referenced_prepared.target_resource!r} -- a DIFFERENT action than the one "
        "actually, physically actuated. ConsequenceBoundary.execute() Step 4 reuses "
        "`existing_prep` verbatim whenever `get_prepared(token) is not None`, regardless "
        "of whether its action_iri/target_resource match the CURRENT envelope, while "
        "Step 5 actuates using the CURRENT envelope's action_iri/target_resource -- so "
        "Zero Unreceipted Actuation is satisfied only in the sense that SOME durable "
        "receipt predates the call; that receipt's own content does not describe the "
        "actuation that occurred (no-dual-bookkeeping.md object-identity violation: "
        "'ActuationClosed must reference the SAME Actuation that was opened')."
    )
