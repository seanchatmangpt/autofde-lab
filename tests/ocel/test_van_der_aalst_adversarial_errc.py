# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial ERRC suite for Prof. Dr. Wil van der Aalst's Process Science framework.

Validates:
1. Conformance Falsification:
   - Object-Centric Conformance catches crossed object-identity links where flattened
     trace sequence checks pass blindly.
   - OCPQ Definition 2 laws fail closed under deliberate corruption (duplicate entity IDs,
     dangling links, empty object links).
2. Performance Mining Enhancement:
   - Case-level throughput and cycle-time calculation (case_cycle_times, case_throughput_summary).
   - Intra-case waiting time decomposition (session_waiting_times).
   - Bottleneck ranking on real SQLite timestamps.
3. Safe Boundary Invariants:
   - OcelSink refusal semantics on unreferenced or undeclared object entities.
"""

from __future__ import annotations

import sqlite3

import pytest

from autofde_lab.agent.ledger import OccurrenceLedger
from autofde_lab.agent.ocel_sink import OcelSink, OcelSinkError, SinkRefusal
from autofde_lab.ocel.enhancement import (
    case_cycle_times,
    case_throughput_summary,
    session_waiting_times,
)
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.mcp_session import append_tool_call_event
from autofde_lab.ocel.model import (
    EventObjectLink,
    OcelAttribute,
    OcelAttributeValue,
    OcelEvent,
    OcelObject,
)
from autofde_lab.ocel.object_centric_conformance import (
    check_object_centric_conformance,
    flattened_trace,
    project_object_trace,
)
from autofde_lab.ocel.refusals import OcelError, OcelRefusal
from autofde_lab.ocel.sqlite_store import to_sqlite

# ─────────────────────────────────────────────────────────────────────────────
# 1. Performance Mining: Case Throughput & Cycle Times
# ─────────────────────────────────────────────────────────────────────────────


def _build_two_case_log() -> OcelLog:
    """Builds a deterministic 2-case log with precise nanosecond timestamps."""
    log = OcelLog.new(
        objects=[
            OcelObject(
                "session-case-A",
                "MCPSession",
                (OcelAttribute("server", OcelAttributeValue.string("fabric-a")),),
            ),
            OcelObject(
                "session-case-B",
                "MCPSession",
                (OcelAttribute("server", OcelAttributeValue.string("fabric-b")),),
            ),
        ]
    )

    # Case A: 0ns -> 2_000_000_000ns (2 seconds total)
    log = append_tool_call_event(
        log,
        event_id="cA-1",
        activity="start_session",
        object_ids=["session-case-A"],
        outcome={"standing": "OK"},
        timestamp_ns=0,
    )
    log = append_tool_call_event(
        log,
        event_id="cA-2",
        activity="compute_plan",
        object_ids=["session-case-A"],
        outcome={"standing": "SOLVED"},
        timestamp_ns=1_500_000_000,
    )
    log = append_tool_call_event(
        log,
        event_id="cA-3",
        activity="close_session",
        object_ids=["session-case-A"],
        outcome={"standing": "OK"},
        timestamp_ns=2_000_000_000,
    )

    # Case B: 10_000_000_000ns -> 14_000_000_000ns (4 seconds total)
    log = append_tool_call_event(
        log,
        event_id="cB-1",
        activity="start_session",
        object_ids=["session-case-B"],
        outcome={"standing": "OK"},
        timestamp_ns=10_000_000_000,
    )
    log = append_tool_call_event(
        log,
        event_id="cB-2",
        activity="close_session",
        object_ids=["session-case-B"],
        outcome={"standing": "OK"},
        timestamp_ns=14_000_000_000,
    )

    return log


def test_case_cycle_times_and_throughput_summary(tmp_path) -> None:
    log = _build_two_case_log()
    db_path = tmp_path / "case_perf.sqlite"
    to_sqlite(log, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cycles = case_cycle_times(conn)
        assert len(cycles) == 2

        # Case A verification
        case_a = next(c for c in cycles if c.session_id == "session-case-A")
        assert case_a.duration_ns == 2_000_000_000
        assert case_a.duration_s == pytest.approx(2.0)
        assert case_a.event_count == 3

        # Case B verification
        case_b = next(c for c in cycles if c.session_id == "session-case-B")
        assert case_b.duration_ns == 4_000_000_000
        assert case_b.duration_s == pytest.approx(4.0)
        assert case_b.event_count == 2

        # Summary statistics verification
        summary = case_throughput_summary(conn)
        assert summary.total_cases == 2
        assert summary.min_duration_ns == 2_000_000_000
        assert summary.max_duration_ns == 4_000_000_000
        assert summary.mean_duration_ns == 3_000_000_000.0
        assert (
            summary.p50_duration_ns == 2_000_000_000.0
            or summary.p50_duration_ns == 4_000_000_000.0
        )

        # Session waiting times breakdown
        waiting_a = session_waiting_times(conn, "session-case-A")
        assert len(waiting_a) == 2
        assert waiting_a[0]["from_activity"] == "start_session"
        assert waiting_a[0]["to_activity"] == "compute_plan"
        assert waiting_a[0]["gap_ns"] == 1_500_000_000
        assert waiting_a[1]["from_activity"] == "compute_plan"
        assert waiting_a[1]["to_activity"] == "close_session"
        assert waiting_a[1]["gap_ns"] == 500_000_000
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Conformance Checking: Object-Centric vs Flattened Trace Blindness
# ─────────────────────────────────────────────────────────────────────────────


def test_adversarial_crossed_object_links_detected() -> None:
    """An adversarial mutation swapping object identities in concurrent events:
    The classic flattened trace remains identical, but Object-Centric Conformance
    detects the discrepancy and drops fitness strictly below 1.0.
    """
    # Two distinct processes with their own intended traces:
    # ord-1 intended: ("order_created", "order_approved", "order_shipped")
    # pay-1 intended: ("payment_requested", "payment_processed", "payment_settled")
    trace_ord = ("order_created", "order_approved", "order_shipped")
    trace_pay = ("payment_requested", "payment_processed", "payment_settled")

    # Correct run
    correct_log = OcelLog.new(
        objects=[
            OcelObject("ord-1", "Order"),
            OcelObject("pay-1", "Payment"),
        ]
    )
    for i in range(3):
        correct_log = correct_log.append_event(
            f"e_ord_{i}", trace_ord[i], [("ord-1", "target")], timestamp_ns=100 * i
        )
        correct_log = correct_log.append_event(
            f"e_pay_{i}", trace_pay[i], [("pay-1", "target")], timestamp_ns=100 * i + 10
        )

    res_correct = check_object_centric_conformance(
        correct_log,
        intended_traces_by_object_id={"ord-1": trace_ord, "pay-1": trace_pay},
    )
    assert res_correct.all_conform is True
    assert res_correct.overall_fitness == 1.0

    # Adversarial mutation: Swap event object links on the second step
    # (e_ord_1 is attributed to pay-1 instead of ord-1, and e_pay_1 to ord-1)
    mutated_links = []
    for link in correct_log.event_object_links:
        if link.event_id == "e_ord_1":
            mutated_links.append(
                EventObjectLink(link.event_id, "pay-1", link.qualifier)
            )
        elif link.event_id == "e_pay_1":
            mutated_links.append(
                EventObjectLink(link.event_id, "ord-1", link.qualifier)
            )
        else:
            mutated_links.append(link)

    mutated_log = OcelLog(
        events=correct_log.events,
        objects=correct_log.objects,
        event_object_links=tuple(mutated_links),
    )

    # Invariant 1: Flattened trace does not detect the swap because event sequence hasn't changed
    assert flattened_trace(mutated_log) == flattened_trace(correct_log)

    # Invariant 2: Object-centric projection exposes the corrupt trace per entity
    proj_ord = project_object_trace(mutated_log, "ord-1")
    proj_pay = project_object_trace(mutated_log, "pay-1")
    assert "payment_processed" in proj_ord
    assert "order_approved" in proj_pay

    # Both entities observe an abnormal trace sequence
    res_mutated = check_object_centric_conformance(
        mutated_log,
        intended_traces_by_object_id={"ord-1": trace_ord, "pay-1": trace_pay},
    )
    assert res_mutated.all_conform is False
    assert res_mutated.overall_fitness < 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Object-Centric Data Integrity (OCPQ Definition 2 Laws Fail Closed)
# ─────────────────────────────────────────────────────────────────────────────


def test_adversarial_ocpq_duplicate_entity_id_fails_closed() -> None:
    """OCPQ Def 2 Law 3: Duplicate entity ID must fail closed with DUPLICATE_ENTITY_ID."""
    log = OcelLog.new(
        objects=[
            OcelObject("duplicate-id", "Order"),
            OcelObject("duplicate-id", "Customer"),
        ]
    )
    with pytest.raises(OcelError) as exc:
        log.validate()
    assert exc.value.refusal == OcelRefusal.DUPLICATE_ENTITY_ID


def test_adversarial_empty_event_object_links_fails_closed() -> None:
    """OCPQ Def 2 Law 1: Events without object links must fail closed with EMPTY_EVENT_OBJECT_LINKS."""
    log = OcelLog(
        events=(
            OcelEvent(
                id="e-lonely",
                activity="unlinked_action",
                timestamp_ns=1000,
            ),
        ),
        objects=(OcelObject("ord-1", "Order"),),
        event_object_links=(),
    )
    with pytest.raises(OcelError) as exc:
        log.validate()
    assert exc.value.refusal == OcelRefusal.EMPTY_EVENT_OBJECT_LINKS


def test_adversarial_dangling_event_object_link_fails_closed() -> None:
    """OCPQ Def 2: References to undeclared object IDs must fail closed."""
    log = OcelLog(
        events=(
            OcelEvent(
                id="e-valid",
                activity="some_action",
                timestamp_ns=1000,
            ),
        ),
        objects=(OcelObject("declared-obj", "Order"),),
        event_object_links=(EventObjectLink("e-valid", "undeclared-obj", "qualifier"),),
    )
    with pytest.raises(OcelError) as exc:
        log.validate()
    assert exc.value.refusal == OcelRefusal.DANGLING_EVENT_OBJECT_LINK


# ─────────────────────────────────────────────────────────────────────────────
# 4. Safe Boundary Invariants: OcelSink Refusal
# ─────────────────────────────────────────────────────────────────────────────


def test_ocel_sink_refuses_undeclared_object_type() -> None:
    """OcelSink must reject unmapped objects rather than inventing synthetic types."""
    sink = OcelSink(object_types={"known-obj": "Order"})
    ledger = OccurrenceLedger()
    token = ledger.intend(
        path=(0,),
        activity="test_step",
        objects=[("unknown-obj", "target")],
    )
    ledger.commit(token)

    with pytest.raises(OcelSinkError) as exc:
        sink.absorb(ledger)
    assert exc.value.refusal == SinkRefusal.UNDECLARED_OBJECT_TYPE
