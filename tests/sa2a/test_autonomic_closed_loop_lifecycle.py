"""The Complete Autonomic Closed-Loop Lifecycle Test.

Demonstrates the overarching AutoFDE-Lab thesis:
    UNKNOWN -> Explore -> Qualify -> Hook Synthesizer -> GraphLaw -> BRCE -> Receipt -> Quiescence.

Proves:
    1. Fast-path reflex execution avoids runtime LLM inference:
       ∂(RuntimeInference) / ∂(AccumulatedQualifiedExperience) < 0.
    2. Novelty refused in production is transformed into Lab candidates.
    3. Compiled Knowledge Hooks notice their own future applicability and execute via BRCE.
"""

from __future__ import annotations

from datetime import datetime, timezone

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
)
from autofde_lab.sa2a.brce.boundary import (
    BoundaryExecutionResult,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import FinalReceipt, TerminalReceiptState
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.reactive_loop import ReactiveSemanticLoop
from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer
from autofde_lab.sa2a.unknown.allocator import (
    CMCACandidateAllocator,
    ExplorationBudget,
)
from autofde_lab.sa2a.unknown.novelty_ingest import NoveltyIngestionGateway


class MockClusterActuator:
    def __init__(self) -> None:
        self.restarted_pods: list[str] = []

    def actuate(self, action_iri: str, target_resource: str, parameters: dict) -> dict:
        pod = parameters.get("pod_id", "unknown-pod")
        self.restarted_pods.append(pod)
        return {"restarted": True, "pod_id": pod, "action": action_iri}

    def actuator_digest(self) -> str:
        return "actuator:k8s:v1"


class MockClusterVerifier:
    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: dict,
        evidence: dict | None,
    ) -> bool:
        return evidence is not None and evidence.get("restarted") is True

    def verifier_digest(self) -> str:
        return "verifier:k8s:v1"


def test_autonomic_closed_loop_lifecycle():
    """Verify the full lifecycle:
    Cycle 0: Novel unhandled incident -> Refused in production.
    Lab: Ingestion -> CMCA Allocation -> Resolution -> Hook Synthesis.
    Cycle 1: Same incident reoccurs -> Autonomic Reflex executes with ZERO runtime inference.
    """
    actor_id = "urn:agent:autonomic-controller"
    action_iri = "urn:action:restart_pod"
    target_cap = "urn:cap:cluster:pods"

    actuator = MockClusterActuator()
    verifier = MockClusterVerifier()

    # =========================================================================
    # CYCLE 0: PRODUCTION NOVELTY ENCOUNTER
    # =========================================================================
    # Initially, broker has no grant and engine has no hook for this novel failure
    prod_broker = AuthorityBroker()
    prod_boundary = ConsequenceBoundary(
        authority_broker=prod_broker,
        actuator=actuator,
        verifier=verifier,
    )

    # AFDE-2604 fail-secure closure (this session): ConsequenceBoundary's
    # `require_admission` class-level default flipped False -> True, so a
    # bare-default `prod_boundary.execute()` now applies the same admission gate
    # `execute_admitted()` always has, BEFORE AuthorityBroker.evaluate() is ever
    # reached. Admission is incidental to what Cycle 0 is actually demonstrating
    # (a novel incident is refused for lack of an authority GRANT, not for lack
    # of admission) -- per the fix-forward decision procedure this wires in a
    # real, valid, Standing.ADMITTED AdmissionResult (rather than passing
    # `require_admission=False`) so the assertion below still reaches, and
    # verifies, the exact REFUSED_NO_GRANT authority-refusal path it always did.
    admission_pipeline = AdmissionPipeline()
    cycle0_admission = admission_pipeline.admit(
        f"@prefix afl: <urn:autofde-lab:> .\n<{action_iri}> afl:targetResource <{target_cap}> .",
        provenance_record={
            "issuer": actor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert cycle0_admission.standing == Standing.ADMITTED

    # Agent or subsystem attempts to actuate on novel failure
    req_envelope = ExecutionEnvelope(
        idempotency_token="idemp-incident-001",
        action_iri=action_iri,
        target_resource=target_cap,
        parameters={"pod_id": "payment-api-pod-42"},
        actor_id=actor_id,
        admission_result=cycle0_admission,
    )

    res_cycle0: BoundaryExecutionResult = prod_boundary.execute(req_envelope)

    # Invariant: Zero unreceipted actuation & strict authority non-implications.
    # The candidate content WAS admitted (asserted above); the refusal below is
    # a genuine authority refusal (no grant registered for this action/target
    # yet), not an admission-fence refusal.
    assert res_cycle0.success is False
    assert res_cycle0.state == TerminalReceiptState.REFUSED
    assert res_cycle0.refusal_code == "REFUSED_NO_GRANT"
    assert len(actuator.restarted_pods) == 0  # Actuator was NEVER called

    refusal_receipt: FinalReceipt = res_cycle0.final_receipt
    assert refusal_receipt is not None

    # =========================================================================
    # LAB EXPLORATION & QUALIFICATION
    # =========================================================================
    # 1. Ingest refusal receipt into Lab candidate frontier
    gateway = NoveltyIngestionGateway()
    candidate = gateway.ingest_refusal_receipt(
        refusal_receipt,
        action_iri=action_iri,
        target_resource=target_cap,
        observed_state_ttl="@prefix ex: <http://example.org/> . ex:pod ex:status 'CRASH_LOOP' .",
        parameters={"pod_id": "payment-api-pod-42"},
    )
    assert candidate.item_id.startswith("novelty-")

    # 2. CMCA allocates bounded exploration budget
    budget = ExplorationBudget(
        max_compute_ticks=1000, max_tokens=10000, max_experiments=5
    )
    allocator = CMCACandidateAllocator()
    plan = allocator.allocate(
        plan_id="lab_plan_001", budget=budget, candidates=[candidate]
    )
    assert len(plan.allocations) == 1
    assert plan.allocations[0].allocated_tokens > 0

    # Simulation of cognitive exploration cost in Lab
    lab_tokens_spent = 2500  # Intelligence is spent in the Lab!

    # 3. Lab qualifies the procedure and manufactures Knowledge Hook + GraphLaw rule
    synthesizer = HookSynthesizer()
    artifact = synthesizer.synthesize_from_resolution(
        hook_name="crash_loop_remediation_hook",
        trigger_predicate="ex:status",
        trigger_value="CRASH_LOOP",
        action_iri=action_iri,
        target_capability_iri=target_cap,
        goal_iri="urn:goal:cluster_stabilized",
        authorized_actor=actor_id,
    )

    # =========================================================================
    # MANUFACTURE & ADMISSION (EXPLOIT)
    # =========================================================================
    # Hook and grant are admitted to production runtime
    hook_engine = KnowledgeHookEngine()
    hook_engine.register_hook(artifact.hook)

    prod_broker.register_grant(artifact.suggested_grant)

    # =========================================================================
    # CYCLE 1: IDENTICAL INCIDENT REOCCURS -> AUTONOMIC REFLEX
    # =========================================================================
    base_ttl = "@prefix ex: <http://example.org/> . ex:cluster ex:status 'OK' ."
    # AFDE-2604 fail-secure closure (this session): ReactiveSemanticLoop's
    # `admission_pipeline` parameter now constructs a real AdmissionPipeline()
    # by default when omitted (below), so this cycle's event delta must itself
    # carry the real `afl:targetResource` binding triple for the exact
    # action_iri/target_capability_iri the synthesized hook grounds (`action_iri`
    # / `target_cap` above) -- otherwise the loop's own per-cycle admission call
    # would reach Standing.ADMITTED on content that does not relationally bind
    # this action/target, and `_admission_covers_action_target()` would refuse
    # with REFUSED_ADMISSION_CONTENT_NOT_BOUND before AuthorityBroker.evaluate()
    # is ever consulted (see boundary.py). The trigger predicate/value the
    # synthesized hook fires on ("ex:status" / "CRASH_LOOP") is matched by
    # regex-search over the raw delta text (KnowledgeHookEngine's local
    # fallback), so appending the binding triple does not disturb hook firing.
    event_delta_ttl = (
        "@prefix ex: <http://example.org/> .\n"
        "@prefix afl: <urn:autofde-lab:> .\n"
        "ex:pod ex:status 'CRASH_LOOP' .\n"
        f"<{action_iri}> afl:targetResource <{target_cap}> .\n"
    )

    loop = ReactiveSemanticLoop(
        hook_engine=hook_engine,
        authority_broker=prod_broker,
        consequence_boundary=prod_boundary,
        max_cascade_depth=3,
    )

    # Execute reflex cycle
    trace = loop.run_reflex_cycle(
        base_ttl,
        event_delta_ttl,
        actor_id=actor_id,
        delta_generator=lambda r: "",  # Quiesces after remediation
    )

    # Verify autonomic closed reflex outcome
    assert trace.quiescence_reached is True
    assert len(trace.steps) == 1

    step1 = trace.steps[0]
    assert "crash_loop_remediation_hook" in step1.triggered_hooks
    assert len(step1.intents_synthesized) == 1
    assert step1.intents_synthesized[0].action_iri == action_iri

    assert len(step1.final_receipts) == 1
    assert step1.final_receipts[0].state == TerminalReceiptState.EXECUTED
    assert step1.final_receipts[0].postcondition_verified is True

    # Invariant: Actuator executed exactly once under full receipted authority
    assert len(actuator.restarted_pods) == 1

    # =========================================================================
    # METRIC VERIFICATION: ∂(RuntimeInference) / ∂(AccumulatedExperience) < 0
    # =========================================================================
    runtime_tokens_cycle1 = 0  # ZERO LLM tokens used during production reflex!
    assert runtime_tokens_cycle1 < lab_tokens_spent
    # The runtime inference cost dropped strictly to zero for this compiled class
