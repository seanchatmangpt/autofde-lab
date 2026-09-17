# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Qualification Test Suite for BRCE Consequence & Zero Unreceipted Actuation Court.

Conforms to RFC-SA2A-002 v26.9.16 Chicago Zero-Mock Standard:
- Real plant components only: Genuine brokers, boundaries, and receipt stores.
- Real physical disk I/O on every consequence and receipt.
- Zero mocks: Absolutely NO unittest.mock / Mock / MagicMock / patch / monkeypatch.
- Anti-Oracle Rule: Genuine dynamic cryptographic digest bindings, zero snapshot oracles.

Tests:
1. Strict PreparedReceipt commitment before actuator call (CHI-BRCE-01-PREPARED-COMMIT)
2. Actuator bypass prevention (CHI-BRCE-02-BYPASS-PREVENTION)
3. Anti-collusion (Actuator != Verifier) (CHI-BRCE-03-ANTI-COLLUSION)
4. Independent disk state postcondition observation (CHI-POST-01-INDEPENDENT-OBSERVATION)
5. Duplicate idempotency token replay refusal (CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL)
6. Comprehensive Court Adjudication & Fresh-Consumer Recovery
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant,
    REFUSED_NO_GRANT,
)
from autofde_lab.sa2a.brce.boundary import (
    ColludingRolesError,
    ConsequenceBoundary,
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
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    CHI_BRCE_01_PREPARED_COMMIT,
    CHI_BRCE_02_BYPASS_PREVENTION,
    CHI_BRCE_03_ANTI_COLLUSION,
    CHI_POST_01_INDEPENDENT_OBSERVATION,
    CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL,
    ConsequenceCourt,
    ConsequenceCourtRuling,
    DeceptiveDiskActuator,
    DurableDiskReceiptStore,
    GateVerdict,
    GuardedDiskJournalActuator,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
    verify_anti_collusion,
    verify_bypass_prevention,
    verify_idempotency_replay_refusal,
    verify_independent_postcondition_observation,
    verify_prepared_commitment,
)


# =============================================================================
# Gate 1: Strict PreparedReceipt Commitment Before Actuator Call
# =============================================================================


def test_strict_prepared_receipt_commitment_before_actuation(tmp_path: Path) -> None:
    """CHI-BRCE-01: PreparedReceipt must be durably committed before actuator DO (§4.8, §31).

    Verifies:
    1. PreparedReceipt exists on physical disk prior to actuation.
    2. Actuator witnesses the committed PreparedReceipt.
    3. FinalReceipt binds the exact PreparedReceipt digest.
    4. If prepared receipt commitment fails, actuation is prevented and disk untouched.
    """
    receipt_dir = tmp_path / "receipts"
    journal_path = tmp_path / "actuator_journal.json"
    actor_id = "urn:agent:cluster_ops"
    action_iri = "urn:action:quarantine_node"
    target_resource = "urn:cap:k8s:node"
    parameters = {"node_id": "worker-pool-01", "grace_seconds": 30}
    token = "idemp-prep-commit-001"

    durable_store = DurableDiskReceiptStore(receipt_dir)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-gate1",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    court = ConsequenceCourt()
    gate_result = court.audit_prepared_commitment(
        broker=broker,
        receipt_store=durable_store,
        journal_path=journal_path,
        actor_id=actor_id,
        action_iri=action_iri,
        target_resource=target_resource,
        parameters=parameters,
        idempotency_token=token,
    )

    assert gate_result.passed is True
    assert gate_result.verdict == GateVerdict.PASSED
    assert gate_result.gate_id == CHI_BRCE_01_PREPARED_COMMIT

    # Physical disk verification of PreparedReceipt
    prep_disk_file = receipt_dir / f"prep_{token}.json"
    assert prep_disk_file.exists()
    disk_prep_data = json.loads(prep_disk_file.read_text(encoding="utf-8"))
    assert disk_prep_data["idempotency_token"] == token
    assert disk_prep_data["actor_id"] == actor_id
    assert disk_prep_data["parameters"] == parameters

    # Physical disk verification of consequence actuation
    assert journal_path.exists()
    journal_data = json.loads(journal_path.read_text(encoding="utf-8"))
    assert len(journal_data) == 1
    assert journal_data[0]["action"] == action_iri

    # Falsification check: If receipt store fails to commit prepared receipt,
    # boundary MUST raise UnreceiptedActuationAttemptError and NEVER actuate!
    class FailingReceiptStore(ReceiptStore):
        def save_prepared(self, receipt: PreparedReceipt) -> None:
            # Simulate failure to commit
            pass  # Drops the receipt!

    failing_store = FailingReceiptStore()
    failing_journal = tmp_path / "failing_journal.json"
    actuator = RealDiskJournalActuator(failing_journal)
    verifier = IndependentDiskJournalVerifier(failing_journal)
    boundary_failing = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=failing_store,
        # AFDE-2604 fail-secure closure: this falsification check is about receipt-
        # store commit failure (a real, orthogonal ZUA property), not admission --
        # require_admission=False so envelope_fail still reaches the receipt-store
        # commitment check instead of being refused earlier at the admission gate.
        require_admission=False,
    )

    envelope_fail = ExecutionEnvelope(
        idempotency_token="idemp-fail-001",
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=actor_id,
        parameters=parameters,
    )

    with pytest.raises(UnreceiptedActuationAttemptError, match="Zero Unreceipted Actuation violated"):
        boundary_failing.execute(envelope_fail)

    # Actuator was NEVER called, physical disk journal was NEVER created
    assert actuator.call_count == 0
    assert not failing_journal.exists()


# =============================================================================
# Gate 2: Actuator Bypass Prevention
# =============================================================================


def test_actuator_bypass_prevention(tmp_path: Path) -> None:
    """CHI-BRCE-02: Actuation cannot bypass BRCE or execute without authority (§30, §63).

    Verifies:
    1. Consequence request without valid grant is refused with REFUSED_NO_GRANT.
    2. Zero ungranted actuation touches physical disk.
    3. Direct actuator invocation without a committed PreparedReceipt raises
       UnreceiptedActuationAttemptError.
    """
    receipt_dir = tmp_path / "receipts"
    journal_path = tmp_path / "bypass_journal.json"
    actor_id = "urn:agent:adversary"
    unauthorized_action = "urn:action:delete_database"
    target_resource = "urn:cap:database:main"
    token = "idemp-bypass-001"

    durable_store = DurableDiskReceiptStore(receipt_dir)
    broker = AuthorityBroker()  # No grant registered!

    court = ConsequenceCourt()
    gate_result = court.audit_bypass_prevention(
        broker=broker,
        receipt_store=durable_store,
        journal_path=journal_path,
        actor_id=actor_id,
        unauthorized_action_iri=unauthorized_action,
        target_resource=target_resource,
        parameters={"force": True},
        idempotency_token=token,
    )

    assert gate_result.passed is True
    assert gate_result.verdict == GateVerdict.PASSED
    assert gate_result.gate_id == CHI_BRCE_02_BYPASS_PREVENTION
    assert gate_result.evidence["boundary_refusal_code"] == REFUSED_NO_GRANT
    assert gate_result.evidence["actuator_calls_on_refusal"] == 0
    assert not journal_path.exists()

    # Direct bypass test: attempt to invoke GuardedDiskJournalActuator directly
    guarded_actuator = GuardedDiskJournalActuator(journal_path, receipt_store=durable_store)
    with pytest.raises(UnreceiptedActuationAttemptError, match="Actuator bypass attempt detected"):
        guarded_actuator.actuate(
            action_iri=unauthorized_action,
            target_resource=target_resource,
            parameters={"bypass": "direct"},
        )
    assert not journal_path.exists()


# =============================================================================
# Gate 3: Anti-Collusion (Actuator != Verifier)
# =============================================================================


def test_anti_collusion_actuator_and_verifier_separation(tmp_path: Path) -> None:
    """CHI-BRCE-03: Actuator and Verifier must be distinct entities (§30).

    Verifies:
    1. Using identical object instance raises ColludingRolesError.
    2. Sharing identical cryptographic digest is rejected.
    3. Independent entities pass gate.
    """
    journal_path = tmp_path / "anti_collusion_journal.json"
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    broker = AuthorityBroker()

    # Sub-check 1: Identical instance
    with pytest.raises(ColludingRolesError, match="colluding roles forbidden"):
        ConsequenceBoundary(
            authority_broker=broker,
            actuator=actuator,
            verifier=actuator,  # Colluding role!
        )

    # Sub-check 2: Distinct instances, but matching identity digests
    class ColludingDigestVerifier:
        def __init__(self, digest: str) -> None:
            self._digest = digest

        def verify_postcondition(self, *args: Any, **kwargs: Any) -> bool:
            return True

        def verifier_digest(self) -> str:
            return self._digest

    colluding_digest_verifier = ColludingDigestVerifier(actuator.actuator_digest())
    court = ConsequenceCourt()
    result_collusion = court.audit_anti_collusion(
        broker=broker,
        actuator=actuator,
        verifier=colluding_digest_verifier,
    )
    assert result_collusion.passed is False
    assert result_collusion.verdict == GateVerdict.FAILED
    assert "identical identity digests" in result_collusion.reason

    # Sub-check 3: Valid distinct pair
    result_valid = court.audit_anti_collusion(
        broker=broker,
        actuator=actuator,
        verifier=verifier,
    )
    assert result_valid.passed is True
    assert result_valid.verdict == GateVerdict.PASSED
    assert result_valid.gate_id == CHI_BRCE_03_ANTI_COLLUSION


# =============================================================================
# Gate 4: Independent Disk State Postcondition Observation
# =============================================================================


def test_independent_disk_state_postcondition_observation(tmp_path: Path) -> None:
    """CHI-POST-01: Verifier independently observes physical disk state (§30).

    Verifies:
    1. Legitimate actuation on disk verified independently -> EXECUTED, postcondition_verified=True.
    2. Deceptive actuator claiming success with phantom disk write is caught -> UNKNOWN_OUTCOME.
    3. Corrupted disk content is detected and rejected -> UNKNOWN_OUTCOME.
    """
    receipt_dir = tmp_path / "receipts"
    journal_path = tmp_path / "post_journal.json"
    actor_id = "urn:agent:disk_writer"
    action_iri = "urn:action:write_checkpoint"
    target_resource = "urn:cap:storage:checkpoint"
    parameters = {"checkpoint_id": "cp-99", "state_hash": "abc123fff"}
    token = "idemp-post-001"

    durable_store = DurableDiskReceiptStore(receipt_dir)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-gate4",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    court = ConsequenceCourt()
    gate_result = court.audit_independent_postcondition_observation(
        broker=broker,
        receipt_store=durable_store,
        journal_path=journal_path,
        actor_id=actor_id,
        action_iri=action_iri,
        target_resource=target_resource,
        parameters=parameters,
        idempotency_token=token,
    )

    assert gate_result.passed is True
    assert gate_result.verdict == GateVerdict.PASSED
    assert gate_result.gate_id == CHI_POST_01_INDEPENDENT_OBSERVATION
    assert gate_result.evidence["legitimate_verification"] is True
    assert gate_result.evidence["phantom_actuation_caught"] is True
    assert gate_result.evidence["corrupt_disk_caught"] is True

    # Stand-alone check: tamper with file on disk directly
    # Verifier reads disk and immediately flags violation
    verifier = IndependentDiskJournalVerifier(journal_path)
    # Correct verify
    assert verifier.verify_postcondition(
        action_iri=action_iri,
        target_resource=target_resource,
        parameters=parameters,
        evidence={"last_digest": hashlib.sha256(
            json.dumps(dict(sorted(parameters.items())), sort_keys=True).encode("utf-8")
        ).hexdigest()},
    ) is True

    # Overwrite physical disk file with tampered content
    journal_path.write_text(json.dumps([{"tampered": True}]), encoding="utf-8")
    assert verifier.verify_postcondition(
        action_iri=action_iri,
        target_resource=target_resource,
        parameters=parameters,
        evidence=None,
    ) is False


# =============================================================================
# Gate 5: Duplicate Idempotency Token Replay Refusal
# =============================================================================


def test_duplicate_idempotency_token_replay_refusal(tmp_path: Path) -> None:
    """CHI-BRCE-04: Duplicate idempotency tokens must never re-actuate (§55).

    Verifies:
    1. Re-executing completed idempotency token returns cached FinalReceipt (replayed=True).
    2. Actuator call count does not increment on replay.
    3. Conflicting parameter execution under same token is rejected.
    """
    receipt_dir = tmp_path / "receipts"
    journal_path = tmp_path / "replay_journal.json"
    actor_id = "urn:agent:batch_worker"
    action_iri = "urn:action:sync_state"
    target_resource = "urn:cap:sync:target"
    parameters = {"sync_epoch": 42}
    token = "idemp-replay-001"

    durable_store = DurableDiskReceiptStore(receipt_dir)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-gate5",
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )

    court = ConsequenceCourt()
    gate_result = court.audit_idempotency_replay_refusal(
        broker=broker,
        receipt_store=durable_store,
        journal_path=journal_path,
        actor_id=actor_id,
        action_iri=action_iri,
        target_resource=target_resource,
        parameters=parameters,
        idempotency_token=token,
    )

    assert gate_result.passed is True
    assert gate_result.verdict == GateVerdict.PASSED
    assert gate_result.gate_id == CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL
    assert gate_result.evidence["replayed_flag"] is True
    assert gate_result.evidence["initial_call_count"] == 1
    assert gate_result.evidence["final_call_count"] == 1

    # Conflict test: Attempt to save prepared receipt with same token but different parameters
    conflicting_prep = PreparedReceipt(
        prepared_id="prep-conflict-999",
        idempotency_token=token,
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=actor_id,
        grant_id="grant-gate5",
        plan_digest="genesis:0" * 4,
        artifact_digest="none",
        admitted_input_digest="genesis:0" * 4,
        consequence_class="LOCAL_EFFECT",
        parameters={"sync_epoch": 999},  # Conflicting parameter!
    )
    with pytest.raises(ValueError, match="Idempotency token conflict"):
        durable_store.save_prepared(conflicting_prep)


# =============================================================================
# Gate 6: Comprehensive Consequence Court Adjudication & Fresh-Consumer Recovery
# =============================================================================


def test_consequence_court_full_adjudication_and_fresh_consumer(tmp_path: Path) -> None:
    """Full 5-Gate Consequence Court Adjudication and Fresh-Consumer Verification.

    Verifies:
    1. Court adjudicates all 5 gates successfully on real filesystem disk I/O.
    2. Court ruling has 5/5 passed gates and status QUALIFIED.
    3. Fresh consumer re-reading raw disk receipt files validates offline replay chain.
    """
    court = ConsequenceCourt()
    ruling: ConsequenceCourtRuling = court.adjudicate(
        base_dir=tmp_path,
        actor_id="urn:agent:autonomic-pilot",
        action_iri="urn:action:quarantine_node",
        target_resource="urn:cap:cluster:nodes",
        parameters={"node_id": "prod-k8s-node-7", "isolation": "STRICT"},
    )

    assert ruling.passed is True
    assert ruling.total_gates == 5
    assert ruling.passed_gates == 5
    assert "QUALIFIED" in ruling.summary
    assert len(ruling.audit_digest) == 64

    # Verify all expected gates are represented
    assert CHI_BRCE_01_PREPARED_COMMIT in ruling.gate_results
    assert CHI_BRCE_02_BYPASS_PREVENTION in ruling.gate_results
    assert CHI_BRCE_03_ANTI_COLLUSION in ruling.gate_results
    assert CHI_POST_01_INDEPENDENT_OBSERVATION in ruling.gate_results
    assert CHI_BRCE_04_IDEMPOTENCY_REPLAY_REFUSAL in ruling.gate_results

    for gate_id, gate_res in ruling.gate_results.items():
        assert gate_res.passed is True, f"Gate {gate_id} failed: {gate_res.reason}"
        assert gate_res.verdict == GateVerdict.PASSED

    # Fresh Consumer Proof:
    # Discover the court directory created during adjudication
    court_subdirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name.startswith("court_")]
    assert len(court_subdirs) == 1
    receipts_dir = court_subdirs[0] / "receipts"

    # Instantiate brand-new DurableDiskReceiptStore to reload from physical disk
    fresh_store = DurableDiskReceiptStore(receipts_dir)
    assert len(fresh_store.all_records()) >= 2

    # Replay verification with genuine ReplayEngine
    fresh_broker = AuthorityBroker()
    fresh_broker.register_grant(
        AuthorityGrant(
            grant_id="grant-court-qual-001",
            subject_id="urn:agent:autonomic-pilot",
            action_iri="urn:action:quarantine_node",
            target_resource_iri="urn:cap:cluster:nodes",
        )
    )

    replay_engine = ReplayEngine(authority_broker=fresh_broker)
    replay_report = replay_engine.verify_chain(fresh_store.all_records())

    assert replay_report.verdict == ReplayVerdict.VALID
    # The full store contains both genuine executed receipts and adversarial refusal/falsification receipts
    assert replay_report.standing in (ReplayStanding.ALIVE, ReplayStanding.PARTIAL_ALIVE)
    assert replay_report.executed_count >= 1
    assert replay_report.verified_without_actuation is True

    # Check that replaying solely the executed pair yields pure ALIVE standing
    gate1_records = [
        r for r in fresh_store.all_records()
        if r.get("idempotency_token") == ruling.gate_results[CHI_BRCE_01_PREPARED_COMMIT].evidence["idempotency_token"]
    ]
    gate1_report = replay_engine.verify_chain(gate1_records)
    assert gate1_report.verdict == ReplayVerdict.VALID
    assert gate1_report.standing == ReplayStanding.ALIVE
    assert gate1_report.executed_count == 1
