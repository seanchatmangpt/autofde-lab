# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Performance mining -- van der Aalst's third process-mining pillar
(discovery / conformance checking / **enhancement**), not previously present
in this repo in any form (hand-rolled or via ``wasm4pm``).

Every ``events`` row already carries a real ``timestamp_ns`` (written by
:mod:`autofde_lab.ocel.mcp_instrumentation` at the moment each MCP tool call
completed) -- this module adds no new capture code and no new schema. It
answers a real performance-mining question directly from data that has been
sitting unused in :mod:`autofde_lab.ocel.sqlite_store`'s schema since
:mod:`autofde_lab.ocel.queries` was written: *how long does the real system
wait between one MCP tool call finishing and the next one starting, per
activity, and which step is the bottleneck?*

Convention (van der Aalst, performance-mining chapter of *Process Mining:
Data Science in Action*): a "gap" is attributed to the activity that
*precedes* it -- the step that made the next one wait. Computed per session
(gaps are only meaningful within one ordered trace, never across sessions)
via :func:`autofde_lab.ocel.queries.session_event_order`, the same ordering
primitive :mod:`autofde_lab.ocel.wasm4pm_bridge` already reuses.

Like ``ocel/powl_replay.py`` and ``ocel/wasm4pm_bridge.py``, this only
computes and reports -- no actuation, no admission, no receipt semantics.
"""

from __future__ import annotations

import itertools
import sqlite3
import statistics
from dataclasses import dataclass

from autofde_lab.ocel.queries import all_session_ids, session_event_order

__all__ = [
    "ActivityDuration",
    "CaseCycleTime",
    "CaseThroughputSummary",
    "activity_durations",
    "bottleneck_ranking",
    "case_cycle_times",
    "case_throughput_summary",
    "session_waiting_times",
]


@dataclass(frozen=True)
class ActivityDuration:
    activity: str
    count: int
    mean_gap_ns: float
    p95_gap_ns: float


@dataclass(frozen=True)
class CaseCycleTime:
    session_id: str
    start_timestamp_ns: int
    end_timestamp_ns: int
    duration_ns: int
    duration_s: float
    event_count: int


@dataclass(frozen=True)
class CaseThroughputSummary:
    total_cases: int
    min_duration_ns: int
    max_duration_ns: int
    mean_duration_ns: float
    p50_duration_ns: float
    p95_duration_ns: float


def _gaps_by_preceding_activity(conn: sqlite3.Connection) -> dict[str, list[int]]:
    gaps: dict[str, list[int]] = {}
    for session_id in all_session_ids(conn):
        ordered = session_event_order(conn, session_id)
        for prev_row, next_row in itertools.pairwise(ordered):
            gap_ns = next_row["timestamp_ns"] - prev_row["timestamp_ns"]
            gaps.setdefault(prev_row["activity"], []).append(gap_ns)
    return gaps


def activity_durations(conn: sqlite3.Connection) -> list[ActivityDuration]:
    """Real per-activity wait-before-next-step statistics.

    For each activity that was directly followed by another event within the
    same session, real ``count``/``mean_gap_ns``/``p95_gap_ns`` across every
    such occurrence in the whole recorded corpus. An activity that only ever
    appeared as the last event in its session (nothing followed it) is
    absent -- there is no "gap after" to measure.
    """
    gaps = _gaps_by_preceding_activity(conn)
    results = []
    for activity, values in gaps.items():
        sorted_values = sorted(values)
        p95_index = min(len(sorted_values) - 1, round(0.95 * (len(sorted_values) - 1)))
        results.append(
            ActivityDuration(
                activity=activity,
                count=len(values),
                mean_gap_ns=statistics.fmean(values),
                p95_gap_ns=float(sorted_values[p95_index]),
            )
        )
    results.sort(key=lambda row: row.activity)
    return results


def bottleneck_ranking(conn: sqlite3.Connection) -> list[ActivityDuration]:
    """:func:`activity_durations`, sorted slowest-mean-gap first.

    "Which step between two recorded MCP tool calls costs the most real
    wall-clock time" -- answered directly, not inferred.
    """
    return sorted(
        activity_durations(conn), key=lambda row: row.mean_gap_ns, reverse=True
    )


def case_cycle_times(conn: sqlite3.Connection) -> list[CaseCycleTime]:
    """Real case-level throughput and cycle times across recorded sessions.

    Per van der Aalst (Process Mining, Chapter 9: Performance Analysis), case
    duration / throughput time is the difference between the first and last
    event timestamp in a case. Cases with 0 or 1 event have duration 0 ns.
    """
    results: list[CaseCycleTime] = []
    for session_id in all_session_ids(conn):
        events = session_event_order(conn, session_id)
        if not events:
            continue
        start_ns = events[0]["timestamp_ns"]
        end_ns = events[-1]["timestamp_ns"]
        dur_ns = max(0, end_ns - start_ns)
        results.append(
            CaseCycleTime(
                session_id=session_id,
                start_timestamp_ns=start_ns,
                end_timestamp_ns=end_ns,
                duration_ns=dur_ns,
                duration_s=dur_ns / 1e9,
                event_count=len(events),
            )
        )
    results.sort(key=lambda c: c.session_id)
    return results


def case_throughput_summary(conn: sqlite3.Connection) -> CaseThroughputSummary:
    """Aggregate statistical summary of case-level throughput / cycle times."""
    cases = case_cycle_times(conn)
    if not cases:
        return CaseThroughputSummary(
            total_cases=0,
            min_duration_ns=0,
            max_duration_ns=0,
            mean_duration_ns=0.0,
            p50_duration_ns=0.0,
            p95_duration_ns=0.0,
        )

    durations = sorted(c.duration_ns for c in cases)
    n = len(durations)
    p50_idx = min(n - 1, round(0.50 * (n - 1)))
    p95_idx = min(n - 1, round(0.95 * (n - 1)))

    return CaseThroughputSummary(
        total_cases=n,
        min_duration_ns=durations[0],
        max_duration_ns=durations[-1],
        mean_duration_ns=statistics.fmean(durations),
        p50_duration_ns=float(durations[p50_idx]),
        p95_duration_ns=float(durations[p95_idx]),
    )


def session_waiting_times(
    conn: sqlite3.Connection, session_id: str
) -> list[dict[str, int | str]]:
    """Decompose one session into intra-case transition gaps (waiting times).

    Returns a list of dicts with from_activity, to_activity, and gap_ns.
    """
    events = session_event_order(conn, session_id)
    transitions: list[dict[str, int | str]] = []
    for prev, nxt in itertools.pairwise(events):
        gap = max(0, nxt["timestamp_ns"] - prev["timestamp_ns"])
        transitions.append(
            {
                "from_activity": prev["activity"],
                "to_activity": nxt["activity"],
                "gap_ns": gap,
            }
        )
    return transitions
