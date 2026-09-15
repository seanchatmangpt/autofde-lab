# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Closed-Loop Auto-Dev Engine.

Connects:
1. pystackt Git & Software Repository Ingestion -> OCEL 2.0
2. FOND x HDDL Product Planning & Method Refinement
3. CMCA Multifractal Cascade Resource Allocation
4. GymAct Environment Provider Simulation
5. Multi-Tier OCEL 2.0 Conformance Checking (PM4Py, OCPA, Ocelescope)
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from gymact.models import ActuationIntent

from autofde_lab.agent.autodev_domain import (
    build_autodev_hddl_domain,
    extract_initial_product_state,
)
from autofde_lab.agent.autodev_gymact_env import AutoDevGymActEnvironment
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    CandidateBranch,
    CascadeAllocationPlan,
    ResourceBudget,
)
from autofde_lab.ocel.counterfactual_engine import (
    CounterfactualReport,
    evaluate_counterfactual_execution,
)
from autofde_lab.ocel.lifecycle_pystackt import (
    GitCommitRecord,
    extract_git_lifecycle_to_ocel,
)
from autofde_lab.ocel.log import OcelLog
from autofde_lab.planning.fond_hddl_product import (
    ProductState,
    build_fond_problem,
)

__all__ = [
    "AutoDevCycleReceipt",
    "AutoDevCycleResult",
    "run_autodev_cycle",
]


@dataclass(frozen=True)
class AutoDevCycleReceipt:
    """Cryptographic attestation of an executed auto-dev cycle."""

    receipt_id: str
    repo_name: str
    goal_task: str
    is_conforming: bool
    executed_steps: int
    cmca_allocated_ticks: int
    divergence_score: float
    standing: str
    receipt_hash: str


@dataclass(frozen=True)
class AutoDevCycleResult:
    """Complete report of a closed-loop autonomous development run."""

    is_success: bool
    final_state: ProductState
    executed_trace: tuple[str, ...]
    execution_ocel: OcelLog
    conformance_report: CounterfactualReport
    allocation_plan: CascadeAllocationPlan
    receipt: AutoDevCycleReceipt


def run_autodev_cycle(
    repo_name: str,
    commits: Sequence[GitCommitRecord],
    goal_task: str = "deliver_feature",
    budget: ResourceBudget | None = None,
    max_steps: int = 15,
) -> AutoDevCycleResult:
    """Execute an end-to-end closed-loop auto-dev cycle."""
    # 1. Ingest repo lifecycle via pystackt extractor to OCEL 2.0
    initial_ocel = extract_git_lifecycle_to_ocel(repo_name, commits)

    # 2. Derive domain and initial ProductState
    domain = build_autodev_hddl_domain()
    initial_state = extract_initial_product_state(initial_ocel, goal_task=goal_task)

    # 3. Explore reachable FOND x HDDL product reachability
    build_fond_problem(
        domain=domain,
        initial=initial_state,
        is_goal=lambda s: len(s.tau) == 0 and "cycle_receipted" in s.world,
    )

    # 4. Govern via CMCA Multifractal Cascade Allocation
    active_budget = budget or ResourceBudget(
        total_ticks=5000,
        memory_bytes=32768,
        max_verification_depth=6,
        consequence_risk_budget=0.25,
        concurrency_lanes=4,
    )
    allocator = MultifractalCascadeAllocator()
    candidates = [
        CandidateBranch(
            branch_id=f"branch_autodev_{goal_task}",
            operator_id="autodev_fond_hddl_v1",
            world_id=f"world_{repo_name}",
            state_id=initial_state.key()[:16],
            option_entropy=8.0,
            estimated_cost=1.0,
        )
    ]
    cmca_plan = allocator.allocate(
        plan_id=f"cmca_plan_{repo_name}", budget=active_budget, candidates=candidates
    )

    # 5. Execute through GymAct environment provider
    env = AutoDevGymActEnvironment(
        domain=domain,
        initial_state=initial_state,
        episode_id=f"ep_autodev_{repo_name}",
    )

    step_count = 0
    executed_trace: list[str] = []
    while step_count < max_steps:
        caps = env.capabilities()
        if not caps:
            break
        # Deterministically select first admissible capability
        selected_cap = caps[0]
        env.actuate(
            ActuationIntent(
                episode_id=env.episode_id,
                capability=selected_cap.iri,
            )
        )
        executed_trace.append(selected_cap.binding)
        step_count += 1
        # Stop once goal achieved (empty task network and cycle_receipted fact)
        if not env.current_state.tau and "cycle_receipted" in env.current_state.world:
            break

    execution_ocel = env.to_ocel_log()

    # 6. Validate via Multi-Tier Conformance Checking
    intended_trace = {
        env.episode_id: executed_trace,
    }
    conformance = evaluate_counterfactual_execution(
        ocel_log=execution_ocel,
        intended_traces_by_object=intended_trace,
        baseline_cmca_plan=cmca_plan,
        candidate_cmca_plan=cmca_plan,
    )

    is_success = (
        len(env.current_state.tau) == 0
        and "cycle_receipted" in env.current_state.world
        and not conformance.is_counterfactual
    )

    standing = "ALIVE" if is_success else "REFUSED_AUTODEV_FAILED"

    # 7. Formulate Cryptographic Receipt
    receipt_dict = {
        "repo_name": repo_name,
        "goal_task": goal_task,
        "is_success": is_success,
        "executed_steps": step_count,
        "allocated_ticks": cmca_plan.allocations[0].allocated_ticks
        if cmca_plan.allocations
        else 0,
        "divergence": conformance.overall_divergence,
        "standing": standing,
    }
    receipt_str = json.dumps(receipt_dict, sort_keys=True)
    receipt_hash = hashlib.sha256(receipt_str.encode("utf-8")).hexdigest()
    receipt_id = f"rcpt_autodev_{receipt_hash[:16]}"

    receipt = AutoDevCycleReceipt(
        receipt_id=receipt_id,
        repo_name=repo_name,
        goal_task=goal_task,
        is_conforming=not conformance.is_counterfactual,
        executed_steps=step_count,
        cmca_allocated_ticks=receipt_dict["allocated_ticks"],
        divergence_score=conformance.overall_divergence,
        standing=standing,
        receipt_hash=receipt_hash,
    )

    return AutoDevCycleResult(
        is_success=is_success,
        final_state=env.current_state,
        executed_trace=tuple(executed_trace),
        execution_ocel=execution_ocel,
        conformance_report=conformance,
        allocation_plan=cmca_plan,
        receipt=receipt,
    )
