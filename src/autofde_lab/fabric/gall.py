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
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REPO_ALIAS = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_EXECUTION_POLICIES = {"continuous_epoch_run", "autonomic_wave_attempt"}
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
    receipt_iri: str | None = None
    receipt_digest: str | None = None
    required_standing: str = "ALIVE"

    def __post_init__(self) -> None:
        if not self.iri or ":" not in self.iri:
            raise ValueError("dependency iri must be absolute")
        if self.standing not in _STANDING and not self.standing.startswith("REFUSED_"):
            raise ValueError(f"unsupported standing: {self.standing}")
        if self.required_standing not in _STANDING:
            raise ValueError(f"unsupported required standing: {self.required_standing}")
        if (self.receipt_iri is None) != (self.receipt_digest is None):
            raise ValueError(
                "dependency receipt identity and digest must be supplied together"
            )
        if self.receipt_iri is not None and ":" not in self.receipt_iri:
            raise ValueError("dependency receipt iri must be absolute")
        if self.receipt_digest is not None and not _DIGEST.fullmatch(
            self.receipt_digest
        ):
            raise ValueError(
                "dependency receipt digest must be sha256:<64 lowercase hex>"
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

    def __post_init__(self) -> None:
        if not self.iri or ":" not in self.iri:
            raise ValueError("checkpoint iri must be absolute")
        if not _REPOSITORY.fullmatch(self.repository):
            raise ValueError("repository must be owner/name")
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


def execution_descriptor(
    checkpoint: Checkpoint,
    *,
    work_order_iri: str,
    execution_repo_alias: str,
    provider: str,
    execution_policy: str,
) -> dict[str, object]:
    """Manufacture the authority-free descriptor admitted by XaaS SemanticWork.

    This is still SELECT/CONSTRUCT input, not a lease.  It intentionally carries
    no epoch, worker, lease token, actuation authority, or standing promotion.
    Exact upstream receipt edges are required here because XaaS must never infer
    dependency evidence from generic ALIVE adjacency.
    """

    if not work_order_iri or ":" not in work_order_iri:
        raise ValueError("work_order_iri must be absolute")
    if not _REPO_ALIAS.fullmatch(execution_repo_alias):
        raise ValueError("execution_repo_alias is invalid")
    if not provider:
        raise ValueError("provider is required")
    if execution_policy not in _EXECUTION_POLICIES:
        raise ValueError(f"unsupported execution policy: {execution_policy}")

    dependencies: list[dict[str, str]] = []
    for dependency in checkpoint.dependencies:
        if dependency.required_standing != "ALIVE":
            raise ValueError(
                f"XaaS execution descriptor supports required ALIVE only: {dependency.iri}"
            )
        if dependency.standing != "ALIVE":
            raise ValueError(
                f"dependency is not admitted for execution: {dependency.iri}={dependency.standing}"
            )
        if dependency.receipt_iri is None or dependency.receipt_digest is None:
            raise ValueError(
                f"dependency requires exact receipt identity for execution: {dependency.iri}"
            )
        dependencies.append(
            {
                "work_order_iri": dependency.iri,
                "required_standing": dependency.required_standing,
                "observed_standing": dependency.standing,
                "receipt_iri": dependency.receipt_iri,
                "receipt_digest": dependency.receipt_digest,
            }
        )

    return {
        "work_order_iri": work_order_iri,
        "checkpoint_iri": checkpoint.iri,
        "graph_digest": checkpoint.graph_digest,
        "repository_identity": checkpoint.repository,
        "execution_repo_alias": execution_repo_alias,
        "base_sha": checkpoint.base_sha,
        "goal": checkpoint.goal,
        "provider": provider,
        "verifier_suite": checkpoint.verifier,
        "execution_policy": execution_policy,
        "dependencies": dependencies,
        "standing": checkpoint.standing,
    }
