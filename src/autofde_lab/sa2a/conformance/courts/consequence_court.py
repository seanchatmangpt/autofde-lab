# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""BRCE Consequence & Zero Unreceipted Actuation Court (RFC-SA2A-002 v26.9.16).

Implements Chicago Zero-Mock Conformance Gates:
- CHI-BRCE-01-PREPARED-COMMIT: Strict PreparedReceipt commitment before actuator call (§4.8, §31)
- CHI-BRCE-02-BYPASS-PREVENTION: Actuator bypass prevention (§30, §63)
- CHI-BRCE-03-ANTI-COLLUSION: Anti-collusion (Actuator != Verifier) (§30)
- CHI-POST-01-INDEPENDENT-OBSERVATION: Independent disk state postcondition observation (§30)
- CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL: Duplicate idempotency token replay refusal (§55)

Strict Chicago Standards:
- Real plant components, real physical disk I/O, genuine brokers and boundaries.
- Zero unittest.mock / Mock / MagicMock / patch / monkeypatch.
- Deterministic cryptographic digest bindings.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant,
    ConsequenceRequest,
    REFUSED_NO_GRANT,
)
from autofde_lab.sa2a.brce.boundary import (
    BoundaryExecutionResult,
    ColludingRolesError,
    ConsequenceActuator,
    ConsequenceBoundary,
    ConsequenceVerifier,
    ExecutionEnvelope,
    UnreceiptedActuationAttemptError,
)
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    ReceiptStore,
    TerminalReceiptState,
    compute_receipt_digest,
)

# -----------------------------------------------------------------------------
# Conformance Gate Identifiers
# -----------------------------------------------------------------------------
CHI_BRCE_01_PREPARED_COMMIT = "CHI-BRCE-01-PREPARED-COMMIT"
CHI_BRCE_02_BYPASS_PREVENTION = "CHI-BRCE-02-BYPASS-PREVENTION"
CHI_BRCE_03_ANTI_COLLUSION = "CHI-BRCE-03-ANTI-COLLUSION"
CHI_POST_01_INDEPENDENT_OBSERVATION = "CHI-POST-01-INDEPENDENT-OBSERVATION"
CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL = "CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL"

# Standard Aliases
CHI_BRCE_PREPARED_COMMIT = CHI_BRCE_01_PREPARED_COMMIT
CHI_BRCE_BYPASS_PREVENTION = CHI_BRCE_02_BYPASS_PREVENTION
CHI_BRCE_ANTI_COLLUSION = CHI_BRCE_03_ANTI_COLLUSION
CHI_POST_ANTI_COLLUSION = CHI_BRCE_03_ANTI_COLLUSION
CHI_POST_INDEPENDENT_OBSERVATION = CHI_POST_01_INDEPENDENT_OBSERVATION
CHI_POST_DISK_OBSERVATION = CHI_POST_01_INDEPENDENT_OBSERVATION
CHI_BRCE_REPLAY_REFUSAL = CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL


class GateVerdict(str, Enum):
    """Verdict of a conformance gate evaluation."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class CourtGateResult:
    """Detailed result of an individual conformance gate audit."""

    gate_id: str
    verdict: GateVerdict
    passed: bool
    evidence: Mapping[str, Any]
    reason: str
    observed_digest: str = ""


@dataclass(frozen=True, slots=True)
class ConsequenceCourtRuling:
    """Comprehensive qualification ruling from the Consequence Court."""

    passed: bool
    total_gates: int
    passed_gates: int
    gate_results: Mapping[str, CourtGateResult]
    audit_digest: str
    summary: str
    adjudicated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))


# -----------------------------------------------------------------------------
# Real Plant Components (Chicago Zero-Mock: Real Physical Disk I/O)
# -----------------------------------------------------------------------------


class DurableDiskReceiptStore(ReceiptStore):
    """Durable disk-backed receipt store providing atomic filesystem persistence.

    Enforces that every PreparedReceipt and FinalReceipt is durably committed
    to physical disk via atomic rename and fsync prior to proceeding.

    AFDE-2604 (additive, optional): accepts the same optional `authority_broker` as the base
    `ReceiptStore` and forwards it unchanged. Every existing caller (13 call sites across
    `src/` and `tests/` as of this session, none of which pass `authority_broker`) keeps
    constructing this class with only `store_dir` and is completely unaffected.
    """

    def __init__(self, store_dir: Path, authority_broker: Optional[AuthorityBroker] = None) -> None:
        super().__init__(authority_broker=authority_broker)
        self._store_dir = store_dir
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._sync_from_disk()

    def _sync_from_disk(self) -> None:
        """Hydrate in-memory indexes from existing disk artifacts for fresh-consumer verification."""
        for prep_file in sorted(self._store_dir.glob("prep_*.json")):
            try:
                data = json.loads(prep_file.read_text(encoding="utf-8"))
                receipt = PreparedReceipt(
                    prepared_id=data["prepared_id"],
                    idempotency_token=data["idempotency_token"],
                    action_iri=data["action_iri"],
                    target_resource=data["target_resource"],
                    actor_id=data["actor_id"],
                    grant_id=data["grant_id"],
                    plan_digest=data["plan_digest"],
                    artifact_digest=data["artifact_digest"],
                    admitted_input_digest=data["admitted_input_digest"],
                    # AFDE-2604 (durable admission-identity evidence): must be read back
                    # from disk the same way every other digest-affecting field here is --
                    # a real, necessary follow-up to admission_digest's addition to
                    # PreparedReceipt.digest's body, or a fresh-consumer reload of a real
                    # admitted receipt would silently recompute a MISMATCHED digest
                    # (defaulting to "none" instead of the stored value). .get(...) tolerates
                    # a durable record written before this field existed.
                    admission_digest=data.get("admission_digest", "none"),
                    consequence_class=data["consequence_class"],
                    parameters=data.get("parameters", {}),
                    prepared_at_ms=data.get("prepared_at_ms", 0),
                    previous_receipt_digest=data.get("previous_receipt_digest", "genesis:0" * 4),
                )
                self._prepared_by_token[receipt.idempotency_token] = receipt
                self._receipts_by_digest[receipt.digest] = receipt
                if receipt.digest not in self._chain:
                    self._chain.append(receipt.digest)
            except Exception:
                continue

        for final_file in sorted(self._store_dir.glob("final_*.json")):
            try:
                data = json.loads(final_file.read_text(encoding="utf-8"))
                receipt = FinalReceipt(
                    receipt_id=data["receipt_id"],
                    prepared_receipt_digest=data["prepared_receipt_digest"],
                    idempotency_token=data["idempotency_token"],
                    state=TerminalReceiptState(data["state"]),
                    postcondition_verified=bool(data.get("postcondition_verified", False)),
                    evidence=data.get("evidence", {}),
                    refusal_code=data.get("refusal_code"),
                    reason=data.get("reason", ""),
                    executed_at_ms=data.get("executed_at_ms", 0),
                    execution_duration_ms=data.get("execution_duration_ms", 0),
                )
                self._final_by_token[receipt.idempotency_token] = receipt
                self._receipts_by_digest[receipt.digest] = receipt
                if receipt.digest not in self._chain:
                    self._chain.append(receipt.digest)
            except Exception:
                continue

    def save_prepared(self, receipt: PreparedReceipt) -> None:
        super().save_prepared(receipt)
        target = self._store_dir / f"prep_{receipt.idempotency_token}.json"
        tmp_target = self._store_dir / f".tmp_prep_{uuid.uuid4().hex}"
        content = json.dumps(receipt.to_dict(), indent=2, sort_keys=True).encode("utf-8")
        with open(tmp_target, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_target, target)

    def save_final(self, receipt: FinalReceipt) -> None:
        super().save_final(receipt)
        target = self._store_dir / f"final_{receipt.idempotency_token}.json"
        tmp_target = self._store_dir / f".tmp_final_{uuid.uuid4().hex}"
        content = json.dumps(receipt.to_dict(), indent=2, sort_keys=True).encode("utf-8")
        with open(tmp_target, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_target, target)

    @property
    def store_dir(self) -> Path:
        return self._store_dir


class RealDiskJournalActuator:
    """Real consequence actuator that mutates external physical filesystem state."""

    def __init__(self, journal_path: Path) -> None:
        self._journal_path = journal_path
        self._actuator_id = f"actuator:disk_journal:{journal_path.name}"
        self.call_count = 0
        self.last_observed_prepared_token: Optional[str] = None
        self.last_observed_prepared_digest: Optional[str] = None

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Perform consequence: write real state transition record to physical disk journal."""
        self.call_count += 1
        param_dict = dict(sorted(parameters.items()))
        payload_bytes = json.dumps(param_dict, sort_keys=True).encode("utf-8")
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()

        entry = {
            "action": action_iri,
            "target": target_resource,
            "parameters": param_dict,
            "payload_digest": payload_digest,
            "call_index": self.call_count,
            "timestamp_ns": time.time_ns(),
        }

        # Real disk I/O
        if self._journal_path.exists():
            try:
                records = json.loads(self._journal_path.read_text(encoding="utf-8"))
            except Exception:
                records = []
        else:
            records = []

        records.append(entry)
        tmp_journal = self._journal_path.with_suffix(f".tmp_{uuid.uuid4().hex}")
        with open(tmp_journal, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_journal, self._journal_path)

        return {
            "applied": True,
            "entry_count": len(records),
            "last_digest": payload_digest,
            "journal_file": str(self._journal_path),
            "call_index": self.call_count,
        }

    def actuator_digest(self) -> str:
        return self._actuator_id

    @property
    def journal_path(self) -> Path:
        return self._journal_path


class GuardedDiskJournalActuator(RealDiskJournalActuator):
    """Consequence Actuator guarded by active PreparedReceipt verification.

    Enforces Actuator Bypass Prevention (§30, §63):
    Rejects any direct invocation unless a durable PreparedReceipt for the action
    and target already exists in the bound receipt store.
    """

    def __init__(self, journal_path: Path, receipt_store: ReceiptStore) -> None:
        super().__init__(journal_path)
        self._receipt_store = receipt_store

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        # Guard: Actuator inspects durable store to prove PreparedReceipt was committed BEFORE call
        # Look for a prepared receipt matching this action and target
        matching_prep: Optional[PreparedReceipt] = None
        for r_dict in self._receipt_store.all_records():
            if r_dict.get("kind") == "prepared":
                if (
                    r_dict.get("action_iri") == action_iri
                    and r_dict.get("target_resource") == target_resource
                ):
                    matching_prep = self._receipt_store.get_prepared(r_dict["idempotency_token"])
                    break

        if matching_prep is None:
            raise UnreceiptedActuationAttemptError(
                f"Actuator bypass attempt detected! Direct actuation forbidden without committed PreparedReceipt "
                f"for action '{action_iri}' on resource '{target_resource}'."
            )

        self.last_observed_prepared_token = matching_prep.idempotency_token
        self.last_observed_prepared_digest = matching_prep.digest
        return super().actuate(action_iri, target_resource, parameters)


class DeceptiveDiskActuator:
    """Adversarial actuator that claims success in evidence but fails or corrupts disk state."""

    def __init__(self, journal_path: Path, mode: str = "phantom") -> None:
        self._journal_path = journal_path
        self._mode = mode  # 'phantom' (never writes to disk), 'corrupt' (writes bogus digest)
        self._actuator_id = f"actuator:deceptive:{mode}:{journal_path.name}"
        self.call_count = 0

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.call_count += 1
        fake_digest = hashlib.sha256(b"fake_payload_evidence").hexdigest()

        if self._mode == "corrupt":
            corrupt_record = [{
                "action": action_iri,
                "target": target_resource,
                "parameters": dict(parameters),
                "payload_digest": "corrupted_garbage_digest",
            }]
            self._journal_path.write_text(json.dumps(corrupt_record, indent=2), encoding="utf-8")

        # In 'phantom' mode, we do NOT write to disk at all!
        return {
            "applied": True,  # Lying evidence!
            "entry_count": 1,
            "last_digest": fake_digest,
            "journal_file": str(self._journal_path),
        }

    def actuator_digest(self) -> str:
        return self._actuator_id


class IndependentDiskJournalVerifier:
    """Distinct, independent verifier that inspects the physical disk state.

    Must NOT be the actuator instance (prevents colluding roles §30).
    Reads the physical filesystem directly without trusting actuator in-memory state.
    """

    def __init__(self, journal_path: Path) -> None:
        self._journal_path = journal_path
        self._verifier_id = f"verifier:disk_journal:{journal_path.name}"
        self.verification_count = 0

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Optional[Mapping[str, Any]],
    ) -> bool:
        """Independently inspect physical disk file to confirm claimed consequence."""
        self.verification_count += 1
        if not self._journal_path.exists():
            return False

        try:
            records = json.loads(self._journal_path.read_text(encoding="utf-8"))
            if not records:
                return False

            latest = records[-1]
            if latest.get("action") != action_iri or latest.get("target") != target_resource:
                return False

            param_dict = dict(sorted(parameters.items()))
            expected_digest = hashlib.sha256(
                json.dumps(param_dict, sort_keys=True).encode("utf-8")
            ).hexdigest()

            if latest.get("payload_digest") != expected_digest:
                return False

            # Check that evidence matches independently observed disk record
            if evidence is not None and evidence.get("last_digest") != expected_digest:
                return False

            return True
        except Exception:
            return False

    def verifier_digest(self) -> str:
        return self._verifier_id

    @property
    def journal_path(self) -> Path:
        return self._journal_path


# -----------------------------------------------------------------------------
# Consequence Conformance Court (§30, §31, §55)
# -----------------------------------------------------------------------------


class ConsequenceCourt:
    """BRCE Consequence & Zero Unreceipted Actuation Qualification Court.

    Validates systems against the 5 canonical Chicago Conformance Gates:
    1. CHI-BRCE-01-PREPARED-COMMIT: Strict PreparedReceipt commitment before actuator call
    2. CHI-BRCE-02-BYPASS-PREVENTION: Actuator bypass prevention
    3. CHI-BRCE-03-ANTI-COLLUSION: Anti-collusion (Actuator != Verifier)
    4. CHI-POST-01-INDEPENDENT-OBSERVATION: Independent disk state postcondition observation
    5. CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL: Duplicate idempotency token replay refusal

    Predates and is orthogonal to AFDE-2604's admission fencing (RFC-SA2A-002):
    every gate here audits Zero-Unreceipted-Actuation/replay/authority/postcondition
    properties of `ConsequenceBoundary` itself, never whether a candidate was
    admitted. Every `ConsequenceBoundary(...)` this class constructs internally
    therefore passes `require_admission=False` explicitly -- since
    `ConsequenceBoundary`'s own class-level default flipped to `True` (AFDE-2604
    fail-secure closure), omitting this here would refuse every gate's envelope at
    the admission check before it ever reached the actuation/replay/postcondition
    logic these gates exist to audit, masking the real property under test with an
    unrelated one. This is an explicit, named, permanent opt-out for this court's
    own scope -- not a silent bypass -- exactly the affirmative-choice pattern the
    fail-secure closure requires of any caller that genuinely needs the old shape.
    """

    def __init__(self) -> None:
        self._court_id = f"court:consequence:{uuid.uuid4().hex[:8]}"

    @property
    def court_id(self) -> str:
        return self._court_id

    # -------------------------------------------------------------------------
    # Gate 1: Strict PreparedReceipt commitment before actuator call
    # -------------------------------------------------------------------------
    def audit_prepared_commitment(
        self,
        broker: AuthorityBroker,
        receipt_store: ReceiptStore,
        journal_path: Path,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        idempotency_token: str,
    ) -> CourtGateResult:
        """Audit CHI-BRCE-01: PreparedReceipt must be durably committed before actuator DO."""
        actuator = GuardedDiskJournalActuator(journal_path, receipt_store=receipt_store)
        verifier = IndependentDiskJournalVerifier(journal_path)

        boundary = ConsequenceBoundary(
            authority_broker=broker,
            actuator=actuator,
            verifier=verifier,
            receipt_store=receipt_store,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        envelope = ExecutionEnvelope(
            idempotency_token=idempotency_token,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )

        # Execute through boundary
        res = boundary.execute(envelope)

        # Check: PreparedReceipt must exist in receipt store
        prep_rec = receipt_store.get_prepared(idempotency_token)
        if prep_rec is None:
            return CourtGateResult(
                gate_id=CHI_BRCE_01_PREPARED_COMMIT,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"error": "PreparedReceipt was not found in store after execution"},
                reason="Durable PreparedReceipt was missing from store.",
            )

        # Check: Actuator was called strictly after receipt was committed
        if actuator.last_observed_prepared_token != idempotency_token:
            return CourtGateResult(
                gate_id=CHI_BRCE_01_PREPARED_COMMIT,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"actuator_observed": actuator.last_observed_prepared_token},
                reason="Actuator was not able to verify committed PreparedReceipt prior to actuation.",
            )

        # Check: Final receipt correctly links to prepared receipt digest
        final_rec = res.final_receipt
        if final_rec is None or final_rec.prepared_receipt_digest != prep_rec.digest:
            return CourtGateResult(
                gate_id=CHI_BRCE_01_PREPARED_COMMIT,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={
                    "prep_digest": prep_rec.digest,
                    "final_linked_digest": final_rec.prepared_receipt_digest if final_rec else None,
                },
                reason="Final receipt did not bind the exact PreparedReceipt digest.",
            )

        evidence = {
            "prepared_receipt_id": prep_rec.prepared_id,
            "prepared_digest": prep_rec.digest,
            "idempotency_token": idempotency_token,
            "actuator_verified_prep": True,
            "final_receipt_id": final_rec.receipt_id,
        }
        return CourtGateResult(
            gate_id=CHI_BRCE_01_PREPARED_COMMIT,
            verdict=GateVerdict.PASSED,
            passed=True,
            evidence=evidence,
            reason="Strict PreparedReceipt commitment prior to actuator invocation verified.",
            observed_digest=prep_rec.digest,
        )

    # -------------------------------------------------------------------------
    # Gate 2: Actuator bypass prevention
    # -------------------------------------------------------------------------
    def audit_bypass_prevention(
        self,
        broker: AuthorityBroker,
        receipt_store: ReceiptStore,
        journal_path: Path,
        actor_id: str,
        unauthorized_action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        idempotency_token: str,
    ) -> CourtGateResult:
        """Audit CHI-BRCE-02: Bypassing BRCE or acting without grant must fail closed."""
        actuator = GuardedDiskJournalActuator(journal_path, receipt_store=receipt_store)
        verifier = IndependentDiskJournalVerifier(journal_path)

        boundary = ConsequenceBoundary(
            authority_broker=broker,
            actuator=actuator,
            verifier=verifier,
            receipt_store=receipt_store,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        initial_journal_exists = journal_path.exists()
        initial_call_count = actuator.call_count

        # Sub-check A: Execution through boundary without grant -> must refuse, zero actuation
        envelope = ExecutionEnvelope(
            idempotency_token=idempotency_token,
            action_iri=unauthorized_action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )

        res = boundary.execute(envelope)
        if res.success is not False or res.state != TerminalReceiptState.REFUSED:
            return CourtGateResult(
                gate_id=CHI_BRCE_02_BYPASS_PREVENTION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"res_state": res.state.value, "success": res.success},
                reason="Ungranted execution was not refused by boundary.",
            )

        if actuator.call_count != initial_call_count:
            return CourtGateResult(
                gate_id=CHI_BRCE_02_BYPASS_PREVENTION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"actuator_call_count": actuator.call_count},
                reason="Actuator was invoked during ungranted execution attempt.",
            )

        if not initial_journal_exists and journal_path.exists():
            return CourtGateResult(
                gate_id=CHI_BRCE_02_BYPASS_PREVENTION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"disk_mutated": True},
                reason="Physical disk state was mutated during ungranted execution attempt.",
            )

        # Sub-check B: Direct actuator call without committed PreparedReceipt -> must raise UnreceiptedActuationAttemptError
        direct_call_prevented = False
        try:
            actuator.actuate(
                action_iri="urn:action:bypass:direct",
                target_resource=target_resource,
                parameters={"malicious": True},
            )
        except UnreceiptedActuationAttemptError:
            direct_call_prevented = True
        except Exception:
            direct_call_prevented = False

        if not direct_call_prevented:
            return CourtGateResult(
                gate_id=CHI_BRCE_02_BYPASS_PREVENTION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"direct_call_prevented": direct_call_prevented},
                reason="Direct actuator call outside boundary was not prevented.",
            )

        return CourtGateResult(
            gate_id=CHI_BRCE_02_BYPASS_PREVENTION,
            verdict=GateVerdict.PASSED,
            passed=True,
            evidence={
                "boundary_refusal_code": res.refusal_code,
                "actuator_calls_on_refusal": 0,
                "direct_actuation_blocked": True,
            },
            reason="Actuator bypass prevention verified: ungranted requests refused and direct actuation blocked.",
            observed_digest=res.final_receipt.digest if res.final_receipt else "",
        )

    # -------------------------------------------------------------------------
    # Gate 3: Anti-collusion (Actuator != Verifier)
    # -------------------------------------------------------------------------
    def audit_anti_collusion(
        self,
        broker: AuthorityBroker,
        actuator: ConsequenceActuator,
        verifier: ConsequenceVerifier,
    ) -> CourtGateResult:
        """Audit CHI-BRCE-03: Actuator and Verifier must be distinct entities (§30)."""
        # Sub-check A: Passing identical instance must raise ColludingRolesError
        collusion_caught = False
        try:
            ConsequenceBoundary(
                authority_broker=broker,
                actuator=actuator,
                verifier=actuator,  # Colluding instance!
            )
        except ColludingRolesError:
            collusion_caught = True

        if not collusion_caught:
            return CourtGateResult(
                gate_id=CHI_BRCE_03_ANTI_COLLUSION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"identical_instance_blocked": False},
                reason="ConsequenceBoundary failed to reject identical actuator and verifier instances.",
            )

        # Sub-check B: Actuator and verifier identity digest separation
        if actuator.actuator_digest() == verifier.verifier_digest():
            return CourtGateResult(
                gate_id=CHI_BRCE_03_ANTI_COLLUSION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={
                    "actuator_digest": actuator.actuator_digest(),
                    "verifier_digest": verifier.verifier_digest(),
                },
                reason="Actuator and verifier share identical identity digests.",
            )

        # Sub-check C: Valid distinct configuration accepted
        boundary = ConsequenceBoundary(
            authority_broker=broker,
            actuator=actuator,
            verifier=verifier,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        return CourtGateResult(
            gate_id=CHI_BRCE_03_ANTI_COLLUSION,
            verdict=GateVerdict.PASSED,
            passed=True,
            evidence={
                "collusion_blocked": True,
                "actuator_digest": actuator.actuator_digest(),
                "verifier_digest": verifier.verifier_digest(),
                "distinct_instances": actuator is not verifier,
            },
            reason="Anti-collusion verified: distinct roles, distinct digests, self-attestation rejected.",
            observed_digest=compute_receipt_digest(
                f"{actuator.actuator_digest()}||{verifier.verifier_digest()}"
            ),
        )

    # -------------------------------------------------------------------------
    # Gate 4: Independent disk state postcondition observation
    # -------------------------------------------------------------------------
    def audit_independent_postcondition_observation(
        self,
        broker: AuthorityBroker,
        receipt_store: ReceiptStore,
        journal_path: Path,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        idempotency_token: str,
    ) -> CourtGateResult:
        """Audit CHI-POST-01: Verifier must inspect real disk state without trusting actuator evidence."""
        # Sub-check A: Legitimate execution -> verifier reads disk, returns True -> EXECUTED
        legit_actuator = RealDiskJournalActuator(journal_path)
        independent_verifier = IndependentDiskJournalVerifier(journal_path)

        boundary_legit = ConsequenceBoundary(
            authority_broker=broker,
            actuator=legit_actuator,
            verifier=independent_verifier,
            receipt_store=receipt_store,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        envelope_legit = ExecutionEnvelope(
            idempotency_token=idempotency_token,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )

        res_legit = boundary_legit.execute(envelope_legit)
        if not (
            res_legit.success is True
            and res_legit.state == TerminalReceiptState.EXECUTED
            and res_legit.final_receipt is not None
            and res_legit.final_receipt.postcondition_verified is True
        ):
            return CourtGateResult(
                gate_id=CHI_POST_01_INDEPENDENT_OBSERVATION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"legit_success": res_legit.success, "legit_state": res_legit.state.value},
                reason="Independent verifier failed to verify genuine disk consequence.",
            )

        # Sub-check B: Deceptive Actuator (lies about success, but disk not written)
        deceptive_journal = journal_path.parent / f"phantom_journal_{uuid.uuid4().hex[:6]}.json"
        deceptive_actuator = DeceptiveDiskActuator(deceptive_journal, mode="phantom")
        deceptive_verifier = IndependentDiskJournalVerifier(deceptive_journal)

        boundary_deceptive = ConsequenceBoundary(
            authority_broker=broker,
            actuator=deceptive_actuator,  # Lies that it succeeded!
            verifier=deceptive_verifier,  # Reads real disk
            receipt_store=receipt_store,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        token_deceptive = f"idemp-deceptive-{uuid.uuid4().hex[:6]}"
        envelope_deceptive = ExecutionEnvelope(
            idempotency_token=token_deceptive,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )

        res_deceptive = boundary_deceptive.execute(envelope_deceptive)
        # Verifier must catch the deception! Terminal state must NOT be EXECUTED
        if (
            res_deceptive.success is True
            or res_deceptive.state == TerminalReceiptState.EXECUTED
            or (res_deceptive.final_receipt and res_deceptive.final_receipt.postcondition_verified)
        ):
            return CourtGateResult(
                gate_id=CHI_POST_01_INDEPENDENT_OBSERVATION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"deceptive_result": res_deceptive.state.value},
                reason="Independent verifier failed to detect deceptive phantom actuation.",
            )

        # Sub-check C: Corrupted disk state -> verifier detects hash mismatch
        corrupt_journal = journal_path.parent / f"corrupt_journal_{uuid.uuid4().hex[:6]}.json"
        corrupt_actuator = DeceptiveDiskActuator(corrupt_journal, mode="corrupt")
        corrupt_verifier = IndependentDiskJournalVerifier(corrupt_journal)

        boundary_corrupt = ConsequenceBoundary(
            authority_broker=broker,
            actuator=corrupt_actuator,
            verifier=corrupt_verifier,
            receipt_store=receipt_store,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        token_corrupt = f"idemp-corrupt-{uuid.uuid4().hex[:6]}"
        envelope_corrupt = ExecutionEnvelope(
            idempotency_token=token_corrupt,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )

        res_corrupt = boundary_corrupt.execute(envelope_corrupt)
        if (
            res_corrupt.success is True
            or (res_corrupt.final_receipt and res_corrupt.final_receipt.postcondition_verified)
        ):
            return CourtGateResult(
                gate_id=CHI_POST_01_INDEPENDENT_OBSERVATION,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"corrupt_result": res_corrupt.state.value},
                reason="Independent verifier failed to detect corrupted disk content.",
            )

        return CourtGateResult(
            gate_id=CHI_POST_01_INDEPENDENT_OBSERVATION,
            verdict=GateVerdict.PASSED,
            passed=True,
            evidence={
                "legitimate_verification": True,
                "phantom_actuation_caught": res_deceptive.state == TerminalReceiptState.UNKNOWN_OUTCOME,
                "corrupt_disk_caught": res_corrupt.state == TerminalReceiptState.UNKNOWN_OUTCOME,
                "disk_records_verified_bytes": True,
            },
            reason="Independent disk state observation verified across genuine, phantom, and corrupted cases.",
            observed_digest=res_legit.final_receipt.digest,
        )

    # -------------------------------------------------------------------------
    # Gate 5: Duplicate idempotency token replay refusal
    # -------------------------------------------------------------------------
    def audit_idempotency_replay_refusal(
        self,
        broker: AuthorityBroker,
        receipt_store: ReceiptStore,
        journal_path: Path,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        idempotency_token: str,
    ) -> CourtGateResult:
        """Audit CHI-BRCE-04: Duplicate idempotency tokens must never trigger re-actuation (§55)."""
        actuator = RealDiskJournalActuator(journal_path)
        verifier = IndependentDiskJournalVerifier(journal_path)

        boundary = ConsequenceBoundary(
            authority_broker=broker,
            actuator=actuator,
            verifier=verifier,
            receipt_store=receipt_store,
            require_admission=False,  # see class docstring: this court predates admission fencing
        )

        envelope1 = ExecutionEnvelope(
            idempotency_token=idempotency_token,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )

        # Initial execution
        res1 = boundary.execute(envelope1)
        initial_calls = actuator.call_count

        # Sub-check A: Re-executing exact same envelope -> cached result, zero new actuator calls
        envelope2 = ExecutionEnvelope(
            idempotency_token=idempotency_token,
            action_iri=action_iri,
            target_resource=target_resource,
            actor_id=actor_id,
            parameters=parameters,
        )
        res2 = boundary.execute(envelope2)

        if not res2.replayed:
            return CourtGateResult(
                gate_id=CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={"replayed": res2.replayed},
                reason="Duplicate idempotency token did not flag replayed=True.",
            )

        if actuator.call_count != initial_calls:
            return CourtGateResult(
                gate_id=CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={
                    "initial_calls": initial_calls,
                    "replayed_calls": actuator.call_count,
                },
                reason="Actuator was called on duplicate idempotency token execution!",
            )

        if res2.final_receipt is None or res1.final_receipt is None:
            return CourtGateResult(
                gate_id=CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={},
                reason="Missing final receipt on replayed execution.",
            )

        if res2.final_receipt.digest != res1.final_receipt.digest:
            return CourtGateResult(
                gate_id=CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
                verdict=GateVerdict.FAILED,
                passed=False,
                evidence={
                    "first_digest": res1.final_receipt.digest,
                    "second_digest": res2.final_receipt.digest,
                },
                reason="Replayed execution returned mismatched final receipt digest.",
            )

        return CourtGateResult(
            gate_id=CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
            verdict=GateVerdict.PASSED,
            passed=True,
            evidence={
                "initial_call_count": initial_calls,
                "final_call_count": actuator.call_count,
                "replayed_flag": res2.replayed,
                "receipt_digest_identical": True,
            },
            reason="Duplicate idempotency replay refused re-actuation and cleanly returned cached receipt.",
            observed_digest=res2.final_receipt.digest,
        )

    # -------------------------------------------------------------------------
    # Full Adjudication Suite
    # -------------------------------------------------------------------------
    def adjudicate(
        self,
        base_dir: Path,
        actor_id: str = "urn:agent:qualifier",
        action_iri: str = "urn:action:quarantine_node",
        target_resource: str = "urn:cap:cluster:nodes",
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> ConsequenceCourtRuling:
        """Adjudicate all 5 conformance gates against real disk I/O and produce a binding ruling."""
        if parameters is None:
            parameters = {"node_id": "node-alpha-1", "mode": "STRICT"}

        court_dir = base_dir / f"court_{uuid.uuid4().hex[:8]}"
        court_dir.mkdir(parents=True, exist_ok=True)
        receipt_dir = court_dir / "receipts"
        journal_path = court_dir / "consequence_journal.json"

        # Initialize Real Durable Plant Collaborators
        durable_store = DurableDiskReceiptStore(receipt_dir)
        broker = AuthorityBroker()
        broker.register_grant(
            AuthorityGrant(
                grant_id="grant-court-qual-001",
                subject_id=actor_id,
                action_iri=action_iri,
                target_resource_iri=target_resource,
            )
        )

        results: dict[str, CourtGateResult] = {}

        # 1. Gate 1: Strict PreparedCommit
        token_1 = f"idemp-gate1-{uuid.uuid4().hex[:6]}"
        res_gate1 = self.audit_prepared_commitment(
            broker=broker,
            receipt_store=durable_store,
            journal_path=journal_path,
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            parameters=parameters,
            idempotency_token=token_1,
        )
        results[CHI_BRCE_01_PREPARED_COMMIT] = res_gate1

        # 2. Gate 2: Bypass Prevention
        token_2 = f"idemp-gate2-{uuid.uuid4().hex[:6]}"
        res_gate2 = self.audit_bypass_prevention(
            broker=broker,
            receipt_store=durable_store,
            journal_path=journal_path,
            actor_id=actor_id,
            unauthorized_action_iri="urn:action:unauthorized_drop_db",
            target_resource=target_resource,
            parameters=parameters,
            idempotency_token=token_2,
        )
        results[CHI_BRCE_02_BYPASS_PREVENTION] = res_gate2

        # 3. Gate 3: Anti-Collusion
        res_gate3 = self.audit_anti_collusion(
            broker=broker,
            actuator=RealDiskJournalActuator(court_dir / "gate3_journal.json"),
            verifier=IndependentDiskJournalVerifier(court_dir / "gate3_journal.json"),
        )
        results[CHI_BRCE_03_ANTI_COLLUSION] = res_gate3

        # 4. Gate 4: Independent Observation
        token_4 = f"idemp-gate4-{uuid.uuid4().hex[:6]}"
        res_gate4 = self.audit_independent_postcondition_observation(
            broker=broker,
            receipt_store=durable_store,
            journal_path=court_dir / "gate4_journal.json",
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            parameters=parameters,
            idempotency_token=token_4,
        )
        results[CHI_POST_01_INDEPENDENT_OBSERVATION] = res_gate4

        # 5. Gate 5: Idempotency Replay Refusal
        token_5 = f"idemp-gate5-{uuid.uuid4().hex[:6]}"
        res_gate5 = self.audit_idempotency_replay_refusal(
            broker=broker,
            receipt_store=durable_store,
            journal_path=court_dir / "gate5_journal.json",
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            parameters=parameters,
            idempotency_token=token_5,
        )
        results[CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL] = res_gate5

        all_passed = all(r.passed for r in results.values())
        passed_count = sum(1 for r in results.values() if r.passed)

        ruling_digest = hashlib.sha256(
            json.dumps(
                {
                    "court_id": self._court_id,
                    "all_passed": all_passed,
                    "gates": {k: v.verdict.value for k, v in results.items()},
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        summary = (
            f"Consequence Court Adjudication: {passed_count}/{len(results)} gates passed. "
            f"Status: {'QUALIFIED' if all_passed else 'DISQUALIFIED'}."
        )

        return ConsequenceCourtRuling(
            passed=all_passed,
            total_gates=len(results),
            passed_gates=passed_count,
            gate_results=results,
            audit_digest=ruling_digest,
            summary=summary,
        )


# -----------------------------------------------------------------------------
# Stand-alone Verification Functions for Direct Programmatic Invocations
# -----------------------------------------------------------------------------


def verify_prepared_commitment(
    court: ConsequenceCourt,
    broker: AuthorityBroker,
    store: ReceiptStore,
    journal: Path,
    envelope: ExecutionEnvelope,
) -> CourtGateResult:
    return court.audit_prepared_commitment(
        broker=broker,
        receipt_store=store,
        journal_path=journal,
        actor_id=envelope.actor_id,
        action_iri=envelope.action_iri,
        target_resource=envelope.target_resource,
        parameters=envelope.parameters,
        idempotency_token=envelope.idempotency_token,
    )


def verify_bypass_prevention(
    court: ConsequenceCourt,
    broker: AuthorityBroker,
    store: ReceiptStore,
    journal: Path,
    envelope: ExecutionEnvelope,
) -> CourtGateResult:
    return court.audit_bypass_prevention(
        broker=broker,
        receipt_store=store,
        journal_path=journal,
        actor_id=envelope.actor_id,
        unauthorized_action_iri=envelope.action_iri,
        target_resource=envelope.target_resource,
        parameters=envelope.parameters,
        idempotency_token=envelope.idempotency_token,
    )


def verify_anti_collusion(
    court: ConsequenceCourt,
    broker: AuthorityBroker,
    actuator: ConsequenceActuator,
    verifier: ConsequenceVerifier,
) -> CourtGateResult:
    return court.audit_anti_collusion(broker=broker, actuator=actuator, verifier=verifier)


def verify_independent_postcondition_observation(
    court: ConsequenceCourt,
    broker: AuthorityBroker,
    store: ReceiptStore,
    journal: Path,
    envelope: ExecutionEnvelope,
) -> CourtGateResult:
    return court.audit_independent_postcondition_observation(
        broker=broker,
        receipt_store=store,
        journal_path=journal,
        actor_id=envelope.actor_id,
        action_iri=envelope.action_iri,
        target_resource=envelope.target_resource,
        parameters=envelope.parameters,
        idempotency_token=envelope.idempotency_token,
    )


def verify_idempotency_replay_refusal(
    court: ConsequenceCourt,
    broker: AuthorityBroker,
    store: ReceiptStore,
    journal: Path,
    envelope: ExecutionEnvelope,
) -> CourtGateResult:
    return court.audit_idempotency_replay_refusal(
        broker=broker,
        receipt_store=store,
        journal_path=journal,
        actor_id=envelope.actor_id,
        action_iri=envelope.action_iri,
        target_resource=envelope.target_resource,
        parameters=envelope.parameters,
        idempotency_token=envelope.idempotency_token,
    )
