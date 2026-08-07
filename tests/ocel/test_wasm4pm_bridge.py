# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real tests for :mod:`autofde_lab.ocel.wasm4pm_bridge`.

Skipped (not failed) when the ``wpm`` binary isn't built -- this repo's own
``UNSUPPORTED`` vocabulary for an absent optional external tool -- so the
suite stays green on a machine without ``~/wasm4pm`` checked out.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

import pytest

from autofde_lab.ocel import sqlite_store
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.wasm4pm_bridge import (
    ConformanceReport,
    DiscoveryResult,
    Wasm4pmUnavailable,
    _parse_table,
    discover_and_check,
    resolve_wpm_binary,
    session_traces_to_wasm4pm_json,
)


def _require_wpm() -> str:
    try:
        return resolve_wpm_binary()
    except Wasm4pmUnavailable as exc:
        pytest.skip(str(exc))


def test_parse_table_reads_metric_value_pairs():
    stdout = (
        "\nDiscovered Petri net (ILP miner)\n\n"
        "Metric          Value   \n"
        "Places          3       \n"
        "Fitness (self)  1.0000  \n"
    )
    metrics = _parse_table(stdout)
    assert metrics["Places"] == "3"
    assert metrics["Fitness (self)"] == "1.0000"


def _build_two_case_log() -> tuple[sqlite3.Connection, list[str]]:
    from autofde_lab.ocel.model import EventObjectLink, OcelEvent, OcelObject

    sessions = ["s1", "s2"]
    objects = [OcelObject(id=s, object_type="MCPSession", attributes=()) for s in sessions]
    events = []
    links = []
    for s_idx, session in enumerate(sessions):
        for e_idx, activity in enumerate(["decision_catalog", "decision_match", "decision_solve"]):
            event_id = f"{session}-e{e_idx}"
            events.append(
                OcelEvent(
                    id=event_id,
                    activity=activity,
                    timestamp_ns=s_idx * 100 + e_idx,
                    attributes=(),
                )
            )
            links.append(EventObjectLink(event_id=event_id, object_id=session, qualifier=None))

    log = OcelLog(
        objects=tuple(objects),
        events=tuple(events),
        event_object_links=tuple(links),
        object_object_links=(),
        object_changes=(),
    )
    log.validate()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    sqlite_store.to_sqlite(log, ":memory:")  # smoke-check to_sqlite doesn't raise on this shape
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    sqlite_store.to_sqlite(log, path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn, sessions


def test_session_traces_to_wasm4pm_json_shape():
    conn, session_ids = _build_two_case_log()
    doc = session_traces_to_wasm4pm_json(conn, session_ids)
    assert len(doc["traces"]) == 2
    for trace in doc["traces"]:
        activities = [e["attributes"][0]["value"]["content"] for e in trace["events"]]
        assert activities == ["decision_catalog", "decision_match", "decision_solve"]
        assert trace["events"][0]["attributes"][0]["value"]["type"] == "String"


def test_real_discover_and_conformance_round_trip():
    _require_wpm()
    conn, session_ids = _build_two_case_log()
    discovery, conformance = asyncio.run(discover_and_check(conn, session_ids, timeout_s=30))

    assert isinstance(discovery, DiscoveryResult)
    assert discovery.places > 0
    assert discovery.transitions > 0

    assert isinstance(conformance, ConformanceReport)
    assert conformance.total_cases == 2
    assert 0.0 <= conformance.avg_fitness <= 1.0


def test_real_conformance_against_mcp_user_simulation_log(tmp_path):
    _require_wpm()
    fixture = "notebooks/artifacts/mcp_user_simulation.ocel.json"
    try:
        data = json.loads(open(fixture).read())
    except FileNotFoundError:
        pytest.skip(f"{fixture} not present in this checkout")

    log = OcelLog.from_ocel2_json(data)
    db_path = tmp_path / "mcp_sim.sqlite"
    sqlite_store.to_sqlite(log, db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    session_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM objects WHERE object_type = 'MCPSession'"
        ).fetchall()
    ]
    assert session_ids, "expected at least one real MCPSession object in the fixture"

    discovery, conformance = asyncio.run(discover_and_check(conn, session_ids, timeout_s=60))

    # Real payoff: a Petri net mined from real session data, replayed against
    # that same data with a real (non-1.0, non-trivial) fitness measurement,
    # plus a real ETConformance precision score alongside it.
    assert discovery.places > 0
    assert conformance.total_cases == len(session_ids)
    assert 0.0 <= conformance.avg_fitness <= 1.0
    assert conformance.precision is not None
    assert 0.0 <= conformance.precision <= 1.0
    assert conformance.generalization is not None
    assert 0.0 <= conformance.generalization <= 1.0
