"""Semantic A2A admission, routing and authority for the Fortune-5 simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import (
    AuthorityGrant,
    Command,
    KnownRoute,
    SemanticMessage,
    ServiceSpec,
    WorldSpec,
    stable_id,
)

ACTION_RISK: dict[str, float] = {
    "shed_load": 0.20,
    "scale_out": 0.30,
    "restart": 0.40,
    "repair_dependency": 0.45,
    "rollback": 0.55,
    "failover": 0.70,
}

FAULT_TO_ACTION: dict[str, str] = {
    "backpressure": "scale_out",
    "cpu_throttle": "scale_out",
    "quota": "shed_load",
    "oom": "restart",
    "crash_loop": "restart",
    "config_drift": "rollback",
    "schema": "rollback",
    "cert": "rollback",
    "zone_loss": "failover",
    "dependency_latency": "repair_dependency",
    "dns": "repair_dependency",
    "network_policy": "repair_dependency",
    "rbac": "repair_dependency",
    "secret": "repair_dependency",
    "node_pressure": "failover",
}


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    admitted: bool
    code: str
    reason: str


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    authorized: bool
    code: str
    reason: str
    grant_id: str | None


class SemanticAdmission:
    """Fail-closed semantic admission for simulation messages."""

    def __init__(self, world: WorldSpec) -> None:
        self._world = world
        self._services = {service.service_id: service for service in world.services}

    def admit(self, message: SemanticMessage, *, current_world_digest: str) -> AdmissionDecision:
        if message.ontology_version != self._world.ontology_version:
            return AdmissionDecision(False, "REFUSED:ONTOLOGY_VERSION_MISMATCH", "semantic version mismatch")
        if message.target_service not in self._services:
            return AdmissionDecision(False, "REFUSED:UNKNOWN_TARGET", "target service is not in the admitted world")
        if message.intent != "stabilize":
            return AdmissionDecision(False, "REFUSED:UNSUPPORTED_INTENT", "only stabilize is admitted")
        if not message.fault_kind:
            return AdmissionDecision(False, "REFUSED:MISSING_FAULT_KIND", "fault kind is required")
        if message.observed_world_digest != current_world_digest:
            return AdmissionDecision(False, "REFUSED:STALE_WORLD_IDENTITY", "message was observed against another world state")
        return AdmissionDecision(True, "ADMITTED", "semantic message admitted")


class KnownRouteRegistry:
    """Deterministic UNKNOWN -> KNOWN route registry."""

    def __init__(self) -> None:
        self._routes: dict[str, KnownRoute] = {}

    @staticmethod
    def signature(message: SemanticMessage, service: ServiceSpec) -> str:
        return "|".join((message.fault_kind, message.breach_kind, service.layer))

    def lookup(self, signature: str) -> KnownRoute | None:
        return self._routes.get(signature)

    def qualify(
        self,
        *,
        signature: str,
        action: str,
        actor_role: str,
        qualification_receipt_id: str,
    ) -> KnownRoute:
        existing = self._routes.get(signature)
        if existing is not None:
            return existing
        route = KnownRoute(
            route_id=stable_id("route", signature, action, qualification_receipt_id),
            signature=signature,
            action=action,
            actor_role=actor_role,
            qualification_receipt_id=qualification_receipt_id,
            successful_replays=0,
        )
        self._routes[signature] = route
        return route

    def record_successful_replay(self, signature: str) -> KnownRoute:
        route = self._routes[signature]
        updated = KnownRoute(
            route_id=route.route_id,
            signature=route.signature,
            action=route.action,
            actor_role=route.actor_role,
            qualification_receipt_id=route.qualification_receipt_id,
            successful_replays=route.successful_replays + 1,
        )
        self._routes[signature] = updated
        return updated

    @property
    def routes(self) -> tuple[KnownRoute, ...]:
        return tuple(self._routes[key] for key in sorted(self._routes))


class FrontierPlanner:
    """Bounded heuristic used only for previously UNKNOWN semantic classes."""

    def choose(self, message: SemanticMessage, service: ServiceSpec) -> tuple[str, tuple[tuple[str, str], ...]]:
        action = FAULT_TO_ACTION.get(message.fault_kind, "shed_load")
        if action == "scale_out":
            params = (("replicas", "2"),)
        elif action == "shed_load":
            params = (("fraction", "0.20"),)
        elif action == "failover":
            params = (("fraction", "0.50"),)
        else:
            params = ()
        return action, params


class AuthorityPolicy:
    """Explicit authority broker over world grants and per-round change budget."""

    def __init__(self, world: WorldSpec) -> None:
        self._world = world
        self._services = {service.service_id: service for service in world.services}
        self._used_units: dict[tuple[int, str], int] = {}

    def authorize(self, command: Command, *, round_index: int) -> AuthorityDecision:
        service = self._services.get(command.target_service)
        if service is None:
            return AuthorityDecision(False, "REFUSED:UNKNOWN_TARGET", "target not present", None)
        candidates: Iterable[AuthorityGrant] = (
            grant
            for grant in self._world.authority_grants
            if grant.actor_role == command.actor_role
            and grant.subject_layer == service.layer
            and command.action in grant.actions
        )
        grant = next(iter(candidates), None)
        if grant is None:
            return AuthorityDecision(False, "REFUSED:NO_GRANT", "no grant covers actor/action/layer", None)
        if command.risk > grant.max_risk:
            return AuthorityDecision(False, "REFUSED:RISK_EXCEEDS_GRANT", "risk exceeds grant envelope", grant.grant_id)
        units = _change_units(command)
        key = (round_index, grant.grant_id)
        used = self._used_units.get(key, 0)
        if used + units > grant.max_change_units_per_round:
            return AuthorityDecision(
                False,
                "REFUSED:CHANGE_BUDGET",
                f"change units {used + units} exceed grant budget {grant.max_change_units_per_round}",
                grant.grant_id,
            )
        self._used_units[key] = used + units
        return AuthorityDecision(True, "AUTHORIZED", "grant covers exact action and service layer", grant.grant_id)


def build_command(
    *,
    message: SemanticMessage,
    service: ServiceSpec,
    action: str,
    parameters: tuple[tuple[str, str], ...],
    route_id: str,
    source: str,
) -> Command:
    if action not in ACTION_RISK:
        raise ValueError(f"REFUSED:UNKNOWN_ACTION:{action}")
    actor_role = "sre"
    actor_id = f"agent:{actor_role}"
    return Command(
        command_id=stable_id(
            "cmd",
            message.message_id,
            action,
            service.service_id,
            parameters,
            route_id,
        ),
        message_id=message.message_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_service=service.service_id,
        parameters=parameters,
        risk=ACTION_RISK[action],
        route_id=route_id,
        source=source,
    )


def _change_units(command: Command) -> int:
    if command.action == "scale_out":
        params = dict(command.parameters)
        return max(1, int(params.get("replicas", "1")))
    if command.action == "failover":
        return 4
    if command.action in {"rollback", "repair_dependency"}:
        return 3
    return 1


__all__ = [
    "ACTION_RISK",
    "FAULT_TO_ACTION",
    "AdmissionDecision",
    "AuthorityDecision",
    "AuthorityPolicy",
    "FrontierPlanner",
    "KnownRouteRegistry",
    "SemanticAdmission",
    "build_command",
]
