"""Deterministic semantic projections for the Fortune-5 production simulator.

The ontology/world is canonical; HDDL, POWL and FOND are projections over one
shared action vocabulary.  This module manufactures text/JSON artifacts but
does not execute them or grant authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import WorldSpec, digest
from .world import ACTION_SET

WORKFLOW_ACTIONS = (
    "observe",
    "propose",
    "admit",
    "authorize",
    "actuate",
    "receipt",
    "verify",
    "recover",
)


@dataclass(frozen=True, slots=True)
class FormalProjection:
    world_digest: str
    hddl: str
    powl: dict[str, object]
    fond: str
    action_vocabulary: tuple[str, ...]
    projection_digest: str

    def canonical(self) -> dict[str, object]:
        return {
            "world_digest": self.world_digest,
            "hddl": self.hddl,
            "powl": self.powl,
            "fond": self.fond,
            "action_vocabulary": list(self.action_vocabulary),
            "projection_digest": self.projection_digest,
        }


def _hddl(world: WorldSpec) -> str:
    services = " ".join(service.service_id.replace(":", "_") for service in world.services)
    workflow_actions = """
  (:action observe
    :parameters (?s - service)
    :precondition (not (observed ?s))
    :effect (observed ?s))
  (:action propose
    :parameters (?s - service)
    :precondition (observed ?s)
    :effect (proposed ?s))
  (:action admit
    :parameters (?s - service)
    :precondition (proposed ?s)
    :effect (admitted ?s))
  (:action authorize
    :parameters (?s - service)
    :precondition (admitted ?s)
    :effect (authorized ?s))
  (:action actuate
    :parameters (?s - service)
    :precondition (authorized ?s)
    :effect (actuated ?s))
  (:action receipt
    :parameters (?s - service)
    :precondition (actuated ?s)
    :effect (receipted ?s))
  (:action verify
    :parameters (?s - service)
    :precondition (receipted ?s)
    :effect (verified ?s))
"""
    actions = "\n".join(
        f"""  (:action {action}
    :parameters (?s - service)
    :precondition (admitted ?s)
    :effect (handled ?s))"""
        for action in ACTION_SET
    )
    return f"""(define (domain fortune5-sa2a)
  (:requirements :typing :hierarchy :negative-preconditions)
  (:types service)
  (:predicates
    (observed ?s - service)
    (proposed ?s - service)
    (admitted ?s - service)
    (authorized ?s - service)
    (actuated ?s - service)
    (receipted ?s - service)
    (verified ?s - service)
    (handled ?s - service))

  (:task stabilize-service :parameters (?s - service))
  (:method stabilize-service-method
    :parameters (?s - service)
    :task (stabilize-service ?s)
    :ordered-subtasks (and
      (observe ?s)
      (propose ?s)
      (admit ?s)
      (authorize ?s)
      (actuate ?s)
      (receipt ?s)
      (verify ?s)))

{workflow_actions}
{actions}
)

(define (problem fortune5-world-{world.world_digest[:16]})
  (:domain fortune5-sa2a)
  (:objects {services} - service)
  (:htn :tasks (and {''.join(f'(stabilize-service {s.service_id.replace(":", "_")}) ' for s in world.services[:8])}))
)
"""


def _powl(world: WorldSpec) -> dict[str, object]:
    nodes = [{"id": name, "type": "activity"} for name in WORKFLOW_ACTIONS]
    edges = [
        ["observe", "propose"],
        ["propose", "admit"],
        ["admit", "authorize"],
        ["authorize", "actuate"],
        ["actuate", "receipt"],
        ["receipt", "verify"],
        ["verify", "recover"],
    ]
    return {
        "schema": "urn:autofde-lab:powl:v2",
        "world_digest": world.world_digest,
        "nodes": nodes,
        "order": edges,
        "parallelism": {
            "rule": "different services may execute independently after admission",
            "partition_key": "service_id",
        },
    }


def _fond(world: WorldSpec) -> str:
    actions = []
    for action in ACTION_SET:
        if action == "scale_out":
            outcomes = "(oneof (stabilized ?s) (capacity-limited ?s))"
        elif action == "failover":
            outcomes = "(oneof (stabilized ?s) (failover-degraded ?s))"
        elif action == "restart":
            outcomes = "(oneof (stabilized ?s) (restart-failed ?s))"
        elif action == "rollback":
            outcomes = "(oneof (stabilized ?s) (rollback-failed ?s))"
        elif action == "repair_dependency":
            outcomes = "(oneof (stabilized ?s) (dependency-still-failing ?s))"
        else:
            outcomes = "(oneof (stabilized ?s) (load-still-high ?s))"
        actions.append(
            f"""  (:action {action}
    :parameters (?s - service)
    :precondition (and (admitted ?s) (authorized ?s))
    :effect {outcomes})"""
        )
    return f"""(define (domain fortune5-sa2a-fond)
  (:requirements :strips :typing :non-deterministic)
  (:types service)
  (:predicates
    (admitted ?s - service)
    (authorized ?s - service)
    (stabilized ?s - service)
    (capacity-limited ?s - service)
    (failover-degraded ?s - service)
    (restart-failed ?s - service)
    (rollback-failed ?s - service)
    (dependency-still-failing ?s - service)
    (load-still-high ?s - service))
{chr(10).join(actions)}
)
; world={world.world_digest}
"""


def generate_formal_projection(world: WorldSpec) -> FormalProjection:
    hddl = _hddl(world)
    powl = _powl(world)
    fond = _fond(world)
    vocabulary = tuple(sorted(set(ACTION_SET)))
    base = {
        "world_digest": world.world_digest,
        "hddl": hddl,
        "powl": powl,
        "fond": fond,
        "action_vocabulary": list(vocabulary),
    }
    return FormalProjection(
        world_digest=world.world_digest,
        hddl=hddl,
        powl=powl,
        fond=fond,
        action_vocabulary=vocabulary,
        projection_digest=digest(base),
    )


def verify_projection_coherence(projection: FormalProjection) -> tuple[bool, tuple[str, ...]]:
    violations: list[str] = []
    for action in projection.action_vocabulary:
        if f"(:action {action}" not in projection.hddl:
            violations.append(f"HDDL_MISSING_ACTION:{action}")
        if f"(:action {action}" not in projection.fond:
            violations.append(f"FOND_MISSING_ACTION:{action}")
    order = {tuple(edge) for edge in projection.powl.get("order", []) if isinstance(edge, list)}
    required_edges = {
        ("observe", "propose"),
        ("propose", "admit"),
        ("admit", "authorize"),
        ("authorize", "actuate"),
        ("actuate", "receipt"),
        ("receipt", "verify"),
    }
    for edge in sorted(required_edges - order):
        violations.append(f"POWL_MISSING_EDGE:{edge[0]}->{edge[1]}")
    return (not violations, tuple(violations))


__all__ = [
    "FormalProjection",
    "WORKFLOW_ACTIONS",
    "generate_formal_projection",
    "verify_projection_coherence",
]
