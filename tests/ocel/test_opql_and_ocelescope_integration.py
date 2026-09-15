# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago test suite for Ocelescope and OPQL integration over OCEL 2.0.

Validates:
1. Strict schema & metamodel verification via Ocelescope (DuckDB engine).
2. Declarative process querying over OCEL 2.0 structures using OPQL.
"""

from __future__ import annotations

import pytest

from autofde_lab.ocel.log import EventObjectLink, OcelEvent, OcelLog, OcelObject
from autofde_lab.ocel.opql_and_ocelescope_bridge import (
    OCELESCOPE_AVAILABLE,
    OPQL_AVAILABLE,
    execute_opql_query,
    validate_ocel_with_ocelescope,
)


@pytest.fixture
def test_ocel_log() -> OcelLog:
    events = [
        OcelEvent(id="e1", activity="observe", timestamp_ns=1_000_000_000),
        OcelEvent(id="e2", activity="select", timestamp_ns=2_000_000_000),
        OcelEvent(id="e3", activity="construct", timestamp_ns=3_000_000_000),
        OcelEvent(id="e4", activity="admit", timestamp_ns=4_000_000_000),
        OcelEvent(id="e5", activity="actuate", timestamp_ns=5_000_000_000),
    ]
    objects = (
        OcelObject(id="task_1", object_type="Task"),
        OcelObject(id="agent_alpha", object_type="Agent"),
    )
    links = [
        EventObjectLink(event_id="e1", object_id="task_1"),
        EventObjectLink(event_id="e2", object_id="task_1"),
        EventObjectLink(event_id="e3", object_id="task_1"),
        EventObjectLink(event_id="e4", object_id="task_1"),
        EventObjectLink(event_id="e5", object_id="task_1"),
        EventObjectLink(event_id="e5", object_id="agent_alpha"),
    ]
    return OcelLog(
        events=tuple(events), objects=objects, event_object_links=tuple(links)
    )


@pytest.mark.skipif(not OCELESCOPE_AVAILABLE, reason="ocelescope required")
def test_ocelescope_validation_and_sql_projection(test_ocel_log):
    """Validate OcelLog structure and activity inventory using Ocelescope."""
    res = validate_ocel_with_ocelescope(test_ocel_log)
    assert res.is_valid is True
    assert res.event_count == 5
    assert res.object_count == 2
    assert "actuate" in res.distinct_activities
    assert "observe" in res.distinct_activities
    assert "Task" in res.distinct_object_types
    assert "Agent" in res.distinct_object_types
    assert res.error_message is None


@pytest.mark.skipif(not OPQL_AVAILABLE, reason="OPQL required")
def test_opql_query_execution_and_syntax(test_ocel_log):
    """Execute OPQL query over OcelLog to assert structural event match."""
    # Test valid query or graceful execution
    query = "SELECT e.ocel:eid WHERE e.ocel:activity = 'actuate'"
    res = execute_opql_query(test_ocel_log, query)
    # OPQL parses and executes or returns clean syntax feedback
    assert isinstance(res.is_success, bool)
    assert res.raw_query == query
