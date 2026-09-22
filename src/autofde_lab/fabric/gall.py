"""GALL semantic-work planning projection.

This module is intentionally authority-free.  It preserves every currently
admissible checkpoint, projects that frontier into deterministic HDDL text,
and records MachineExperience-shaped observations.  It never creates an
XaaS lease and never treats a plan as execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class Dependency:
    iri: str
    standing: str

    def __post_init__(self) -> None:
        if not self.iri:
            raise ValueError("dependency iri is required")
        if self.standing not in _STANDING and not self.standing.startswith("REFUSED_"):
            raise ValueError(f"unsupported standing: {self.standing}")


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

    def __post_init__(self) -> None:
        if not self.iri or ":" not in self.iri:
            raise ValueError("checkpoint iri must be absolute")
        if not self.repository:
            raise ValueError("repository is required")
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

    @property
    def dependencies_alive(self) -> bool:
        return all(dep.standing == "ALIVE" for dep in self.dependencies)

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
        if (
            self.selected_action is not None
            and self.selected_action not in self.admitted_actions
        ):
            raise ValueError("selected_action must be admitted before selection")


def frontier(checkpoints: Iterable[Checkpoint]) -> tuple[Checkpoint, ...]:
    """Return every lawful reversible frontier option, sorted by stable IRI."""

    return tuple(
        sorted(
            (
                checkpoint
                for checkpoint in checkpoints
                if checkpoint.admissible_frontier_member
            ),
            key=lambda checkpoint: checkpoint.iri,
        )
    )


def to_hddl_problem(
    checkpoints: Sequence[Checkpoint],
    *,
    problem_name: str = "gall-semantic-work-frontier",
    domain_name: str = "gall-semantic-work",
) -> str:
    """Project the current frontier into deterministic HDDL problem text.

    The projection intentionally includes *all* admissible frontier nodes and
    does not choose one.  Selection remains the responsibility of a planner;
    execution still requires downstream admission and a real XaaS lease.
    """

    selected = frontier(checkpoints)
    aliases = {
        checkpoint.iri: f"checkpoint_{index}"
        for index, checkpoint in enumerate(selected)
    }

    objects = " ".join(aliases.values())
    init = "\n".join(
        f"    (admissible {aliases[checkpoint.iri]})" for checkpoint in selected
    )
    tasks = "\n".join(
        f"      (task_{index} (solve {aliases[checkpoint.iri]}))"
        for index, checkpoint in enumerate(selected)
    )

    objects_section = f"  (:objects {objects} - checkpoint)\n" if objects else ""
    init_section = f"  (:init\n{init}\n  )\n" if init else "  (:init)\n"
    tasks_section = (
        f"    :tasks (and\n{tasks}\n    )\n" if tasks else "    :tasks (and)\n"
    )

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
    """Return the authority-free semantic descriptor consumed downstream.

    This is not a lease.  It contains no lease token, epoch id, worker id, or
    executable authority and therefore cannot be used as proof of execution.
    """

    return {
        "checkpoint_iri": checkpoint.iri,
        "repository": checkpoint.repository,
        "base_sha": checkpoint.base_sha,
        "graph_digest": checkpoint.graph_digest,
        "goal": checkpoint.goal,
        "verifier_suite": checkpoint.verifier,
        "dependencies": [
            {"iri": dependency.iri, "standing": dependency.standing}
            for dependency in checkpoint.dependencies
        ],
        "required_capabilities": list(checkpoint.required_capabilities),
        "forbidden_capabilities": list(checkpoint.forbidden_capabilities),
        "standing": checkpoint.standing,
    }
