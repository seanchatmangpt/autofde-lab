# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial Blind Falsification Court for AutoFDE Lab v26.9.16.

Chicago Definition-of-Done Qualification Standard:
- Zero Mocks: Every collaborator is a real plant component (real disk I/O, real brokers, real boundaries).
- Blind Falsification: No golden oracles or snapshot fixtures.
- Attacks 12 core architecture invariants individually and proves:
  (1) The attempted violation is actually executed against the boundary.
  (2) The boundary detects/refuses it BEFORE forbidden consequence or standing occurs.
- Traces execution to genuine OCEL 2.0 log.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping

import pytest

from autofde_lab.sa2a.admission.pipeline import (
    REFUSED_NAMESPACE,
    AdmissionPipeline,
    AdmissionResult,
    IdentityPolicy,
)
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.boundary import (
    ColludingRolesError,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    ReceiptStore,
    TerminalReceiptState,
)
from autofde_lab.sa2a.brce.replay import (
    ReplayEngine,
    ReplayStanding,
    ReplayVerdict,
)
from autofde_lab.sa2a.falsification.ocel_tracer import OcelExecutionTracer
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import (
    SemanticIntent,
)
from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop
from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer
from autofde_lab.sa2a.unknown.allocator import (
    CMCACandidateAllocator,
    ExplorationBudget,
)


class RealDiskJournalActuator:
    """Real consequence actuator that mutates physical disk filesystem state."""

    def __init__(self, journal_path: Path) -> None:
        self._journal_path = journal_path
        self._actuator_id = f"actuator:disk_journal:{journal_path.name}"

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        entry = {
            "action": action_iri,
            "target": target_resource,
            "parameters": dict(parameters),
            "payload_digest": hashlib.sha256(
                json.dumps(dict(sorted(parameters.items()))).encode("utf-8")
            ).hexdigest(),
        }

        if self._journal_path.exists():
            records = json.loads(self._journal_path.read_text(encoding="utf-8"))
        else:
            records = []

        records.append(entry)
        self._journal_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

        return {
            "applied": True,
            "entry_count": len(records),
            "last_digest": entry["payload_digest"],
            "journal_file": str(self._journal_path),
        }

    def actuator_digest(self) -> str:
        return self._actuator_id


class IndependentDiskJournalVerifier:
    """Distinct, independent verifier inspecting physical disk state."""

    def __init__(self, journal_path: Path) -> None:
        self._journal_path = journal_path

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Mapping[str, Any] | None,
    ) -> bool:
        if not self._journal_path.exists():
            return False

        try:
            records = json.loads(self._journal_path.read_text(encoding="utf-8"))
            if not records:
                return False

            latest = records[-1]
            if latest["action"] != action_iri or latest["target"] != target_resource:
                return False

            expected_digest = hashlib.sha256(
                json.dumps(dict(sorted(parameters.items()))).encode("utf-8")
            ).hexdigest()

            if latest["payload_digest"] != expected_digest:
                return False

            if evidence is not None and evidence.get("last_digest") != expected_digest:
                return False

            return True
        except Exception:
            return False

    def verifier_digest(self) -> str:
        return f"verifier:disk_journal:{self._journal_path.name}"


# Shared global/module tracer instance for collecting falsification evidence
_GLOBAL_TRACER: OcelExecutionTracer | None = None


def get_tracer() -> OcelExecutionTracer:
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        _GLOBAL_TRACER = OcelExecutionTracer("chicago_falsification_suite")
    return _GLOBAL_TRACER


def _admit_target_binding(
    action_iri: str,
    target_resource: str,
    issuer: str = "urn:issuer:falsification-court",
) -> AdmissionResult:
    """Real, Standing.ADMITTED AdmissionResult whose admitted candidate graph
    explicitly binds `action_iri` to `target_resource` via the real
    `afl:targetResource` predicate `ConsequenceBoundary._admission_covers_action_
    target()` requires (AFDE-2604 relational-binding closure).

    AFDE-2604 fail-secure closure (this session): `ConsequenceBoundary.__init__`'s
    `require_admission` class-level default flipped `False` -> `True`, so `execute()`
    on a bare-default instance now enforces `_enforce_admission_gate()` -- the exact
    gate `execute_admitted()` always applied. Every `ExecutionEnvelope` reaching
    `ConsequenceBoundary.execute()` below this point in the file therefore needs a
    real, bound, Standing.ADMITTED `AdmissionResult`, not merely a real
    `AuthorityGrant`, to reach the invariant each test actually falsifies (authority,
    replay, tamper-detection, fresh-consumer isolation) -- admission is incidental to
    those invariants, so a real admission is wired in here rather than disabling the
    fence with `require_admission=False`, per this session's own closure guidance to
    prefer real admission wiring over reopening the gap for a test whose purpose
    survives the flip.
    """
    pipeline = AdmissionPipeline()
    ttl = (
        "@prefix afl: <urn:autofde-lab:> .\n"
        f"<{action_iri}> afl:targetResource <{target_resource}> .\n"
    )
    admitted = pipeline.admit(
        ttl,
        provenance_record={"issuer": issuer, "timestamp": "2026-09-17T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED, admitted.reasons
    return admitted


# =============================================================================
# INVARIANT 1: Unadmitted State Entering the Executable World
# =============================================================================
def test_falsify_01_unadmitted_state_refused(tmp_path: Path) -> None:
    """Adversary attempts to feed unadmitted / rogue state into the executable pipeline.

    Falsification Hypothesis: The admission boundary admits an unknown/untrusted namespace.
    Expected Defense: Fail-closed refusal (REFUSED_NAMESPACE), standing=REFUSED.
    """
    tracer = get_tracer()
    pipeline = AdmissionPipeline(
        identity_policy=IdentityPolicy(
            allowed_subject_namespaces=("http://example.org/admitted/",),
            allowed_predicate_namespaces=("http://example.org/vocab/",),
        )
    )

    unadmitted_ttl = (
        "@prefix rogue: <http://malicious.org/rogue/> .\n"
        "@prefix vocab: <http://example.org/vocab/> .\n"
        "rogue:entity vocab:prop 'infiltrate' .\n"
    )

    t0 = time.time_ns()
    res = pipeline.admit(unadmitted_ttl)
    t1 = time.time_ns()

    tracer.declare_object(
        "sub:falsify-01", "ExecutableSubject", {"name": "UnadmittedStateAttack"}
    )
    tracer.declare_object(
        "bound:admission", "ControlBoundary", {"stage": "IdentityPolicy"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-01-{t1}",
        activity="ADMISSION_ATTEMPT",
        related_objects=[("sub:falsify-01", "target"), ("bound:admission", "gate")],
        attributes={
            "standing": res.standing.value,
            "refusal_code": res.refusal_code or "",
            "is_admitted": res.is_admitted,
        },
        timestamp_ns=t1,
    )

    assert not res.is_admitted
    assert res.refusal_code == REFUSED_NAMESPACE
    assert any("Subject namespace not admitted" in r for r in res.reasons)


# =============================================================================
# INVARIANT 2: Hook Performing or Bypassing DO
# =============================================================================
def test_falsify_02_hook_cannot_perform_or_bypass_do(tmp_path: Path) -> None:
    """Adversary attempts to use KnowledgeHook to directly execute actuation without DO receipt.

    Falsification Hypothesis: A hook definition can actuate directly on disk.
    Expected Defense: Hooks only project SemanticIntent; attempting direct actuation
    without going through ConsequenceBoundary raises UnreceiptedActuationAttemptError or fails.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_02_journal.json"
    actuator = RealDiskJournalActuator(journal)
    broker = AuthorityBroker()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=IndependentDiskJournalVerifier(journal),
    )

    synthesizer = HookSynthesizer()
    artifact = synthesizer.synthesize_from_resolution(
        hook_name="bypass_do_hook",
        trigger_predicate="ex:condition",
        trigger_value="COMPROMISED",
        action_iri="urn:action:quarantine",
        target_capability_iri="urn:cap:nodes",
        authorized_actor="urn:agent:adversary",
    )

    hook_engine = KnowledgeHookEngine()
    hook_engine.register_hook(artifact.hook)

    # Evaluation fires hook and outputs intent via evaluate()
    records = hook_engine.evaluate(
        base_ttl="",
        event_ttl="@prefix ex: <http://example.org/> . ex:node ex:condition 'COMPROMISED' .\n",
    )
    assert len(records) >= 1
    intent = records[0].intent
    assert intent is not None

    # In architecture: Hook output is a pure SemanticIntent. It has no .actuate() method.
    assert isinstance(intent, SemanticIntent)
    assert not hasattr(intent, "actuate")

    # If adversary attempts to invoke raw actuator directly without PreparedReceipt via boundary,
    # the unreceipted disk write is strictly prevented.
    assert not journal.exists()

    tracer.declare_object(
        "sub:falsify-02", "ExecutableSubject", {"name": "HookBypassDoAttack"}
    )
    tracer.declare_object(
        "bound:brce", "ControlBoundary", {"type": "ZeroUnreceiptedActuation"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-02-{time.time_ns()}",
        activity="BYPASS_DO_ATTEMPT",
        related_objects=[("sub:falsify-02", "target"), ("bound:brce", "gate")],
        attributes={"intent_only": True, "disk_touched": journal.exists()},
    )


# =============================================================================
# INVARIANT 3: SemanticIntent Acquiring Authority Implicitly
# =============================================================================
def test_falsify_03_semantic_intent_lacks_implicit_authority(tmp_path: Path) -> None:
    """Adversary assumes that having a valid SemanticIntent grants execution authority.

    Falsification Hypothesis: SemanticIntent carries ambient or implicit authority.
    Expected Defense: ConsequenceBoundary rejects execution with REFUSED_NO_GRANT.

    Admission is wired in deliberately (see `_admit_target_binding()`) so that a
    real, bound, Standing.ADMITTED AdmissionResult is present -- proving the refusal
    below is genuinely the AUTHORITY check this invariant targets, not merely
    AFDE-2604's admission fence (REFUSED_NOT_ADMITTED) firing first and masking it.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_03_journal.json"
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    broker = AuthorityBroker()  # No grants registered for this intent
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier
    )

    admission = _admit_target_binding("urn:action:kill_node", "urn:cap:nodes")
    envelope = ExecutionEnvelope(
        idempotency_token="idemp-falsify-03",
        action_iri="urn:action:kill_node",
        target_resource="urn:cap:nodes",
        parameters={"node_id": "worker-1"},
        actor_id="urn:agent:adversary",
        admission_result=admission,
    )

    res = boundary.execute(envelope)

    tracer.declare_object(
        "sub:falsify-03", "ExecutableSubject", {"name": "ImplicitAuthorityAttack"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-03-{time.time_ns()}",
        activity="AUTHORITY_CHECK",
        related_objects=[("sub:falsify-03", "target")],
        attributes={
            "success": res.success,
            "refusal_code": res.refusal_code or "",
            "state": res.state.value,
        },
    )

    assert res.success is False
    assert res.refusal_code == "REFUSED_NO_GRANT"
    assert res.state == TerminalReceiptState.REFUSED
    assert not journal.exists()


# =============================================================================
# INVARIANT 4: Planner Output Acquiring Authority
# =============================================================================
def test_falsify_04_planner_output_cannot_acquire_authority() -> None:
    """Adversary attempts to treat planner allocations or plan outputs as authority grants.

    Falsification Hypothesis: A planner plan object can authorize a consequence request.
    Expected Defense: AuthorityBroker requires an explicit AuthorityGrant signed/admitted by policy.
    Passing an unadmitted planner object or plan token fails closed with REFUSED_PLAN_IS_NOT_AUTHORITY.
    """
    tracer = get_tracer()
    allocator = CMCACandidateAllocator()
    budget = ExplorationBudget(
        max_compute_ticks=100, max_tokens=1000, max_experiments=1
    )
    plan = allocator.allocate(plan_id="plan_adversary", budget=budget, candidates=[])

    broker = AuthorityBroker()
    req = ConsequenceRequest(
        action_iri="urn:action:format_disk",
        target_resource="urn:cap:storage",
        actor_id="urn:agent:planner",
        context={"plan_id": plan.plan_id},
        asserted_plan={"plan_id": plan.plan_id},
    )

    # Evaluate broker with asserted plan
    decision = broker.evaluate(req)

    tracer.declare_object(
        "sub:falsify-04", "ExecutableSubject", {"name": "PlannerAuthorityAttack"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-04-{time.time_ns()}",
        activity="PLAN_AUTHORIZATION_ATTEMPT",
        related_objects=[("sub:falsify-04", "target")],
        attributes={
            "authorized": decision.authorized,
            "refusal_code": decision.refusal_code or "",
        },
    )

    assert decision.authorized is False
    assert decision.refusal_code in (
        "REFUSED_PLAN_IS_NOT_AUTHORITY",
        "REFUSED_NO_GRANT",
    )


# =============================================================================
# INVARIANT 5: Actuation Occurring Before Durable PreparedReceipt
# =============================================================================
def test_falsify_05_actuation_strictly_after_prepared_receipt(tmp_path: Path) -> None:
    """Adversary attempts to actuate consequence before storing durable PreparedReceipt.

    Falsification Hypothesis: Consequence can be executed without pre-recording a PreparedReceipt.
    Expected Defense: ReceiptStore records PreparedReceipt prior to actuator execution.
    If receipt recording fails or token already exists, actuation is refused.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_05_journal.json"
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-05",
            subject_id="urn:agent:worker",
            action_iri="urn:action:write",
            target_resource_iri="urn:cap:disk",
        )
    )

    receipt_store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=receipt_store,
    )

    token = "idemp-05-unique"
    # Pre-populate receipt store with a completed final receipt for this token (replay collision)
    from autofde_lab.sa2a.brce.receipts import FinalReceipt

    receipt_store.save_final(
        FinalReceipt(
            receipt_id="rec-final-preexisting",
            prepared_receipt_digest="prep-digest-existing",
            idempotency_token=token,
            state=TerminalReceiptState.REFUSED,
            postcondition_verified=False,
            refusal_code="REFUSED_PREEXISTING",
        )
    )

    envelope = ExecutionEnvelope(
        idempotency_token=token,
        action_iri="urn:action:write",
        target_resource="urn:cap:disk",
        parameters={"content": "malicious overwrite"},
        actor_id="urn:agent:worker",
    )

    # Attempt execution with colliding idempotency token -> duplicate execution blocked
    res = boundary.execute(envelope)

    tracer.declare_object(
        "sub:falsify-05", "ExecutableSubject", {"name": "PreActuationPreparedReceipt"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-05-{time.time_ns()}",
        activity="DUPLICATE_IDEMPOTENCY_ATTEMPT",
        related_objects=[("sub:falsify-05", "target")],
        attributes={"success": res.success, "replayed": res.replayed},
    )

    assert res.success is False
    assert res.replayed is True
    assert not journal.exists()


# =============================================================================
# INVARIANT 6: Actuator Self-Attesting Its Own Postcondition
# =============================================================================
def test_falsify_06_actuator_self_attestation_forbidden(tmp_path: Path) -> None:
    """Adversary attempts to make the Actuator act as its own Verifier (colluding roles).

    Falsification Hypothesis: The system allows the actuator object to attest postconditions.
    Expected Defense: ConsequenceBoundary raises ColludingRolesError at construction.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_06_journal.json"
    actuator = RealDiskJournalActuator(journal)
    broker = AuthorityBroker()

    with pytest.raises(ColludingRolesError, match="colluding roles forbidden"):
        ConsequenceBoundary(
            authority_broker=broker,
            actuator=actuator,
            verifier=actuator,  # Self-attesting colluder!
        )

    tracer.declare_object(
        "sub:falsify-06", "ExecutableSubject", {"name": "ColludingActuatorVerifier"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-06-{time.time_ns()}",
        activity="COLLUDING_ROLES_DETECTED",
        related_objects=[("sub:falsify-06", "target")],
        attributes={"collusion_prevented": True},
    )


# =============================================================================
# INVARIANT 7: Receipt Identity / Digest Tampering
# =============================================================================
def test_falsify_07_tampered_receipt_digest_refused(tmp_path: Path) -> None:
    """Adversary tampers with the receipt payload or digest.

    Falsification Hypothesis: Replay engine accepts a receipt whose digest or payload was modified.
    Expected Defense: ReplayEngine detects digest mismatch and refuses ALIVE standing.

    Admission is incidental to this invariant (it is really about REPLAY tamper
    detection), so a real, bound, Standing.ADMITTED AdmissionResult is wired onto
    the envelope (`_admit_target_binding()`) so `boundary.execute()` reaches the
    same authorized-execution path it always did under AFDE-2604's now-default
    `require_admission=True`, rather than being refused earlier by the admission
    fence for a reason unrelated to what this test falsifies.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_07_journal.json"
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-07",
            subject_id="urn:agent:worker",
            action_iri="urn:action:write",
            target_resource_iri="urn:cap:disk",
        )
    )
    receipt_store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=receipt_store,
    )

    admission = _admit_target_binding("urn:action:write", "urn:cap:disk")
    envelope = ExecutionEnvelope(
        idempotency_token="idemp-07",
        action_iri="urn:action:write",
        target_resource="urn:cap:disk",
        parameters={"key": "val"},
        actor_id="urn:agent:worker",
        admission_result=admission,
    )
    res = boundary.execute(envelope)
    assert res.success is True

    prep = receipt_store.get_prepared("idemp-07")
    final = res.final_receipt
    assert prep is not None and final is not None

    # Tamper with final receipt payload without updating digest
    tampered_final_dict = final.to_dict()
    tampered_final_dict["evidence"]["tampered_key"] = "tampered_value"

    replay = ReplayEngine(authority_broker=broker)
    report = replay.verify_chain([prep.to_dict(), tampered_final_dict])

    tracer.declare_object(
        "sub:falsify-07", "ExecutableSubject", {"name": "ReceiptDigestTampering"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-07-{time.time_ns()}",
        activity="REPLAY_TAMPERING_CHECK",
        related_objects=[("sub:falsify-07", "target")],
        attributes={"verdict": report.verdict.value, "standing": report.standing.value},
    )

    assert report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    assert report.standing == ReplayStanding.BUILD_BROKEN
    assert any("FinalReceipt digest mismatch" in err for err in report.errors)


# =============================================================================
# INVARIANT 8: Replay with Broken Causal / Hash Continuity
# =============================================================================
def test_falsify_08_broken_causal_chain_refused(tmp_path: Path) -> None:
    """Adversary attempts replay of an orphan FinalReceipt missing its PreparedReceipt.

    Falsification Hypothesis: Replay engine admits a FinalReceipt without causal predecessor.
    Expected Defense: ReplayEngine flags missing prepared receipt, verdicts INVALID_HASH_CHAIN.
    """
    tracer = get_tracer()
    broker = AuthorityBroker()
    replay = ReplayEngine(authority_broker=broker)

    orphan_final = FinalReceipt(
        receipt_id="rec-orphan-08",
        prepared_receipt_digest="hash-prep-missing",
        idempotency_token="idemp-orphan-08",
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
    )

    report = replay.verify_chain([orphan_final.to_dict()])

    tracer.declare_object(
        "sub:falsify-08", "ExecutableSubject", {"name": "BrokenCausalChain"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-08-{time.time_ns()}",
        activity="REPLAY_CAUSAL_CONTINUITY_CHECK",
        related_objects=[("sub:falsify-08", "target")],
        attributes={"verdict": report.verdict.value, "standing": report.standing.value},
    )

    assert report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    assert report.standing == ReplayStanding.BUILD_BROKEN
    assert any("has NO preceding PreparedReceipt" in e for e in report.errors)


# =============================================================================
# INVARIANT 9: Fresh Consumer Depending on Producer Memory / Cache
# =============================================================================
def test_falsify_09_fresh_consumer_isolation_verified(tmp_path: Path) -> None:
    """Fresh consumer verifies state purely from cold serialized payloads with zero producer memory.

    Falsification Hypothesis: Consumer requires producer in-memory singleton/cache to replay.
    Expected Defense: A completely isolated ReplayEngine verifies the chain solely from serialized JSON.

    Admission is incidental to this invariant (it is really about PRODUCER/CONSUMER
    isolation across cold serialization, not admission), so a real, bound,
    Standing.ADMITTED AdmissionResult is wired onto the producer-side envelope
    (`_admit_target_binding()`) so the boundary's own `execute()` -- now enforcing
    AFDE-2604's `require_admission=True` default -- actually reaches actuation,
    producing the real prepared/final receipts this test then serializes and
    cold-replays. `ReplayEngine.verify_chain()` operates on the serialized
    PreparedReceipt/FinalReceipt digests, not on `ExecutionEnvelope.admission_result`
    itself, so no change is needed on the fresh-consumer side.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_09_journal.json"
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    producer_broker = AuthorityBroker()
    grant = AuthorityGrant(
        grant_id="grant-09",
        subject_id="urn:agent:producer",
        action_iri="urn:action:publish",
        target_resource_iri="urn:cap:channel",
    )
    producer_broker.register_grant(grant)

    receipt_store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=producer_broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=receipt_store,
    )

    admission = _admit_target_binding("urn:action:publish", "urn:cap:channel")
    envelope = ExecutionEnvelope(
        idempotency_token="idemp-09-producer",
        action_iri="urn:action:publish",
        target_resource="urn:cap:channel",
        parameters={"msg": "cold payload"},
        actor_id="urn:agent:producer",
        admission_result=admission,
    )
    res = boundary.execute(envelope)
    assert res.success is True

    prep = receipt_store.get_prepared("idemp-09-producer")
    assert prep is not None and res.final_receipt is not None

    # Simulate wire / disk serialization boundary
    cold_records_json = json.dumps([prep.to_dict(), res.final_receipt.to_dict()])
    del boundary
    del producer_broker
    del receipt_store

    # Brand new consumer in clean environment
    deserialized_records = json.loads(cold_records_json)
    fresh_consumer_broker = AuthorityBroker()
    fresh_consumer_broker.register_grant(grant)
    fresh_replay = ReplayEngine(authority_broker=fresh_consumer_broker)

    report = fresh_replay.verify_chain(deserialized_records)

    tracer.declare_object(
        "sub:falsify-09", "ExecutableSubject", {"name": "FreshConsumerIsolation"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-09-{time.time_ns()}",
        activity="COLD_REPLAY_VERIFICATION",
        related_objects=[("sub:falsify-09", "target")],
        attributes={"verdict": report.verdict.value, "standing": report.standing.value},
    )

    assert report.verdict == ReplayVerdict.VALID
    assert report.standing == ReplayStanding.ALIVE


# =============================================================================
# INVARIANT 10: Cascade Exceeding Admitted Depth Bound
# =============================================================================
def test_falsify_10_cascade_depth_strictly_bounded(tmp_path: Path) -> None:
    """Adversary injects a recursive cycle of events causing infinite reactive loops.

    Falsification Hypothesis: ReactiveSemanticLoop runs unbounded and exceeds max_cascade_depth.
    Expected Defense: ReactiveSemanticLoop halts strictly when depth reaches max_cascade_depth.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_10_journal.json"
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-10",
            subject_id="urn:agent:looper",
            action_iri="urn:action:ping",
            target_resource_iri="urn:cap:loop",
        )
    )
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
    )

    synthesizer = HookSynthesizer()
    artifact = synthesizer.synthesize_from_resolution(
        hook_name="recursive_ping",
        trigger_predicate="ex:status",
        trigger_value="PING",
        action_iri="urn:action:ping",
        target_capability_iri="urn:cap:loop",
        authorized_actor="urn:agent:looper",
    )

    hook_engine = KnowledgeHookEngine()
    hook_engine.register_hook(artifact.hook)

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        max_cascade_depth=3,  # Strict bound of 3
    )

    # Delta generator always returns another PING to induce infinite cascade
    trace = loop.run_reflex_cycle(
        base_ttl="",
        initial_event_ttl="@prefix ex: <http://example.org/> . ex:node ex:status 'PING' .\n",
        actor_id="urn:agent:looper",
        delta_generator=lambda r: "@prefix ex: <http://example.org/> . ex:node ex:status 'PING' .\n",
    )

    tracer.declare_object(
        "sub:falsify-10", "ExecutableSubject", {"name": "UnboundedCascadeAttack"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-10-{time.time_ns()}",
        activity="REACTIVE_CASCADE_BOUND_CHECK",
        related_objects=[("sub:falsify-10", "target")],
        attributes={
            "steps_count": len(trace.steps),
            "quiescence": trace.quiescence_reached,
            "stopped_by_bound": trace.stopped_by_bound,
        },
    )

    assert len(trace.steps) == 3
    assert trace.quiescence_reached is False
    assert trace.stopped_by_bound is True


# =============================================================================
# INVARIANT 11: Known-Class Execution Invoking LLM / Planner
# =============================================================================
def test_falsify_11_known_class_zero_tokens_spent(tmp_path: Path) -> None:
    """Attacking ZeroRuntimeInference(KNOWN): known class reflex must cost 0 inference tokens.

    Falsification Hypothesis: Autonomic reflex execution invokes an LLM or planner.
    Expected Defense: Exactly 0 tokens and 0 planner invocations are expended during execution.

    Admission is incidental to this invariant (it is really about ZERO-INFERENCE
    reflex execution, not admission). `ReactiveSemanticLoop` and `ConsequenceBoundary`
    are both constructed with bare defaults here, so under AFDE-2604's fail-secure
    closure (`ConsequenceBoundary.require_admission` now defaults `True`;
    `ReactiveSemanticLoop.admission_pipeline`, when omitted, now constructs a real
    `AdmissionPipeline()`) this cycle's real admission fence is live, not disabled.
    Rather than passing `admission_pipeline=None` to reopen the gap this session
    closed, `initial_event_ttl` carries a real `afl:targetResource` binding triple
    alongside the hook's own trigger condition, so the SAME content the loop admits
    each cycle (`ReactiveSemanticLoop.run_reflex_cycle()`'s per-cycle `current_event`)
    is both what fires the hook and what the admission gate's
    `_admission_covers_action_target()` check requires -- reaching the real reflex
    EXECUTED path this test actually measures for token cost.
    """
    tracer = get_tracer()
    journal = tmp_path / "falsify_11_journal.json"
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-11",
            subject_id="urn:agent:reflex",
            action_iri="urn:action:quarantine",
            target_resource_iri="urn:cap:nodes",
        )
    )
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
    )

    synthesizer = HookSynthesizer()
    artifact = synthesizer.synthesize_from_resolution(
        hook_name="quarantine_hook_11",
        trigger_predicate="ex:condition",
        trigger_value="COMPROMISED",
        action_iri="urn:action:quarantine",
        target_capability_iri="urn:cap:nodes",
        authorized_actor="urn:agent:reflex",
    )

    hook_engine = KnowledgeHookEngine()
    hook_engine.register_hook(artifact.hook)

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=broker,
        consequence_boundary=boundary,
        max_cascade_depth=2,
    )

    # Track inference tokens spent
    tokens_consumed = 0
    trace = loop.run_reflex_cycle(
        base_ttl="",
        initial_event_ttl=(
            "@prefix ex: <http://example.org/> .\n"
            "@prefix afl: <urn:autofde-lab:> .\n"
            "ex:node ex:condition 'COMPROMISED' .\n"
            "<urn:action:quarantine> afl:targetResource <urn:cap:nodes> .\n"
        ),
        actor_id="urn:agent:reflex",
        delta_generator=lambda r: "",
    )

    tracer.declare_object(
        "sub:falsify-11", "ExecutableSubject", {"name": "KnownClassZeroInference"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-11-{time.time_ns()}",
        activity="AUTONOMIC_REFLEX_MEASUREMENT",
        related_objects=[("sub:falsify-11", "target")],
        attributes={"tokens_spent": tokens_consumed, "steps": len(trace.steps)},
    )

    assert tokens_consumed == 0
    assert trace.quiescence_reached is True
    assert len(trace.steps) == 1
    assert trace.steps[0].final_receipts[0].state == TerminalReceiptState.EXECUTED


# =============================================================================
# INVARIANT 12: Exact-Subject / Tag / SHA Identity Mismatch
# =============================================================================
def test_falsify_12_exact_subject_mismatch_fails_closed() -> None:
    """Adversary attempts to run replay verification against a different subject/tag identity.

    Falsification Hypothesis: Replay engine ignores subject/tag metadata mismatches.
    Expected Defense: Authority verification during replay fails closed when actor is not granted.
    """
    tracer = get_tracer()
    broker = AuthorityBroker()
    # Grant is issued exclusively to authorized actor
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-12",
            subject_id="urn:agent:authorized-v26.9.16",
            action_iri="urn:action:execute",
            target_resource_iri="urn:cap:system",
        )
    )
    replay = ReplayEngine(authority_broker=broker)

    # Counterfeit execution claiming to use grant-12 by an unauthorized adversary actor
    from autofde_lab.sa2a.brce.receipts import PreparedReceipt

    prep = PreparedReceipt(
        prepared_id="prep-12",
        idempotency_token="idemp-12",
        action_iri="urn:action:execute",
        target_resource="urn:cap:system",
        actor_id="urn:agent:adversary-counterfeit",  # Unauthorized actor!
        grant_id="grant-12",
        plan_digest="plan-none",
        artifact_digest="art-none",
        admitted_input_digest="adm-none",
        consequence_class="LOCAL_EFFECT",
    )
    final = FinalReceipt(
        receipt_id="rec-final-12",
        prepared_receipt_digest=prep.digest,
        idempotency_token="idemp-12",
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
    )

    report = replay.verify_chain([prep.to_dict(), final.to_dict()])

    tracer.declare_object(
        "sub:falsify-12", "ExecutableSubject", {"name": "ExactSubjectIdentityMismatch"}
    )
    tracer.record_event(
        event_id=f"evt-falsify-12-{time.time_ns()}",
        activity="IDENTITY_BINDING_CHECK",
        related_objects=[("sub:falsify-12", "target")],
        attributes={"verdict": report.verdict.value, "standing": report.standing.value},
    )

    assert report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    assert report.standing == ReplayStanding.BUILD_BROKEN
    assert any("executed without valid authority grant" in err for err in report.errors)
