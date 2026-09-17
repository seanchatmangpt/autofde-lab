# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial Counterfactual Mutators.

Systematic generators of counterfactual variations across the Vision 2030 stack:
- Premature Actuation: Executing consequences before admission or observation.
- Unadmitted Step Injection: Injecting rogue or unreceipted actions into execution traces.
- Skipped Teardown / Invariant: Truncating mandatory lifecycle cleanups.
- Crossed Object Link: Reassigning event-to-object links to incompatible entities.
- Resource Allocation Inversion: Inverting CMCA allocations to starve high-salience branches.
"""

from __future__ import annotations

from collections.abc import Sequence

from autofde_lab.cmca.contracts import (
    BranchAllocation,
    CascadeAllocationPlan,
)
from autofde_lab.ocel.log import EventObjectLink, OcelLog

__all__ = [
    "mutate_crossed_object_links",
    "mutate_premature_actuation",
    "mutate_resource_allocation_inversion",
    "mutate_skipped_teardown",
    "mutate_subtask_inversion",
    "mutate_unadmitted_action_injection",
]


def mutate_premature_actuation(
    trace: Sequence[str],
    actuate_action: str = "actuate",
) -> list[str]:
    """Move an actuation step to the start of the trace before observation or admission."""
    mutated = list(trace)
    if actuate_action in mutated:
        mutated.remove(actuate_action)
    mutated.insert(0, actuate_action)
    return mutated


def mutate_unadmitted_action_injection(
    trace: Sequence[str],
    rogue_action: str = "unadmitted_arbitrary_actuation",
    insertion_index: int | None = None,
) -> list[str]:
    """Inject an unadmitted rogue action into a lawful trace."""
    mutated = list(trace)
    idx = (
        len(mutated) // 2
        if insertion_index is None
        else min(insertion_index, len(mutated))
    )
    mutated.insert(idx, rogue_action)
    return mutated


def mutate_skipped_teardown(
    trace: Sequence[str],
    teardown_action: str = "teardown",
) -> list[str]:
    """Omit mandatory teardown/receipt steps from the trace."""
    return [a for a in trace if a != teardown_action]


def mutate_subtask_inversion(
    trace: Sequence[str],
    step_a: str,
    step_b: str,
) -> list[str]:
    """Invert the relative execution order of two dependent subtasks."""
    mutated = list(trace)
    if step_a in mutated and step_b in mutated:
        idx_a = mutated.index(step_a)
        idx_b = mutated.index(step_b)
        mutated[idx_a], mutated[idx_b] = mutated[idx_b], mutated[idx_a]
    return mutated


def mutate_crossed_object_links(
    ocel_log: OcelLog,
    source_object_id: str,
    target_object_id: str,
) -> OcelLog:
    """Cross event-to-object links between two objects, creating identity violations."""
    new_links: list[EventObjectLink] = []
    for link in ocel_log.event_object_links:
        if link.object_id == source_object_id:
            new_links.append(
                EventObjectLink(
                    event_id=link.event_id,
                    object_id=target_object_id,
                    qualifier=link.qualifier,
                )
            )
        elif link.object_id == target_object_id:
            new_links.append(
                EventObjectLink(
                    event_id=link.event_id,
                    object_id=source_object_id,
                    qualifier=link.qualifier,
                )
            )
        else:
            new_links.append(link)

    return OcelLog(
        events=ocel_log.events,
        objects=ocel_log.objects,
        event_object_links=tuple(new_links),
        object_object_links=ocel_log.object_object_links,
        object_changes=ocel_log.object_changes,
    )


def mutate_resource_allocation_inversion(
    plan: CascadeAllocationPlan,
) -> CascadeAllocationPlan:
    """Invert resource allocations so the lowest-salience branch receives the highest budget."""
    if not plan.allocations:
        return plan

    sorted_allocs = sorted(plan.allocations, key=lambda a: a.allocated_ticks)
    # Reverse the assigned ticks and memory
    reversed_ticks = [a.allocated_ticks for a in reversed(sorted_allocs)]
    reversed_memory = [a.allocated_memory_bytes for a in reversed(sorted_allocs)]
    reversed_fraction = [a.allocated_fraction for a in reversed(sorted_allocs)]

    mutated_allocs: list[BranchAllocation] = []
    for i, a in enumerate(sorted_allocs):
        mutated_allocs.append(
            BranchAllocation(
                branch_id=a.branch_id,
                allocated_fraction=reversed_fraction[i],
                allocated_ticks=reversed_ticks[i],
                allocated_memory_bytes=reversed_memory[i],
                verification_depth=a.verification_depth,
                standing=a.standing,
                priority_lane=a.priority_lane,
            )
        )

    return CascadeAllocationPlan(
        plan_id=f"mutated_inversion_{plan.plan_id}",
        parent_budget=plan.parent_budget,
        allocations=tuple(mutated_allocs),
        total_option_value_preserved=plan.total_option_value_preserved,
        entropy=plan.entropy,
    )
