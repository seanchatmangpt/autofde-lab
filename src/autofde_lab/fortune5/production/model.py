"""Typed model for the Fortune-5 Semantic A2A production-system simulator.

This package is a deterministic simulation and evidence court.  It does not
control real infrastructure and it does not manufacture enterprise standing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}:{digest(list(parts))[:24]}"


@dataclass(frozen=True, slots=True)
class RegionSpec:
    region_id: str
    cloud: str
    failure_domain: str
    capacity_multiplier: float = 1.0

    def canonical(self) -> dict[str, object]:
        return {
            "region_id": self.region_id,
            "cloud": self.cloud,
            "failure_domain": self.failure_domain,
            "capacity_multiplier": self.capacity_multiplier,
        }


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    service_id: str
    name: str
    region_id: str
    layer: str
    criticality: str
    dependencies: tuple[str, ...]
    min_replicas: int
    max_replicas: int
    capacity_rps_per_replica: float
    base_latency_ms: float
    base_error_rate: float
    cost_per_replica_round: float
    energy_kwh_per_replica_round: float
    data_class: str = "internal"

    def __post_init__(self) -> None:
        if self.min_replicas < 1 or self.max_replicas < self.min_replicas:
            raise ValueError(f"REFUSED:INVALID_REPLICA_RANGE:{self.service_id}")
        if self.capacity_rps_per_replica <= 0:
            raise ValueError(f"REFUSED:INVALID_CAPACITY:{self.service_id}")
        if self.base_latency_ms <= 0:
            raise ValueError(f"REFUSED:INVALID_LATENCY:{self.service_id}")
        if not 0 <= self.base_error_rate < 1:
            raise ValueError(f"REFUSED:INVALID_ERROR_RATE:{self.service_id}")

    def canonical(self) -> dict[str, object]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "region_id": self.region_id,
            "layer": self.layer,
            "criticality": self.criticality,
            "dependencies": list(self.dependencies),
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "capacity_rps_per_replica": self.capacity_rps_per_replica,
            "base_latency_ms": self.base_latency_ms,
            "base_error_rate": self.base_error_rate,
            "cost_per_replica_round": self.cost_per_replica_round,
            "energy_kwh_per_replica_round": self.energy_kwh_per_replica_round,
            "data_class": self.data_class,
        }


@dataclass(frozen=True, slots=True)
class SLOSpec:
    service_id: str
    availability_target: float
    latency_p95_ms: float
    error_rate_max: float

    def canonical(self) -> dict[str, object]:
        return {
            "service_id": self.service_id,
            "availability_target": self.availability_target,
            "latency_p95_ms": self.latency_p95_ms,
            "error_rate_max": self.error_rate_max,
        }


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    actor_role: str
    actions: tuple[str, ...]
    subject_layer: str
    max_risk: float
    max_change_units_per_round: int

    def canonical(self) -> dict[str, object]:
        return {
            "grant_id": self.grant_id,
            "actor_role": self.actor_role,
            "actions": list(self.actions),
            "subject_layer": self.subject_layer,
            "max_risk": self.max_risk,
            "max_change_units_per_round": self.max_change_units_per_round,
        }


@dataclass(frozen=True, slots=True)
class FaultEvent:
    fault_id: str
    round_index: int
    target_service: str
    kind: str
    severity: float
    duration_rounds: int

    def __post_init__(self) -> None:
        if self.round_index < 0 or self.duration_rounds < 1:
            raise ValueError("REFUSED:INVALID_FAULT_TIME")
        if not 0 < self.severity <= 1:
            raise ValueError("REFUSED:INVALID_FAULT_SEVERITY")

    @property
    def ends_after_round(self) -> int:
        return self.round_index + self.duration_rounds - 1

    def canonical(self) -> dict[str, object]:
        return {
            "fault_id": self.fault_id,
            "round_index": self.round_index,
            "target_service": self.target_service,
            "kind": self.kind,
            "severity": self.severity,
            "duration_rounds": self.duration_rounds,
        }


@dataclass(frozen=True, slots=True)
class WorldSpec:
    seed: int
    scenario_id: str
    ontology_version: str
    scale_profile: str
    regions: tuple[RegionSpec, ...]
    services: tuple[ServiceSpec, ...]
    slos: tuple[SLOSpec, ...]
    authority_grants: tuple[AuthorityGrant, ...]
    faults: tuple[FaultEvent, ...]
    base_traffic_rps: float
    cost_budget_per_round: float
    energy_budget_kwh_per_round: float
    carbon_budget_kg_per_round: float
    scenario_choices: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        region_ids = {r.region_id for r in self.regions}
        service_ids = [s.service_id for s in self.services]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("REFUSED:DUPLICATE_SERVICE_ID")
        known_services = set(service_ids)
        for service in self.services:
            if service.region_id not in region_ids:
                raise ValueError(f"REFUSED:UNKNOWN_REGION:{service.service_id}")
            unknown = set(service.dependencies) - known_services
            if unknown:
                raise ValueError(
                    f"REFUSED:UNKNOWN_SERVICE_DEPENDENCY:{service.service_id}:{','.join(sorted(unknown))}"
                )
        if {s.service_id for s in self.slos} != known_services:
            raise ValueError("REFUSED:SLO_SERVICE_SET_MISMATCH")
        for fault in self.faults:
            if fault.target_service not in known_services:
                raise ValueError(f"REFUSED:FAULT_TARGET_UNKNOWN:{fault.target_service}")
        if (
            min(
                self.base_traffic_rps,
                self.cost_budget_per_round,
                self.energy_budget_kwh_per_round,
                self.carbon_budget_kg_per_round,
            )
            <= 0
        ):
            raise ValueError("REFUSED:INVALID_WORLD_BUDGET")

    @property
    def canonical(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "scenario_id": self.scenario_id,
            "ontology_version": self.ontology_version,
            "scale_profile": self.scale_profile,
            "regions": [r.canonical() for r in self.regions],
            "services": [s.canonical() for s in self.services],
            "slos": [s.canonical() for s in self.slos],
            "authority_grants": [g.canonical() for g in self.authority_grants],
            "faults": [f.canonical() for f in self.faults],
            "base_traffic_rps": self.base_traffic_rps,
            "cost_budget_per_round": self.cost_budget_per_round,
            "energy_budget_kwh_per_round": self.energy_budget_kwh_per_round,
            "carbon_budget_kg_per_round": self.carbon_budget_kg_per_round,
            "scenario_choices": [list(item) for item in self.scenario_choices],
        }

    @property
    def world_digest(self) -> str:
        return digest(self.canonical)


@dataclass(slots=True)
class ServiceState:
    service_id: str
    replicas: int
    version: int = 1
    load_factor: float = 1.0
    latency_ms: float = 0.0
    error_rate: float = 0.0
    availability: float = 1.0
    queue_depth: float = 0.0
    active_fault_ids: set[str] = field(default_factory=set)
    cleared_fault_ids: set[str] = field(default_factory=set)
    last_action: str | None = None

    def canonical(self) -> dict[str, object]:
        return {
            "service_id": self.service_id,
            "replicas": self.replicas,
            "version": self.version,
            "load_factor": round(self.load_factor, 9),
            "latency_ms": round(self.latency_ms, 9),
            "error_rate": round(self.error_rate, 9),
            "availability": round(self.availability, 9),
            "queue_depth": round(self.queue_depth, 9),
            "active_fault_ids": sorted(self.active_fault_ids),
            "cleared_fault_ids": sorted(self.cleared_fault_ids),
            "last_action": self.last_action,
        }


@dataclass(frozen=True, slots=True)
class SemanticMessage:
    message_id: str
    sender_id: str
    sender_role: str
    target_service: str
    intent: str
    fault_kind: str
    breach_kind: str
    parameters: tuple[tuple[str, str], ...]
    ontology_version: str
    observed_world_digest: str

    def canonical(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "target_service": self.target_service,
            "intent": self.intent,
            "fault_kind": self.fault_kind,
            "breach_kind": self.breach_kind,
            "parameters": [list(p) for p in self.parameters],
            "ontology_version": self.ontology_version,
            "observed_world_digest": self.observed_world_digest,
        }


@dataclass(frozen=True, slots=True)
class Command:
    command_id: str
    message_id: str
    actor_id: str
    actor_role: str
    action: str
    target_service: str
    parameters: tuple[tuple[str, str], ...]
    risk: float
    route_id: str
    source: str

    def canonical(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "message_id": self.message_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "action": self.action,
            "target_service": self.target_service,
            "parameters": [list(p) for p in self.parameters],
            "risk": self.risk,
            "route_id": self.route_id,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class PreparedReceipt:
    receipt_id: str
    command_id: str
    authority_grant_id: str
    target_service: str
    pre_state_digest: str
    prepared_at_ns: int

    def canonical(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "command_id": self.command_id,
            "authority_grant_id": self.authority_grant_id,
            "target_service": self.target_service,
            "pre_state_digest": self.pre_state_digest,
            "prepared_at_ns": self.prepared_at_ns,
        }


@dataclass(frozen=True, slots=True)
class FinalReceipt:
    receipt_id: str
    prepared_receipt_id: str
    command_id: str
    target_service: str
    success: bool
    postcondition_verified: bool
    pre_state_digest: str
    post_state_digest: str
    consequence: tuple[tuple[str, str], ...]
    finalized_at_ns: int

    def canonical(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "prepared_receipt_id": self.prepared_receipt_id,
            "command_id": self.command_id,
            "target_service": self.target_service,
            "success": self.success,
            "postcondition_verified": self.postcondition_verified,
            "pre_state_digest": self.pre_state_digest,
            "post_state_digest": self.post_state_digest,
            "consequence": [list(p) for p in self.consequence],
            "finalized_at_ns": self.finalized_at_ns,
        }


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_id: str
    event_type: str
    round_index: int
    timestamp_ns: int
    actor_id: str
    subject_id: str
    attributes: tuple[tuple[str, Any], ...]
    object_refs: tuple[tuple[str, str], ...]

    def canonical(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "round_index": self.round_index,
            "timestamp_ns": self.timestamp_ns,
            "actor_id": self.actor_id,
            "subject_id": self.subject_id,
            "attributes": [[k, v] for k, v in self.attributes],
            "object_refs": [list(p) for p in self.object_refs],
        }


@dataclass(frozen=True, slots=True)
class TelemetrySpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: tuple[tuple[str, Any], ...]

    def canonical(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time_unix_nano": self.start_time_unix_nano,
            "end_time_unix_nano": self.end_time_unix_nano,
            "attributes": [[k, v] for k, v in self.attributes],
        }


@dataclass(frozen=True, slots=True)
class KnownRoute:
    route_id: str
    signature: str
    action: str
    actor_role: str
    qualification_receipt_id: str
    successful_replays: int = 0

    def canonical(self) -> dict[str, object]:
        return {
            "route_id": self.route_id,
            "signature": self.signature,
            "action": self.action,
            "actor_role": self.actor_role,
            "qualification_receipt_id": self.qualification_receipt_id,
            "successful_replays": self.successful_replays,
        }


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    run_id: str
    world_digest: str
    rounds: int
    events: int
    actuations: int
    final_receipts: int
    refused_authority: int
    frontier_invocations: int
    known_route_hits: int
    known_routes: int
    slo_breaches: int
    unreconciled_actuations: int
    authority_violations: int
    duplicate_effects: int
    replay_digest: str
    ocel_digest: str
    readiness_standing: str
    cost_budget_violations: int
    energy_budget_violations: int
    carbon_budget_violations: int

    def canonical(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


__all__ = [
    "AuthorityGrant",
    "Command",
    "EventRecord",
    "FaultEvent",
    "FinalReceipt",
    "KnownRoute",
    "PreparedReceipt",
    "RegionSpec",
    "SLOSpec",
    "SemanticMessage",
    "ServiceSpec",
    "ServiceState",
    "SimulationSummary",
    "TelemetrySpan",
    "WorldSpec",
    "canonical_json",
    "digest",
    "stable_id",
]
