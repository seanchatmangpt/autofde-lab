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
  `IndependentDiskJournalVerifier`, and a real `AdmissionPipeline` producing a genuine
  `Standing.ADMITTED` `AdmissionResult` (real RDF parse/canonicalize/digest, not a
  fabricated result object).
- Zero unittest.mock / Mock / MagicMock / patch / monkeypatch.
- The one local subclass below (`CountingAuthorityBroker`) is NOT a mock: `evaluate()`
  performs the exact real `AuthorityBroker.evaluate()` logic via `super()`; the counter is
  incidental instrumentation proving, from real execution, whether the real authority check
  actually ran for a given call -- a real object with real (if slightly augmented) behavior,
  per the "hand-written real implementation is not a mock" carve-out in
  `.claude/rules/testing-chicago-style.md`.

UPDATED (AFDE-2604 local closure, prior session): a prior pass of this session found and
pinned `DEFEATED = FALSE` here -- the mutation (replaying a granted actor's idempotency
token under a distinct, never-granted adversary `actor_id`) was NOT rejected;
`ConsequenceBoundary.execute()` returned the granted actor's cached `EXECUTED` receipt to
the adversary byte-for-byte, with zero fresh `AuthorityBroker.evaluate()` call for the
adversary's own identity. THAT PASS CLOSED THAT GAP: `ConsequenceBoundary.execute()` Step 1
re-derives authorization from scratch, for the REPLAYING envelope's own
`actor_id`/`action_iri`/`target_resource` (never trusting the cached receipt's identity or a
self-asserted `grant_id`), before ever returning a cached `EXECUTED` response --
`REFUSED_REPLAY_NOT_REAUTHORIZED` is the typed refusal. See
`src/autofde_lab/sa2a/brce/boundary.py::ConsequenceBoundary.execute()` Step 1 and
`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`'s "Local closure work (fix
implemented)" section for the full account.

RESTRUCTURED (this pass, fail-secure `require_admission` default closure -- DW-1/UE-2/UE-3):
`ConsequenceBoundary.__init__`'s `require_admission` class-level default flipped, in this
same session but in a sibling file (`src/autofde_lab/sa2a/brce/boundary.py`, out of scope for
this file's own fix per this pass's explicit file-boundary), from `False` to `True` --
`execute()` on a bare-default instance now enforces the same admission gate
`execute_admitted()` always has. This is INCIDENTAL to what this test actually probes (the
idempotency-token identity-swap mutation above), not the thing it is testing -- so, per this
codebase's `.claude/rules/testing-chicago-style.md`, the fix is to wire a real, valid
`Standing.ADMITTED` `AdmissionResult` (via a real `AdmissionPipeline().admit()` call, real RDF
content, real provenance) onto every `ExecutionEnvelope` this test constructs, so the test
still reaches the exact same `ConsequenceBoundary.execute()` Step 1 identity-reauth code path
it always exercised -- never by weakening the instance to `require_admission=False`.

One consequence of that default flip is real and load-bearing here: the "otherwise-complete,
currently-valid episode" (Step 1 below) can no longer be constructed via
`ConsequenceCourt.audit_idempotency_replay_refusal()`. That court method (in
`src/autofde_lab/sa2a/conformance/courts/consequence_court.py`, likewise out of this file's
edit scope) constructs its own `ExecutionEnvelope`s with no `admission_result` bound at all,
so under the new class-level default every one of its `ConsequenceBoundary.execute()` calls
now refuses `REFUSED_NOT_ADMITTED` before ever reaching the idempotency/reauth logic this
test needs to exercise -- confirmed directly this session (`gate_result.passed == False`,
`reason == "Replayed execution returned mismatched final receipt digest."`, and the durably
persisted first-call receipt carries `refusal_code == REFUSED_NOT_ADMITTED`, not
`EXECUTED`). That helper needs its own admission-wiring fix; this file's task scope is
`test_mutation_consequence.py` only. So Step 1 below constructs the equivalent
"otherwise-complete, currently-valid episode" directly -- same real `ConsequenceBoundary`,
same real `AuthorityBroker`, same real `DurableDiskReceiptStore` / `RealDiskJournalActuator`
/ `IndependentDiskJournalVerifier` the court's own gate is built on (imported from the same
`consequence_court` module, unmodified) -- with a real bound admission on every envelope, so
this test's actual subject (the Step 2 identity-swap mutation below) still reaches the exact
`ConsequenceBoundary.execute()` production code path it always did, rather than being masked
by an admission refusal that has nothing to do with what this test probes.

Result of THIS session's re-run of the same mutation, with real admission correctly wired
in: DEFEATED = TRUE. The rigor of the mutation itself is unchanged (same idempotency-token-
identity-swap attack, same real collaborators, same adversarial construction) -- the fresh
authority re-check the prior pass's fix added is still reached and still refuses the
adversary, admission enforcement notwithstanding.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityDecision,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.boundary import (
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
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


def test_idempotency_replay_does_not_bind_replaying_actor_identity(
    tmp_path: Path,
) -> None:
    """Mutation: swap the `actor_id` identity on a replayed idempotency-token request.

    Step 1 -- otherwise-complete, currently-valid episode (real `ConsequenceBoundary`, real
    disk I/O via `DurableDiskReceiptStore` / `RealDiskJournalActuator` /
    `IndependentDiskJournalVerifier`, real `AuthorityBroker`, real `AdmissionPipeline`):
    a legitimately granted actor (`urn:agent:batch_worker`) executes for real
    (`action_iri`/`target_resource` bound by a genuine `Standing.ADMITTED` `AdmissionResult`),
    producing a real, disk-persisted `FinalReceipt` with `state == EXECUTED`; a second,
    distinct `ExecutionEnvelope` for the SAME actor then replays the SAME idempotency token,
    proving a genuine same-actor replay is re-verified (not merely cached) and still succeeds
    with the identical receipt digest.

    Step 2 -- the mutation (EXACTLY ONE identity field changed): a THIRD
    `ExecutionEnvelope` reuses the SAME `idempotency_token`, `action_iri`,
    `target_resource`, and `parameters` as the granted actor's real execution (and carries
    the SAME bound admission, since admission is a property of the action/target content,
    never of the requesting actor -- see `_admission_covers_action_target()` in
    `boundary.py`, which checks nothing about `actor_id`), but swaps `actor_id` for a
    distinct, well-formed, NEVER-granted adversary identity (`urn:agent:adversary`). This
    envelope is submitted directly to the real `ConsequenceBoundary.execute()` -- the exact
    admission primitive every one of the court's five gates is built on (see every
    `audit_*` method in `consequence_court.py`, which each construct a fresh
    `ConsequenceBoundary` and call `.execute()`).

    Expected lawful behavior (per `.claude/rules/no-dual-bookkeeping.md`'s "identity is
    explicit or it does not exist" and `.claude/rules/level4-completion-law.md`'s
    "constructed identity, never adjacency"): the boundary must bind a replayed
    idempotency-token response to the ORIGINAL requester's admitted identity, or refuse
    the replaying request outright. An idempotency token is not an authority grant --
    presenting one must never substitute for the requester's own authority evaluation. An
    admitted candidate's action/target binding is likewise not an authority grant for
    whichever actor happens to present it.

    FIXED (AFDE-2604 local closure, prior session) -- observed, current behavior asserted
    below: `ConsequenceBoundary.execute()` Step 1's idempotency short-circuit
    (`self._receipt_store.get_final(envelope.idempotency_token)`) still finds a cached
    `EXECUTED` final keyed solely on the token string, but it no longer trusts that cache
    blindly. Before returning it, the boundary performs a FRESH
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
    Broker for the replaying request's own identity before it is trusted. This remains
    true with the current session's fail-secure `require_admission=True` default: real
    admission and real authority are two independent, composed gates, and this test wires
    both for real rather than letting either one substitute for the other.

    DEFEATED = TRUE. The mutation (identity-swap on an idempotency-token replay) remains
    a real, well-formed, adversarial construction -- unchanged from the original pinning
    -- and is correctly rejected, with real admission now wired into every envelope this
    test constructs (see module docstring for why Step 1 no longer delegates to
    `ConsequenceCourt.audit_idempotency_replay_refusal()`, a sibling-file helper this
    file's task scope may not modify and which is itself unconditionally broken by the
    same `require_admission` default flip -- a separate, real gap left for that file's
    own fix).
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

    # Real admission: a genuine `AdmissionPipeline().admit()` call over real Turtle content
    # that explicitly, relationally binds THIS action_iri to THIS target_resource (the exact
    # triple `_admission_covers_action_target()` in boundary.py requires -- see its
    # docstring). Admission carries no actor identity at all (the triple mentions neither
    # `granted_actor_id` nor `adversary_actor_id`): it is a property of the admitted
    # candidate's action/target content, orthogonal to -- and never a substitute for -- the
    # per-actor `AuthorityBroker` evaluation this test's mutation is actually about. The
    # SAME `AdmissionResult` is therefore legitimately reused below across the granted
    # actor's envelopes and the adversary's mutated envelope.
    admission_pipeline = AdmissionPipeline()
    admitted = admission_pipeline.admit(
        "@prefix afl: <urn:autofde-lab:> .\n"
        f"<{action_iri}> afl:targetResource <{target_resource}> .",
        provenance_record={
            "issuer": "urn:issuer:test-identity-swap",
            "timestamp": "2026-09-17T00:00:00Z",
        },
    )
    assert admitted.standing == Standing.ADMITTED, (
        f"Test setup's own AdmissionPipeline().admit() call must reach real "
        f"Standing.ADMITTED for this test's premise to hold; got "
        f"{admitted.standing!r} (refusal_code={admitted.refusal_code!r}, "
        f"reasons={admitted.reasons!r})."
    )

    # -------------------------------------------------------------------------------
    # Step 1: otherwise-complete, currently-valid episode -- real ConsequenceBoundary,
    # real disk-backed collaborators (same classes the court's own gates use), real
    # admission bound to every envelope. See module docstring for why this no longer
    # delegates to ConsequenceCourt.audit_idempotency_replay_refusal().
    # -------------------------------------------------------------------------------
    episode_actuator = RealDiskJournalActuator(journal_path)
    episode_verifier = IndependentDiskJournalVerifier(journal_path)
    episode_boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=episode_actuator,
        verifier=episode_verifier,
        receipt_store=durable_store,
    )

    envelope1 = ExecutionEnvelope(
        idempotency_token=token,
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=granted_actor_id,
        parameters=parameters,
        admission_result=admitted,
    )
    res1 = episode_boundary.execute(envelope1)
    assert res1.success is True
    assert res1.state == TerminalReceiptState.EXECUTED
    assert res1.replayed is False
    assert res1.final_receipt is not None

    # Sub-check: re-executing under the SAME actor with a SAME-content, distinct envelope
    # object -- a genuine same-actor replay. UPDATED (AFDE-2604 fix): this now makes a
    # SECOND real authority evaluation (the reauth check below fires on every replay of a
    # cached EXECUTED final, not merely a cross-identity one), re-verifying rather than
    # blindly trusting the cache, yet still returns the byte-identical cached receipt for
    # the SAME actor -- this is the correct, expected cost of closing the gap: a genuine
    # same-actor replay still succeeds, it is simply no longer free of an authority check.
    envelope1_replay = ExecutionEnvelope(
        idempotency_token=token,
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=granted_actor_id,
        parameters=parameters,
        admission_result=admitted,
    )
    res1_replay = episode_boundary.execute(envelope1_replay)
    assert res1_replay.success is True
    assert res1_replay.state == TerminalReceiptState.EXECUTED
    assert res1_replay.replayed is True
    assert res1_replay.final_receipt is not None
    assert res1_replay.final_receipt.digest == res1.final_receipt.digest

    # Real disk evidence: no new physical actuation occurred for the same-actor replay --
    # the cached response was reused (after reauth), the actuator was not re-invoked.
    assert episode_actuator.call_count == 1

    # Real disk evidence: the granted actor's execution genuinely completed.
    final_before = durable_store.get_final(token)
    assert final_before is not None
    assert final_before.state == TerminalReceiptState.EXECUTED
    assert final_before.digest == res1.final_receipt.digest

    # Two real authority evaluations for this valid episode: the granted actor's initial
    # execution (a first-time authorization), PLUS one fresh re-authorization check for the
    # same-actor replay above (Step 1's reauth check, since that sub-check also hits a
    # cached EXECUTED final and must now re-verify it).
    calls_after_valid_episode = broker.evaluate_call_count
    assert calls_after_valid_episode == 2

    # -------------------------------------------------------------------------------
    # Step 2: MUTATION -- exactly one identity field (`actor_id`) is swapped for a
    # distinct, well-formed, never-granted adversary identity, while reusing the SAME
    # idempotency_token, action_iri, target_resource, parameters, and (per the admission
    # docstring note above) the SAME real admission -- admission binds action/target
    # content, not actor identity, so reusing it here is not itself a mutation.
    # -------------------------------------------------------------------------------
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=durable_store,  # the SAME real durable store the episode above used
    )

    impersonation_envelope = ExecutionEnvelope(
        idempotency_token=token,  # SAME token as the granted actor's real execution
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=adversary_actor_id,  # MUTATED identity: ungranted adversary
        parameters=parameters,
        admission_result=admitted,  # SAME real admission (action/target-bound, not actor-bound)
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
    # The boundary REJECTS `impersonation_envelope`: the adversary's genuinely distinct
    # request is routed through a fresh authority evaluation (confirmed above), which
    # refuses it (matching `direct_decision`), and that refusal -- not the granted actor's
    # cached success -- is what the adversary receives. Real admission being correctly
    # wired in on this envelope changes nothing about this outcome: admission and
    # authority are independent, composed gates, and admission alone was never, and is
    # still never, permission to actuate under an unauthorized identity.
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
    # cached response was trusted before being handed back). `actuator` here is the
    # Step-2-local instance constructed above (never used for the granted actor's real
    # execution, which ran through `episode_actuator` in Step 1), so its own call count
    # starting at, and remaining, zero is exactly the proof that no actuation happened on
    # THIS request.
    assert actuator.call_count == 0, (
        "No new physical actuation occurred (this alone would be correct in isolation -- "
        "the actuator was not re-invoked -- but it is exactly what makes the identity "
        "bypass silent: no new disk write flags the mismatch, no verifier ever runs, and "
        "the caller walks away with someone else's receipt reporting EXECUTED for their "
        "own request)."
    )
