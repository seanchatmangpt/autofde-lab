"""Receipt models and replay protection for Semantic A2A (RFC-SA2A-001 v26.9.16 §31, §55).

Establishes:
- Terminal receipt states (§31):
    EXECUTED, REFUSED, FAILED, RECONCILED, COMPENSATED, UNKNOWN_OUTCOME.
- PreparedReceipt (§31, §4.8):
    Durable receipt minted and recorded BEFORE consequential execution begins
    ("Zero Unreceipted Actuation").
- FinalReceipt (§31):
    Receipt issued upon execution completion, binding prepared receipt digest,
    postcondition verification, and terminal outcome.
- Replay protection (§55):
    Idempotency tokens, sequence validation, and prevention of duplicate actuation.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence


class TerminalReceiptState(str, Enum):
    """Terminal receipt states under RFC-SA2A-001 §31."""

    EXECUTED = "EXECUTED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    RECONCILED = "RECONCILED"
    COMPENSATED = "COMPENSATED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


def compute_receipt_digest(data: Mapping[str, Any] | Sequence[Any] | str | bytes) -> str:
    """Compute canonical SHA-256 hex digest for arbitrary receipt data."""
    if isinstance(data, bytes):
        payload = data
    elif isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class PreparedReceipt:
    """Durable prepared receipt minted BEFORE execution begins (§4.8, §31).

    Enforces Zero Unreceipted Actuation: No external effect may be actuated
    without a durable PreparedReceipt committed to persistent/durable state.
    """

    prepared_id: str
    idempotency_token: str
    action_iri: str
    target_resource: str
    actor_id: str
    grant_id: str
    plan_digest: str
    artifact_digest: str
    admitted_input_digest: str
    consequence_class: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    prepared_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    previous_receipt_digest: str = "genesis:0" * 4

    @property
    def digest(self) -> str:
        """Compute content-addressed digest of the prepared receipt."""
        body = {
            "prepared_id": self.prepared_id,
            "idempotency_token": self.idempotency_token,
            "action_iri": self.action_iri,
            "target_resource": self.target_resource,
            "actor_id": self.actor_id,
            "grant_id": self.grant_id,
            "plan_digest": self.plan_digest,
            "artifact_digest": self.artifact_digest,
            "admitted_input_digest": self.admitted_input_digest,
            "consequence_class": self.consequence_class,
            "parameters": self.parameters,
            "prepared_at_ms": self.prepared_at_ms,
            "previous_receipt_digest": self.previous_receipt_digest,
        }
        return compute_receipt_digest({"kind": "prepared", "body": body})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "prepared",
            "prepared_id": self.prepared_id,
            "idempotency_token": self.idempotency_token,
            "action_iri": self.action_iri,
            "target_resource": self.target_resource,
            "actor_id": self.actor_id,
            "grant_id": self.grant_id,
            "plan_digest": self.plan_digest,
            "artifact_digest": self.artifact_digest,
            "admitted_input_digest": self.admitted_input_digest,
            "consequence_class": self.consequence_class,
            "parameters": dict(self.parameters),
            "prepared_at_ms": self.prepared_at_ms,
            "previous_receipt_digest": self.previous_receipt_digest,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class FinalReceipt:
    """Terminal final receipt issued upon execution completion (§31).

    Binds:
    - prepared_receipt_digest: Exact hash of the prerequisite PreparedReceipt.
    - state: Terminal state (EXECUTED, REFUSED, FAILED, RECONCILED, COMPENSATED, UNKNOWN_OUTCOME).
    - postcondition_verified: Verification result from an independent postcondition verifier.
    - evidence: Observed consequences / result payload.
    - refusal_code: Code if refused or failed.
    """

    receipt_id: str
    prepared_receipt_digest: str
    idempotency_token: str
    state: TerminalReceiptState
    postcondition_verified: bool
    evidence: Mapping[str, Any] = field(default_factory=dict)
    refusal_code: Optional[str] = None
    reason: str = ""
    executed_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    execution_duration_ms: int = 0

    @property
    def digest(self) -> str:
        """Compute content-addressed digest of the final receipt."""
        body = {
            "receipt_id": self.receipt_id,
            "prepared_receipt_digest": self.prepared_receipt_digest,
            "idempotency_token": self.idempotency_token,
            "state": self.state.value,
            "postcondition_verified": self.postcondition_verified,
            "evidence": self.evidence,
            "refusal_code": self.refusal_code,
            "reason": self.reason,
            "executed_at_ms": self.executed_at_ms,
            "execution_duration_ms": self.execution_duration_ms,
        }
        return compute_receipt_digest({"kind": "final", "body": body})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "final",
            "receipt_id": self.receipt_id,
            "prepared_receipt_digest": self.prepared_receipt_digest,
            "idempotency_token": self.idempotency_token,
            "state": self.state.value,
            "postcondition_verified": self.postcondition_verified,
            "evidence": dict(self.evidence),
            "refusal_code": self.refusal_code,
            "reason": self.reason,
            "executed_at_ms": self.executed_at_ms,
            "execution_duration_ms": self.execution_duration_ms,
            "digest": self.digest,
        }


class ReceiptStore:
    """In-memory or persistent store for prepared and final receipts.

    Provides replay protection (§55) by maintaining indexed maps of:
    - idempotency_token -> (PreparedReceipt, Optional[FinalReceipt])
    - receipt_digest -> receipt
    """

    def __init__(self) -> None:
        self._prepared_by_token: Dict[str, PreparedReceipt] = {}
        self._final_by_token: Dict[str, FinalReceipt] = {}
        self._receipts_by_digest: Dict[str, PreparedReceipt | FinalReceipt] = {}
        self._chain: List[str] = []  # Chronological order of digests

    def save_prepared(self, receipt: PreparedReceipt) -> None:
        """Store prepared receipt, checking idempotency."""
        if receipt.idempotency_token in self._prepared_by_token:
            existing = self._prepared_by_token[receipt.idempotency_token]
            if existing.digest != receipt.digest:
                raise ValueError(
                    f"Idempotency token conflict: {receipt.idempotency_token} already used with different parameters"
                )
            return  # Idempotent write
        self._prepared_by_token[receipt.idempotency_token] = receipt
        self._receipts_by_digest[receipt.digest] = receipt
        self._chain.append(receipt.digest)

    def save_final(self, receipt: FinalReceipt) -> None:
        """Store final receipt, checking idempotency."""
        if receipt.idempotency_token in self._final_by_token:
            existing = self._final_by_token[receipt.idempotency_token]
            if existing.digest != receipt.digest:
                raise ValueError(
                    f"Idempotency token conflict: final receipt already recorded for {receipt.idempotency_token}"
                )
            return
        self._final_by_token[receipt.idempotency_token] = receipt
        self._receipts_by_digest[receipt.digest] = receipt
        self._chain.append(receipt.digest)

    def get_prepared(self, idempotency_token: str) -> Optional[PreparedReceipt]:
        return self._prepared_by_token.get(idempotency_token)

    def get_final(self, idempotency_token: str) -> Optional[FinalReceipt]:
        return self._final_by_token.get(idempotency_token)

    def get_by_digest(self, digest: str) -> Optional[PreparedReceipt | FinalReceipt]:
        return self._receipts_by_digest.get(digest)

    def has_idempotency_token(self, idempotency_token: str) -> bool:
        return idempotency_token in self._prepared_by_token

    def is_completed(self, idempotency_token: str) -> bool:
        return idempotency_token in self._final_by_token

    def last_receipt_digest(self) -> str:
        if not self._chain:
            return "genesis:0" * 4
        return self._chain[-1]

    def all_records(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for d in self._chain:
            item = self._receipts_by_digest[d]
            records.append(item.to_dict())
        return records
