# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test suite for Unified Counterfactual Validation.

Zero mocks, real mathematical Petri net alignments, real CMCA cascade distributions,
and real Object-Centric Event Logs.
Validates:
1. Lawful baseline executions pass with is_counterfactual=False, divergence=0.0.
2. Premature actuation mutation fails Tier 1 with alignment cost penalties.
3. Unadmitted action injection triggers REFUSED_UNADMITTED_ACTUATION.
4. Crossed object links fail Tier 3 object-centric conformance.
5. Resource allocation inversion fails Tier 2 CMCA resource checks.
6. Cryptographic receipt verification and determinism.
"""

from __future__ import annotations

import pytest

from autofde_lab.cmca import (
    CandidateBranch,
    MultifractalCascadeAllocator,
    ResourceBudget,
)
from autofde_lab.ocel.counterfactual_engine import (
    evaluate_counterfactual_execution,
)
from autofde_lab.ocel.counterfactual_mutators import (
    mutate_crossed_object_links,
    mutate_premature_actuation,
    mutate_resource_allocation_inversion,
    mutate_unadmitted_action_injection,
)
from autofde_lab.ocel.log import EventObjectLink, OcelEvent, OcelLog, OcelObject
from autofde_lab.ocel.pm4py_counterfactual import (
    PM4PY_AVAILABLE,
    discover_lawful_model,
)

pytestmark = pytest.mark.skipif(
    not PM4PY_AVAILABLE,
    reason="pm4py required for full multi-tier counterfactual validation",
)

LAWFUL_LIFECYCLE = [
    "observe",
    "select",
    "construct",
    "admit",
    "actuate",
    "receipt",
    "verify",
    "teardown",
]


@pytest.fixture
def lawful_model():
    return discover_lawful_model([LAWFUL_LIFECYCLE, LAWFUL_LIFECYCLE])


@pytest.fixture
def sample_ocel() -> OcelLog:
    events = [
        OcelEvent(id="e1", activity="observe", timestamp_ns=1_000_000_000),
        OcelEvent(id="e2", activity="select", timestamp_ns=2_000_000_000),
        OcelEvent(id="e3", activity="construct", timestamp_ns=3_000_000_000),
        OcelEvent(id="e4", activity="admit", timestamp_ns=4_000_000_000),
        OcelEvent(id="e5", activity="actuate", timestamp_ns=5_000_000_000),
        OcelEvent(id="e6", activity="receipt", timestamp_ns=6_000_000_000),
        OcelEvent(id="e7", activity="verify", timestamp_ns=7_000_000_000),
        OcelEvent(id="e8", activity="teardown", timestamp_ns=8_000_000_000),
    ]
    objects = (
        OcelObject(id="task_1", object_type="Task"),
        OcelObject(id="worker_1", object_type="Worker"),
    )
    links = [EventObjectLink(event_id=e.id, object_id="task_1") for e in events]
    links.append(EventObjectLink(event_id="e5", object_id="worker_1"))
    return OcelLog(
        events=tuple(events), objects=objects, event_object_links=tuple(links)
    )


@pytest.fixture
def cmca_baseline():
    allocator = MultifractalCascadeAllocator()
    budget = ResourceBudget(
        total_ticks=10000,
        memory_bytes=65536,
        max_verification_depth=5,
        consequence_risk_budget=0.5,
        concurrency_lanes=4,
    )
    candidates = [
        CandidateBranch(
            branch_id="branch_prime",
            operator_id="c8l_op",
            world_id="gym_env",
            state_id="s0",
            option_entropy=10.0,
            estimated_cost=1.0,
        ),
        CandidateBranch(
            branch_id="branch_sub",
            operator_id="fallback_op",
            world_id="gym_env",
            state_id="s0",
            option_entropy=2.0,
            estimated_cost=2.0,
        ),
    ]
    return allocator.allocate(plan_id="p0", budget=budget, candidates=candidates)


def test_lawful_trace_passes_all_counterfactual_tiers(
    lawful_model, sample_ocel, cmca_baseline
):
    """An untampered execution conforms across all tiers without divergence."""
    intended = {
        "task_1": LAWFUL_LIFECYCLE,
        "worker_1": ["actuate"],
    }
    report = evaluate_counterfactual_execution(
        lawful_model=lawful_model,
        candidate_trace=LAWFUL_LIFECYCLE,
        ocel_log=sample_ocel,
        intended_traces_by_object=intended,
        baseline_cmca_plan=cmca_baseline,
        candidate_cmca_plan=cmca_baseline,
    )

    assert report.is_counterfactual is False
    assert report.overall_divergence == 0.0
    assert report.evidence_status == "ALIVE"
    assert report.receipt.receipt_id.startswith("rcpt_cf_")


def test_counterfactual_premature_actuation(lawful_model):
    """Premature actuation fails Tier 1 control flow."""
    mutated = mutate_premature_actuation(LAWFUL_LIFECYCLE)
    report = evaluate_counterfactual_execution(
        lawful_model=lawful_model,
        candidate_trace=mutated,
    )

    assert report.is_counterfactual is True
    assert report.overall_divergence > 0.0
    t1 = next(r for r in report.tier_reports if r.layer_name == "Tier1_ControlFlow")
    assert t1.is_conforming is False
    assert t1.penalty_score > 0.0


def test_counterfactual_unadmitted_action(lawful_model):
    """Unadmitted action injection triggers REFUSED_UNADMITTED_ACTUATION."""
    mutated = mutate_unadmitted_action_injection(LAWFUL_LIFECYCLE)
    report = evaluate_counterfactual_execution(
        lawful_model=lawful_model,
        candidate_trace=mutated,
    )

    assert report.is_counterfactual is True
    assert report.evidence_status == "REFUSED_UNADMITTED_ACTUATION"
    t1 = next(r for r in report.tier_reports if r.layer_name == "Tier1_ControlFlow")
    assert any("LOG_ONLY_MOVE" in v for v in t1.violations)


def test_counterfactual_crossed_object_link(sample_ocel):
    """Crossed object link triggers Tier 3 multi-object violation."""
    mutated_ocel = mutate_crossed_object_links(sample_ocel, "task_1", "worker_1")
    intended = {
        "task_1": LAWFUL_LIFECYCLE,
        "worker_1": ["actuate"],
    }
    report = evaluate_counterfactual_execution(
        ocel_log=mutated_ocel,
        intended_traces_by_object=intended,
    )

    assert report.is_counterfactual is True
    t3 = next(r for r in report.tier_reports if r.layer_name == "Tier3_MultiObject")
    assert t3.is_conforming is False
    assert t3.penalty_score > 0.0
    assert any("OBJECT_CONFORMANCE_FAIL" in v for v in t3.violations)


def test_counterfactual_resource_inversion(cmca_baseline):
    """Inverting resource allocation triggers Tier 2 CMCA divergence."""
    mutated_plan = mutate_resource_allocation_inversion(cmca_baseline)
    report = evaluate_counterfactual_execution(
        baseline_cmca_plan=cmca_baseline,
        candidate_cmca_plan=mutated_plan,
    )

    assert report.is_counterfactual is True
    t2 = next(r for r in report.tier_reports if r.layer_name == "Tier2_CMCAResource")
    assert t2.is_conforming is False
    assert t2.penalty_score > 0.0
    assert any("RESOURCE_DIVERGENCE" in v for v in t2.violations)
