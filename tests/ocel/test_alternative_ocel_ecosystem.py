# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Comprehensive test suite verifying alternative OCEL 2.0 libraries with POWL and HDDL.

Exercises:
1. Columnar projection with Polars & DuckDB (ocel-rs parity).
2. OCPA multi-object synchronization delay calculation across concurrent objects.
3. Software engineering lifecycle extraction (pystackt parity) into OCEL 2.0.
4. HDDL-to-POWL hierarchical decomposition and conformance validation.
"""

from __future__ import annotations

import pytest

from autofde_lab.ocel.columnar_polars import (
    DUCKDB_AVAILABLE,
    POLARS_AVAILABLE,
    columnar_summary_metrics,
    ocel_to_duckdb,
    ocel_to_polars_tables,
)
from autofde_lab.ocel.hddl_powl_ocel_bridge import (
    HddlMethodDecomposition,
    project_hddl_to_powl_traces,
    validate_ocel_against_hddl_powl,
)
from autofde_lab.ocel.lifecycle_pystackt import (
    GitCommitRecord,
    extract_git_lifecycle_to_ocel,
)
from autofde_lab.ocel.log import EventObjectLink, OcelEvent, OcelLog, OcelObject
from autofde_lab.ocel.ocpa_metrics import (
    OCPA_AVAILABLE,
    calculate_object_synchronization_delays,
    ocel_to_ocpa_object_centric_event_log,
)


@pytest.fixture
def sample_ocel_log() -> OcelLog:
    """Fixture producing a multi-object lifecycle log."""
    events = [
        OcelEvent(id="e1", activity="observe", timestamp_ns=1_000_000_000),
        OcelEvent(id="e2", activity="select", timestamp_ns=2_000_000_000),
        OcelEvent(id="e3", activity="construct", timestamp_ns=3_000_000_000),
        OcelEvent(id="e4", activity="actuate", timestamp_ns=5_000_000_000),
        OcelEvent(id="e5", activity="receipt", timestamp_ns=6_000_000_000),
    ]
    objects = (
        OcelObject(id="session_1", object_type="Session"),
        OcelObject(id="worker_a", object_type="Agent"),
        OcelObject(id="res_db", object_type="Resource"),
    )
    links = (
        EventObjectLink(event_id="e1", object_id="session_1"),
        EventObjectLink(event_id="e2", object_id="session_1"),
        EventObjectLink(event_id="e3", object_id="session_1"),
        EventObjectLink(event_id="e4", object_id="session_1"),
        EventObjectLink(event_id="e4", object_id="worker_a"),
        EventObjectLink(event_id="e4", object_id="res_db"),
        EventObjectLink(event_id="e5", object_id="session_1"),
        EventObjectLink(event_id="e5", object_id="worker_a"),
    )
    return OcelLog(events=tuple(events), objects=objects, event_object_links=links)


def test_columnar_polars_and_duckdb_projection(sample_ocel_log):
    """Verify high-throughput columnar transformation and DuckDB SQL queryability."""
    if not POLARS_AVAILABLE or not DUCKDB_AVAILABLE:
        pytest.skip("polars or duckdb unavailable")

    tables = ocel_to_polars_tables(sample_ocel_log)
    assert "events" in tables
    assert "objects" in tables
    assert len(tables["events"]) == 5
    assert len(tables["objects"]) == 3

    metrics = columnar_summary_metrics(tables)
    assert metrics["total_events"] == 5
    assert metrics["total_objects"] == 3
    assert metrics["total_e2o_links"] == 8

    # Query with DuckDB SQL
    conn = ocel_to_duckdb(sample_ocel_log)
    res = conn.execute(
        "SELECT activity, count(*) as c FROM ocel_events GROUP BY activity ORDER BY c DESC"
    ).fetchall()
    assert len(res) == 5


def test_ocpa_synchronization_delays(sample_ocel_log):
    """Verify OCPA-style multi-object synchronization delay calculation."""
    metrics = calculate_object_synchronization_delays(sample_ocel_log)

    # e4 is a multi-object join with session_1, worker_a, and res_db
    e4_metrics = [m for m in metrics if m.event_id == "e4"]
    assert len(e4_metrics) >= 1
    for m in e4_metrics:
        assert m.delay_seconds >= 0.0

    if OCPA_AVAILABLE:
        ocpa_log = ocel_to_ocpa_object_centric_event_log(sample_ocel_log)
        assert ocpa_log is not None


def test_pystackt_software_lifecycle_extraction():
    """Verify extraction of git commits and review workflows into OCEL 2.0."""
    commits = [
        GitCommitRecord(
            commit_sha="c1a2b3c4d5",
            author="engineer_1",
            timestamp_iso="2026-09-15T00:00:00Z",
            message="feat(pplan): implement P-PLAN control plane",
            affected_files=("lib/ash_pplan.ex", "planning/control_plane.hddl"),
            pr_number="12",
            verification_status="PASSED",
        ),
        GitCommitRecord(
            commit_sha="d5e6f7a8b9",
            author="engineer_2",
            timestamp_iso="2026-09-15T00:15:00Z",
            message="fix(r2rml): add 1-safe workflow net check",
            affected_files=("lib/ash_r2rml/powl.ex",),
            pr_number="13",
            verification_status="PASSED",
        ),
    ]

    ocel = extract_git_lifecycle_to_ocel("ash_pplan", commits)

    assert len(ocel.events) == 4  # 2 commits + 2 verifications
    assert any(obj.object_type == "Repository" for obj in ocel.objects)
    assert any(obj.object_type == "Developer" for obj in ocel.objects)
    assert any(obj.object_type == "PullRequest" for obj in ocel.objects)


def test_hddl_to_powl_decomposition_and_ocel_validation():
    """Verify mapping of HDDL methods (like ash_pplan) to POWL models and trace conformance."""
    methods = [
        HddlMethodDecomposition(
            method_name="compose_owners",
            task_name="deliver_controlled_process",
            subtasks=(
                "decompose_hddl",
                "validate_fond",
                "compile_reactor",
                "observe_and_receipt",
            ),
        ),
        HddlMethodDecomposition(
            method_name="atomic_decompose",
            task_name="decompose_hddl",
            subtasks=("parse_syntax", "check_hierarchy"),
        ),
        HddlMethodDecomposition(
            method_name="atomic_observe",
            task_name="observe_and_receipt",
            subtasks=("record_telemetry", "generate_receipt"),
        ),
    ]

    expanded_traces = project_hddl_to_powl_traces("deliver_controlled_process", methods)
    assert len(expanded_traces) == 1
    assert expanded_traces[0] == [
        "parse_syntax",
        "check_hierarchy",
        "validate_fond",
        "compile_reactor",
        "record_telemetry",
        "generate_receipt",
    ]

    # Conforming trace
    lawful_trace = [
        "parse_syntax",
        "check_hierarchy",
        "validate_fond",
        "compile_reactor",
        "record_telemetry",
        "generate_receipt",
    ]
    res = validate_ocel_against_hddl_powl(
        "deliver_controlled_process", methods, lawful_trace
    )
    assert res.is_valid_powl_trace is True
    assert res.conformance.trace_fitness == 1.0

    # Counterfactual mutant trace: early receipt before compilation
    counterfactual_trace = [
        "generate_receipt",
        "parse_syntax",
        "check_hierarchy",
        "validate_fond",
        "compile_reactor",
        "record_telemetry",
    ]
    cf_res = validate_ocel_against_hddl_powl(
        "deliver_controlled_process", methods, counterfactual_trace
    )
    assert cf_res.is_valid_powl_trace is False
    assert cf_res.conformance.trace_fitness < 1.0
