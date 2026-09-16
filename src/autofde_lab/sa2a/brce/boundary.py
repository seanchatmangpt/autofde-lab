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
    """

    def __init__(
        self,
        authority_broker: AuthorityBroker,
        actuator: ConsequenceActuator,
        verifier: ConsequenceVerifier,
        receipt_store: Optional[ReceiptStore] = None,
    ) -> None:
        if actuator is verifier:
            raise ColludingRolesError(
                "Actuator and Verifier must be distinct objects; colluding roles forbidden (§30)."
            )
        self._authority_broker = authority_broker
        self._actuator = actuator
        self._verifier = verifier
        self._receipt_store = receipt_store or ReceiptStore()

    @property
    def receipt_store(self) -> ReceiptStore:
        return self._receipt_store

    def execute(self, envelope: ExecutionEnvelope) -> BoundaryExecutionResult:
        """Execute consequential action through strict reference pipeline.

        SELECT -> CONSTRUCT -> AuthorityBroker -> BRCE -> DO
        """
        # Step 1: Idempotency / Replay Protection (§55)
        existing_final = self._receipt_store.get_final(envelope.idempotency_token)
        if existing_final is not None:
            prepared = self._receipt_store.get_prepared(envelope.idempotency_token)
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
                consequence_class=envelope.consequence_class,
                parameters=envelope.parameters,
                previous_receipt_digest=self._receipt_store.last_receipt_digest(),
            )
            self._receipt_store.save_prepared(prepared_receipt)
        else:
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
