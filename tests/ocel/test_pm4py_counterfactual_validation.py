# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test suite for PM4Py counterfactual process validation.

Validates:
1. Real inductive Petri net discovery over lawful AutoFDE / GymAct lifecycles.
2. Perfect conformance (fitness 1.0, cost 0) for lawful traces.
3. Quantified detection of adversarial counterfactual mutations:
   - Premature Actuation (actuating before inspection/admission)
   - Unadmitted Step Injection (rogue unreceipted command)
   - Incomplete Cycle (skipped receipt/teardown)
   - Object Lifecycle Concurrency & Link integrity via OcelLog conversion.
"""

from __future__ import annotations

import pytest

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import EventObjectLink, OcelEvent, OcelObject
from autofde_lab.ocel.pm4py_counterfactual import (
    PM4PY_AVAILABLE,
    discover_lawful_model,
    evaluate_counterfactual_trace,
    ocel_to_pm4py_log,
)

pytestmark = pytest.mark.skipif(
    not PM4PY_AVAILABLE,
    reason="pm4py is required for counterfactual validation tests",
)

LAWFUL_AGENT_LIFECYCLE = [
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
def lawful_agent_model():
    """Build a real Petri net model from lawful agent execution traces."""
    training_traces = [
        LAWFUL_AGENT_LIFECYCLE,
        LAWFUL_AGENT_LIFECYCLE,
        LAWFUL_AGENT_LIFECYCLE,
    ]
    return discover_lawful_model(training_traces)


def test_lawful_trace_achieves_perfect_conformance(lawful_agent_model):
    """A completely lawful execution trace scores fitness 1.0 and zero alignment cost."""
    result = evaluate_counterfactual_trace(lawful_agent_model, LAWFUL_AGENT_LIFECYCLE)

    assert result.is_conforming is True
    assert result.trace_fitness == 1.0
    assert result.alignment_cost == 0
    assert result.missing_tokens == 0
    assert result.remaining_tokens == 0
    assert len(result.deviations) == 0
    assert result.evidence_status == "ALIVE"


def test_counterfactual_premature_actuation_fails(lawful_agent_model):
    """Counterfactual: Actuate immediately without observe/select/construct/admit."""
    counterfactual_trace = [
        "actuate",
        "observe",
        "select",
        "construct",
        "admit",
        "receipt",
        "verify",
        "teardown",
    ]

    result = evaluate_counterfactual_trace(lawful_agent_model, counterfactual_trace)

    assert result.is_conforming is False
    assert result.trace_fitness < 1.0
    assert result.alignment_cost > 0
    assert result.has_deviations is True

    # Check that deviations identify the misplaced actuation
    [(d.log_move, d.model_move) for d in result.deviations]
    # In alignment: actuate was performed in log when model was expecting observe
    assert any(
        d.log_move == "actuate" or d.model_move == "observe" for d in result.deviations
    )


def test_counterfactual_unadmitted_action_injection(lawful_agent_model):
    """Counterfactual: Injecting an unadmitted rogue action creates log-only move with penalty."""
    counterfactual_trace = [
        "observe",
        "select",
        "construct",
        "admit",
        "unadmitted_privilege_escalation",
        "actuate",
        "receipt",
        "verify",
        "teardown",
    ]

    result = evaluate_counterfactual_trace(lawful_agent_model, counterfactual_trace)

    assert result.is_conforming is False
    assert result.alignment_cost > 0
    assert result.has_deviations is True

    # The unadmitted step must be flagged as a log move without a model counterpart
    rogue_deviations = [
        d
        for d in result.deviations
        if d.log_move == "unadmitted_privilege_escalation" and d.model_move is None
    ]
    assert len(rogue_deviations) == 1


def test_counterfactual_skipped_teardown(lawful_agent_model):
    """Counterfactual: Omitting the mandatory teardown leaves remaining tokens and model-only moves."""
    counterfactual_trace = [
        "observe",
        "select",
        "construct",
        "admit",
        "actuate",
        "receipt",
        "verify",
        # teardown skipped
    ]

    result = evaluate_counterfactual_trace(lawful_agent_model, counterfactual_trace)

    assert result.is_conforming is False
    assert result.alignment_cost > 0
    assert (
        result.remaining_tokens > 0
        or result.missing_tokens > 0
        or result.trace_fitness < 1.0
    )

    # Alignment should indicate model expected teardown
    teardown_skips = [
        d
        for d in result.deviations
        if d.model_move == "teardown" and d.log_move is None
    ]
    assert len(teardown_skips) == 1


def test_ocel_log_to_pm4py_conversion_and_validation():
    """Convert an AutoFDE OcelLog with multiple objects and check object-centric conformance."""
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
        OcelObject(id="task_alpha", object_type="Task"),
        OcelObject(id="worker_0", object_type="Worker"),
    )
    # Link all events to task_alpha
    links = [
        EventObjectLink(event_id=e.id, object_id="task_alpha", qualifier="primary")
        for e in events
    ]
    # Link only actuate to worker_0
    links.append(
        EventObjectLink(event_id="e5", object_id="worker_0", qualifier="executor")
    )

    ocel_log = OcelLog(
        events=tuple(events),
        objects=objects,
        event_object_links=tuple(links),
    )

    # 1. Project per object to PM4Py
    pm_log = ocel_to_pm4py_log(ocel_log, group_by_object=True)
    assert len(pm_log) == 2

    # Discover model on lawful trace
    lawful_model = discover_lawful_model([LAWFUL_AGENT_LIFECYCLE])

    # 2. Extract task_alpha trace from PM4Py EventLog
    task_trace = next(t for t in pm_log if t.attributes["concept:name"] == "task_alpha")
    task_result = evaluate_counterfactual_trace(
        lawful_model, [e["concept:name"] for e in task_trace]
    )
    assert task_result.is_conforming is True
    assert task_result.trace_fitness == 1.0

    # 3. Worker_0 only executed ['actuate'], which is non-conforming to the full lifecycle
    worker_trace = next(t for t in pm_log if t.attributes["concept:name"] == "worker_0")
    worker_result = evaluate_counterfactual_trace(
        lawful_model, [e["concept:name"] for e in worker_trace]
    )
    assert worker_result.is_conforming is False
    assert worker_result.trace_fitness < 1.0
    assert worker_result.alignment_cost > 0
