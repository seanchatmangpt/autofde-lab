"""Prior-art-first generator capability routing.

This module selects existing manufacturing capabilities. It does not execute
generators. An absent capability produces a typed UNSUPPORTED result instead
of silently authoring handwritten code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .model import Failure, FailureKind, digest


class CapabilityStanding(str, Enum):
    OBSERVED = "OBSERVED"
    ADMITTED = "ADMITTED"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class GeneratorCapability:
    capability_id: str
    owner: str
    input_kind: str
    output_kind: str
    standing: CapabilityStanding
    evidence_ids: tuple[str, ...]
    executable_identity: str | None = None
    executable_revision: str | None = None
    priority: int = 100

    def __post_init__(self) -> None:
        for value, name in (
            (self.capability_id, "capability_id"),
            (self.owner, "owner"),
            (self.input_kind, "input_kind"),
            (self.output_kind, "output_kind"),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")

    @property
    def identity(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class ManufactureRequirement:
    input_kind: str
    output_kind: str
    subject_id: str
    semantic_requirements: tuple[str, ...] = ()

    @property
    def requirement_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class ManufactureStep:
    capability_identity: str
    owner: str
    input_kind: str
    output_kind: str
    authority: str = "NONE"


@dataclass(frozen=True, slots=True)
class ManufactureRoute:
    requirement_id: str
    steps: tuple[ManufactureStep, ...]
    failure: Failure | None = None

    @property
    def routable(self) -> bool:
        return self.failure is None

    @property
    def route_id(self) -> str:
        return digest(self)


class ManufactureRouter:
    """Route to an exact existing capability before permitting invention."""

    def __init__(self, capabilities: Iterable[GeneratorCapability] = ()) -> None:
        self._capabilities: dict[str, GeneratorCapability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: GeneratorCapability) -> None:
        if capability.capability_id in self._capabilities:
            raise ValueError(
                f"duplicate generator capability: {capability.capability_id}"
            )
        self._capabilities[capability.capability_id] = capability

    def route(self, requirement: ManufactureRequirement) -> ManufactureRoute:
        eligible = [
            capability
            for capability in self._capabilities.values()
            if capability.input_kind == requirement.input_kind
            and capability.output_kind == requirement.output_kind
            and capability.standing
            in {CapabilityStanding.ADMITTED, CapabilityStanding.ALIVE}
        ]
        if not eligible:
            failure = Failure(
                kind=FailureKind.UNSUPPORTED_GENERATOR_CAPABILITY,
                detail=(
                    f"no admitted generator: {requirement.input_kind}"
                    f" -> {requirement.output_kind}"
                ),
                subject_id=requirement.subject_id,
            )
            return ManufactureRoute(
                requirement_id=requirement.requirement_id,
                steps=(),
                failure=failure,
            )

        selected = sorted(
            eligible,
            key=lambda capability: (
                capability.priority,
                capability.owner,
                capability.capability_id,
            ),
        )[0]
        return ManufactureRoute(
            requirement_id=requirement.requirement_id,
            steps=(
                ManufactureStep(
                    capability_identity=selected.identity,
                    owner=selected.owner,
                    input_kind=selected.input_kind,
                    output_kind=selected.output_kind,
                ),
            ),
        )

    def capabilities(self) -> tuple[GeneratorCapability, ...]:
        return tuple(self._capabilities[key] for key in sorted(self._capabilities))


def ecosystem_capabilities(
    *,
    ggen_create_revision: str,
    ggen_revision: str,
    ggen_igniter_revision: str,
) -> tuple[GeneratorCapability, ...]:
    """Seed only known ownership boundaries; callers bind real evidence."""

    return (
        GeneratorCapability(
            capability_id="ggen-create/exemplar-to-package",
            owner="seanchatmangpt/ggen-create",
            input_kind="working-exemplar",
            output_kind="ggen-package",
            standing=CapabilityStanding.ADMITTED,
            evidence_ids=(f"git:{ggen_create_revision}",),
            executable_identity="ggen-create",
            executable_revision=ggen_create_revision,
            priority=10,
        ),
        GeneratorCapability(
            capability_id="ggen/package-to-artifacts",
            owner="seanchatmangpt/ggen",
            input_kind="ggen-package",
            output_kind="generated-artifacts",
            standing=CapabilityStanding.ADMITTED,
            evidence_ids=(f"git:{ggen_revision}",),
            executable_identity="ggen",
            executable_revision=ggen_revision,
            priority=10,
        ),
        GeneratorCapability(
            capability_id="ggen-igniter/rdf-to-elixir",
            owner="seanchatmangpt/ggen_igniter",
            input_kind="rdf-semantic-source",
            output_kind="elixir-project-projection",
            standing=CapabilityStanding.ADMITTED,
            evidence_ids=(f"git:{ggen_igniter_revision}",),
            executable_identity="mix ggen_igniter.sync",
            executable_revision=ggen_igniter_revision,
            priority=10,
        ),
    )
