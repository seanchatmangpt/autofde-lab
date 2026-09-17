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

AFDE-2604 store-layer defense-in-depth (this session, plus a later closure pass): a prior
pass fixed the candidate-to-authority/replay-reauthorization gap entirely at the point of use
(`ConsequenceBoundary.execute()`, `brce/boundary.py`), leaving `ReceiptStore.save_prepared`/
`save_final` themselves performing zero validation of a receipt's claimed `grant_id` against
the real `AuthorityBroker` grant registry -- documented, deliberately, in
`tests/sa2a/conformance/test_mutation_cross_court_identity.py`'s Test 1 docstring as a named,
unchanged store-layer finding. A first closure pass added a SECOND, INDEPENDENT layer
directly at the store: `ReceiptStore` gains an optional, constructor-injected
`authority_broker` reference (default `None`, preserving every existing caller
byte-for-byte). When configured, a NEW `PreparedReceipt` (one whose `idempotency_token` is
not already recorded) is refused with a typed `ReceiptGrantValidationError` unless its
claimed `grant_id` corresponds to a real, currently-registered `AuthorityGrant` that actually
authorizes this exact (actor_id, action_iri, target_resource) identity.

That first pass left `save_final` completely unvalidated and documented it as "unchanged" --
an independent adversarial re-derivation
(`tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation_mutations.py`) found
this was a real, exploitable gap, not a harmless one, and closed it here:

1. **`save_final` never called any validation at all.** `FinalReceipt` carries no
   `grant_id`/`actor_id`/`action_iri`/`target_resource` fields of its own (confirmed by
   dataclass field inspection), so a terminal `EXECUTED` `FinalReceipt` could be minted and
   durably persisted for an `idempotency_token` that was **never** passed to `save_prepared`
   at all -- with a broker configured that holds zero grants anywhere. This bypassed the
   entire "Zero Unreceipted Actuation" property (RFC-SA2A-001 SS4.8, SS31) the
   `PreparedReceipt`/`FinalReceipt` split exists to enforce.
2. **TOCTOU**: `_validate_grant_id` only ever ran once, at `save_prepared` time. A grant
   genuinely valid at that instant could expire (`AuthorityGrant.valid_until` elapses for
   real -- `AuthorityBroker.evaluate()` checks it with a live `time.time()` comparison, never
   cached at grant-registration time) before the corresponding `FinalReceipt` was saved, with
   zero re-check at commit time.

Fix (this session): `save_final` now mirrors `save_prepared`'s validation when a broker is
configured. Because `FinalReceipt` has no identity fields of its own, the identity is
resolved from the corresponding `PreparedReceipt` recorded under the SAME
`idempotency_token` -- refusing outright (typed `ReceiptGrantValidationError`,
`REFUSED_NO_PREPARED_RECEIPT`) when none exists (closes gap 1) -- and then a FRESH
`AuthorityBroker.evaluate()` call is performed at `save_final` time against that resolved
identity, never reusing/caching the `save_prepared`-time decision (closes gap 2: TOCTOU,
since the fresh call re-checks `valid_until` against the CURRENT clock). No-op, exactly as
`save_prepared`, when this store was constructed without a broker (the default) -- every
existing caller is unaffected.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

from autofde_lab.sa2a.authority.broker import AuthorityBroker, ConsequenceRequest


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


REFUSED_NO_PREPARED_RECEIPT = "REFUSED_NO_PREPARED_RECEIPT"
"""Refusal code (AFDE-2604, save_final closure): raised when `ReceiptStore.save_final` is
called, with a broker configured, for an `idempotency_token` that has no corresponding
`PreparedReceipt` ever recorded in this store. Distinct from any `AuthorityBroker` refusal
code (`REFUSED_NO_GRANT`, `REFUSED_EXPIRED_GRANT`, ...) because the broker is never even
consulted -- there is no identity to evaluate without a PreparedReceipt to resolve it from.
"""


class ReceiptGrantValidationError(ValueError):
    """Raised by `ReceiptStore.save_prepared`/`save_final` (AFDE-2604 store-layer
    defense-in-depth) when this store was constructed with a real `AuthorityBroker` and the
    receipt being saved is not honestly authorized.

    This is a SECOND, INDEPENDENT layer, not a replacement for the existing point-of-use
    fence: `ConsequenceBoundary.execute()` already performs its own real-time
    `AuthorityBroker.evaluate()` call before it ever constructs a `PreparedReceipt` (§28,
    §29; `brce/boundary.py` Step 2), and its idempotency-replay path independently
    re-authorizes on every replay (`REFUSED_REPLAY_NOT_REAUTHORIZED`). This exception exists
    so that ANY caller of `ReceiptStore.save_prepared`/`save_final` -- not only
    `ConsequenceBoundary` itself, e.g. a directly-constructed forged receipt of the kind
    `tests/sa2a/conformance/test_mutation_cross_court_identity.py` builds -- is fenced
    against durably persisting a receipt whose claim the broker's own grant registry does not
    honestly support, per `.claude/rules/no-dual-bookkeeping.md`: "identity is explicit or it
    does not exist."

    Two distinct causes, both raised as this same typed exception:

    - **`save_prepared`**: the `PreparedReceipt`'s own claimed `grant_id` does not correspond
      to a real, currently-registered `AuthorityGrant` for its own
      (actor_id, action_iri, target_resource). `refusal_code` is whatever
      `AuthorityBroker.evaluate()` returned (`REFUSED_NO_GRANT`, `REFUSED_EXPIRED_GRANT`,
      `REFUSED_CONSTRAINT_VIOLATION`, ...).
    - **`save_final`**: either (a) no `PreparedReceipt` was ever recorded for this
      `FinalReceipt`'s `idempotency_token` (`refusal_code=REFUSED_NO_PREPARED_RECEIPT` --
      `FinalReceipt` has no identity fields of its own, so there is nothing to resolve), or
      (b) a `PreparedReceipt` was found but a FRESH `AuthorityBroker.evaluate()` call against
      its identity -- performed at `save_final` time, not reused from `save_prepared` time --
      now returns `authorized=False` (most notably `REFUSED_EXPIRED_GRANT`: the grant was
      valid when `save_prepared` ran but has genuinely expired since, a TOCTOU window this
      fresh re-check closes).

    Scope, named honestly rather than silently mishandled: this check validates the claimed
    `grant_id` by looking it up directly in the broker's real `AuthorityGrant` registry
    (`AuthorityBroker.evaluate(ConsequenceRequest(..., grant_id=...))`, the same
    exact-grant-id lookup path `AuthorityBroker.evaluate()` itself uses). A receipt whose
    `grant_id` is instead a synthetic ODRL-policy-permission id (the
    `"policy-grant-<policy_uid>-<perm_uid>"` string `AuthorityBroker.evaluate()` mints for a
    policy-permission match with no explicit registered grant) is NOT a registered
    `AuthorityGrant` and would be refused here if presented while a broker is configured --
    a named scope limitation of this store-layer defense, not a defect: no caller in this
    repo constructs a `ReceiptStore`/`DurableDiskReceiptStore` with a broker today (this
    feature is additive and opt-in), so no existing ODRL-policy call path is affected.
    """

    def __init__(self, receipt: "PreparedReceipt | FinalReceipt", refusal_code: str, reason: str) -> None:
        self.receipt = receipt
        self.refusal_code = refusal_code
        self.reason = reason
        super().__init__(reason)


class ReceiptStore:
    """In-memory or persistent store for prepared and final receipts.

    Provides replay protection (§55) by maintaining indexed maps of:
    - idempotency_token -> (PreparedReceipt, Optional[FinalReceipt])
    - receipt_digest -> receipt

    AFDE-2604 (additive, optional -- every existing caller that never passes
    `authority_broker` is completely unaffected): when constructed with a real
    `AuthorityBroker` reference, `save_prepared` independently validates each NEW receipt's
    claimed `grant_id` against that broker's real grant registry before persisting it, and
    `save_final` mirrors that same validation (resolving the identity from the corresponding
    `PreparedReceipt` and re-evaluating fresh, at commit time, to close the TOCTOU window).
    See `ReceiptGrantValidationError` for exactly what is and is not covered by this check.
    """

    def __init__(self, authority_broker: Optional[AuthorityBroker] = None) -> None:
        self._prepared_by_token: Dict[str, PreparedReceipt] = {}
        self._final_by_token: Dict[str, FinalReceipt] = {}
        self._receipts_by_digest: Dict[str, PreparedReceipt | FinalReceipt] = {}
        self._chain: List[str] = []  # Chronological order of digests
        self._authority_broker: Optional[AuthorityBroker] = authority_broker

    def _evaluate_grant_or_raise(
        self,
        *,
        receipt: "PreparedReceipt | FinalReceipt",
        actor_id: str,
        action_iri: str,
        target_resource: str,
        grant_id: str,
        receipt_label: str,
        receipt_ident: str,
    ) -> None:
        """Shared evaluation core for both `save_prepared` and `save_final`: performs a
        FRESH `AuthorityBroker.evaluate()` call (never a cached/reused decision) against the
        given identity and raises typed `ReceiptGrantValidationError` on refusal. Callers
        resolve `actor_id`/`action_iri`/`target_resource`/`grant_id` themselves --
        `PreparedReceipt` carries them directly; `FinalReceipt` does not, so `save_final`
        resolves them from the corresponding `PreparedReceipt` before calling this.
        """
        decision = self._authority_broker.evaluate(  # type: ignore[union-attr]
            ConsequenceRequest(
                actor_id=actor_id,
                action_iri=action_iri,
                target_resource=target_resource,
                grant_id=grant_id,
            )
        )
        if not decision.authorized:
            raise ReceiptGrantValidationError(
                receipt,
                decision.refusal_code or "REFUSED_GRANT_VALIDATION_FAILED",
                (
                    f"ReceiptStore refuses to persist {receipt_label} "
                    f"{receipt_ident!r} (idempotency_token={receipt.idempotency_token!r}): "
                    f"claimed grant_id={grant_id!r} does not correspond to a real, "
                    f"currently-registered AuthorityGrant authorizing "
                    f"actor_id={actor_id!r}, action_iri={action_iri!r}, "
                    f"target_resource={target_resource!r} -- a fresh "
                    f"AuthorityBroker.evaluate() call for this exact claim returned "
                    f"authorized=False (refusal_code={decision.refusal_code!r}: "
                    f"{decision.reason})."
                ),
            )

    def _validate_grant_id(self, receipt: PreparedReceipt) -> None:
        """AFDE-2604: refuse (typed `ReceiptGrantValidationError`, never silent) a receipt
        whose claimed `grant_id` does not correspond to a real, currently-registered
        `AuthorityGrant` for this receipt's own (actor_id, action_iri, target_resource).
        No-op when this store was constructed without a broker (the default).
        """
        if self._authority_broker is None:
            return
        self._evaluate_grant_or_raise(
            receipt=receipt,
            actor_id=receipt.actor_id,
            action_iri=receipt.action_iri,
            target_resource=receipt.target_resource,
            grant_id=receipt.grant_id,
            receipt_label="PreparedReceipt",
            receipt_ident=receipt.prepared_id,
        )

    def _validate_final_grant_id(self, receipt: FinalReceipt) -> None:
        """AFDE-2604 (save_final closure, this session): mirrors `_validate_grant_id` onto
        `save_final`. No-op when this store was constructed without a broker (the default --
        byte-for-byte unchanged for every existing caller).

        `FinalReceipt` carries no `actor_id`/`action_iri`/`target_resource`/`grant_id` of its
        own, so this resolves that identity from the corresponding `PreparedReceipt` recorded
        under the SAME `idempotency_token` in this store:

        - If none exists, refuses outright with `REFUSED_NO_PREPARED_RECEIPT` -- a terminal
          `EXECUTED` receipt for an identity that was never prepared violates Zero
          Unreceipted Actuation regardless of any grant.
        - If one exists, performs a FRESH `AuthorityBroker.evaluate()` call against that
          `PreparedReceipt`'s identity -- deliberately NOT the decision (if any) computed at
          `save_prepared` time -- so a grant that has genuinely expired since `save_prepared`
          (TOCTOU) is caught for real, using the broker's own live `time.time()` check
          against `AuthorityGrant.valid_until`.
        """
        if self._authority_broker is None:
            return
        prepared = self._prepared_by_token.get(receipt.idempotency_token)
        if prepared is None:
            raise ReceiptGrantValidationError(
                receipt,
                REFUSED_NO_PREPARED_RECEIPT,
                (
                    f"ReceiptStore refuses to persist FinalReceipt {receipt.receipt_id!r} "
                    f"(idempotency_token={receipt.idempotency_token!r}): no PreparedReceipt was "
                    f"ever recorded in this store for this idempotency_token -- Zero "
                    f"Unreceipted Actuation requires a durable PreparedReceipt to exist for "
                    f"this exact identity BEFORE a terminal FinalReceipt can be committed."
                ),
            )
        self._evaluate_grant_or_raise(
            receipt=receipt,
            actor_id=prepared.actor_id,
            action_iri=prepared.action_iri,
            target_resource=prepared.target_resource,
            grant_id=prepared.grant_id,
            receipt_label="FinalReceipt",
            receipt_ident=receipt.receipt_id,
        )

    def save_prepared(self, receipt: PreparedReceipt) -> None:
        """Store prepared receipt, checking idempotency.

        AFDE-2604 store-layer defense-in-depth: when this store was constructed with a real
        `authority_broker`, a NEW receipt (idempotency_token not already recorded) is
        validated via `_validate_grant_id` before being persisted -- see
        `ReceiptGrantValidationError` for exactly what is checked and its named scope. When
        `authority_broker` is `None` (the default, and every existing caller's behavior
        before this session), this method is byte-for-byte unchanged: zero regression.
        """
        if receipt.idempotency_token in self._prepared_by_token:
            existing = self._prepared_by_token[receipt.idempotency_token]
            if existing.digest != receipt.digest:
                raise ValueError(
                    f"Idempotency token conflict: {receipt.idempotency_token} already used with different parameters"
                )
            return  # Idempotent write
        self._validate_grant_id(receipt)
        self._prepared_by_token[receipt.idempotency_token] = receipt
        self._receipts_by_digest[receipt.digest] = receipt
        self._chain.append(receipt.digest)

    def save_final(self, receipt: FinalReceipt) -> None:
        """Store final receipt, checking idempotency.

        AFDE-2604 (save_final closure, this session): when this store was constructed with a
        real `authority_broker`, a NEW final receipt (idempotency_token not already recorded
        as final) is validated via `_validate_final_grant_id` before being persisted --
        mirroring `save_prepared`'s own validation, closing two real gaps an independent
        adversarial pass found (see module docstring and
        `tests/sa2a/conformance/test_afde_2604_receipt_store_grant_validation_mutations.py`):
        a `FinalReceipt` for an identity that was never prepared is refused
        (`REFUSED_NO_PREPARED_RECEIPT`), and a grant that expired between `save_prepared` and
        `save_final` is caught by a fresh re-evaluation at commit time
        (`REFUSED_EXPIRED_GRANT`). When `authority_broker` is `None` (the default, and every
        existing caller's behavior before this fix), this method is byte-for-byte unchanged:
        zero regression.
        """
        if receipt.idempotency_token in self._final_by_token:
            existing = self._final_by_token[receipt.idempotency_token]
            if existing.digest != receipt.digest:
                raise ValueError(
                    f"Idempotency token conflict: final receipt already recorded for {receipt.idempotency_token}"
                )
            return
        self._validate_final_grant_id(receipt)
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
