"""Cross-court adapter through the repository's real Semantic A2A core.

This module proves that a Fortune-5 simulation consequence can traverse the
actual admission -> construction -> AuthorityBroker -> ConsequenceBoundary ->
PreparedReceipt -> DO -> postcondition -> FinalReceipt pipeline.  It is a
simulation adapter only: the actuator mutates an in-memory state cell, never
real infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline, AdmissionResult
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant as CoreAuthorityGrant,
)
from autofde_lab.sa2a.brce.boundary import (
    BoundaryExecutionResult,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import ReceiptStore, TerminalReceiptState
from autofde_lab.sa2a.construct.constructor import (
    AdmittedSemantics,
    ArtifactManufacturer,
    TargetProfile,
)

from .model import Command, ServiceSpec, digest


_TARGET_PREDICATE = "urn:autofde-lab:targetResource"
_ACTION_PREFIX = "urn:autofde-lab:fortune5:action:"
_TARGET_PREFIX = "urn:autofde-lab:fortune5:service:"


def action_iri(action: str) -> str:
    return _ACTION_PREFIX + quote(action, safe="")


def target_iri(service_id: str) -> str:
    return _TARGET_PREFIX + quote(service_id, safe="")


@dataclass(slots=True)
class SimulationStateCell:
    """Minimal mutable consequence target for the real BRCE adapter."""

    service: ServiceSpec
    replicas: int
    version: int = 1
    restart_count: int = 0
    load_factor: float = 1.0
    failover_count: int = 0
    repair_count: int = 0
    last_action: str | None = None

    def canonical(self) -> dict[str, object]:
        return {
            "service_id": self.service.service_id,
            "replicas": self.replicas,
            "version": self.version,
            "restart_count": self.restart_count,
            "load_factor": round(self.load_factor, 9),
            "failover_count": self.failover_count,
            "repair_count": self.repair_count,
            "last_action": self.last_action,
        }

    @property
    def state_digest(self) -> str:
        return digest(self.canonical())


class SimulationConsequenceActuator:
    """Real ConsequenceBoundary actuator backed only by an in-memory state cell."""

    def __init__(self, cell: SimulationStateCell) -> None:
        self.cell = cell
        self.call_count = 0

    def actuator_digest(self) -> str:
        return digest({"kind": "fortune5-simulation-actuator", "version": "v26.9.18"})

    def actuate(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        expected_target = target_iri(self.cell.service.service_id)
        if target_resource != expected_target:
            raise ValueError("REFUSED:SIMULATOR_TARGET_IDENTITY_MISMATCH")
        if not action_iri.startswith(_ACTION_PREFIX):
            raise ValueError("REFUSED:SIMULATOR_ACTION_NAMESPACE")
        action = action_iri.removeprefix(_ACTION_PREFIX)
        pre = self.cell.state_digest
        self.call_count += 1
        if action == "scale_out":
            delta = max(1, int(parameters.get("replicas", 1)))
            self.cell.replicas = min(
                self.cell.service.max_replicas, self.cell.replicas + delta
            )
        elif action == "restart":
            self.cell.restart_count += 1
        elif action == "rollback":
            self.cell.version = max(1, self.cell.version - 1)
        elif action == "failover":
            self.cell.failover_count += 1
            self.cell.load_factor = max(0.2, self.cell.load_factor * 0.5)
        elif action == "shed_load":
            fraction = min(0.8, max(0.05, float(parameters.get("fraction", 0.20))))
            self.cell.load_factor = max(0.2, self.cell.load_factor * (1.0 - fraction))
        elif action == "repair_dependency":
            self.cell.repair_count += 1
        else:
            raise ValueError(f"REFUSED:UNSUPPORTED_SIMULATED_ACTION:{action}")
        self.cell.last_action = action
        post = self.cell.state_digest
        return {
            "simulation_only": True,
            "action": action,
            "target_resource": target_resource,
            "pre_state_digest": pre,
            "post_state_digest": post,
            "call_count": self.call_count,
        }


class SimulationPostconditionVerifier:
    """Independent BRCE postcondition verifier reading the state cell afresh."""

    def __init__(self, cell: SimulationStateCell) -> None:
        self.cell = cell

    def verifier_digest(self) -> str:
        return digest({"kind": "fortune5-simulation-verifier", "version": "v26.9.18"})

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Mapping[str, Any] | None,
    ) -> bool:
        if evidence is None:
            return False
        if target_resource != target_iri(self.cell.service.service_id):
            return False
        return (
            bool(evidence.get("simulation_only"))
            and evidence.get("target_resource") == target_resource
            and evidence.get("post_state_digest") == self.cell.state_digest
            and evidence.get("pre_state_digest") != evidence.get("post_state_digest")
        )


@dataclass(frozen=True, slots=True)
class NativeSA2AExecution:
    admission: AdmissionResult
    result: BoundaryExecutionResult
    replay: BoundaryExecutionResult
    actuator_calls: int
    cell_state_digest: str


def _candidate_turtle(action: str, target: str) -> str:
    return (
        f"<{action}> <{_TARGET_PREDICATE}> <{target}> .\n"
        f"<{action}> <urn:autofde-lab:fortune5:kind> "
        f"<urn:autofde-lab:fortune5:Consequence> .\n"
    )


def _admitted_semantics(admission: AdmissionResult) -> AdmittedSemantics:
    if not admission.is_admitted or not admission.canonical_ntriples:
        raise ValueError("REFUSED:NATIVE_SA2A_REQUIRES_ADMITTED_SEMANTICS")
    triples = tuple(
        line.strip()
        for line in admission.canonical_ntriples.splitlines()
        if line.strip()
    )
    return AdmittedSemantics(
        ontology_id="urn:autofde-lab:fortune5:production-simulation",
        canonical_triples=triples,
        semantic_version="v26.9.18",
        provenance_hash=admission.receipt.receipt_hash,
        metadata=(("simulation", "true"),),
    )


def execute_command_through_native_sa2a(
    command: Command,
    service: ServiceSpec,
) -> NativeSA2AExecution:
    """Execute one simulated command through the real SA2A admission/BRCE stack.

    The same envelope is immediately replayed to prove idempotency: the second
    call must return the cached FinalReceipt without a second actuator call.
    """
    action = action_iri(command.action)
    target = target_iri(service.service_id)
    admission = AdmissionPipeline().admit(
        _candidate_turtle(action, target),
        format="turtle",
        provenance_record={
            "issuer": "fortune5-production-simulation",
            "timestamp": "2026-09-18T00:00:00Z",
        },
    )
    if not admission.is_admitted:
        raise ValueError(
            f"REFUSED:NATIVE_SA2A_ADMISSION:{admission.refusal_code}:{admission.reasons}"
        )

    semantics = _admitted_semantics(admission)
    artifact = ArtifactManufacturer(
        manufacturer_identity="urn:autofde-lab:fortune5:simulation-manufacturer",
        manufacturer_version="26.9.18",
    ).manufacture(semantics, TargetProfile.PYTHON_EPHEMERAL)

    grant_id = f"grant:{command.command_id}"
    broker = AuthorityBroker(
        grants=[
            CoreAuthorityGrant(
                grant_id=grant_id,
                subject_id=command.actor_id,
                action_iri=action,
                target_resource_iri=target,
                issuer_id="urn:autofde-lab:fortune5:simulation-authority",
            )
        ]
    )
    cell = SimulationStateCell(service=service, replicas=service.min_replicas)
    actuator = SimulationConsequenceActuator(cell)
    verifier = SimulationPostconditionVerifier(cell)
    store = ReceiptStore(authority_broker=broker)
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
        require_admission=True,
    )
    envelope = ExecutionEnvelope(
        idempotency_token=command.command_id,
        action_iri=action,
        target_resource=target,
        actor_id=command.actor_id,
        parameters=dict(command.parameters),
        consequence_class="FORTUNE5_SIMULATION_EFFECT",
        grant_id=grant_id,
        plan_digest=digest(
            {
                "route_id": command.route_id,
                "message_id": command.message_id,
                "source": command.source,
            }
        ),
        artifact=artifact,
        construction_receipt=artifact.receipt,
        admitted_semantics=semantics,
        admission_result=admission,
    )
    result = boundary.execute_admitted(envelope)
    if result.state != TerminalReceiptState.EXECUTED:
        raise ValueError(
            f"REFUSED:NATIVE_SA2A_EXECUTION:{result.refusal_code}:{result.reason}"
        )
    replay = boundary.execute_admitted(envelope)
    return NativeSA2AExecution(
        admission=admission,
        result=result,
        replay=replay,
        actuator_calls=actuator.call_count,
        cell_state_digest=cell.state_digest,
    )


def prove_unbound_admission_refuses(
    command: Command,
    service: ServiceSpec,
) -> BoundaryExecutionResult:
    """Admit unrelated content and prove the strict BRCE gate refuses before DO."""
    action = action_iri(command.action)
    target = target_iri(service.service_id)
    unrelated_target = target_iri(service.service_id + ":other")
    admission = AdmissionPipeline().admit(
        _candidate_turtle(action, unrelated_target),
        format="turtle",
        provenance_record={
            "issuer": "fortune5-production-simulation",
            "timestamp": "2026-09-18T00:00:00Z",
        },
    )
    broker = AuthorityBroker(
        grants=[
            CoreAuthorityGrant(
                grant_id=f"grant:{command.command_id}:negative",
                subject_id=command.actor_id,
                action_iri=action,
                target_resource_iri=target,
            )
        ]
    )
    cell = SimulationStateCell(service=service, replicas=service.min_replicas)
    actuator = SimulationConsequenceActuator(cell)
    verifier = SimulationPostconditionVerifier(cell)
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=ReceiptStore(),
        require_admission=True,
    )
    result = boundary.execute_admitted(
        ExecutionEnvelope(
            idempotency_token=command.command_id + ":negative",
            action_iri=action,
            target_resource=target,
            actor_id=command.actor_id,
            grant_id=f"grant:{command.command_id}:negative",
            admission_result=admission,
        )
    )
    if actuator.call_count:
        raise AssertionError("native SA2A strict gate allowed unbound admission to reach DO")
    return result


__all__ = [
    "NativeSA2AExecution",
    "SimulationConsequenceActuator",
    "SimulationPostconditionVerifier",
    "SimulationStateCell",
    "action_iri",
    "execute_command_through_native_sa2a",
    "prove_unbound_admission_refuses",
    "target_iri",
]
