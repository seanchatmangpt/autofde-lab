"""Unit tests for BRCE Consequence Boundary & Replay (RFC-SA2A-001 v26.9.16 §30, §31, §32, §55).

Verifies:
1. Prepared receipt requirement BEFORE actuation (Zero Unreceipted Actuation §4.8, §31).
2. Strict pipeline flow: SELECT -> CONSTRUCT -> AuthorityBroker -> BRCE -> DO.
3. Authority non-implication enforcement at boundary (§29).
4. Prevention of colluding actuator and verifier (§30).
5. Replay protection & Idempotency (§55): Duplicate tokens return cached result without re-executing.
6. Offline Replay verification reproducing admission, construction, authority, and receipt validation WITHOUT re-executing external consequences (Replay != DO §32).
7. Tampered receipt detection during replay.
"""

from __future__ import annotations

import pytest
from typing import Any, Mapping, Optional

from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant,
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
)
from autofde_lab.sa2a.brce.replay import (
    ReplayEngine,
    ReplayStanding,
    ReplayVerdict,
)
from autofde_lab.sa2a.construct.constructor import (
    AdmittedSemantics,
    ArtifactManufacturer,
    TargetProfile,
)


class MockActuator:
    """Mock external actuator tracking calls."""

    def __init__(self, should_fail: bool = False) -> None:
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []
        self.should_fail = should_fail
        self.checked_store_on_actuation: Optional[ReceiptStore] = None
        self.prepared_receipt_present_at_actuation = False

    def bind_store_probe(self, store: ReceiptStore, token: str) -> None:
        self._store_to_probe = store
        self._token_to_probe = token

    def actuate(self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        self.call_count += 1
        # Check if prepared receipt already exists in store at the exact instant of actuation
        if hasattr(self, "_store_to_probe"):
            self.prepared_receipt_present_at_actuation = self._store_to_probe.has_idempotency_token(
                self._token_to_probe
            )

        if self.should_fail:
            raise RuntimeError("Hardware/Network execution failure during actuation")

        evidence = {
            "status": "applied",
            "action": action_iri,
            "target": target_resource,
            "applied_params": dict(parameters),
            "step": self.call_count,
        }
        self.calls.append(evidence)
        return evidence

    def actuator_digest(self) -> str:
        return "actuator-mock-v1"


class MockVerifier:
    """Mock independent verifier tracking calls."""

    def __init__(self, satisfy: bool = True) -> None:
        self.satisfy = satisfy
        self.verification_calls = 0

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Optional[Mapping[str, Any]],
    ) -> bool:
        self.verification_calls += 1
        return self.satisfy

    def verifier_digest(self) -> str:
        return "verifier-mock-v1"


class TestBrceBoundaryAndReceipts:
    """Tests for Reference Consequence Boundary BRCE and Prepared Receipts."""

    def test_prepared_receipt_must_exist_before_actuation(self):
        """Verify Zero Unreceipted Actuation (§4.8, §31): PreparedReceipt is durably stored BEFORE actuation."""
        broker = AuthorityBroker()
        grant = AuthorityGrant(
            grant_id="grant-101",
            subject_id="agent-alice",
            action_iri="urn:action:write_sensor",
            target_resource_iri="urn:res:sensor_42",
        )
        broker.register_grant(grant)

        actuator = MockActuator()
        verifier = MockVerifier(satisfy=True)
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier)

        token = "token-order-check-001"
        actuator.bind_store_probe(boundary.receipt_store, token)

        envelope = ExecutionEnvelope(
            idempotency_token=token,
            action_iri="urn:action:write_sensor",
            target_resource="urn:res:sensor_42",
            actor_id="agent-alice",
            grant_id="grant-101",
            parameters={"value": 42.5},
        )

        res = boundary.execute(envelope)

        assert res.success is True
        assert res.state == TerminalReceiptState.EXECUTED
        assert actuator.call_count == 1
        # Crucial: PreparedReceipt was durably present at the moment actuate() was called!
        assert actuator.prepared_receipt_present_at_actuation is True
        assert res.prepared_receipt is not None
        assert res.final_receipt is not None
        assert res.final_receipt.prepared_receipt_digest == res.prepared_receipt.digest
        assert res.final_receipt.state == TerminalReceiptState.EXECUTED
        assert res.final_receipt.postcondition_verified is True

    def test_colluding_actuator_and_verifier_refused(self):
        """Actuator and Verifier sharing the exact same instance is refused at boundary creation (§30)."""
        broker = AuthorityBroker()
        actuator_verifier = MockActuator()  # Same object implementing both or duck typed
        # Note: in Python an object can implement both protocols
        with pytest.raises(ColludingRolesError):
            ConsequenceBoundary(
                authority_broker=broker,
                actuator=actuator_verifier,  # type: ignore
                verifier=actuator_verifier,  # type: ignore
            )

    def test_authority_non_implication_enforced_at_boundary(self):
        """Boundary evaluates AuthorityBroker; unauthorized request is REFUSED with no actuation performed."""
        broker = AuthorityBroker()
        actuator = MockActuator()
        verifier = MockVerifier()
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier)

        envelope = ExecutionEnvelope(
            idempotency_token="token-unauthorized-001",
            action_iri="urn:action:restricted_wipe",
            target_resource="urn:res:db_primary",
            actor_id="agent-bob",
            grant_id="invalid-grant",
        )

        res = boundary.execute(envelope)

        assert res.success is False
        assert res.state == TerminalReceiptState.REFUSED
        assert res.refusal_code == REFUSED_NO_GRANT
        # ZERO actuation occurred
        assert actuator.call_count == 0
        assert verifier.verification_calls == 0
        assert res.prepared_receipt is None
        assert res.final_receipt is not None
        assert res.final_receipt.state == TerminalReceiptState.REFUSED

    def test_idempotency_and_replay_protection(self):
        """Duplicate idempotency token returns previous receipt without re-actuating (§55)."""
        broker = AuthorityBroker()
        grant = AuthorityGrant(
            grant_id="grant-202",
            subject_id="agent-alice",
            action_iri="urn:action:deploy",
            target_resource_iri="urn:res:cluster",
        )
        broker.register_grant(grant)

        actuator = MockActuator()
        verifier = MockVerifier(satisfy=True)
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier)

        token = "idemp-deploy-token-999"
        envelope = ExecutionEnvelope(
            idempotency_token=token,
            action_iri="urn:action:deploy",
            target_resource="urn:res:cluster",
            actor_id="agent-alice",
            grant_id="grant-202",
            parameters={"version": "1.0.4"},
        )

        # First execution: executes actuator
        res1 = boundary.execute(envelope)
        assert res1.success is True
        assert res1.replayed is False
        assert actuator.call_count == 1

        # Second execution with identical token: Replay protection fires!
        res2 = boundary.execute(envelope)
        assert res2.success is True
        assert res2.replayed is True
        # Actuator was NOT called a second time!
        assert actuator.call_count == 1
        assert res2.final_receipt.digest == res1.final_receipt.digest
        assert res2.prepared_receipt.digest == res1.prepared_receipt.digest

    def test_actuator_failure_yields_failed_receipt(self):
        """Actuator exception is caught and recorded as FAILED receipt without leaking unreceipted state."""
        broker = AuthorityBroker()
        grant = AuthorityGrant(
            grant_id="grant-fail",
            subject_id="agent-alice",
            action_iri="urn:action:fragile",
            target_resource_iri="urn:res:device",
        )
        broker.register_grant(grant)

        actuator = MockActuator(should_fail=True)
        verifier = MockVerifier(satisfy=False)
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier)

        envelope = ExecutionEnvelope(
            idempotency_token="token-fail-1",
            action_iri="urn:action:fragile",
            target_resource="urn:res:device",
            actor_id="agent-alice",
            grant_id="grant-fail",
        )

        res = boundary.execute(envelope)
        assert res.success is False
        assert res.state == TerminalReceiptState.FAILED
        assert res.prepared_receipt is not None
        assert res.final_receipt is not None
        assert res.final_receipt.state == TerminalReceiptState.FAILED
        assert "Hardware/Network execution failure" in res.final_receipt.reason


class TestReplayEngine:
    """Tests for ReplayEngine (Replay != DO, §32)."""

    def test_replay_verification_without_actuation(self):
        """Replay verifies admission, plan, construction, authority, and receipt chain WITHOUT executing."""
        broker = AuthorityBroker()
        grant = AuthorityGrant(
            grant_id="grant-replay-1",
            subject_id="agent-alice",
            action_iri="urn:action:write_log",
            target_resource_iri="urn:res:system_log",
        )
        broker.register_grant(grant)

        actuator = MockActuator()
        verifier = MockVerifier(satisfy=True)
        store = ReceiptStore()
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store)

        envelope = ExecutionEnvelope(
            idempotency_token="token-replay-test",
            action_iri="urn:action:write_log",
            target_resource="urn:res:system_log",
            actor_id="agent-alice",
            grant_id="grant-replay-1",
            parameters={"msg": "hello world"},
        )
        res = boundary.execute(envelope)
        assert res.success is True

        # Now test ReplayEngine over recorded receipts
        replay_engine = ReplayEngine(authority_broker=broker)
        report = replay_engine.verify_chain(store.all_records())

        assert report.verdict == ReplayVerdict.VALID
        assert report.standing == ReplayStanding.ALIVE
        assert report.total_pairs == 1
        assert report.executed_count == 1
        assert report.failed_count == 0
        assert report.refused_count == 0
        assert report.verified_without_actuation is True
        # Actuator calls remain exactly 1 from earlier boundary execution (Replay != DO)
        assert actuator.call_count == 1

    def test_replay_detects_tampered_receipt_chain(self):
        """Tampering with a receipt payload invalidates the cryptographic hash chain during replay."""
        broker = AuthorityBroker()
        grant = AuthorityGrant(
            grant_id="grant-tamper",
            subject_id="agent-alice",
            action_iri="urn:action:audit",
            target_resource_iri="urn:res:sec",
        )
        broker.register_grant(grant)

        actuator = MockActuator()
        verifier = MockVerifier()
        store = ReceiptStore()
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store)

        envelope = ExecutionEnvelope(
            idempotency_token="token-tamper",
            action_iri="urn:action:audit",
            target_resource="urn:res:sec",
            actor_id="agent-alice",
            grant_id="grant-tamper",
        )
        boundary.execute(envelope)

        records = store.all_records()
        # Tamper with the final receipt evidence without recomputing hash
        records[1]["evidence"]["tampered_field"] = "malicious_injection"

        replay_engine = ReplayEngine(authority_broker=broker)
        report = replay_engine.verify_chain(records)

        assert report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
        assert report.standing == ReplayStanding.BUILD_BROKEN
        assert len(report.errors) > 0

    def test_replay_verifies_construction_binding(self):
        r"""Replay verifies ConstructionReceipt binding A = \mu(O*) without executing artifact."""
        semantics = AdmittedSemantics(
            ontology_id="urn:onto:finance",
            canonical_triples=("s p o", "s2 p2 o2"),
        )
        manufacturer = ArtifactManufacturer(
            manufacturer_identity="mfg-sa2a-v1",
            manufacturer_version="1.0.0",
        )
        artifact = manufacturer.manufacture(
            semantics,
            target_profile=TargetProfile.PYTHON_EPHEMERAL,
        )
        receipt = artifact.receipt

        broker = AuthorityBroker()
        grant = AuthorityGrant(
            grant_id="grant-constructed",
            subject_id="agent-alice",
            action_iri="urn:action:calc",
            target_resource_iri="urn:res:ledger",
        )
        broker.register_grant(grant)

        actuator = MockActuator()
        verifier = MockVerifier()
        store = ReceiptStore()
        boundary = ConsequenceBoundary(authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store)

        envelope = ExecutionEnvelope(
            idempotency_token="token-construction-test",
            action_iri="urn:action:calc",
            target_resource="urn:res:ledger",
            actor_id="agent-alice",
            grant_id="grant-constructed",
            artifact=artifact,
            construction_receipt=receipt,
            admitted_semantics=semantics,
        )
        res = boundary.execute(envelope)
        assert res.success is True

        replay_engine = ReplayEngine(authority_broker=broker)
        report = replay_engine.verify_chain(
            store.all_records(),
            admitted_semantics=semantics,
            artifact=artifact,
            construction_receipt=receipt,
        )

        assert report.verdict == ReplayVerdict.VALID
        assert report.standing == ReplayStanding.ALIVE
