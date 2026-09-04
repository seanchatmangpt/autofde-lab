#!/usr/bin/env python3
"""Own OCEL 2.0 JSON parser for WS10 conformance (stdlib only).

Loads an OCEL 2.0 JSON document (shape as produced by tools/ocel_v2/emitter.py)
into plain dataclasses with normalized timestamps. No dependency on pm4py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class OcelObject:
    id: str
    type: str
    attrs: dict[str, Any]


@dataclass(frozen=True)
class OcelEvent:
    id: str
    type: str
    time: datetime
    time_raw: str
    attrs: dict[str, Any]
    objects: tuple[str, ...]  # related object ids, in document order


@dataclass
class OcelLog:
    object_types: dict[str, dict[str, str]]
    event_types: dict[str, dict[str, str]]
    objects: dict[str, OcelObject]
    events: list[OcelEvent] = field(default_factory=list)  # sorted by (time, doc order)

    def objects_of_type(self, otype: str) -> list[OcelObject]:
        return [o for o in self.objects.values() if o.type == otype]

    def related_of_type(self, ev: OcelEvent, otype: str) -> list[str]:
        return [oid for oid in ev.objects if oid in self.objects and self.objects[oid].type == otype]

    def events_of_type(self, *etypes: str) -> list[OcelEvent]:
        s = set(etypes)
        return [e for e in self.events if e.type in s]


def parse_time(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _attrs_of(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {a["name"]: a.get("value") for a in items or []}


def parse_ocel(doc: dict[str, Any]) -> OcelLog:
    object_types = {t["name"]: {a["name"]: a["type"] for a in t.get("attributes", [])}
                    for t in doc.get("objectTypes", [])}
    event_types = {t["name"]: {a["name"]: a["type"] for a in t.get("attributes", [])}
                   for t in doc.get("eventTypes", [])}
    objects: dict[str, OcelObject] = {}
    for o in doc.get("objects", []):
        objects[o["id"]] = OcelObject(id=o["id"], type=o["type"], attrs=_attrs_of(o.get("attributes")))
    events: list[OcelEvent] = []
    for i, e in enumerate(doc.get("events", [])):
        events.append(OcelEvent(
            id=e["id"], type=e["type"], time=parse_time(e["time"]), time_raw=e["time"],
            attrs=_attrs_of(e.get("attributes")),
            objects=tuple(r["objectId"] for r in e.get("relationships", [])),
        ))
    order = {e.id: i for i, e in enumerate(events)}
    events.sort(key=lambda e: (e.time, order[e.id]))
    return OcelLog(object_types, event_types, objects, events)


def load_ocel(path: str) -> OcelLog:
    with open(path, "r", encoding="utf-8") as f:
        return parse_ocel(json.load(f))
