"""Deterministic Fortune-5 production-world generator G(seed, theta) -> W."""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Mapping, Sequence

from .model import (
    AuthorityGrant,
    FaultEvent,
    RegionSpec,
    SLOSpec,
    ServiceSpec,
    WorldSpec,
    stable_id,
)

SCALE_PROFILES: dict[str, tuple[int, int]] = {
    "demo": (2, 8),
    "enterprise": (3, 16),
    "fortune5": (6, 24),
}

CLOUDS = ("aws", "azure", "gcp")
FAULT_KINDS = (
    "config_drift",
    "dependency_latency",
    "dns",
    "rbac",
    "secret",
    "network_policy",
    "quota",
    "oom",
    "cpu_throttle",
    "crash_loop",
    "cert",
    "backpressure",
    "node_pressure",
    "zone_loss",
    "schema",
)

SERVICE_TEMPLATES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("edge-gateway", "edge", "mission-critical", ()),
    ("identity", "identity", "mission-critical", ()),
    ("catalog-api", "application", "high", ("identity",)),
    ("orders-api", "application", "mission-critical", ("identity", "catalog-api")),
    ("payments-api", "application", "mission-critical", ("identity",)),
    ("event-bus", "event", "mission-critical", ()),
    ("fulfillment-worker", "worker", "high", ("event-bus",)),
    ("inventory-api", "application", "high", ("identity", "event-bus")),
    ("inventory-db", "data", "mission-critical", ()),
    ("orders-db", "data", "mission-critical", ()),
    ("payments-db", "data", "mission-critical", ()),
    ("cache", "cache", "high", ()),
    ("search", "search", "high", ("catalog-api",)),
    ("object-store", "data", "high", ()),
    ("stream-processor", "stream", "high", ("event-bus",)),
    ("feature-store", "ml-data", "high", ("stream-processor",)),
    ("inference-gateway", "ai", "high", ("feature-store",)),
    ("agent-runtime", "agent", "high", ("inference-gateway",)),
    ("policy-control", "control", "mission-critical", ("identity",)),
    ("observability", "observability", "mission-critical", ("event-bus",)),
    ("release-control", "control", "high", ("policy-control",)),
    ("finops", "governance", "medium", ("observability",)),
    ("security-analytics", "security", "high", ("observability", "identity")),
    ("dr-orchestrator", "resilience", "mission-critical", ("observability",)),
)

LAYER_DEFAULTS: dict[str, tuple[float, float, float, int, int, float, float]] = {
    "edge": (2500.0, 8.0, 0.0005, 4, 64, 4.0, 0.7),
    "identity": (1600.0, 12.0, 0.0008, 3, 48, 4.5, 0.8),
    "application": (1200.0, 24.0, 0.0010, 3, 64, 5.0, 1.0),
    "event": (3000.0, 10.0, 0.0005, 3, 48, 6.0, 1.2),
    "worker": (900.0, 40.0, 0.0015, 2, 64, 4.0, 1.0),
    "data": (1800.0, 6.0, 0.0003, 3, 32, 9.0, 2.0),
    "cache": (5000.0, 2.0, 0.0002, 3, 48, 3.0, 0.6),
    "search": (1200.0, 35.0, 0.0010, 3, 48, 7.0, 1.4),
    "stream": (2200.0, 18.0, 0.0008, 3, 48, 6.0, 1.3),
    "ml-data": (900.0, 30.0, 0.0010, 2, 32, 7.0, 1.5),
    "ai": (400.0, 90.0, 0.0020, 2, 32, 15.0, 3.5),
    "agent": (300.0, 120.0, 0.0025, 2, 32, 10.0, 2.0),
    "control": (1000.0, 15.0, 0.0005, 3, 24, 5.0, 1.0),
    "observability": (2500.0, 20.0, 0.0005, 3, 48, 6.0, 1.2),
    "governance": (600.0, 30.0, 0.0010, 2, 16, 3.0, 0.7),
    "security": (1000.0, 25.0, 0.0006, 3, 32, 7.0, 1.4),
    "resilience": (800.0, 20.0, 0.0005, 3, 24, 6.0, 1.2),
}

ACTION_SET = (
    "scale_out",
    "restart",
    "rollback",
    "failover",
    "shed_load",
    "repair_dependency",
)


def _service_id(region_id: str, name: str) -> str:
    return f"{region_id}:{name}"


def _resolve_dependencies(region_id: str, dependency_names: Sequence[str]) -> tuple[str, ...]:
    return tuple(_service_id(region_id, name) for name in dependency_names)


def generate_world(
    *,
    seed: int,
    scale_profile: str = "fortune5",
    scenario_choices: Mapping[str, str] | None = None,
    ontology_version: str = "urn:autofde-lab:sa2a:v26.9.18",
    fault_density: float = 0.12,
    horizon_rounds: int = 40,
) -> WorldSpec:
    """Generate a deterministic, multi-cloud full-stack enterprise world."""
    if scale_profile not in SCALE_PROFILES:
        raise ValueError(f"REFUSED:UNKNOWN_SCALE_PROFILE:{scale_profile}")
    if not 0 <= fault_density <= 1:
        raise ValueError("REFUSED:INVALID_FAULT_DENSITY")
    if horizon_rounds < 1:
        raise ValueError("REFUSED:INVALID_HORIZON")

    rng = random.Random(seed)
    region_count, template_count = SCALE_PROFILES[scale_profile]
    scenario = dict(scenario_choices or {})
    cloud_bias = scenario.get("cloud")

    regions: list[RegionSpec] = []
    for index in range(region_count):
        cloud = cloud_bias if cloud_bias in CLOUDS else CLOUDS[index % len(CLOUDS)]
        regions.append(
            RegionSpec(
                region_id=f"{cloud}-{index + 1}",
                cloud=cloud,
                failure_domain=f"{cloud}:fd:{index + 1}",
                capacity_multiplier=round(0.9 + rng.random() * 0.25, 6),
            )
        )

    selected_templates = SERVICE_TEMPLATES[:template_count]
    services: list[ServiceSpec] = []
    slos: list[SLOSpec] = []
    data_class = scenario.get("data_class", "internal")
    for region in regions:
        for name, layer, criticality, deps in selected_templates:
            defaults = LAYER_DEFAULTS[layer]
            capacity, latency, error, min_rep, max_rep, cost, energy = defaults
            capacity *= region.capacity_multiplier * (0.92 + rng.random() * 0.16)
            latency *= 0.90 + rng.random() * 0.20
            service = ServiceSpec(
                service_id=_service_id(region.region_id, name),
                name=name,
                region_id=region.region_id,
                layer=layer,
                criticality=criticality,
                dependencies=_resolve_dependencies(region.region_id, deps),
                min_replicas=min_rep,
                max_replicas=max_rep,
                capacity_rps_per_replica=round(capacity, 6),
                base_latency_ms=round(latency, 6),
                base_error_rate=error,
                cost_per_replica_round=cost,
                energy_kwh_per_replica_round=energy,
                data_class=data_class,
            )
            services.append(service)
            mission = criticality == "mission-critical"
            slos.append(
                SLOSpec(
                    service_id=service.service_id,
                    availability_target=0.999 if mission else 0.995,
                    latency_p95_ms=round(service.base_latency_ms * (2.4 if mission else 3.0), 6),
                    error_rate_max=0.01 if mission else 0.02,
                )
            )

    layers = sorted({service.layer for service in services})
    grants = tuple(
        AuthorityGrant(
            grant_id=stable_id("grant", "sre", layer, ACTION_SET),
            actor_role="sre",
            actions=ACTION_SET,
            subject_layer=layer,
            max_risk=0.85,
            max_change_units_per_round=48,
        )
        for layer in layers
    )

    service_ids = [service.service_id for service in services]
    fault_count = max(1, round(len(service_ids) * fault_density))
    faults: list[FaultEvent] = []
    for index in range(fault_count):
        kind = FAULT_KINDS[index % len(FAULT_KINDS)]
        target = service_ids[rng.randrange(len(service_ids))]
        round_index = 2 + rng.randrange(max(1, horizon_rounds - 4))
        severity = round(0.25 + rng.random() * 0.65, 6)
        duration = 2 + rng.randrange(5)
        faults.append(
            FaultEvent(
                fault_id=stable_id("fault", seed, index, kind, target, round_index),
                round_index=round_index,
                target_service=target,
                kind=kind,
                severity=severity,
                duration_rounds=duration,
            )
        )

    if services and horizon_rounds >= 12:
        target_a = services[0].service_id
        target_b = services[template_count].service_id if len(services) > template_count else target_a
        repeated_kind = "config_drift"
        faults.extend(
            (
                FaultEvent(
                    fault_id=stable_id("fault", seed, "repeat-a", target_a),
                    round_index=3,
                    target_service=target_a,
                    kind=repeated_kind,
                    severity=0.75,
                    duration_rounds=2,
                ),
                FaultEvent(
                    fault_id=stable_id("fault", seed, "repeat-b", target_b),
                    round_index=10,
                    target_service=target_b,
                    kind=repeated_kind,
                    severity=0.75,
                    duration_rounds=2,
                ),
            )
        )

    base_traffic = 1200.0 * region_count * max(1, template_count / 8)
    min_cost = sum(s.min_replicas * s.cost_per_replica_round for s in services)
    min_energy = sum(s.min_replicas * s.energy_kwh_per_replica_round for s in services)
    min_carbon = min_energy * 0.34
    return WorldSpec(
        seed=seed,
        scenario_id=stable_id(
            "f5-world", seed, scale_profile, sorted((scenario_choices or {}).items())
        ),
        ontology_version=ontology_version,
        scale_profile=scale_profile,
        regions=tuple(regions),
        services=tuple(services),
        slos=tuple(slos),
        authority_grants=grants,
        faults=tuple(sorted(faults, key=lambda f: (f.round_index, f.fault_id))),
        base_traffic_rps=round(base_traffic, 6),
        cost_budget_per_round=round(min_cost * 1.75, 6),
        energy_budget_kwh_per_round=round(min_energy * 1.75, 6),
        carbon_budget_kg_per_round=round(min_carbon * 1.75, 6),
        scenario_choices=tuple(sorted((scenario_choices or {}).items())),
    )


def with_faults(world: WorldSpec, faults: Sequence[FaultEvent]) -> WorldSpec:
    return replace(world, faults=tuple(sorted(faults, key=lambda f: (f.round_index, f.fault_id))))


__all__ = [
    "ACTION_SET",
    "CLOUDS",
    "FAULT_KINDS",
    "SCALE_PROFILES",
    "SERVICE_TEMPLATES",
    "generate_world",
    "with_faults",
]
