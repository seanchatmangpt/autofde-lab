"""GALL semantic-work planning projection.

Planning remains authority-free. The planner may preserve every reversible
frontier option, but a downstream execution descriptor is only manufactured
when the semantic subject and every dependency carry exact receipt evidence.
A plan, model output, or frontier membership is never execution or authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_STANDING = {
    "UNKNOWN",
    "PARTIAL_ALIVE",
    "ALIVE",
    "BLOCKED",
    "BUILD_BROKEN",
    "UNSUPPORTED",
}
_EXECUTION_POLICIES = {"continuous_epoch_run", "autonomic_wave_attempt"}


@dataclass(frozen=True, slots=True)
class Dependency:
    iri: str
    standing: str
    required_standing: str = "ALIVE"
    receipt_iri: str | None = None
    receipt_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.iri or ":" not in self.iri:
            raise ValueError("dependency iri must be absolute")
        if self.standing not in _STANDING and not self.standing.startswith("REFUSED_"):
            raise ValueError(f"unsupported standing: {self.standing}")
        if self.required_standing not in _STANDING and not self.required_standing.startswith("REFUSED_"):
            raise ValueError(f"unsupported required standing: {self.required_standing}")
        if self.receipt_iri is not None and ":" not in self.receipt_iri:
            raise ValueError("dependency receipt_iri must be absolute")
        if self.receipt_digest is not None and not _DIGEST.fullmatch(self.receipt_digest):
            raise ValueError("dependency receipt_digest must be sha256:<64 lowercase hex>")

    @property
    def standing_satisfied(self) -> bool:
        return self.required_standing == "ALIVE" and self.standing == "ALIVE"

    @property
    def execution_evidence_complete(self) -> bool:
        return (
            self.standing_satisfied
            and self.receipt_iri is not None
            and self.receipt_digest is not None
        )


@dataclass(frozen=True, slots=True)
class Checkpoint:
    iri: str
    repository: str
    base_sha: str
    graph_digest: str
    goal: str
    verifier: str
    standing: str = "UNKNOWN"
    dependencies: tuple[Dependency, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    forbidden_capabilities: tuple[str, ...] = ()
    work_order_iri: str | None = None
    provider: str | None = None
    execution_policy: str | None = None

    def __post_init__(self) -> None:
        if not self.iri or ":" not in self.iri:
            raise ValueError("checkpoint iri must be absolute")
        if self.work_order_iri is not None and ":" not in self.work_order_iri:
            raise ValueError("work_order_iri must be absolute")
        if not self.repository or "/" not in self.repository:
            raise ValueError("repository identity must be owner/repo")
        if not _SHA.fullmatch(self.base_sha):
            raise ValueError("base_sha must be a full lowercase git sha")
        if not _DIGEST.fullmatch(self.graph_digest):
            raise ValueError("graph_digest must be sha256:<64 lowercase hex>")
        if not self.goal:
            raise ValueError("goal is required")
        if not self.verifier:
            raise ValueError("verifier is required")
        if self.standing not in _STANDING and not self.standing.startswith("REFUSED_"):
            raise ValueError(f"unsupported standing: {self.standing}")
        if self.execution_policy is not None and self.execution_policy not in _EXECUTION_POLICIES:
            raise ValueError(f"unsupported execution_policy: {self.execution_policy}")

    @property
    def dependencies_alive(self) -> bool:
        return all(dep.standing_satisfied for dep in self.dependencies)

    @property
    def execution_evidence_complete(self) -> bool:
        return all(dep.execution_evidence_complete for dep in self.dependencies)

    @property
    def admissible_frontier_member(self) -> bool:
        return self.standing == "UNKNOWN" and self.dependencies_alive


@dataclass(frozen=True, slots=True)
class MachineExperience:
    checkpoint_iri: str
    state_before: str
    available_actions: tuple[str, ...]
    admitted_actions: tuple[str, ...]
    selected_action: str | None
    observation: str
    state_after: str
    receipt_iri: str | None = None

    def __post_init__(self) -> None:
        if not set(self.admitted_actions).issubset(self.available_actions):
            raise ValueError("admitted_actions must be a subset of available_actions")
        if self.selected_action is not None and self.selected_action not in self.admitted_actions:
            raise ValueError("selected_action must be admitted before selection")


def frontier(checkpoints: Iterable[Checkpoint]) -> tuple[Checkpoint, ...]:
    """Return every lawful reversible frontier option, sorted by stable IRI."""

    return tuple(
        sorted(
            (checkpoint for checkpoint in checkpoints if checkpoint.admissible_frontier_member),
            key=lambda checkpoint: checkpoint.iri,
        )
    )


def to_hddl_problem(
    checkpoints: Sequence[Checkpoint],
    *,
    problem_name: str = "gall-semantic-work-frontier",
    domain_name: str = "gall-semantic-work",
) -> str:
    """Project all currently admissible options without selecting a winner."""

    selected = frontier(checkpoints)
    aliases = {checkpoint.iri: f"checkpoint_{index}" for index, checkpoint in enumerate(selected)}

    objects = " ".join(aliases.values())
    init = "\n".join(f"    (admissible {aliases[checkpoint.iri]})" for checkpoint in selected)
    tasks = "\n".join(
        f"      (task_{index} (solve {aliases[checkpoint.iri]}))"
        for index, checkpoint in enumerate(selected)
    )

    objects_section = f"  (:objects {objects} - checkpoint)\n" if objects else ""
    init_section = f"  (:init\n{init}\n  )\n" if init else "  (:init)\n"
    tasks_section = f"    :tasks (and\n{tasks}\n    )\n" if tasks else "    :tasks (and)\n"

    return (
        f"(define (problem {problem_name})\n"
        f"  (:domain {domain_name})\n"
        f"{objects_section}"
        f"{init_section}"
        "  (:htn\n"
        f"{tasks_section}"
        "  )\n"
        ")\n"
    )


def checkpoint_descriptor(checkpoint: Checkpoint) -> dict[str, object]:
    """Manufacture the authority-free cross-repository execution descriptor.

    This is deliberately stricter than frontier(). Planning may preserve an
    ALIVE dependency without knowing its receipt bytes, but execution handoff
    may not: every dependency must bind exact receipt identity and digest.
    """

    if checkpoint.work_order_iri is None:
        raise ValueError("work_order_iri is required for execution descriptor")
    if checkpoint.provider is None:
        raise ValueError("provider is required for execution descriptor")
    if checkpoint.execution_policy is None:
        raise ValueError("execution_policy is required for execution descriptor")
    if not checkpoint.execution_evidence_complete:
        raise ValueError("dependency receipt evidence is incomplete")

    return {
        "schema": "gall.work-order-execution/2",
        "type": "gall:WorkOrderExecutionDescriptor",
        "work_order_iri": checkpoint.work_order_iri,
        "checkpoint_iri": checkpoint.iri,
        "repository_identity": checkpoint.repository,
        "base_sha": checkpoint.base_sha,
        "graph_digest": checkpoint.graph_digest,
        "goal": checkpoint.goal,
        "provider": checkpoint.provider,
        "verifier_suite": checkpoint.verifier,
        "execution_policy": checkpoint.execution_policy,
        "dependencies": [
            {
                "work_order_iri": dependency.iri,
                "required_standing": dependency.required_standing,
                "observed_standing": dependency.standing,
                "receipt_iri": dependency.receipt_iri,
                "receipt_digest": dependency.receipt_digest,
            }
            for dependency in checkpoint.dependencies
        ],
        "required_capabilities": list(checkpoint.required_capabilities),
        "forbidden_capabilities": list(checkpoint.forbidden_capabilities),
        "standing": checkpoint.standing,
        "authority": "NONE",
    }
