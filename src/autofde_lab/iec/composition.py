"""Deterministic multi-hop composition over admitted generator capabilities."""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from .manufacture import (
    CapabilityStanding,
    GeneratorCapability,
    ManufactureRequirement,
    ManufactureRoute,
    ManufactureStep,
)
from .model import Failure, FailureKind, digest


@dataclass(frozen=True, slots=True)
class CompositionPolicy:
    max_hops: int = 8
    alive_cost: int = 1
    admitted_cost: int = 2

    def __post_init__(self) -> None:
        if self.max_hops <= 0:
            raise ValueError("max_hops must be positive")
        if self.alive_cost <= 0 or self.admitted_cost <= 0:
            raise ValueError("composition costs must be positive")

    def cost(self, capability: GeneratorCapability) -> int:
        standing_cost = (
            self.alive_cost
            if capability.standing is CapabilityStanding.ALIVE
            else self.admitted_cost
        )
        return standing_cost + max(0, capability.priority)


@dataclass(frozen=True, slots=True)
class ComposedRoute:
    requirement_id: str
    capabilities: tuple[GeneratorCapability, ...]
    total_cost: int
    failure: Failure | None = None

    @property
    def routable(self) -> bool:
        return self.failure is None

    @property
    def route_id(self) -> str:
        return digest(
            {
                "requirement_id": self.requirement_id,
                "capabilities": tuple(
                    capability.identity for capability in self.capabilities
                ),
                "total_cost": self.total_cost,
                "failure": self.failure,
            }
        )

    def as_manufacture_route(self) -> ManufactureRoute:
        if self.failure is not None:
            return ManufactureRoute(
                requirement_id=self.requirement_id,
                steps=(),
                failure=self.failure,
            )
        return ManufactureRoute(
            requirement_id=self.requirement_id,
            steps=tuple(
                ManufactureStep(
                    capability_identity=capability.identity,
                    owner=capability.owner,
                    input_kind=capability.input_kind,
                    output_kind=capability.output_kind,
                )
                for capability in self.capabilities
            ),
        )


class CapabilityComposer:
    """Dijkstra search over known capability morphisms.

    The result remains a CONSTRUCT route with authority NONE on every step.
    """

    def __init__(
        self,
        capabilities: tuple[GeneratorCapability, ...],
        *,
        policy: CompositionPolicy | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.policy = policy or CompositionPolicy()

    def route(self, requirement: ManufactureRequirement) -> ComposedRoute:
        eligible = tuple(
            capability
            for capability in self.capabilities
            if capability.standing
            in {CapabilityStanding.ADMITTED, CapabilityStanding.ALIVE}
        )
        by_input: dict[str, list[GeneratorCapability]] = {}
        for capability in eligible:
            by_input.setdefault(capability.input_kind, []).append(capability)
        for values in by_input.values():
            values.sort(
                key=lambda capability: (
                    self.policy.cost(capability),
                    capability.owner,
                    capability.capability_id,
                )
            )

        queue: list[
            tuple[
                int,
                int,
                str,
                tuple[str, ...],
                tuple[GeneratorCapability, ...],
            ]
        ] = [(0, 0, requirement.input_kind, (), ())]
        best: dict[tuple[str, int], int] = {(requirement.input_kind, 0): 0}

        while queue:
            cost, hops, current_kind, path_key, path = heapq.heappop(queue)
            if current_kind == requirement.output_kind:
                return ComposedRoute(
                    requirement_id=requirement.requirement_id,
                    capabilities=path,
                    total_cost=cost,
                )
            if hops >= self.policy.max_hops:
                continue

            for capability in by_input.get(current_kind, ()):
                next_kind = capability.output_kind
                next_hops = hops + 1
                next_cost = cost + self.policy.cost(capability)
                next_path_key = path_key + (capability.capability_id,)
                state = (next_kind, next_hops)
                if next_cost > best.get(state, 2**63 - 1):
                    continue
                if next_cost < best.get(state, 2**63 - 1):
                    best[state] = next_cost
                heapq.heappush(
                    queue,
                    (
                        next_cost,
                        next_hops,
                        next_kind,
                        next_path_key,
                        path + (capability,),
                    ),
                )

        failure = Failure(
            kind=FailureKind.UNSUPPORTED_GENERATOR_CAPABILITY,
            detail=(
                "no admitted composition: "
                f"{requirement.input_kind} -> {requirement.output_kind}"
            ),
            subject_id=requirement.subject_id,
        )
        return ComposedRoute(
            requirement_id=requirement.requirement_id,
            capabilities=(),
            total_cost=0,
            failure=failure,
        )
