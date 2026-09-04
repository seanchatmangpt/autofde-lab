#!/usr/bin/env python3
"""
check_ocel_authority.py — falsifier over an OCEL 2.0 file.

Rule: for any Action object A, an AuthorityRefused event related to A that
is followed (in time, ties broken by log order) by an ActionStarted event
related to A, with no intervening AuthorityGranted for A, is a VIOLATION.
A REFUSED log line whose subprocess nevertheless ran is exactly this shape.

CLI:  python3 check_ocel_authority.py <file.ocel.json>
Prints JSON {"violations": [...], "actions_checked": N}; exit 1 if violations.
"""
from __future__ import annotations

import json
import sys
from typing import Any


def check(ocel: dict[str, Any]) -> dict[str, Any]:
    action_ids = {o["id"] for o in ocel.get("objects", []) if o.get("type") == "Action"}
    per_action: dict[str, list[tuple[str, int, str, str]]] = {a: [] for a in action_ids}
    for idx, ev in enumerate(ocel.get("events", [])):
        for rel in ev.get("relationships", []):
            oid = rel.get("objectId")
            if oid in per_action:
                per_action[oid].append((ev.get("time", ""), idx, ev.get("type", ""), ev.get("id", "")))
    violations = []
    for aid, evs in per_action.items():
        evs.sort()
        refused_open: str | None = None
        for _t, _i, etype, eid in evs:
            if etype == "AuthorityRefused":
                refused_open = eid
            elif etype == "AuthorityGranted":
                refused_open = None
            elif etype == "ActionStarted" and refused_open is not None:
                violations.append({"action": aid, "refused_event": refused_open, "started_event": eid})
    return {"violations": violations, "actions_checked": len(action_ids)}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"error": "usage: check_ocel_authority.py <file.ocel.json>"}))
        return 2
    with open(argv[1], encoding="utf-8") as f:
        result = check(json.load(f))
    print(json.dumps(result))
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
