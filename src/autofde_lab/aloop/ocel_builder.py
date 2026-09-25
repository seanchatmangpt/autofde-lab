# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tiny deterministic writer for ALOOP-profile OCEL 2.0 JSON documents.

It emits the literal official OCEL 2.0 JSON shape (``objectTypes``,
``eventTypes``, ``objects``, ``events``, qualified ``relationships``, object
attributes with ``time``) as plain dicts, so fixtures and mutants can be
written -- and deliberately broken -- byte by byte. Parsing and structural
admission are *not* reimplemented here: the court reuses
:class:`autofde_lab.ocel.OcelLog` for that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from autofde_lab.ocel.model import format_ns

STATIC_TIME = format_ns(0)

_OBJECT_ATTRS: dict[str, list[tuple[str, str]]] = {
    "Subject": [("sha", "string"), ("repository", "string")],
    "Consequence": [("key", "string")],
    "Authority": [("kind", "string"), ("grantedBy", "string")],
    "Evidence": [("origin", "string"), ("locator", "string"), ("sha256", "string")],
    "Receipt": [("digest", "string"), ("locator", "string")],
    "Failure": [("code", "string"), ("broken_term", "string")],
    "Human": [("role", "string")],
    "Provider": [("name", "string")],
    "WorkerRun": [("run_id", "string")],
}
_EVENT_ATTRS: dict[str, list[tuple[str, str]]] = {
    "goal.blocked": [("reason", "string")],
    "commit": [("basis", "string")],
    "actuate": [("basis", "string")],
    "human.intervene": [("basis", "string")],
}


class Builder:
    """Append-only OCEL 2.0 document builder with deterministic output."""

    def __init__(self, object_types: Sequence[str], event_types: Sequence[str]) -> None:
        self.object_types = list(object_types)
        self.event_types = list(event_types)
        self.objects: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def obj(self, oid: str, otype: str, **attrs: str) -> str:
        if oid in self._ids:
            return oid
        self._ids.add(oid)
        obj: dict[str, Any] = {"id": oid, "type": otype}
        if attrs:  # the official schema makes both arrays optional; omit when empty
            obj["attributes"] = [
                {"name": k, "value": v, "time": STATIC_TIME}
                for k, v in sorted(attrs.items())
            ]
        self.objects.append(obj)
        return oid

    def event(
        self,
        eid: str,
        etype: str,
        time_ns: int,
        rels: Iterable[tuple[str, str]],
        **attrs: str,
    ) -> str:
        event: dict[str, Any] = {"id": eid, "type": etype, "time": format_ns(time_ns)}
        if attrs:
            event["attributes"] = [
                {"name": k, "value": v} for k, v in sorted(attrs.items())
            ]
        event["relationships"] = [{"objectId": o, "qualifier": q} for q, o in rels]
        self.events.append(event)
        return eid

    def document(self) -> dict[str, Any]:
        return {
            "objectTypes": [
                {
                    "name": t,
                    "attributes": [
                        {"name": n, "type": k} for n, k in _OBJECT_ATTRS.get(t, [])
                    ],
                }
                for t in self.object_types
            ],
            "eventTypes": [
                {
                    "name": t,
                    "attributes": [
                        {"name": n, "type": k} for n, k in _EVENT_ATTRS.get(t, [])
                    ],
                }
                for t in self.event_types
            ],
            "objects": list(self.objects),
            "events": list(self.events),
        }


def dump(document: Any, path: Path) -> bytes:
    """Write ``document`` as compact key-sorted JSON (one trailing newline).

    Compact on purpose: the committed positive corpus stays under the repo's
    500 KB large-file gate while remaining the exact bytes the court reads.
    """
    data = (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(data)
    return data
