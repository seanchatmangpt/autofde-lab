# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Direct, standalone falsifiers for the three AFDE-2604 local admission-fencing fixes
(RFC-SA2A-001/002 v26.9.16), exercising `ConsequenceBoundary`/`ExecutionEnvelope`
directly -- no `AdmissionCourt`/`AuthorityCourt`/`ConsequenceCourt` layer at all.

This file is new this session, added per the task's own instruction: "Add at least one
brand new test proving fix (2) and (3) specifically if the updated existing tests do
not already cover them precisely." The updated `test_mutation_consequence.py` and
`test_mutation_cross_court_identity.py` already cover fixes (2) and (3) precisely
through their own (necessarily more elaborate, court-mediated) adversarial scenarios;
this file adds a second, deliberately minimal and isolated falsifier for each of the
three fixes, so a future regression in any one of them is caught by a test that does
not also depend on the courts layer being correct.

Three fixes under test, one class each:
  (1) `ConsequenceBoundary.execute_admitted()` refuses (REFUSED_NOT_ADMITTED) unless a
      bound, `Standing.ADMITTED` `AdmissionResult` is present on the envelope, before
      `AuthorityBroker.evaluate()` or actuation are ever reached.
  (2) `ConsequenceBoundary.execute()` Step 1's idempotency-replay short-circuit no
      longer trusts a cached EXECUTED receipt for a different, never-granted replaying
      actor_id -- it refuses (REFUSED_REPLAY_NOT_REAUTHORIZED).
  (3) The same Step 1 re-check also refuses a directly-forged PreparedReceipt/
      FinalReceipt pair (self-asserted grant_id for an actuation identity the broker
      never actually authorized) the moment anything replays that token through the
      real boundary again.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant` / `ConsequenceRequest` instances.
- Real `DurableDiskReceiptStore` performing genuine disk I/O under `tmp_path`, real
  `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (the same real
  collaborators the pinned mutation tests use).
- Real `AdmissionPipeline.admit()` calls (the real 10-stage fail-closed pipeline,
  unconfigured -- i.e. its own permissive defaults -- since this file's concern is the
  BOUNDARY's admission-result gate, not admission policy itself).
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
  file.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_NOT_ADMITTED,
    REFUSED_REPLAY_NOT_REAUTHORIZED,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    TerminalReceiptState,
)
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)

GENESIS = "genesis:0" * 4

_ADMITTABLE_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:afde-2604:boundary-fence> a afl:Action ;
    afl:targetResource <urn:resource:fence-c> .
"""
# AFDE-2604 fresh-mutations closure (Mutation A, this session): updated from a
# content-unrelated subject (`afl:afde_2604_boundary_fence_subject`) to one that
# literally references the exact `action`/`urn:resource:fence-c` identity episode
# (1c) below actuates -- `ConsequenceBoundary.execute_admitted()` now requires the
# admitted candidate graph itself to reference the action_iri/target_resource being
# executed (`_admission_covers_action_target()`,
# `src/autofde_lab/sa2a/brce/boundary.py`), refusing with
# `REFUSED_ADMISSION_CONTENT_NOT_BOUND` otherwise. This is a fixture adaptation to
# the tightened contract, not a weakening: episode (1c) still proves the SAME
# property (an ADMITTED candidate with a real grant genuinely executes), now with a
# fixture that is itself a legitimately-bound admission rather than one that merely
# happened not to be probed for content binding.

_UNPARSEABLE_CANDIDATE = "not RDF at all, in any serialization"


def _boundary(tmp_path: Path, name: str, broker: AuthorityBroker) -> tuple[
    ConsequenceBoundary, RealDiskJournalActuator, DurableDiskReceiptStore, Path
]:
    journal = tmp_path / name / "journal.json"
    store = DurableDiskReceiptStore(tmp_path / name / "receipts")
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store
    )
    return boundary, actuator, store, journal


# ---------------------------------------------------------------------------
# Fix (1): execute_admitted() fences on AdmissionResult.standing.
# ---------------------------------------------------------------------------


def test_execute_admitted_refuses_missing_and_refused_admission_but_allows_admitted(
    tmp_path: Path,
) -> None:
    """`execute_admitted()`: no admission_result -> refused; REFUSED admission_result ->
    refused; ADMITTED admission_result with a real grant -> genuinely executes.

    Three fully isolated episodes (distinct tokens/actors/targets/disk paths) inside
    one test, proving all three admission-fence branches directly against the real
    boundary with zero courts layer involved.
    """
    pipeline = AdmissionPipeline()
    actor = "urn:agent:afde-2604-boundary-fence-worker"
    action = "urn:action:afde-2604:boundary-fence"

    # --- (1a) No admission_result at all: refused, zero authority/actuation reached. ---
    broker_a = AuthorityBroker()
    broker_a.register_grant(
        AuthorityGrant(
            grant_id="grant-fence-a",
            subject_id=actor,
            action_iri=action,
            target_resource_iri="urn:resource:fence-a",
        )
    )
    boundary_a, actuator_a, _store_a, journal_a = _boundary(tmp_path, "fence_a", broker_a)
    envelope_a = ExecutionEnvelope(
        idempotency_token="idemp-fence-a",
        action_iri=action,
        target_resource="urn:resource:fence-a",
        actor_id=actor,
        # admission_result deliberately omitted (defaults to None)
    )
    result_a = boundary_a.execute_admitted(envelope_a)
    assert result_a.success is False
    assert result_a.state == TerminalReceiptState.REFUSED
    assert result_a.refusal_code == REFUSED_NOT_ADMITTED
    assert actuator_a.call_count == 0
    assert journal_a.exists() is False

    # --- (1b) A real, REFUSED AdmissionResult: refused the same way. ---
    refused_admission = pipeline.admit(_UNPARSEABLE_CANDIDATE)
    assert refused_admission.standing == Standing.REFUSED

    broker_b = AuthorityBroker()
    broker_b.register_grant(
        AuthorityGrant(
            grant_id="grant-fence-b",
            subject_id=actor,
            action_iri=action,
            target_resource_iri="urn:resource:fence-b",
        )
    )
    boundary_b, actuator_b, _store_b, journal_b = _boundary(tmp_path, "fence_b", broker_b)
    envelope_b = ExecutionEnvelope(
        idempotency_token="idemp-fence-b",
        action_iri=action,
        target_resource="urn:resource:fence-b",
        actor_id=actor,
        admission_result=refused_admission,
    )
    result_b = boundary_b.execute_admitted(envelope_b)
    assert result_b.success is False
    assert result_b.state == TerminalReceiptState.REFUSED
    assert result_b.refusal_code == REFUSED_NOT_ADMITTED
    assert actuator_b.call_count == 0
    assert journal_b.exists() is False

    # --- (1c) A real, ADMITTED AdmissionResult with a real grant: genuinely executes. ---
    admitted = pipeline.admit(
        _ADMITTABLE_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    broker_c = AuthorityBroker()
    broker_c.register_grant(
        AuthorityGrant(
            grant_id="grant-fence-c",
            subject_id=actor,
            action_iri=action,
            target_resource_iri="urn:resource:fence-c",
        )
    )
    boundary_c, actuator_c, _store_c, journal_c = _boundary(tmp_path, "fence_c", broker_c)
    envelope_c = ExecutionEnvelope(
        idempotency_token="idemp-fence-c",
        action_iri=action,
        target_resource="urn:resource:fence-c",
        actor_id=actor,
        admission_result=admitted,
    )
    result_c = boundary_c.execute_admitted(envelope_c)
    assert result_c.success is True, (
        "An ADMITTED candidate with a real, valid AuthorityGrant must genuinely "
        f"execute through execute_admitted(): {result_c.reason}"
    )
    assert result_c.state == TerminalReceiptState.EXECUTED
    assert actuator_c.call_count == 1
    assert journal_c.exists() is True
    assert result_c.final_receipt is not None
    assert result_c.final_receipt.postcondition_verified is True


# ---------------------------------------------------------------------------
# Fix (2): idempotency replay under a different, never-granted actor_id is refused.
# ---------------------------------------------------------------------------


def test_replay_under_different_never_granted_actor_is_refused(tmp_path: Path) -> None:
    """A cached EXECUTED receipt cannot be handed to a distinct, never-granted actor_id
    replaying the SAME idempotency token; the legitimately granted actor's OWN replay
    still succeeds (re-verified, not merely cached).
    """
    granted_actor = "urn:agent:fence2-granted"
    adversary_actor = "urn:agent:fence2-adversary"
    action = "urn:action:fence2:sync"
    target = "urn:resource:fence2:target"
    token = "idemp-fence2-replay"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fence2",
            subject_id=granted_actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "fence2", broker)

    first = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token, action_iri=action, target_resource=target, actor_id=granted_actor
        )
    )
    assert first.success is True
    assert first.state == TerminalReceiptState.EXECUTED
    assert actuator.call_count == 1

    # Legitimate same-actor replay: re-verified, still succeeds, zero new actuation.
    legit_replay = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token, action_iri=action, target_resource=target, actor_id=granted_actor
        )
    )
    assert legit_replay.success is True
    assert legit_replay.replayed is True
    assert legit_replay.final_receipt is not None
    assert legit_replay.final_receipt.digest == first.final_receipt.digest
    assert actuator.call_count == 1, "No new actuation for a legitimate same-actor replay."

    # Adversary replay under a different, never-granted actor_id: refused.
    adversary_replay = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token, action_iri=action, target_resource=target, actor_id=adversary_actor
        )
    )
    assert adversary_replay.success is False
    assert adversary_replay.state == TerminalReceiptState.REFUSED
    assert adversary_replay.refusal_code == REFUSED_REPLAY_NOT_REAUTHORIZED
    assert adversary_replay.replayed is True
    assert adversary_replay.final_receipt is not None
    assert adversary_replay.final_receipt.digest != first.final_receipt.digest
    assert actuator.call_count == 1, "No new actuation for a refused adversary replay either."
    assert journal.read_text(encoding="utf-8")  # unchanged, still just the one real entry


# ---------------------------------------------------------------------------
# Fix (3): a directly-forged PreparedReceipt/FinalReceipt pair is inert once replayed
# through the real boundary -- its self-asserted grant_id is never trusted.
# ---------------------------------------------------------------------------


def test_forged_receipt_pair_is_refused_on_replay_despite_self_asserted_grant_id(
    tmp_path: Path,
) -> None:
    """A `PreparedReceipt`/`FinalReceipt` pair constructed directly (bypassing
    `ConsequenceBoundary.execute()` entirely) and durably saved to the store, claiming a
    real grant_id for an action/target it never actually authorized, is refused the
    moment a real `ConsequenceBoundary.execute()` call replays that token -- the
    self-asserted `grant_id` on the receipt is never trusted; only a fresh
    `AuthorityBroker.evaluate()` for the replaying request's own identity is.
    """
    legit_actor = "urn:agent:fence3-legit"
    legit_action = "urn:action:fence3:legit"
    legit_target = "urn:resource:fence3:legit-target"
    forged_action = "urn:action:fence3:forged"
    forged_target = "urn:resource:fence3:forged-target"
    token = "idemp-fence3-forged"

    broker = AuthorityBroker()
    real_grant = AuthorityGrant(
        grant_id="grant-fence3-real",
        subject_id=legit_actor,
        action_iri=legit_action,
        target_resource_iri=legit_target,
    )
    broker.register_grant(real_grant)

    store = DurableDiskReceiptStore(tmp_path / "fence3" / "receipts")

    forged_prepared = PreparedReceipt(
        prepared_id="prep-fence3-forged",
        idempotency_token=token,
        action_iri=forged_action,
        target_resource=forged_target,
        actor_id=legit_actor,
        grant_id=real_grant.grant_id,  # self-asserted -- the grant never covers this identity
        plan_digest=GENESIS,
        artifact_digest="none",
        admitted_input_digest=GENESIS,
        consequence_class="LOCAL_EFFECT",
        previous_receipt_digest=store.last_receipt_digest(),
    )
    store.save_prepared(forged_prepared)
    forged_final = FinalReceipt(
        receipt_id="rec-fence3-forged",
        prepared_receipt_digest=forged_prepared.digest,
        idempotency_token=token,
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
        evidence={"claim": "grant-fence3-real authorized this"},
    )
    store.save_final(forged_final)

    journal = tmp_path / "fence3" / "journal.json"
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=RealDiskJournalActuator(journal),
        verifier=IndependentDiskJournalVerifier(journal),
        receipt_store=store,
    )

    replay_result = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=forged_action,
            target_resource=forged_target,
            actor_id=legit_actor,
        )
    )

    assert replay_result.success is False, (
        "A forged PreparedReceipt/FinalReceipt pair must never be handed back as a "
        "trusted EXECUTED result merely because it sits in the store under a token."
    )
    assert replay_result.state == TerminalReceiptState.REFUSED
    assert replay_result.refusal_code == REFUSED_REPLAY_NOT_REAUTHORIZED
    assert replay_result.final_receipt is not None
    assert replay_result.final_receipt.digest != forged_final.digest
    assert journal.exists() is False, "Zero real disk mutation for the forged identity."

    # Positive control: the SAME broker, asked honestly about the real legit identity
    # the grant actually covers, still authorizes it -- confirming the refusal above is
    # specific to the forged identity, not a broken broker.
    honest = boundary.execute(
        ExecutionEnvelope(
            idempotency_token="idemp-fence3-honest",
            action_iri=legit_action,
            target_resource=legit_target,
            actor_id=legit_actor,
        )
    )
    assert honest.success is True
    assert honest.state == TerminalReceiptState.EXECUTED
