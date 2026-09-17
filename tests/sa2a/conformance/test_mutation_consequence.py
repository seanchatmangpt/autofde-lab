# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Identity-mutation falsifier for the BRCE Consequence Court (RFC-SA2A-002 v26.9.16).

Per this repo's `.claude/rules/level4-completion-law.md` "Mutation law": construct an
otherwise-complete, currently-valid admission episode for the Consequence Court, mutate
EXACTLY ONE identity field in it, and assert the court's real admission/verify function
rejects the mutation with a typed non-ALIVE/refusal result.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real plant components only: genuine `AuthorityBroker`, `ConsequenceBoundary`,
  `DurableDiskReceiptStore` (real physical disk I/O), real `RealDiskJournalActuator` /
  `IndependentDiskJournalVerifier`.
- Zero unittest.mock / Mock / MagicMock / patch / monkeypatch.
- The one local subclass below (`CountingAuthorityBroker`) is NOT a mock: `evaluate()`
  performs the exact real `AuthorityBroker.evaluate()` logic via `super()`; the counter is
  incidental instrumentation proving, from real execution, whether the real authority check
  actually ran for a given call -- a real object with real (if slightly augmented) behavior,
  per the "hand-written real implementation is not a mock" carve-out in
  `.claude/rules/testing-chicago-style.md`.

UPDATED (AFDE-2604 local closure, this session): a prior pass of this session found and
pinned `DEFEATED = FALSE` here -- the mutation (replaying a granted actor's idempotency
token under a distinct, never-granted adversary `actor_id`) was NOT rejected;
`ConsequenceBoundary.execute()` returned the granted actor's cached `EXECUTED` receipt to
the adversary byte-for-byte, with zero fresh `AuthorityBroker.evaluate()` call for the
adversary's own identity. THIS PASS CLOSES THAT GAP: `ConsequenceBoundary.execute()` Step 1
now re-derives authorization from scratch, for the REPLAYING envelope's own
`actor_id`/`action_iri`/`target_resource` (never trusting the cached receipt's identity or a
self-asserted `grant_id`), before ever returning a cached `EXECUTED` response --
`REFUSED_REPLAY_NOT_REAUTHORIZED` is the new typed refusal. See
`src/autofde_lab/sa2a/brce/boundary.py::ConsequenceBoundary.execute()` Step 1 and
`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`'s "Local closure work (fix
implemented)" section for the full account.

Result of THIS session's re-run of the same mutation: DEFEATED = TRUE. The rigor of the
mutation itself is unchanged (same idempotency-token-identity-swap attack, same real
collaborators, same adversarial construction) -- only the expected (and now actually
observed) outcome flips from accepted-wrongly to correctly-refused. The court/boundary
source under `src/autofde_lab/sa2a/` WAS modified by this session, per the task's explicit
authorization to close the three named gaps rooted in this exact
`ExecutionEnvelope`/`ConsequenceBoundary.execute()` surface.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant,
    AuthorityDecision,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.boundary import (
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
    ConsequenceCourt,
    DurableDiskReceiptStore,
    GateVerdict,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)


class CountingAuthorityBroker(AuthorityBroker):
    """Real `AuthorityBroker` subclass that counts real `evaluate()` invocations.

    Not a mock and not a stub: `evaluate()` runs the exact real non-implication /
    grant-matching logic in `AuthorityBroker.evaluate()` via `super().evaluate(request)`.
    The counter observes, from a real collaborator's real behavior, whether the broker's
    authority check actually executed for a given `ConsequenceBoundary.execute()` call --
    a state-based fact about real execution, not an interaction expectation on a fake.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.evaluate_call_count = 0

    def evaluate(self, request: ConsequenceRequest) -> AuthorityDecision:
        self.evaluate_call_count += 1
        return super().evaluate(request)


def test_idempotency_replay_does_not_bind_replaying_actor_identity(tmp_path: Path) -> None:
    """Mutation: swap the `actor_id` identity on a replayed idempotency-token request.

    Step 1 -- otherwise-complete, currently-valid episode (constructed via the court's
    real gate, real disk I/O, real broker, real boundary):
      `ConsequenceCourt.audit_idempotency_replay_refusal` is run for real with a
      legitimately granted actor (`urn:agent:batch_worker`), producing a real PASSED
      `CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL` gate result and a real, disk-persisted
      `FinalReceipt` with `state == EXECUTED`.

    Step 2 -- the mutation (EXACTLY ONE identity field changed): a THIRD
    `ExecutionEnvelope` reuses the SAME `idempotency_token`, `action_iri`,
    `target_resource`, and `parameters` as the granted actor's real execution, but swaps
    `actor_id` for a distinct, well-formed, NEVER-granted adversary identity
    (`urn:agent:adversary`). This envelope is submitted directly to the real
    `ConsequenceBoundary.execute()` -- the exact admission primitive every one of the
    court's five gates is built on (see every `audit_*` method in `consequence_court.py`,
    which each construct a fresh `ConsequenceBoundary` and call `.execute()`).

    Expected lawful behavior (per `.claude/rules/no-dual-bookkeeping.md`'s "identity is
    explicit or it does not exist" and `.claude/rules/level4-completion-law.md`'s
    "constructed identity, never adjacency"): the boundary must bind a replayed
    idempotency-token response to the ORIGINAL requester's admitted identity, or refuse
    the replaying request outright. An idempotency token is not an authority grant --
    presenting one must never substitute for the requester's own authority evaluation.

    FIXED (AFDE-2604 local closure, this session) -- observed, current behavior asserted
    below: `ConsequenceBoundary.execute()` Step 1's idempotency short-circuit
    (`self._receipt_store.get_final(envelope.idempotency_token)`) still finds a cached
    `EXECUTED` final keyed solely on the token string, but it no longer trusts that cache
    blindly. Before returning it, the boundary now performs a FRESH
    `AuthorityBroker.evaluate()` call for the REPLAYING envelope's own
    `actor_id`/`action_iri`/`target_resource` (ignoring any self-asserted `grant_id`, per
    `.claude/rules/no-dual-bookkeeping.md`'s "identity is explicit or it does not exist").
    So the never-granted adversary's request:
      - receives `success=False`, `state=REFUSED` -- NOT the granted actor's `EXECUTED`
        state;
      - receives `refusal_code == REFUSED_REPLAY_NOT_REAUTHORIZED`, a typed, non-ALIVE
        result naming exactly why (a fresh authority re-check for the adversary's own
        identity did not confirm authorization);
      - receives a `FinalReceipt` whose digest is DIFFERENT from the granted actor's
        original receipt (it is a distinct, deterministic refusal receipt, never
        persisted under the token -- the durable store's own original `EXECUTED` record
        for the granted actor is left completely untouched);
      - DOES have `AuthorityBroker.evaluate()` invoked for its own request -- the real,
        instrumented broker's call count increases by exactly one for this replay
        attempt (proven below via `CountingAuthorityBroker`, a real subclass, not an
        interaction mock) -- and that fresh, real evaluation independently confirms
        `authorized=False`/`REFUSED_NO_GRANT` for the adversary, matching the
        `direct_decision` positive control below.

    This closes the identity-binding gap this test originally pinned: a party who learns
    or guesses a valid idempotency token can no longer present it under an arbitrary,
    unauthorized actor identity and receive the original actor's `EXECUTED` receipt --
    every replay of a cached `EXECUTED` response is now re-evaluated by the Authority
    Broker for the replaying request's own identity before it is trusted.

    DEFEATED = TRUE. The mutation (identity-swap on an idempotency-token replay) remains
    a real, well-formed, adversarial construction -- unchanged from the original pinning
    -- and is now correctly rejected. `src/autofde_lab/sa2a/brce/boundary.py` was
    modified this session to close this gap (see that file's `execute()` Step 1 and the
    new `REFUSED_REPLAY_NOT_REAUTHORIZED` refusal code).
    """
    receipt_dir = tmp_path / "receipts"
    journal_path = tmp_path / "identity_swap_journal.json"
    granted_actor_id = "urn:agent:batch_worker"
    adversary_actor_id = "urn:agent:adversary"  # distinct, well-formed, NEVER granted
    action_iri = "urn:action:sync_state"
    target_resource = "urn:cap:sync:target"
    parameters = {"sync_epoch": 42}
    token = "idemp-identity-swap-001"

    durable_store = DurableDiskReceiptStore(receipt_dir)
    broker = CountingAuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-identity-swap",
            subject_id=granted_actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )
    # Deliberately: `adversary_actor_id` has NO grant registered anywhere in `broker`.
    # A fresh, direct evaluation of a request from this actor must be REFUSED_NO_GRANT.

    # -------------------------------------------------------------------------------
    # Step 1: otherwise-complete, currently-valid episode via the court's real gate.
    # -------------------------------------------------------------------------------
    court = ConsequenceCourt()
    gate_result = court.audit_idempotency_replay_refusal(
        broker=broker,
        receipt_store=durable_store,
        journal_path=journal_path,
        actor_id=granted_actor_id,
        action_iri=action_iri,
        target_resource=target_resource,
        parameters=parameters,
        idempotency_token=token,
    )

    assert gate_result.passed is True
    assert gate_result.verdict == GateVerdict.PASSED
    assert gate_result.gate_id == CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL

    # Real disk evidence: the granted actor's execution genuinely completed.
    final_before = durable_store.get_final(token)
    assert final_before is not None
    assert final_before.state == TerminalReceiptState.EXECUTED

    # UPDATED (AFDE-2604 fix): the court's own gate call now makes TWO real authority
    # evaluations, not one -- the granted actor's initial execution (Step 2, a first-time
    # authorization), PLUS one fresh re-authorization check for its own same-actor replay
    # sub-check (Step 1's new reauth check, since that sub-check also hits a cached
    # EXECUTED final and must now re-verify it, per the fix below). This is the correct,
    # expected cost of closing the gap: a genuine same-actor replay still succeeds
    # (re-verified, not merely cached), it is simply no longer free of an authority check.
    calls_after_valid_episode = broker.evaluate_call_count
    assert calls_after_valid_episode == 2

    # -------------------------------------------------------------------------------
    # Step 2: MUTATION -- exactly one identity field (`actor_id`) is swapped for a
    # distinct, well-formed, never-granted adversary identity, while reusing the SAME
    # idempotency_token, action_iri, target_resource, and parameters.
    # -------------------------------------------------------------------------------
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=durable_store,  # the SAME real durable store the court's gate used
    )

    impersonation_envelope = ExecutionEnvelope(
        idempotency_token=token,        # SAME token as the granted actor's real execution
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=adversary_actor_id,    # MUTATED identity: ungranted adversary
        parameters=parameters,
    )

    calls_before_impersonation = broker.evaluate_call_count
    result = boundary.execute(impersonation_envelope)

    # Proof that the real AuthorityBroker.evaluate() WAS invoked for the adversary's
    # boundary-mediated request, exactly once, as part of the Step 1 replay re-check --
    # captured BEFORE the test's own manual `direct_decision` call below, so this count is
    # attributable solely to the boundary's internal fix, not to any test-level call.
    assert broker.evaluate_call_count == calls_before_impersonation + 1, (
        "ConsequenceBoundary.execute() must route the adversary's replayed-token request "
        "through a fresh AuthorityBroker.evaluate() call for the replaying request's own "
        "actor_id, per the Step 1 re-authorization check (AFDE-2604 fix)."
    )

    # --- Falsifier check: an independent, direct evaluation of this exact adversary
    # request (same actor/action/resource/context) against the SAME broker is, for real,
    # REFUSED_NO_GRANT -- confirming the adversary genuinely has no authority, and that
    # the boundary's own internal re-check above (which produced the SAME refusal code)
    # is asking the broker the same real question, not a reimplementation of its logic. ---
    direct_decision = broker.evaluate(
        ConsequenceRequest(
            actor_id=adversary_actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            context=dict(parameters),
        )
    )
    assert direct_decision.authorized is False
    assert direct_decision.refusal_code == "REFUSED_NO_GRANT"

    # =================================================================================
    # ASSERTING THE FIXED (CORRECT) BEHAVIOR -- the gap is closed.
    #
    # The boundary now REJECTS `impersonation_envelope`: the adversary's genuinely
    # distinct request is routed through a fresh authority evaluation (confirmed above),
    # which refuses it (matching `direct_decision`), and that refusal -- not the granted
    # actor's cached success -- is what the adversary receives.
    # =================================================================================
    assert result.success is False, (
        "AFDE-2604 fix: the boundary must REJECT an idempotency-token replay whose "
        "actor_id does not match the actor_id the token was originally granted/executed "
        "under; it must never report success=True for a never-granted adversary identity."
    )
    assert result.state == TerminalReceiptState.REFUSED, (
        "AFDE-2604 fix: a typed non-EXECUTED / refusal terminal state is required for the "
        "adversary's unmatched-identity replay -- it must never reuse the originally "
        "granted actor's EXECUTED terminal state."
    )
    assert result.replayed is True, (
        "This is still, correctly, a replay attempt on an already-used idempotency token "
        "-- replayed=True is preserved even though the replay is now refused."
    )
    assert result.refusal_code == "REFUSED_REPLAY_NOT_REAUTHORIZED", (
        "AFDE-2604 fix: a typed refusal code must name exactly why the replay was "
        "refused -- a fresh authority re-check for the replaying request's own identity "
        "did not confirm authorization."
    )
    assert result.final_receipt is not None
    assert result.final_receipt.digest != final_before.digest, (
        "The adversary's response must NEVER be byte-identical to the granted actor's "
        "original FinalReceipt -- the two identities must never share one receipt."
    )
    assert result.final_receipt.state == TerminalReceiptState.REFUSED
    assert result.final_receipt.refusal_code == "REFUSED_REPLAY_NOT_REAUTHORIZED"

    # The durable store's own original record for the granted actor's real execution is
    # left completely untouched by the adversary's refused replay attempt -- the fix does
    # not corrupt or overwrite history, it only refuses to hand it to the wrong requester.
    final_after = durable_store.get_final(token)
    assert final_after is not None
    assert final_after.digest == final_before.digest
    assert final_after.state == TerminalReceiptState.EXECUTED

    # No new physical actuation occurred for the refused adversary replay either (this
    # was already true pre-fix, and remains true post-fix -- the actuator was never
    # re-invoked for a cached-token replay in either case; what changed is whether the
    # cached response was trusted before being handed back).
    assert actuator.call_count == 0

    # No new physical actuation occurred (this alone would be correct in isolation -- the
    # actuator was not re-invoked -- but it is exactly what makes the identity bypass
    # silent: no new disk write flags the mismatch, no verifier ever runs, and the caller
    # walks away with someone else's receipt reporting EXECUTED for their own request).
    assert actuator.call_count == 0
