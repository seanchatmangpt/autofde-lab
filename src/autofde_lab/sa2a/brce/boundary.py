"""BRCE (Bounded Runtime Consequence Engine) Consequence Boundary (§30, §63).

Reference consequence boundary for Semantic A2A (RFC-SA2A-001 v26.9.16).
Strict flow:
    SELECT -> CONSTRUCT -> AuthorityBroker -> BRCE -> DO

Core Invariants:
1. Zero Unreceipted Actuation (§4.8, §31):
   Requires a durable PreparedReceipt minted and committed BEFORE actuation begins.
2. Authority Non-Implications (§29):
   Authority is verified via AuthorityBroker; capabilities, plans, proofs do not imply authority.
3. Separation of Concerns:
   Actuator performs effect; separate PostconditionVerifier checks outcome.
4. Replay Protection (§55):
   Idempotency tokens prevent duplicate actuations. If an idempotency token was already
   executed, returns cached FinalReceipt without re-actuating.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence

from rdflib import URIRef

from autofde_lab.sa2a.admission.pipeline import AdmissionResult
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityDecision,
    ConsequenceRequest,
    REFUSED_NO_GRANT,
)
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    ReceiptStore,
    TerminalReceiptState,
)
from autofde_lab.sa2a.construct.constructor import (
    AdmittedSemantics,
    ConstructionReceipt,
    ExecutableArtifact,
)

# AFDE-2604 (local admission-fencing closure): refused when a strict entry point is
# invoked without a bound, Standing.ADMITTED AdmissionResult on the envelope (§13, §19,
# §62 admission law composed with §28-§31 BRCE law). See ConsequenceBoundary.execute_admitted().
REFUSED_NOT_ADMITTED = "REFUSED_NOT_ADMITTED"

# AFDE-2604 fix (2)+(3): refused when an idempotency-token replay of a cached EXECUTED
# receipt cannot be re-authorized, from scratch, for the REPLAYING request's own
# actor_id/action_iri/target_resource identity. An idempotency token is not an authority
# grant (§55); a cached success must never be handed to a request the broker would not
# independently authorize right now. See ConsequenceBoundary.execute() Step 1.
REFUSED_REPLAY_NOT_REAUTHORIZED = "REFUSED_REPLAY_NOT_REAUTHORIZED"

# AFDE-2604 fresh-mutations closure (Mutation A): refused when a real, Standing.ADMITTED
# AdmissionResult is bound to an envelope, but the admitted candidate content itself never
# references the exact action_iri/target_resource being executed. Standing.ADMITTED is a
# property of WHATEVER content was actually admitted; it is never, by itself, permission to
# actuate an arbitrary, unrelated action/target merely because SOME admission happened to
# succeed (no-dual-bookkeeping.md: "identity is explicit or it does not exist" -- co-reference
# via an unrelated Standing.ADMITTED verdict is not a relation). See
# ConsequenceBoundary.execute_admitted() and _admission_covers_action_target() below.
REFUSED_ADMISSION_CONTENT_NOT_BOUND = "REFUSED_ADMISSION_CONTENT_NOT_BOUND"

# AFDE-2604 fresh-mutations closure (Mutation B), GENERALIZED by the AFDE-2604
# architecture fix (Local Round 3, relational binding + unified enforcement): refused
# whenever an idempotency-token replay presents an IDENTITY (action_iri,
# target_resource, OR actor_id) that differs from the one bound to that token by the
# durable PreparedReceipt already committed for it -- whether or not a FinalReceipt
# has been minted yet. An idempotency token identifies exactly one fixed actuation
# identity (actor + action + target); it is never authority to substitute a
# different one after the fact, even when the replaying request happens to be
# independently, validly authorized for that different identity. Originally scoped
# to action_iri/target_resource only, and only when a cached EXECUTED FinalReceipt
# already existed (Mutation B); this same code now also fires (a) on an actor_id
# mismatch against a cached EXECUTED receipt (Mutation D closure) and (b) on ANY
# identity mismatch against a durably-committed PreparedReceipt that has no
# FinalReceipt yet -- the prepared-but-not-finalized crash window (Mutation E
# closure). See ConsequenceBoundary.execute() Steps 1 and 4.
REFUSED_TOKEN_ACTION_MISMATCH = "REFUSED_TOKEN_ACTION_MISMATCH"


# AFDE-2604 architecture fix (Local Round 3, relational binding): the real, already
# -established predicate this repo's own courts/fixtures use to relate an action to
# its target resource when they ARE meant to be bound -- see
# `conformance/courts/admission_court.py`'s `AFL = Namespace("urn:autofde-lab:")` /
# `AFL.targetResource`, and every "legitimately bound" fixture across
# `test_afde_2604_*` (`<action> afl:targetResource <target> .`). Reused here, not
# invented, per this fix's own instruction to use the existing convention.
_AFL_TARGET_RESOURCE = URIRef("urn:autofde-lab:targetResource")


def _admission_covers_action_target(
    admission: AdmissionResult, action_iri: str, target_resource: str
) -> bool:
    """AFDE-2604 architecture fix (Local Round 3, superseding the original Mutation-A
    implementation): real, EXPLICIT RDF-triple content binding, not node co-occurrence.

    Returns True only if the admitted candidate graph itself (the exact RDF graph that
    reached Standing.ADMITTED, per `AdmissionResult.graph`) contains the real triple
    `<action_iri> afl:targetResource <target_resource>` -- i.e. some actual statement
    asserting that THIS action applies to THIS target.

    Superseded gap (identity-binding bypass qualification, Mutations D1/D2): the
    original implementation checked only `URIRef(action_iri) in graph.all_nodes() and
    URIRef(target_resource) in graph.all_nodes()` -- membership in the UNION of every
    subject/object in the graph, regardless of which triple put them there. That is
    node co-occurrence, exactly the "token overlap is not a relation" failure named in
    `.claude/rules/no-dual-bookkeeping.md` ("Identity is explicit or it does not
    exist... Never derive [a relation] by:... token overlap... matching labels...").
    It was satisfied by (D1) two semantically unrelated triples that merely MENTION
    the action and the target separately, with no predicate ever connecting them, and
    by (D2) a graph that legitimately binds action1->target1 and action2->target2 but
    is then presented for the CROSS pairing action1->target2, which the graph never
    asserts anywhere. Both survived because presence-in-the-node-set cannot
    distinguish "the graph admits this exact pair" from "the graph admits this
    identifier paired with something else entirely."

    A Standing.ADMITTED verdict says only "this candidate content is admissible" -- it
    says nothing about which action/target an unrelated caller may attach it to.
    Binding must be a real, explicit typed edge derived from the admitted content
    itself, never from a caller's own self-asserted claim on the envelope (which an
    adversary controls just as freely as a legitimate caller does, and so proves
    nothing), and never from mere co-membership in the same node set.
    """
    graph = admission.graph
    if graph is None:
        return False
    try:
        return (URIRef(action_iri), _AFL_TARGET_RESOURCE, URIRef(target_resource)) in graph
    except Exception:
        return False


class ConsequenceActuator(Protocol):
    """Actuator responsible for executing external consequence (§30)."""

    def actuate(self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        """Perform consequence actuation. Returns evidence mapping."""
        ...

    def actuator_digest(self) -> str:
        """Digest of actuator implementation/identity."""
        ...


class ConsequenceVerifier(Protocol):
    """Independent postcondition verifier (§30). Must not be same object as Actuator."""

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Optional[Mapping[str, Any]],
    ) -> bool:
        """Verify consequence postcondition independently."""
        ...

    def verifier_digest(self) -> str:
        """Digest of verifier implementation/identity."""
        ...


class ConsequenceBoundaryError(RuntimeError):
    """Base exception for Consequence Boundary failures."""


class UnreceiptedActuationAttemptError(ConsequenceBoundaryError):
    """Raised when actuation is attempted without a durable prepared receipt (§4.8)."""


class ColludingRolesError(ConsequenceBoundaryError):
    """Raised when actuator and verifier are the exact same instance."""


class ReplayProtectionViolationError(ConsequenceBoundaryError):
    """Raised when duplicate non-idempotent execution is detected."""


@dataclass(frozen=True, slots=True)
class ExecutionEnvelope:
    """Input payload to the Consequence Boundary."""

    idempotency_token: str
    action_iri: str
    target_resource: str
    actor_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    consequence_class: str = "LOCAL_EFFECT"
    grant_id: Optional[str] = None
    plan_digest: str = "genesis:0" * 4
    artifact: Optional[ExecutableArtifact] = None
    construction_receipt: Optional[ConstructionReceipt] = None
    admitted_semantics: Optional[AdmittedSemantics] = None
    # AFDE-2604 (additive, optional -- existing callers that never pass this are
    # unaffected): the real admission.pipeline.AdmissionResult for this envelope's
    # originating candidate content. ConsequenceBoundary.execute() itself does not
    # inspect this field (backward compatible); only the new, strict
    # ConsequenceBoundary.execute_admitted() entry point requires and checks it.
    admission_result: Optional[AdmissionResult] = None


@dataclass(frozen=True, slots=True)
class BoundaryExecutionResult:
    """Outcome returned by BRCE Boundary."""

    success: bool
    state: TerminalReceiptState
    prepared_receipt: Optional[PreparedReceipt]
    final_receipt: Optional[FinalReceipt]
    refusal_code: Optional[str] = None
    reason: str = ""
    replayed: bool = False


class ConsequenceBoundary:
    """Reference Consequence Boundary (BRCE) enforcing Zero Unreceipted Actuation (§30, §31, §63).

    Pipeline:
    1. Check Idempotency / Replay (§55)
    2. Verify Authority via AuthorityBroker (§28, §29)
    3. Verify Construction integrity if artifact supplied: A = \mu(O*) (§5, §26)
    4. Mint & Commit Durable PreparedReceipt BEFORE DO (§4.8, §31)
    5. Execute Actuator DO (§30)
    6. Postcondition Verification via independent Verifier (§30)
    7. Mint & Commit FinalReceipt (§31)

    AFDE-2604 architecture fix (Local Round 3, unified enforcement): admission
    enforcement is a property of THIS INSTANCE's configuration
    (`require_admission`), never of which public method a caller happens to invoke.
    Superseded gap (cross-entry-point confused-deputy qualification, Mutation CD-2):
    previously `execute_admitted()` was the ONLY method that ever checked
    `envelope.admission_result`; `execute()` never did, for any instance, under any
    configuration -- so a real caller (or a refactor, or an adversary who simply
    prefers the other public method) could reach full, real actuation for the exact
    same action/target an `execute_admitted()` call on the SAME instance genuinely
    refused, merely by calling `.execute()` instead. Fix: `require_admission=True`
    at construction makes `execute()` itself apply the identical admission gate
    `execute_admitted()` applies, so the two methods become behaviorally identical
    for gating purposes on that instance -- there is no longer a caller-selectable
    bypass for an instance configured to require admission.

    AFDE-2604 fail-secure closure (this pass, closing DW-1/UE-2/UE-3): the
    class-level default flipped from `require_admission=False` to
    `require_admission=True`. Previously the permissive default meant "secure by
    default" was a property of the one `sa2a/cli.py hook_reflex` command's own
    construction choices, never of this class itself -- any other caller
    constructing `ConsequenceBoundary(...)` with its own bare defaults (a script, a
    test helper, a future integration) reproduced the fully permissive
    `candidate -> authority -> DO` path with zero warning, a real, adversarially
    confirmed gap (`test_mutation_dw1_direct_library_construction_bypasses_
    admission_entirely` in
    `tests/sa2a/conformance/test_afde_2604_default_wiring_bypass_qualification.py`).
    `execute()` on a bare-default instance now enforces the same admission gate
    `execute_admitted()` always has -- a caller that genuinely needs the old,
    permissive shape (e.g. a unit test of a component that deliberately predates
    or does not care about the admission fence) must now pass
    `require_admission=False` explicitly, so permissive behavior is always an
    affirmative, visible choice at the call site, never a silent default.
    `execute_admitted()` is unaffected by the flag either way -- it always
    enforces the gate, exactly as before this fix.
    """

    def __init__(
        self,
        authority_broker: AuthorityBroker,
        actuator: ConsequenceActuator,
        verifier: ConsequenceVerifier,
        receipt_store: Optional[ReceiptStore] = None,
        require_admission: bool = True,
    ) -> None:
        if actuator is verifier:
            raise ColludingRolesError(
                "Actuator and Verifier must be distinct objects; colluding roles forbidden (§30)."
            )
        self._authority_broker = authority_broker
        self._actuator = actuator
        self._verifier = verifier
        self._receipt_store = receipt_store or ReceiptStore()
        # AFDE-2604 architecture fix (unified enforcement): additive, defaults to
        # False so every existing caller/test that never passes this argument keeps
        # today's exact `execute()` behavior (backward compatible).
        self._require_admission = require_admission

    @property
    def receipt_store(self) -> ReceiptStore:
        return self._receipt_store

    @property
    def require_admission(self) -> bool:
        return self._require_admission

    def execute(self, envelope: ExecutionEnvelope) -> BoundaryExecutionResult:
        """Execute consequential action through strict reference pipeline.

        SELECT -> CONSTRUCT -> AuthorityBroker -> BRCE -> DO

        AFDE-2604 architecture fix (unified enforcement): when this instance was
        constructed with `require_admission=True`, the SAME admission gate
        `execute_admitted()` applies is enforced here too, before Step 1 -- so this
        method and `execute_admitted()` are behaviorally identical for gating
        purposes on a strict instance, and there is no method choice that bypasses
        the fence. When `require_admission=False` (the default), this check is
        skipped entirely and the rest of this method is byte-for-byte unchanged.
        """
        if self._require_admission:
            gate_result = self._enforce_admission_gate(envelope)
            if gate_result is not None:
                return gate_result

        # Step 1: Idempotency / Replay Protection (§55)
        existing_final = self._receipt_store.get_final(envelope.idempotency_token)
        if existing_final is not None:
            prepared = self._receipt_store.get_prepared(envelope.idempotency_token)

            if existing_final.state == TerminalReceiptState.EXECUTED:
                # AFDE-2604 fresh-mutations closure (Mutation B): an idempotency token is
                # bound, permanently, to the EXACT action_iri/target_resource recorded on
                # the PreparedReceipt minted at THIS token's first EXECUTED write (Step 4,
                # always minted before actuation -- see below). A token is never authority
                # to substitute in a DIFFERENT action/target after the fact, even when the
                # replaying request happens to be independently, validly authorized for
                # that different identity -- re-authorizing the SUBSTITUTED identity would
                # correctly confirm the requester may act, but the receipt handed back must
                # never be for a DIFFERENT actuation than the one that receipt evidences
                # (no-dual-bookkeeping.md object-identity binding). Checked BEFORE
                # re-authorization below: there is no reason to even ask whether the
                # substituted identity is authorized if the token was never bound to it.
                #
                # Deliberately scoped to action_iri/target_resource ONLY at this point (not
                # actor_id): an actor-identity mismatch must still route through the real
                # re-authorization call below first (an ungranted adversary is refused there,
                # via REFUSED_REPLAY_NOT_REAUTHORIZED, exactly as `test_mutation_consequence
                # .py`'s already-pinned `test_idempotency_replay_does_not_bind_replaying_
                # actor_identity` requires: a real AuthorityBroker.evaluate() call for the
                # replaying identity, not a short-circuit). The actor-identity check for a
                # replaying actor who IS independently, validly granted for this exact
                # action/target (Mutation D: passes reauth on its own merits, yet is still
                # not the actor this token was ever bound to) runs AFTER reauth succeeds --
                # see below.
                if prepared is not None and (
                    prepared.action_iri != envelope.action_iri
                    or prepared.target_resource != envelope.target_resource
                ):
                    reason = (
                        "Idempotency-token replay refused: idempotency_token "
                        f"{envelope.idempotency_token!r} is bound to action_iri="
                        f"{prepared.action_iri!r}, target_resource="
                        f"{prepared.target_resource!r} (recorded on the PreparedReceipt "
                        "minted at this token's first EXECUTED write), but this replaying "
                        f"request presents a DIFFERENT action_iri={envelope.action_iri!r}, "
                        f"target_resource={envelope.target_resource!r}. An idempotency "
                        "token identifies one fixed actuation identity; presenting it "
                        "never authorizes substituting in a different action/target, even "
                        "one the replaying request is independently, validly granted for "
                        "(§55, no-dual-bookkeeping object-identity binding)."
                    )
                    # Deliberately deterministic and NEVER persisted, for the same reason
                    # the reauth-mismatch receipt below is not persisted: the store already
                    # durably owns the ORIGINAL final (for the token's bound action1) under
                    # this token, and ReceiptStore.save_final() would raise on a digest
                    # mismatch if we tried to overwrite it with a receipt for a different
                    # action.
                    mismatch_receipt = FinalReceipt(
                        receipt_id=f"rec-token-mismatch-{envelope.idempotency_token}",
                        prepared_receipt_digest=prepared.digest,
                        idempotency_token=envelope.idempotency_token,
                        state=TerminalReceiptState.REFUSED,
                        postcondition_verified=False,
                        refusal_code=REFUSED_TOKEN_ACTION_MISMATCH,
                        reason=reason,
                        executed_at_ms=0,
                        execution_duration_ms=0,
                    )
                    return BoundaryExecutionResult(
                        success=False,
                        state=TerminalReceiptState.REFUSED,
                        prepared_receipt=prepared,
                        final_receipt=mismatch_receipt,
                        refusal_code=REFUSED_TOKEN_ACTION_MISMATCH,
                        reason=reason,
                        replayed=True,
                    )

                # AFDE-2604 fix (2)+(3): a cached EXECUTED response is a genuine consequence
                # already actuated for a specific granted identity -- an idempotency token
                # by itself is never authority to hand that response to a DIFFERENT
                # replaying request (fix 2), and a receipt's self-asserted grant_id is never
                # by itself proof that grant really authorized THIS request's action/target
                # (fix 3). Before returning the cached receipt, re-derive authorization from
                # scratch for the REPLAYING envelope's own actor_id/action_iri/
                # target_resource (deliberately ignoring both envelope.grant_id and the
                # cached receipt's own self-asserted grant_id -- neither is trusted here):
                # only a fresh, real AuthorityBroker.evaluate() may confirm the replay.
                reauth_decision = self._authority_broker.evaluate(
                    ConsequenceRequest(
                        actor_id=envelope.actor_id,
                        action_iri=envelope.action_iri,
                        target_resource=envelope.target_resource,
                        context=dict(envelope.parameters),
                    )
                )
                if not reauth_decision.authorized:
                    reason = (
                        "Idempotency-token replay refused: a cached EXECUTED receipt exists "
                        f"for token {envelope.idempotency_token!r}, but a fresh "
                        "AuthorityBroker evaluation for this replaying request's own "
                        f"actor_id={envelope.actor_id!r}, action_iri={envelope.action_iri!r}, "
                        f"target_resource={envelope.target_resource!r} did not confirm "
                        f"authorization (refusal_code={reauth_decision.refusal_code!r}). An "
                        "idempotency token is not an authority grant; presenting one never "
                        "substitutes for the requester's own authority evaluation (§55, §29)."
                    )
                    # Deliberately deterministic (no uuid4/time.time()), unlike a genuine
                    # first-time refusal receipt: this receipt is NEVER persisted (the store
                    # already durably owns the ORIGINAL final under this token, and
                    # ReceiptStore.save_final() would raise on a digest mismatch if we tried
                    # to overwrite it). A repeated replay attempt with the SAME envelope
                    # identity must therefore still yield a stable, reproducible digest --
                    # exactly the idempotent-response property ConsequenceCourt's own
                    # CHI-BRCE-04 gate independently checks by calling execute() twice and
                    # comparing digests.
                    mismatch_receipt = FinalReceipt(
                        receipt_id=f"rec-replay-refused-{envelope.idempotency_token}",
                        prepared_receipt_digest=prepared.digest if prepared is not None else "none",
                        idempotency_token=envelope.idempotency_token,
                        state=TerminalReceiptState.REFUSED,
                        postcondition_verified=False,
                        refusal_code=REFUSED_REPLAY_NOT_REAUTHORIZED,
                        reason=reason,
                        executed_at_ms=0,
                        execution_duration_ms=0,
                    )
                    return BoundaryExecutionResult(
                        success=False,
                        state=TerminalReceiptState.REFUSED,
                        prepared_receipt=None,
                        final_receipt=mismatch_receipt,
                        refusal_code=REFUSED_REPLAY_NOT_REAUTHORIZED,
                        reason=reason,
                        replayed=True,
                    )

                # AFDE-2604 architecture fix (Mutation D closure, replay-idempotency
                # qualification): the replaying request passed the action/target-binding
                # check above AND was independently, freshly re-authorized by the real
                # AuthorityBroker for its own actor_id/action_iri/target_resource -- but
                # neither of those confirms the replaying actor is the SAME actor this
                # token was originally bound to. A completely different actor_b, holding
                # their OWN, independent, validly registered AuthorityGrant for the exact
                # SAME action/target, would pass both checks above and receive actor_a's
                # cached EXECUTED receipt for an actuation actor_b never performed and was
                # never independently receipted for -- misrepresenting whose consequence
                # it is (no-dual-bookkeeping.md object-identity binding). Checked here,
                # AFTER reauth succeeds (not before), so an ungranted adversary is still
                # refused via the real REFUSED_REPLAY_NOT_REAUTHORIZED path above (a real
                # AuthorityBroker.evaluate() call, per `test_mutation_consequence.py`'s
                # already-pinned `test_idempotency_replay_does_not_bind_replaying_actor_
                # identity`), while a validly-granted-but-different actor is caught here.
                if prepared is not None and prepared.actor_id != envelope.actor_id:
                    reason = (
                        "Idempotency-token replay refused: idempotency_token "
                        f"{envelope.idempotency_token!r} is bound to actor_id="
                        f"{prepared.actor_id!r} (recorded on the PreparedReceipt minted at "
                        "this token's first EXECUTED write), but this replaying request "
                        f"presents a DIFFERENT actor_id={envelope.actor_id!r} -- even though "
                        "that actor is independently, validly authorized for this exact "
                        "action_iri/target_resource. An idempotency token identifies one "
                        "fixed actuation identity (including WHO acted, not only what was "
                        "acted upon); presenting it never authorizes substituting in a "
                        "different actor after the fact, and a cached receipt for one "
                        "actor's actuation must never be handed to a different actor's "
                        "request (§55, no-dual-bookkeeping object-identity binding)."
                    )
                    mismatch_receipt = FinalReceipt(
                        receipt_id=f"rec-token-mismatch-{envelope.idempotency_token}",
                        prepared_receipt_digest=prepared.digest,
                        idempotency_token=envelope.idempotency_token,
                        state=TerminalReceiptState.REFUSED,
                        postcondition_verified=False,
                        refusal_code=REFUSED_TOKEN_ACTION_MISMATCH,
                        reason=reason,
                        executed_at_ms=0,
                        execution_duration_ms=0,
                    )
                    return BoundaryExecutionResult(
                        success=False,
                        state=TerminalReceiptState.REFUSED,
                        prepared_receipt=prepared,
                        final_receipt=mismatch_receipt,
                        refusal_code=REFUSED_TOKEN_ACTION_MISMATCH,
                        reason=reason,
                        replayed=True,
                    )

            return BoundaryExecutionResult(
                success=existing_final.state == TerminalReceiptState.EXECUTED,
                state=existing_final.state,
                prepared_receipt=prepared,
                final_receipt=existing_final,
                refusal_code=existing_final.refusal_code,
                reason=f"Idempotency hit: action already completed with state {existing_final.state.value}",
                replayed=True,
            )

        # Step 2: Authority Broker Check (§28, §29)
        auth_req = ConsequenceRequest(
            actor_id=envelope.actor_id,
            action_iri=envelope.action_iri,
            target_resource=envelope.target_resource,
            context=dict(envelope.parameters),
            grant_id=envelope.grant_id,
        )
        auth_decision: AuthorityDecision = self._authority_broker.evaluate(auth_req)
        if not auth_decision.authorized:
            # Emit refused final receipt directly if requested or return Refusal
            refused_final = FinalReceipt(
                receipt_id=f"rec-refused-{uuid.uuid4().hex[:12]}",
                prepared_receipt_digest="none",
                idempotency_token=envelope.idempotency_token,
                state=TerminalReceiptState.REFUSED,
                postcondition_verified=False,
                refusal_code=auth_decision.refusal_code or REFUSED_NO_GRANT,
                reason=auth_decision.reason,
            )
            self._receipt_store.save_final(refused_final)
            return BoundaryExecutionResult(
                success=False,
                state=TerminalReceiptState.REFUSED,
                prepared_receipt=None,
                final_receipt=refused_final,
                refusal_code=auth_decision.refusal_code or REFUSED_NO_GRANT,
                reason=auth_decision.reason,
            )

        # Step 3: Construction Integrity Verification (if artifact provided)
        admitted_input_digest = "genesis:0" * 4
        artifact_digest = "none"
        if envelope.artifact is not None:
            artifact_digest = envelope.artifact.artifact_digest
            if envelope.construction_receipt is not None and envelope.admitted_semantics is not None:
                admitted_input_digest = envelope.admitted_semantics.canonical_digest()
                if not envelope.construction_receipt.verify(
                    envelope.admitted_semantics, envelope.artifact
                ):
                    refused_final = FinalReceipt(
                        receipt_id=f"rec-refused-{uuid.uuid4().hex[:12]}",
                        prepared_receipt_digest="none",
                        idempotency_token=envelope.idempotency_token,
                        state=TerminalReceiptState.REFUSED,
                        postcondition_verified=False,
                        refusal_code="REFUSED_CONSTRUCTION_INTEGRITY",
                        reason="Construction receipt does not verify against admitted semantics and artifact",
                    )
                    self._receipt_store.save_final(refused_final)
                    return BoundaryExecutionResult(
                        success=False,
                        state=TerminalReceiptState.REFUSED,
                        prepared_receipt=None,
                        final_receipt=refused_final,
                        refusal_code="REFUSED_CONSTRUCTION_INTEGRITY",
                        reason=refused_final.reason,
                    )

        # Step 4: Mint and commit durable PreparedReceipt BEFORE DO (§4.8, §31)
        # Zero Unreceipted Actuation: Must exist in durable store before calling self._actuator.actuate
        existing_prep = self._receipt_store.get_prepared(envelope.idempotency_token)
        if existing_prep is None:
            # AFDE-2604 (durable admission-identity evidence, closure pass): binds the
            # exact AdmissionResult that gated this actuation (when present) onto the
            # durable receipt itself, rather than leaving admission as an unrecorded
            # upstream fact this receipt only implicitly depended on.
            admission_digest: str = "none"
            if envelope.admission_result is not None and envelope.admission_result.digest:
                admission_digest = envelope.admission_result.digest
            prepared_receipt = PreparedReceipt(
                prepared_id=f"prep-{uuid.uuid4().hex[:12]}",
                idempotency_token=envelope.idempotency_token,
                action_iri=envelope.action_iri,
                target_resource=envelope.target_resource,
                actor_id=envelope.actor_id,
                grant_id=auth_decision.grant_id or envelope.grant_id or "grant-anon",
                plan_digest=envelope.plan_digest,
                artifact_digest=artifact_digest,
                admitted_input_digest=admitted_input_digest,
                admission_digest=admission_digest,
                consequence_class=envelope.consequence_class,
                parameters=envelope.parameters,
                previous_receipt_digest=self._receipt_store.last_receipt_digest(),
            )
            self._receipt_store.save_prepared(prepared_receipt)
        else:
            # AFDE-2604 architecture fix (Mutation E closure, replay-idempotency
            # qualification): `existing_final` is guaranteed None here (Step 1 above
            # always returns before reaching this point whenever a FinalReceipt
            # already exists), so a non-None `existing_prep` at this point means the
            # token is sitting in the genuine "prepared, not yet finalized" crash
            # window -- a real PreparedReceipt was durably committed (Step 4 of some
            # prior, since-interrupted call), but Steps 5-7 of that call never
            # completed. That durable PreparedReceipt already binds this token to ONE
            # fixed actuation identity (actor_id, action_iri, target_resource),
            # exactly like a cached EXECUTED receipt does above -- reusing it
            # verbatim while actuating a DIFFERENT identity would mint a FinalReceipt
            # whose own `prepared_receipt_digest` describes an action that was never
            # actually, physically actuated (Zero Unreceipted Actuation nominally
            # satisfied -- SOME durable receipt predates the call -- but its content
            # does not describe the actuation that occurred: the exact
            # no-dual-bookkeeping.md object-identity violation named
            # "ActuationClosed must reference the SAME Actuation that was opened").
            # Refuse before any reauthorization or actuation; a legitimate retry
            # presenting the SAME identity the stale PreparedReceipt already
            # describes is unaffected and proceeds normally below.
            if (
                existing_prep.action_iri != envelope.action_iri
                or existing_prep.target_resource != envelope.target_resource
                or existing_prep.actor_id != envelope.actor_id
            ):
                reason = (
                    "Idempotency-token replay refused: idempotency_token "
                    f"{envelope.idempotency_token!r} already has a durably-committed "
                    f"PreparedReceipt bound to actor_id={existing_prep.actor_id!r}, "
                    f"action_iri={existing_prep.action_iri!r}, target_resource="
                    f"{existing_prep.target_resource!r} (no FinalReceipt exists yet for "
                    "this token -- a genuine prepared-but-not-finalized crash window), "
                    f"but this request presents actor_id={envelope.actor_id!r}, "
                    f"action_iri={envelope.action_iri!r}, target_resource="
                    f"{envelope.target_resource!r}. An idempotency token identifies one "
                    "fixed actuation identity from the moment its first PreparedReceipt "
                    "is durably committed, not only from its first FinalReceipt "
                    "(no-dual-bookkeeping.md object-identity binding, §4.8 Zero "
                    "Unreceipted Actuation)."
                )
                mismatch_receipt = FinalReceipt(
                    receipt_id=f"rec-token-mismatch-{envelope.idempotency_token}",
                    prepared_receipt_digest=existing_prep.digest,
                    idempotency_token=envelope.idempotency_token,
                    state=TerminalReceiptState.REFUSED,
                    postcondition_verified=False,
                    refusal_code=REFUSED_TOKEN_ACTION_MISMATCH,
                    reason=reason,
                    executed_at_ms=0,
                    execution_duration_ms=0,
                )
                # This IS this token's genuine first FinalReceipt (existing_final was
                # None on entry, by construction), so it is durably persisted, unlike
                # the deterministic non-persisted mismatch receipts elsewhere in this
                # method that protect an ALREADY-existing durable final from being
                # overwritten.
                self._receipt_store.save_final(mismatch_receipt)
                return BoundaryExecutionResult(
                    success=False,
                    state=TerminalReceiptState.REFUSED,
                    prepared_receipt=existing_prep,
                    final_receipt=mismatch_receipt,
                    refusal_code=REFUSED_TOKEN_ACTION_MISMATCH,
                    reason=reason,
                    replayed=True,
                )
            prepared_receipt = existing_prep

        # Verification that durable prepared receipt actually exists in store prior to execution
        if not self._receipt_store.has_idempotency_token(envelope.idempotency_token):
            raise UnreceiptedActuationAttemptError(
                "PreparedReceipt was not committed to durable storage prior to actuation! Zero Unreceipted Actuation violated."
            )

        # Step 5: Actuate DO
        t0 = time.time()
        actuation_succeeded = False
        evidence: Mapping[str, Any] = {}
        failure_reason = ""
        try:
            evidence = self._actuator.actuate(
                action_iri=envelope.action_iri,
                target_resource=envelope.target_resource,
                parameters=envelope.parameters,
            )
            actuation_succeeded = True
        except Exception as e:
            actuation_succeeded = False
            failure_reason = str(e)

        duration_ms = int((time.time() - t0) * 1000)

        # Step 6: Postcondition Verification via independent Verifier (§30)
        verified = False
        try:
            verified = self._verifier.verify_postcondition(
                action_iri=envelope.action_iri,
                target_resource=envelope.target_resource,
                parameters=envelope.parameters,
                evidence=evidence if actuation_succeeded else None,
            )
        except Exception as ve:
            verified = False
            if not failure_reason:
                failure_reason = f"Verifier exception: {ve}"

        # Step 7: Terminal State Resolution & FinalReceipt Issuance (§31)
        if actuation_succeeded and verified:
            terminal_state = TerminalReceiptState.EXECUTED
        elif actuation_succeeded and not verified:
            terminal_state = TerminalReceiptState.UNKNOWN_OUTCOME
        else:
            terminal_state = TerminalReceiptState.FAILED

        final_receipt = FinalReceipt(
            receipt_id=f"rec-{uuid.uuid4().hex[:12]}",
            prepared_receipt_digest=prepared_receipt.digest,
            idempotency_token=envelope.idempotency_token,
            state=terminal_state,
            postcondition_verified=verified,
            evidence=evidence,
            refusal_code="ACTUATION_FAILED" if not actuation_succeeded else (
                "POSTCONDITION_UNSATISFIED" if not verified else None
            ),
            reason=failure_reason if failure_reason else ("Success" if verified else "Unverified"),
            execution_duration_ms=duration_ms,
        )
        self._receipt_store.save_final(final_receipt)

        return BoundaryExecutionResult(
            success=(terminal_state == TerminalReceiptState.EXECUTED),
            state=terminal_state,
            prepared_receipt=prepared_receipt,
            final_receipt=final_receipt,
            refusal_code=final_receipt.refusal_code,
            reason=final_receipt.reason,
        )

    def _enforce_admission_gate(
        self, envelope: ExecutionEnvelope
    ) -> Optional[BoundaryExecutionResult]:
        """Shared admission gate -- AFDE-2604 architecture fix (unified enforcement).

        Used by BOTH `execute()` (only when this instance was constructed with
        `require_admission=True`) and `execute_admitted()` (always, unconditionally):
        admission enforcement is a single, shared check, applied identically
        regardless of which public method a caller invokes -- never two independent
        implementations that could drift or be individually bypassed.

        Refuses unless a real, bound Standing.ADMITTED AdmissionResult is present on
        the envelope, and that admission's own content actually covers this exact
        action_iri/target_resource (via a real, explicit RDF triple -- see
        `_admission_covers_action_target()`), BEFORE AuthorityBroker.evaluate() or
        actuation are ever reached (AFDE-2604, local closure of A2A-2604 "wire
        semantic admission into the live consequence path").

        Enforces the composed law:
            candidate semantic state -> ADMIT -> SELECT -> CONSTRUCT -> authority grant -> DO
        never:
            candidate -> authority -> DO

        AFDE-2604 fresh-mutations closure (Mutation C): checked on EVERY call, not
        merely the first call for a given idempotency token -- the admission
        requirement is a property of the gate itself, not of first-call-only: a
        token that already reached a real EXECUTED actuation under a genuine
        admission must not become a free pass for a LATER call that presents no
        admission (or a content-unbound one) at all.

        Returns `None` when the gate passes (nothing to do; the caller proceeds with
        its own normal pipeline). Returns the full refusal `BoundaryExecutionResult`
        otherwise. Persistence: if NO final receipt exists yet for this token, a
        genuine admission-gate refusal is durably persisted as this token's first
        (and, for a refusal, only) final receipt. If a final receipt ALREADY exists
        under this token (a prior admission refusal, a prior authority refusal, or a
        prior real execution) and THIS call's own admission gate now fails, a
        deterministic, NON-persisted refusal is returned instead --
        `ReceiptStore.save_final()` would raise on a digest mismatch if we tried to
        overwrite the token's existing durable record, and the durable record itself
        must never be corrupted by a later call's own failure to present admission.
        """
        existing_final = self._receipt_store.get_final(envelope.idempotency_token)
        admission = envelope.admission_result

        refusal_code: Optional[str] = None
        reason: str = ""
        if admission is None or admission.standing != Standing.ADMITTED:
            refusal_code = REFUSED_NOT_ADMITTED
            if admission is None:
                reason = (
                    "AFDE-2604 admission fence: no AdmissionResult is bound to this "
                    "envelope (ExecutionEnvelope.admission_result is None). A candidate "
                    "must be admitted via a real admission.pipeline.AdmissionPipeline."
                    "admit() call, with the resulting AdmissionResult bound onto the "
                    "envelope, before it may reach AuthorityBroker.evaluate() or DO. This "
                    "gate is checked on every call through this admission-gated entry "
                    "point, including a repeat call under a token that already has a "
                    "final receipt -- presenting no admission is refused even if an "
                    "EARLIER call under this same token was genuinely, correctly admitted "
                    "and executed."
                )
            else:
                reason = (
                    "AFDE-2604 admission fence: ExecutionEnvelope.admission_result."
                    f"standing == {admission.standing.value!r}, not Standing.ADMITTED. "
                    "A REFUSED (or otherwise non-ADMITTED) admission outcome must never "
                    "be repaired or bypassed by presenting a valid AuthorityGrant for "
                    "the same actuation identity."
                )
        elif not _admission_covers_action_target(
            admission, envelope.action_iri, envelope.target_resource
        ):
            refusal_code = REFUSED_ADMISSION_CONTENT_NOT_BOUND
            reason = (
                "AFDE-2604 admission fence (relational-binding closure): "
                "ExecutionEnvelope.admission_result reached Standing.ADMITTED (digest="
                f"{admission.digest!r}), but its admitted candidate graph contains no "
                f"real triple <{envelope.action_iri}> <urn:autofde-lab:targetResource> "
                f"<{envelope.target_resource}> . A Standing.ADMITTED verdict for SOME "
                "candidate content is never, by itself, permission to actuate an "
                "arbitrary, unrelated action/target -- the admission must explicitly, "
                "relationally bind the exact action/target being executed, not merely "
                "co-mention both identifiers somewhere in the same graph."
            )

        if refusal_code is None:
            return None

        if existing_final is None:
            refused_final = FinalReceipt(
                receipt_id=f"rec-refused-{uuid.uuid4().hex[:12]}",
                prepared_receipt_digest="none",
                idempotency_token=envelope.idempotency_token,
                state=TerminalReceiptState.REFUSED,
                postcondition_verified=False,
                refusal_code=refusal_code,
                reason=reason,
            )
            self._receipt_store.save_final(refused_final)
        else:
            # A final receipt of ANY state already durably exists under this token --
            # never attempt to overwrite it (ReceiptStore.save_final() would raise on
            # digest mismatch for a different-content receipt, and even a matching one
            # would misrepresent THIS call's own outcome as the original write). Return
            # a deterministic, non-persisted typed refusal for THIS call instead, the
            # same non-persisted-refusal pattern execute()'s own Step 1 mismatch checks
            # use above.
            refused_final = FinalReceipt(
                receipt_id=f"rec-admitted-gate-refused-{envelope.idempotency_token}",
                prepared_receipt_digest="none",
                idempotency_token=envelope.idempotency_token,
                state=TerminalReceiptState.REFUSED,
                postcondition_verified=False,
                refusal_code=refusal_code,
                reason=reason,
                executed_at_ms=0,
                execution_duration_ms=0,
            )
        return BoundaryExecutionResult(
            success=False,
            state=TerminalReceiptState.REFUSED,
            prepared_receipt=None,
            final_receipt=refused_final,
            refusal_code=refusal_code,
            reason=reason,
            replayed=existing_final is not None,
        )

    def execute_admitted(self, envelope: ExecutionEnvelope) -> BoundaryExecutionResult:
        """Strict entry point: refuse unless a real, bound Standing.ADMITTED AdmissionResult
        is present on the envelope, and that admission's own content actually covers this
        exact action_iri/target_resource, BEFORE AuthorityBroker.evaluate() or actuation are
        ever reached (AFDE-2604, local closure of A2A-2604 "wire semantic admission into the
        live consequence path"). See `_enforce_admission_gate()` for the full gate contract
        (shared with `execute()` when this instance requires admission).

        Additive: `execute()` itself is unaffected unless this instance was constructed
        with `require_admission=True` (AFDE-2604 architecture fix, unified enforcement) --
        this method always enforces the gate, regardless of that flag, so it remains a
        strict, opt-in entry point for callers of an otherwise-default-configured
        instance. A typed refusal is returned, never a bare exception. When the gate
        passes, control is delegated to `execute()`, whose own Step 1 idempotency/replay
        handling (including the Mutation B/D/(2)/(3) re-authorization and
        token-identity-binding checks) is the single source of truth for a repeated token.
        """
        gate_result = self._enforce_admission_gate(envelope)
        if gate_result is not None:
            return gate_result
        return self.execute(envelope)
