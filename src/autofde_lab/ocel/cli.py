# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Typer projection of OCEL 2.0 validation, conformance checking, and digest calculations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import (
    EventObjectLink,
    OcelAttribute,
    OcelAttributeValue,
    OcelEvent,
    OcelObject,
)
from autofde_lab.ocel.object_centric_conformance import (
    check_object_centric_conformance,
)

app = typer.Typer(
    name="ocel",
    help="OCEL 2.0 event log validation, canonical SHA-256 digests, and object-centric conformance.",
    no_args_is_help=True,
)


def _emit(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def _load_ocel_log(raw_json: dict[str, Any]) -> OcelLog:
    if "events" in raw_json and "objects" in raw_json and ("eventTypes" in raw_json or "objectTypes" in raw_json):
        return OcelLog.from_ocel2_json(raw_json)

    # Support raw beam4pm capture format
    raw_events = raw_json.get("events", [])
    events: list[OcelEvent] = []
    objects_dict: dict[str, OcelObject] = {}
    e2o: list[EventObjectLink] = []

    for raw in raw_events:
        eid = str(raw.get("event_id", raw.get("id", "")))
        activity = str(raw.get("event_type", raw.get("type", "")))
        time_str = raw.get("event_time", raw.get("time"))
        t_ns = 0
        if time_str:
            try:
                from autofde_lab.ocel.model import parse_ns
                t_ns = parse_ns(time_str)
            except Exception:
                t_ns = 0

        attrs: list[OcelAttribute] = []
        for k, v in (raw.get("attributes") or {}).items():
            attrs.append(OcelAttribute(k, OcelAttributeValue.from_json(v, "string")))

        events.append(OcelEvent(eid, activity, t_ns, tuple(attrs)))

        for rel in raw.get("relationships") or []:
            oid = str(rel.get("object_id", rel.get("objectId", "")))
            qual = rel.get("qualifier")
            if oid:
                e2o.append(EventObjectLink(eid, oid, qual))
                if oid not in objects_dict:
                    objects_dict[oid] = OcelObject(oid, "meeting")

    for mid in raw_json.get("meeting_ids", []):
        if mid not in objects_dict:
            objects_dict[mid] = OcelObject(mid, "meeting")

    return OcelLog(
        objects=tuple(objects_dict.values()),
        events=tuple(events),
        event_object_links=tuple(e2o),
    )


@app.command("validate")
def validate(
    log_path: Path = typer.Argument(..., help="Path to OCEL 2.0 JSON log file"),
) -> None:
    """Validate an OCEL 2.0 log against Küsters & van der Aalst (2025) OCPQ Definition 2."""
    if not log_path.exists():
        _emit({"ok": False, "error": f"File not found: {log_path}"})
        raise typer.Exit(code=1)

    try:
        raw_json = json.loads(log_path.read_text(encoding="utf-8"))
        log = _load_ocel_log(raw_json)
        canonical_digest = log.digest()

        validation_error = None
        try:
            log.validate()
        except Exception as err:
            validation_error = str(err)
        
        _emit({
            "ok": validation_error is None,
            "canonical_digest": canonical_digest,
            "event_count": len(log.events),
            "object_count": len(log.objects),
            "validation_error": validation_error,
        })
    except Exception as exc:
        _emit({"ok": False, "error": str(exc), "type": type(exc).__name__})
        raise typer.Exit(code=2) from exc


@app.command("conformance")
def conformance(
    log_path: Path = typer.Argument(..., help="Path to observed OCEL 2.0 JSON log"),
    intended_traces_json: str = typer.Argument(..., help="JSON mapping object_id -> sequence of intended activity names"),
) -> None:
    """Perform exact object-centric conformance checking against intended object trace specifications."""
    if not log_path.exists():
        _emit({"ok": False, "error": f"File not found: {log_path}"})
        raise typer.Exit(code=1)

    try:
        raw_json = json.loads(log_path.read_text(encoding="utf-8"))
        log = _load_ocel_log(raw_json)

        p = Path(intended_traces_json)
        if p.exists() and p.is_file():
            intended_map = json.loads(p.read_text(encoding="utf-8"))
        else:
            intended_map = json.loads(intended_traces_json)

        result = check_object_centric_conformance(
            log, intended_traces_by_object_id=intended_map
        )

        _emit({
            "ok": True,
            "all_conform": result.all_conform,
            "overall_fitness": result.overall_fitness,
            "object_results": {
                r.object_id: {
                    "fitness": r.fitness,
                    "conforms": r.conforms,
                    "observed": list(r.observed_trace),
                    "intended": list(r.intended_trace),
                }
                for r in result.per_object
            },
        })
    except Exception as exc:
        _emit({"ok": False, "error": str(exc), "type": type(exc).__name__})
        raise typer.Exit(code=2) from exc
