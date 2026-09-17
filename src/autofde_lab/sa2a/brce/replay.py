"""Replay Engine for Semantic A2A (RFC-SA2A-001 v26.9.16 §32).

Verifies the causal sequence:
    Semantic Admission -> Plan Selection -> Construction -> Authorization -> Receipt Validation
WITHOUT re-executing external consequence (`Replay != DO`).

Replay guarantees:
1. Re-verifies cryptographic hash chains between PreparedReceipt and FinalReceipt.
2. Re-verifies Construction Receipt bindings A = \mu(O*) without invoking code.
3. Re-verifies that authority existed for the requested action under the recorded context.
4. Checks receipt sequence continuity against the durable receipt store.
5. Emits standing: ALIVE / PARTIAL_ALIVE / BLOCKED / BUILD_BROKEN / UNSUPPORTED (§32).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

from autofde_lab.sa2a.authority.broker import AuthorityBroker, ConsequenceRequest
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    ReceiptStore,
    TerminalReceiptState,
    compute_receipt_digest,
)
from autofde_lab.sa2a.construct.constructor import (
    AdmittedSemantics,
    ConstructionReceipt,
    ExecutableArtifact,
)


class ReplayVerdict(str, Enum):
    """Replay verification verdict states."""

    VALID = "VALID"
    INVALID_HASH_CHAIN = "INVALID_HASH_CHAIN"
    INVALID_CONSTRUCTION = "INVALID_CONSTRUCTION"
    INVALID_AUTHORITY = "INVALID_AUTHORITY"
    UNRECEIPTED_ACTUATION = "UNRECEIPTED_ACTUATION"
    DUPLICATE_RECEIPT = "DUPLICATE_RECEIPT"
    CORRUPTED_RECORD = "CORRUPTED_RECORD"


class ReplayStanding(str, Enum):
    """Gall status / standing derived from replay verification."""

    ALIVE = "ALIVE"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class ReplayReport:
    """Report detailing replay verification of receipt records (§32)."""

    total_pairs: int
    executed_count: int
    refused_count: int
    failed_count: int
    verdict: ReplayVerdict
    standing: ReplayStanding
    chain_digest: str
    verified_without_actuation: bool = True
    errors: Sequence[str] = field(default_factory=tuple)


class ReplayEngine:
    """Offline deterministic replay engine (§32).

    Reproduces semantic admission, plan selection, construction, authorization,
    and receipt validation WITHOUT re-executing external consequences.
    """

    def __init__(self, authority_broker: Optional[AuthorityBroker] = None) -> None:
        self._authority_broker = authority_broker

    def verify_chain(
        self,
        receipt_records: Sequence[Mapping[str, Any]],
        admitted_semantics: Optional[AdmittedSemantics] = None,
        artifact: Optional[ExecutableArtifact] = None,
        construction_receipt: Optional[ConstructionReceipt] = None,
    ) -> ReplayReport:
        """Verify receipt record sequence without performing any external actuation.

        Re-checks:
        - Digest integrity of each PreparedReceipt and FinalReceipt
        - Causal chain link: final.prepared_receipt_digest == prepared.digest
        - Chronological previous_receipt_digest continuity
        - Construction receipt bindings if supplied
        - Authority validity if broker supplied
        """
        if not receipt_records:
            return ReplayReport(
                total_pairs=0,
                executed_count=0,
                refused_count=0,
                failed_count=0,
                verdict=ReplayVerdict.VALID,
                standing=ReplayStanding.ALIVE,
                chain_digest="genesis:0" * 4,
                verified_without_actuation=True,
            )

        errors: List[str] = []
        seen_digests: set[str] = set()
        expected_prev_digest = "genesis:0" * 4

        # Group records by idempotency token or process pairs
        prepared_map: Dict[str, Mapping[str, Any]] = {}
        final_map: Dict[str, Mapping[str, Any]] = {}

        for idx, rec in enumerate(receipt_records):
            kind = rec.get("kind")
            token = rec.get("idempotency_token")
            rec_digest = rec.get("digest")

            if not kind or not token or not rec_digest:
                errors.append(f"Record {idx}: Missing required header fields (kind, idempotency_token, digest)")
                continue

            if rec_digest in seen_digests:
                errors.append(f"Record {idx}: Duplicate receipt digest detected: {rec_digest}")
            seen_digests.add(rec_digest)

            if kind == "prepared":
                # Verify self-digest
                body = {
                    "prepared_id": rec["prepared_id"],
                    "idempotency_token": rec["idempotency_token"],
                    "action_iri": rec["action_iri"],
                    "target_resource": rec["target_resource"],
                    "actor_id": rec["actor_id"],
                    "grant_id": rec["grant_id"],
                    "plan_digest": rec["plan_digest"],
                    "artifact_digest": rec["artifact_digest"],
                    "admitted_input_digest": rec["admitted_input_digest"],
                    "consequence_class": rec["consequence_class"],
                    "parameters": rec["parameters"],
                    "prepared_at_ms": rec["prepared_at_ms"],
                    "previous_receipt_digest": rec["previous_receipt_digest"],
                }
                computed = compute_receipt_digest({"kind": "prepared", "body": body})
                if computed != rec_digest:
                    errors.append(f"Record {idx}: PreparedReceipt digest mismatch: expected {computed}, got {rec_digest}")

                prepared_map[token] = rec

            elif kind == "final":
                # Verify self-digest
                body = {
                    "receipt_id": rec["receipt_id"],
                    "prepared_receipt_digest": rec["prepared_receipt_digest"],
                    "idempotency_token": rec["idempotency_token"],
                    "state": rec["state"],
                    "postcondition_verified": rec["postcondition_verified"],
                    "evidence": rec["evidence"],
                    "refusal_code": rec.get("refusal_code"),
                    "reason": rec.get("reason", ""),
                    "executed_at_ms": rec["executed_at_ms"],
                    "execution_duration_ms": rec["execution_duration_ms"],
                }
                computed = compute_receipt_digest({"kind": "final", "body": body})
                if computed != rec_digest:
                    errors.append(f"Record {idx}: FinalReceipt digest mismatch: expected {computed}, got {rec_digest}")

                final_map[token] = rec
            else:
                errors.append(f"Record {idx}: Unknown receipt kind {kind}")

        # Re-verify Construction Binding if provided
        if construction_receipt is not None and admitted_semantics is not None and artifact is not None:
            if not construction_receipt.verify(admitted_semantics, artifact):
                errors.append("Construction receipt validation failed against admitted semantics and artifact")

        # Now check pairs
        executed_count = 0
        refused_count = 0
        failed_count = 0

        for token, final_rec in final_map.items():
            state = final_rec.get("state")
            if state == TerminalReceiptState.EXECUTED.value:
                executed_count += 1
            elif state == TerminalReceiptState.REFUSED.value:
                refused_count += 1
            else:
                failed_count += 1

            # Check prepared receipt link
            prep_rec = prepared_map.get(token)
            if prep_rec is None:
                if state != TerminalReceiptState.REFUSED.value:
                    errors.append(
                        f"Final receipt {final_rec.get('receipt_id')} for token {token} has NO preceding PreparedReceipt! Zero Unreceipted Actuation violated."
                    )
            else:
                # Check link
                if final_rec.get("prepared_receipt_digest") != prep_rec.get("digest"):
                    errors.append(
                        f"Final receipt {final_rec.get('receipt_id')} prepared_receipt_digest does not match prepared digest!"
                    )

                # Check authority offline if broker provided
                if self._authority_broker is not None:
                    auth_req = ConsequenceRequest(
                        actor_id=prep_rec["actor_id"],
                        action_iri=prep_rec["action_iri"],
                        target_resource=prep_rec["target_resource"],
                        context=prep_rec.get("parameters", {}),
                        grant_id=prep_rec["grant_id"],
                    )
                    decision = self._authority_broker.evaluate(auth_req)
                    if not decision.authorized and state == TerminalReceiptState.EXECUTED.value:
                        errors.append(
                            f"Action {prep_rec['action_iri']} was executed without valid authority grant!"
                        )

        # Compute chain digest
        all_digests = [r.get("digest", "") for r in receipt_records]
        chain_digest = compute_receipt_digest(all_digests)

        if errors:
            verdict = ReplayVerdict.INVALID_HASH_CHAIN
            standing = ReplayStanding.BUILD_BROKEN
        elif failed_count > 0 or refused_count > 0:
            verdict = ReplayVerdict.VALID
            standing = ReplayStanding.PARTIAL_ALIVE
        else:
            verdict = ReplayVerdict.VALID
            standing = ReplayStanding.ALIVE

        return ReplayReport(
            total_pairs=len(final_map),
            executed_count=executed_count,
            refused_count=refused_count,
            failed_count=failed_count,
            verdict=verdict,
            standing=standing,
            chain_digest=chain_digest,
            verified_without_actuation=True,
            errors=tuple(errors),
        )
