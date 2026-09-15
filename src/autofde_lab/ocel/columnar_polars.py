# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""High-performance columnar projection of OCEL 2.0 logs using Polars and DuckDB.

Provides zero-copy / streaming columnar transformation for high-throughput
event logs emitted from Ash resources (e.g. ash_ex4pm and ash_a2a telemetry forwarder),
mirroring ocel-rs performance characteristics via Polars DataFrames and DuckDB queries.
"""

from __future__ import annotations

from typing import Any

from autofde_lab.ocel.log import OcelLog

__all__ = [
    "DUCKDB_AVAILABLE",
    "POLARS_AVAILABLE",
    "columnar_summary_metrics",
    "ocel_to_duckdb",
    "ocel_to_polars_tables",
]

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:  # pragma: no cover
    pl = None
    POLARS_AVAILABLE = False

try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:  # pragma: no cover
    duckdb = None
    DUCKDB_AVAILABLE = False


def _require_polars() -> None:
    if not POLARS_AVAILABLE:
        raise RuntimeError("polars is required for columnar OCEL operations.")


def _require_duckdb() -> None:
    if not DUCKDB_AVAILABLE:
        raise RuntimeError("duckdb is required for SQL OCEL analytics.")


def ocel_to_polars_tables(ocel_log: OcelLog) -> dict[str, Any]:
    """Convert an OcelLog into a set of high-speed Polars DataFrames.

    Returns a dict containing:
    - 'events': DataFrame of (id, activity, timestamp_ns)
    - 'objects': DataFrame of (id, object_type)
    - 'e2o_links': DataFrame of (event_id, object_id, qualifier)
    - 'o2o_links': DataFrame of (source_id, target_id, qualifier)
    """
    _require_polars()

    # Events table
    events_data = {
        "event_id": [e.id for e in ocel_log.events],
        "activity": [e.activity for e in ocel_log.events],
        "timestamp_ns": [e.timestamp_ns for e in ocel_log.events],
    }
    df_events = pl.DataFrame(events_data)

    # Objects table
    objects_data = {
        "object_id": [obj.id for obj in ocel_log.objects],
        "object_type": [obj.object_type for obj in ocel_log.objects],
    }
    df_objects = pl.DataFrame(objects_data)

    # E2O links table
    links_data = {
        "event_id": [link.event_id for link in ocel_log.event_object_links],
        "object_id": [link.object_id for link in ocel_log.event_object_links],
        "qualifier": [link.qualifier for link in ocel_log.event_object_links],
    }
    df_e2o = pl.DataFrame(links_data)

    # O2O links table
    o2o_data = {
        "source_id": [link.source_id for link in ocel_log.object_object_links],
        "target_id": [link.target_id for link in ocel_log.object_object_links],
        "qualifier": [link.qualifier for link in ocel_log.object_object_links],
    }
    df_o2o = pl.DataFrame(o2o_data)

    return {
        "events": df_events,
        "objects": df_objects,
        "e2o_links": df_e2o,
        "o2o_links": df_o2o,
    }


def columnar_summary_metrics(tables: dict[str, Any]) -> dict[str, Any]:
    """Compute instant aggregation metrics over the columnar Polars tables."""
    _require_polars()
    df_events = tables["events"]
    df_objects = tables["objects"]
    df_e2o = tables["e2o_links"]

    total_events = len(df_events)
    total_objects = len(df_objects)
    total_links = len(df_e2o)

    activities_count = (
        df_events.group_by("activity").count().sort("count", descending=True)
        if total_events > 0
        else pl.DataFrame()
    )

    objects_by_type = (
        df_objects.group_by("object_type").count().sort("count", descending=True)
        if total_objects > 0
        else pl.DataFrame()
    )

    return {
        "total_events": total_events,
        "total_objects": total_objects,
        "total_e2o_links": total_links,
        "activities_count": activities_count.to_dicts() if total_events > 0 else [],
        "objects_by_type": objects_by_type.to_dicts() if total_objects > 0 else [],
    }


def ocel_to_duckdb(ocel_log: OcelLog, conn: Any = None) -> Any:
    """Register OCEL tables as views or tables inside a DuckDB in-memory database."""
    _require_duckdb()
    tables = ocel_to_polars_tables(ocel_log)
    if conn is None:
        conn = duckdb.connect(database=":memory:")

    # Register polars dataframes directly into DuckDB without copying
    df_events = tables["events"]
    df_objects = tables["objects"]
    df_e2o = tables["e2o_links"]
    df_o2o = tables["o2o_links"]

    conn.register("ocel_events", df_events)
    conn.register("ocel_objects", df_objects)
    conn.register("ocel_e2o", df_e2o)
    conn.register("ocel_o2o", df_o2o)

    return conn
