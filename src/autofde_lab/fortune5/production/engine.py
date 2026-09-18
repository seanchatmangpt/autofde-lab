"""Execution engine for the Fortune-5 Semantic A2A production-system simulator."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from .formal import FormalProjection, generate_formal_projection, verify_projection_coherence
from .model import (
    Command, EventRecord, FaultEvent, FinalReceipt, PreparedReceipt, SemanticMessage,
    ServiceSpec, ServiceState, SimulationSummary, TelemetrySpan, WorldSpec, digest, stable_id,
)
from .protocol import (
    AuthorityPolicy, FrontierPlanner, KnownRouteRegistry, SemanticAdmission, build_command,
)


@dataclass(frozen=True, slots=True)
class SimulationRun:
    run_id: str
    world: WorldSpec
    projection: FormalProjection
    events: tuple[EventRecord, ...]
    spans: tuple[TelemetrySpan, ...]
    prepared_receipts: tuple[PreparedReceipt, ...]
    final_receipts: tuple[FinalReceipt, ...]
    known_routes: tuple[object, ...]
    summary: SimulationSummary
    final_state: tuple[tuple[str, dict[str, object]], ...]


class ProductionSimulator:
    """Deterministic full-stack simulation with semantic admission and receipted DO."""

    def __init__(self, world: WorldSpec) -> None:
        self.world = world
        self.rng = random.Random(world.seed)
        self.services = {s.service_id: s for s in world.services}
        self.slos = {s.service_id: s for s in world.slos}
        self.states = {s.service_id: ServiceState(s.service_id, s.min_replicas) for s in world.services}
        self.admission = SemanticAdmission(world)
        self.authority = AuthorityPolicy(world)
        self.routes = KnownRouteRegistry()
        self.frontier = FrontierPlanner()
        self.events: list[EventRecord] = []
        self.spans: list[TelemetrySpan] = []
        self.prepared: list[PreparedReceipt] = []
        self.final: list[FinalReceipt] = []
        self._final_by_command: dict[str, FinalReceipt] = {}
        self._sequence = 0
        self._frontier_invocations = 0
        self._known_route_hits = 0
        self._refused_authority = 0
        self._slo_breaches = 0
        self._cost_budget_violations = 0
        self._energy_budget_violations = 0
        self._carbon_budget_violations = 0
        self._projection = generate_formal_projection(world)
        ok, violations = verify_projection_coherence(self._projection)
        if not ok:
            raise ValueError("REFUSED:FORMAL_PROJECTION_INCOHERENT:" + ",".join(violations))
        self.run_id = stable_id("run", world.world_digest, "fortune5-production")

    def _now(self, round_index: int) -> int:
        self._sequence += 1
        return round_index * 1_000_000 + self._sequence

    def _emit(
        self, *, round_index: int, event_type: str, actor_id: str, subject_id: str,
        attrs: dict[str, object] | None = None,
        refs: Iterable[tuple[str, str]] = (),
        parent_event_id: str | None = None,
    ) -> EventRecord:
        ts = self._now(round_index)
        event_id = stable_id(
            "evt", self.run_id, round_index, self._sequence, event_type, actor_id, subject_id
        )
        attributes = tuple(sorted((attrs or {}).items(), key=lambda x: x[0]))
        object_refs = tuple(sorted(refs))
        event = EventRecord(
            event_id, event_type, round_index, ts, actor_id, subject_id, attributes, object_refs
        )
        self.events.append(event)
        self.spans.append(
            TelemetrySpan(
                trace_id=stable_id("trace", self.run_id, round_index),
                span_id=stable_id("span", event_id),
                parent_span_id=stable_id("span", parent_event_id) if parent_event_id else None,
                name=event_type,
                start_time_unix_nano=ts,
                end_time_unix_nano=ts + 100,
                attributes=tuple(sorted({
                    "event_id": event_id,
                    "round_index": round_index,
                    "actor_id": actor_id,
                    "subject_id": subject_id,
                    **(attrs or {}),
                }.items())),
            )
        )
        return event

    def _faults_for_round(self, round_index: int) -> tuple[FaultEvent, ...]:
        return tuple(
            f for f in self.world.faults if f.round_index <= round_index <= f.ends_after_round
        )

    def _update_states(self, round_index: int) -> None:
        active = self._faults_for_round(round_index)
        faults_by_service: dict[str, list[FaultEvent]] = {}
        for fault in active:
            faults_by_service.setdefault(fault.target_service, []).append(fault)

        traffic_wave = 0.82 + 0.28 * (1 + math.sin((round_index + self.world.seed) / 3.0))
        application_services = max(
            1,
            sum(
                s.layer in {
                    "edge", "identity", "application", "event", "worker", "data",
                    "cache", "search", "stream", "ai", "agent",
                }
                for s in self.world.services
            ),
        )
        per_service_base = self.world.base_traffic_rps / application_services

        for service_id, spec in self.services.items():
            state = self.states[service_id]
            service_faults = [
                f for f in faults_by_service.get(service_id, ())
                if f.fault_id not in state.cleared_fault_ids
            ]
            state.active_fault_ids = {f.fault_id for f in service_faults}
            load = per_service_base * traffic_wave * state.load_factor
            if spec.layer in {"data", "cache", "event", "observability"}:
                load *= 1.35
            capacity = max(1.0, state.replicas * spec.capacity_rps_per_replica)
            fault_capacity_factor = 1.0
            latency_extra = 0.0
            error_extra = 0.0
            for fault in service_faults:
                if fault.kind in {"zone_loss", "node_pressure"}:
                    fault_capacity_factor *= max(0.15, 1.0 - 0.8 * fault.severity)
                elif fault.kind in {"backpressure", "cpu_throttle", "quota"}:
                    fault_capacity_factor *= max(0.25, 1.0 - 0.6 * fault.severity)
                elif fault.kind in {"dependency_latency", "dns", "network_policy"}:
                    latency_extra += spec.base_latency_ms * (4.0 * fault.severity)
                elif fault.kind in {"config_drift", "schema", "cert", "rbac", "secret"}:
                    error_extra += 0.15 * fault.severity
                elif fault.kind in {"oom", "crash_loop"}:
                    error_extra += 0.25 * fault.severity
                    fault_capacity_factor *= max(0.3, 1.0 - 0.5 * fault.severity)

            effective_capacity = capacity * fault_capacity_factor
            utilization = load / effective_capacity
            overload = max(0.0, utilization - 0.70)
            state.queue_depth = max(0.0, state.queue_depth * 0.55 + overload * 150.0)
            dependency_penalty = 0.0
            for dep in spec.dependencies:
                dep_state = self.states[dep]
                if dep_state.availability < 0.99:
                    dependency_penalty += (
                        spec.base_latency_ms * (0.99 - dep_state.availability) * 8.0
                    )
                dependency_penalty += dep_state.queue_depth * 0.02
            state.latency_ms = (
                spec.base_latency_ms * (1.0 + overload * 5.0)
                + latency_extra + dependency_penalty
            )
            state.error_rate = min(
                0.95, spec.base_error_rate + error_extra + overload * 0.08
            )
            state.availability = max(0.0, 1.0 - state.error_rate)

    def _state_digest(self, service_id: str) -> str:
        return digest(self.states[service_id].canonical())

    def _breaches(self) -> list[tuple[ServiceSpec, str, str]]:
        breaches: list[tuple[ServiceSpec, str, str]] = []
        for service_id, spec in self.services.items():
            state = self.states[service_id]
            slo = self.slos[service_id]
            breach_kind: str | None = None
            if state.availability < slo.availability_target:
                breach_kind = "availability"
            elif state.error_rate > slo.error_rate_max:
                breach_kind = "error_rate"
            elif state.latency_ms > slo.latency_p95_ms:
                breach_kind = "latency"
            elif state.queue_depth > 25:
                breach_kind = "queue"
            if breach_kind:
                breaches.append((spec, breach_kind, self._dominant_fault(service_id)))
        return breaches

    def _dominant_fault(self, service_id: str) -> str:
        state = self.states[service_id]
        active = [f for f in self.world.faults if f.fault_id in state.active_fault_ids]
        if not active:
            return "load"
        active.sort(key=lambda f: (-f.severity, f.fault_id))
        return active[0].kind

    def _message(
        self, round_index: int, spec: ServiceSpec, breach: str, fault_kind: str
    ) -> SemanticMessage:
        return SemanticMessage(
            message_id=stable_id(
                "msg", self.run_id, round_index, spec.service_id, breach, fault_kind
            ),
            sender_id="agent:observability",
            sender_role="observability",
            target_service=spec.service_id,
            intent="stabilize",
            fault_kind=fault_kind,
            breach_kind=breach,
            parameters=(("criticality", spec.criticality), ("layer", spec.layer)),
            ontology_version=self.world.ontology_version,
            observed_world_digest=self.world.world_digest,
        )

    def _execute_command(
        self, round_index: int, command: Command, grant_id: str, parent_event_id: str
    ) -> FinalReceipt:
        cached = self._final_by_command.get(command.command_id)
        if cached is not None:
            self._emit(
                round_index=round_index,
                event_type="replay",
                actor_id=command.actor_id,
                subject_id=command.target_service,
                attrs={"command_id": command.command_id, "receipt_id": cached.receipt_id},
                refs=((command.command_id, "command"), (cached.receipt_id, "receipt")),
                parent_event_id=parent_event_id,
            )
            return cached

        pre = self._state_digest(command.target_service)
        prepared = PreparedReceipt(
            receipt_id=stable_id("prepared", command.command_id),
            command_id=command.command_id,
            authority_grant_id=grant_id,
            target_service=command.target_service,
            pre_state_digest=pre,
            prepared_at_ns=self._now(round_index),
        )
        self.prepared.append(prepared)
        prep_evt = self._emit(
            round_index=round_index,
            event_type="prepare_receipt",
            actor_id="agent:brce",
            subject_id=command.target_service,
            attrs={
                "command_id": command.command_id,
                "prepared_receipt_id": prepared.receipt_id,
            },
            refs=(
                (command.command_id, "command"),
                (grant_id, "permission"),
                (prepared.receipt_id, "prepared_receipt"),
            ),
            parent_event_id=parent_event_id,
        )

        success, consequence = self._apply(command)
        post = self._state_digest(command.target_service)
        act_evt = self._emit(
            round_index=round_index,
            event_type="actuate",
            actor_id=command.actor_id,
            subject_id=command.target_service,
            attrs={
                "command_id": command.command_id,
                "action": command.action,
                "success": success,
            },
            refs=(
                (command.command_id, "command"),
                (grant_id, "permission"),
                (prepared.receipt_id, "prepared_receipt"),
            ),
            parent_event_id=prep_evt.event_id,
        )
        verified = success and (
            pre != post or command.action in {"restart", "repair_dependency"}
        )
        final = FinalReceipt(
            receipt_id=stable_id("receipt", command.command_id, pre, post, success, verified),
            prepared_receipt_id=prepared.receipt_id,
            command_id=command.command_id,
            target_service=command.target_service,
            success=success,
            postcondition_verified=verified,
            pre_state_digest=pre,
            post_state_digest=post,
            consequence=tuple(sorted((str(k), str(v)) for k, v in consequence.items())),
            finalized_at_ns=self._now(round_index),
        )
        self.final.append(final)
        self._final_by_command[command.command_id] = final
        rec_evt = self._emit(
            round_index=round_index,
            event_type="receipt",
            actor_id="agent:verifier",
            subject_id=command.target_service,
            attrs={
                "command_id": command.command_id,
                "receipt_id": final.receipt_id,
                "success": success,
                "postcondition_verified": verified,
                "pre_state_digest": pre,
                "post_state_digest": post,
            },
            refs=(
                (command.command_id, "command"),
                (grant_id, "permission"),
                (final.receipt_id, "receipt"),
            ),
            parent_event_id=act_evt.event_id,
        )
        self._emit(
            round_index=round_index,
            event_type="verify",
            actor_id="agent:verifier",
            subject_id=command.target_service,
            attrs={"command_id": command.command_id, "verified": verified},
            refs=((final.receipt_id, "receipt"),),
            parent_event_id=rec_evt.event_id,
        )
        return final

    def _apply(self, command: Command) -> tuple[bool, dict[str, object]]:
        spec = self.services[command.target_service]
        state = self.states[command.target_service]
        params = dict(command.parameters)
        action = command.action
        before = state.canonical()
        if action == "scale_out":
            delta = max(1, int(params.get("replicas", "1")))
            state.replicas = min(spec.max_replicas, state.replicas + delta)
        elif action == "shed_load":
            fraction = min(0.8, max(0.05, float(params.get("fraction", "0.20"))))
            state.load_factor = max(0.2, state.load_factor * (1.0 - fraction))
        elif action == "restart":
            state.cleared_fault_ids.update(state.active_fault_ids)
            state.queue_depth *= 0.25
        elif action == "rollback":
            state.version = max(1, state.version - 1)
            state.cleared_fault_ids.update(state.active_fault_ids)
        elif action == "failover":
            state.cleared_fault_ids.update(state.active_fault_ids)
            state.load_factor = max(0.3, state.load_factor * 0.55)
        elif action == "repair_dependency":
            state.cleared_fault_ids.update(state.active_fault_ids)
            state.queue_depth *= 0.5
        else:
            return False, {"reason": "unknown_action"}
        state.last_action = action
        return True, {
            "before": digest(before),
            "after": digest(state.canonical()),
            "action": action,
        }

    def _budget_check(self, round_index: int) -> None:
        cost = sum(
            self.states[s.service_id].replicas * s.cost_per_replica_round
            for s in self.world.services
        )
        energy = sum(
            self.states[s.service_id].replicas * s.energy_kwh_per_replica_round
            for s in self.world.services
        )
        carbon = energy * 0.34
        if cost > self.world.cost_budget_per_round:
            self._cost_budget_violations += 1
        if energy > self.world.energy_budget_kwh_per_round:
            self._energy_budget_violations += 1
        if carbon > self.world.carbon_budget_kg_per_round:
            self._carbon_budget_violations += 1
        self._emit(
            round_index=round_index,
            event_type="budget_observe",
            actor_id="agent:finops",
            subject_id=self.run_id,
            attrs={
                "cost": round(cost, 6),
                "energy_kwh": round(energy, 6),
                "carbon_kg": round(carbon, 6),
            },
        )

    def step(self, round_index: int) -> None:
        self._update_states(round_index)
        for fault in (f for f in self.world.faults if f.round_index == round_index):
            self._emit(
                round_index=round_index,
                event_type="fault_observe",
                actor_id="agent:observability",
                subject_id=fault.target_service,
                attrs={
                    "fault_id": fault.fault_id,
                    "kind": fault.kind,
                    "severity": fault.severity,
                },
                refs=((fault.fault_id, "fault"),),
            )

        for spec, breach, fault_kind in self._breaches():
            self._slo_breaches += 1
            message = self._message(round_index, spec, breach, fault_kind)
            observe_evt = self._emit(
                round_index=round_index,
                event_type="observe",
                actor_id=message.sender_id,
                subject_id=spec.service_id,
                attrs={
                    "message_id": message.message_id,
                    "breach_kind": breach,
                    "fault_kind": fault_kind,
                },
                refs=((message.message_id, "message"),),
            )
            admission = self.admission.admit(
                message, current_world_digest=self.world.world_digest
            )
            admit_evt = self._emit(
                round_index=round_index,
                event_type="admit" if admission.admitted else "refuse",
                actor_id="agent:admission",
                subject_id=spec.service_id,
                attrs={"message_id": message.message_id, "code": admission.code},
                refs=((message.message_id, "message"),),
                parent_event_id=observe_evt.event_id,
            )
            if not admission.admitted:
                continue

            signature = self.routes.signature(message, spec)
            route = self.routes.lookup(signature)
            if route is None:
                self._frontier_invocations += 1
                action, parameters = self.frontier.choose(message, spec)
                source = "frontier"
                route_id = stable_id("candidate-route", signature, action)
            else:
                self._known_route_hits += 1
                action, parameters = route.action, ()
                if action == "scale_out":
                    parameters = (("replicas", "2"),)
                elif action == "shed_load":
                    parameters = (("fraction", "0.20"),)
                elif action == "failover":
                    parameters = (("fraction", "0.50"),)
                source = "known"
                route_id = route.route_id

            propose_evt = self._emit(
                round_index=round_index,
                event_type="propose",
                actor_id="agent:planner",
                subject_id=spec.service_id,
                attrs={
                    "action": action,
                    "route_source": source,
                    "route_id": route_id,
                },
                refs=((message.message_id, "message"), (route_id, "route")),
                parent_event_id=admit_evt.event_id,
            )
            command = build_command(
                message=message,
                service=spec,
                action=action,
                parameters=parameters,
                route_id=route_id,
                source=source,
            )
            auth = self.authority.authorize(command, round_index=round_index)
            auth_refs = [(command.command_id, "command")]
            if auth.grant_id:
                auth_refs.append((auth.grant_id, "permission"))
            auth_evt = self._emit(
                round_index=round_index,
                event_type="authorize" if auth.authorized else "authority_refuse",
                actor_id="agent:authority",
                subject_id=spec.service_id,
                attrs={
                    "command_id": command.command_id,
                    "code": auth.code,
                    "grant_id": auth.grant_id or "",
                },
                refs=tuple(auth_refs),
                parent_event_id=propose_evt.event_id,
            )
            if not auth.authorized or auth.grant_id is None:
                self._refused_authority += 1
                continue

            final = self._execute_command(
                round_index, command, auth.grant_id, auth_evt.event_id
            )
            if final.success and final.postcondition_verified:
                if route is None:
                    new_route = self.routes.qualify(
                        signature=signature,
                        action=action,
                        actor_role=command.actor_role,
                        qualification_receipt_id=final.receipt_id,
                    )
                    self._emit(
                        round_index=round_index,
                        event_type="promote_known",
                        actor_id="agent:qualification",
                        subject_id=spec.service_id,
                        attrs={"signature": signature, "route_id": new_route.route_id},
                        refs=(
                            (new_route.route_id, "route"),
                            (final.receipt_id, "receipt"),
                        ),
                    )
                else:
                    self.routes.record_successful_replay(signature)
        self._budget_check(round_index)

    def run(self, rounds: int = 40) -> SimulationRun:
        if rounds < 1:
            raise ValueError("REFUSED:INVALID_ROUND_COUNT")
        for round_index in range(rounds):
            self.step(round_index)

        from .ocel import project_events_to_ocel2, verify_ocel2

        ocel = project_events_to_ocel2(
            run_id=self.run_id,
            world=self.world,
            events=tuple(self.events),
            prepared=tuple(self.prepared),
            final=tuple(self.final),
            routes=self.routes.routes,
        )
        court = verify_ocel2(ocel)
        state_payload = tuple(
            (sid, self.states[sid].canonical()) for sid in sorted(self.states)
        )
        replay_digest = digest({
            "world": self.world.world_digest,
            "projection": self._projection.projection_digest,
            "events": [event.canonical() for event in self.events],
            "final_state": list(state_payload),
        })
        summary = SimulationSummary(
            run_id=self.run_id,
            world_digest=self.world.world_digest,
            rounds=rounds,
            events=len(self.events),
            actuations=court["actuations"],
            final_receipts=len(self.final),
            refused_authority=self._refused_authority,
            frontier_invocations=self._frontier_invocations,
            known_route_hits=self._known_route_hits,
            known_routes=len(self.routes.routes),
            slo_breaches=self._slo_breaches,
            unreconciled_actuations=court["unreceipted_actuations"],
            authority_violations=court["authority_violations"],
            duplicate_effects=court["duplicate_effects"],
            replay_digest=replay_digest,
            ocel_digest=digest(ocel),
            readiness_standing=(
                "ALIVE"
                if court["ok"]
                and not (
                    self._cost_budget_violations
                    or self._energy_budget_violations
                    or self._carbon_budget_violations
                )
                else "PARTIAL_ALIVE"
            ),
            cost_budget_violations=self._cost_budget_violations,
            energy_budget_violations=self._energy_budget_violations,
            carbon_budget_violations=self._carbon_budget_violations,
        )
        return SimulationRun(
            run_id=self.run_id,
            world=self.world,
            projection=self._projection,
            events=tuple(self.events),
            spans=tuple(self.spans),
            prepared_receipts=tuple(self.prepared),
            final_receipts=tuple(self.final),
            known_routes=self.routes.routes,
            summary=summary,
            final_state=state_payload,
        )


def run_simulation(world: WorldSpec, *, rounds: int = 40) -> SimulationRun:
    return ProductionSimulator(world).run(rounds=rounds)


__all__ = ["ProductionSimulator", "SimulationRun", "run_simulation"]
