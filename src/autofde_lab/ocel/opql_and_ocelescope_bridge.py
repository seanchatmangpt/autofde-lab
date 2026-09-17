# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration bridge for Ocelescope and OPQL over AutoFDE OCEL 2.0.

Provides:
1. Strict specification and metamodel verification via Ocelescope (DuckDB engine).
2. Declarative process querying over OCEL 2.0 structures via OPQL and SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import dataclass
from typing import Any

from autofde_lab.ocel.log import OcelLog

__all__ = [
    "OCELESCOPE_AVAILABLE",
    "OPQL_AVAILABLE",
    "OcelescopeValidationResult",
    "OpqlQueryResult",
    "execute_opql_query",
    "ocel_to_ocelescope",
    "validate_ocel_with_ocelescope",
]

try:
    import ocelescope
    from ocelescope import OCEL as OcelescopeOCEL

    OCELESCOPE_AVAILABLE = True
except ImportError:  # pragma: no cover
    ocelescope = None
    OcelescopeOCEL = None
    OCELESCOPE_AVAILABLE = False

try:
    from OPQL import SQLITEResolver, ocelimport, ocellog, querysolver

    OPQL_AVAILABLE = True
except ImportError:  # pragma: no cover
    ocelimport = None
    ocellog = None
    querysolver = None
    SQLITEResolver = None
    OPQL_AVAILABLE = False


@dataclass(frozen=True)
class OcelescopeValidationResult:
    """Result of validating an OcelLog with Ocelescope's metamodel parser."""

    is_valid: bool
    event_count: int
    object_count: int
    distinct_activities: tuple[str, ...]
    distinct_object_types: tuple[str, ...]
    error_message: str | None = None


@dataclass(frozen=True)
class OpqlQueryResult:
    """Result of executing an OPQL query over an OCEL 2.0 log."""

    is_success: bool
    matched_rows: tuple[dict[str, Any], ...]
    raw_query: str
    error_message: str | None = None


def _require_ocelescope() -> None:
    if not OCELESCOPE_AVAILABLE:
        raise RuntimeError("ocelescope is not installed or available.")


def _require_opql() -> None:
    if not OPQL_AVAILABLE:
        raise RuntimeError("OPQL is not installed or available.")


def ocel_to_ocelescope(ocel_log: OcelLog) -> Any:
    """Convert an AutoFDE OcelLog to an Ocelescope OCEL instance via JSON-OCEL."""
    _require_ocelescope()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as f:
        json.dump(ocel_log.to_ocel2_json(), f)
        f.flush()
        return OcelescopeOCEL.read(f.name)


def validate_ocel_with_ocelescope(ocel_log: OcelLog) -> OcelescopeValidationResult:
    """Validate an OcelLog structure against Ocelescope's strict parser."""
    _require_ocelescope()
    try:
        oc = ocel_to_ocelescope(ocel_log)
        df_events = oc.sql("SELECT * FROM events").fetchdf()
        df_objects = oc.sql("SELECT * FROM objects").fetchdf()

        event_count = len(df_events)
        object_count = len(df_objects)

        activities = (
            tuple(sorted(df_events["ocel:activity"].dropna().unique()))
            if "ocel:activity" in df_events.columns
            else ()
        )
        obj_types = (
            tuple(sorted(df_objects["ocel:type"].dropna().unique()))
            if "ocel:type" in df_objects.columns
            else ()
        )

        return OcelescopeValidationResult(
            is_valid=True,
            event_count=event_count,
            object_count=object_count,
            distinct_activities=activities,
            distinct_object_types=obj_types,
            error_message=None,
        )
    except Exception as e:  # noqa: BLE001
        return OcelescopeValidationResult(
            is_valid=False,
            event_count=0,
            object_count=0,
            distinct_activities=(),
            distinct_object_types=(),
            error_message=str(e),
        )


def execute_opql_query(
    ocel_log: OcelLog,
    opql_query_string: str,
) -> OpqlQueryResult:
    """Execute a declarative OPQL pattern or query over an OcelLog via OPQL's SQLite backend."""
    _require_opql()
    try:
        conn = sqlite3.connect(":memory:")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as f:
            json.dump(ocel_log.to_ocel2_json(), f)
            f.flush()
            ocelimport.loadJSON(f.name, target_db=conn)

        # Build OPQL model and parse query
        log_model = ocellog.OCELLog(conn)
        parsed_query = querysolver.scan_query(opql_query_string)
        df_res = SQLITEResolver.resolve_query(log_model, parsed_query)

        rows = tuple(df_res.to_dict(orient="records")) if df_res is not None else ()
        return OpqlQueryResult(
            is_success=True,
            matched_rows=rows,
            raw_query=opql_query_string,
            error_message=None,
        )
    except Exception as e:  # noqa: BLE001
        return OpqlQueryResult(
            is_success=False,
            matched_rows=(),
            raw_query=opql_query_string,
            error_message=str(e),
        )
