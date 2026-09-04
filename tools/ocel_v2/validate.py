#!/usr/bin/env python3
"""Strict validator for OCEL 2.0 JSON files.

Checks:
  1. strict_type_mismatches: every object's declared type exists in
     objectTypes, and every attribute on that object matches the type
     declared for it in objectTypes (by name and Python-level type).
  2. duplicate_ids: no duplicate object ids or event ids.
  3. dangling_refs: every relationship/objectId reference inside an event
     (event["relationships"][i]["objectId"]) resolves to a real object id.

CLI:
    python3 validate.py <file.json>

Prints a JSON summary to stdout:
    {"strict_type_mismatches": N, "duplicate_ids": N, "dangling_refs": N}

Exit code 0 only if all three counts are zero, else exit code 1.
"""
from __future__ import annotations

import json
import sys
from typing import Any


# OCEL 2.0 attribute "type" strings -> Python types they must match.
_OCEL_TYPE_TO_PY = {
    "string": str,
    "float": float,
    "integer": int,
    "boolean": bool,
    "time": str,  # timestamps are represented as ISO strings in JSON OCEL
    # emitter.py's single documented nested-JSON escape hatch: a str that
    # must itself parse as JSON (checked in _python_type_matches).
    "string:canonical-json": str,
}


def _python_type_matches(value: Any, ocel_type: str) -> bool:
    """Return True if `value` is a valid Python representation of `ocel_type`."""
    expected = _OCEL_TYPE_TO_PY.get(ocel_type)
    if expected is None:
        # Unknown declared type -> cannot validate structurally; treat as mismatch.
        return False
    if expected is float:
        # JSON ints are valid floats; bool is a subclass of int, exclude it.
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is bool:
        return isinstance(value, bool)
    if expected is str:
        if ocel_type == "string:canonical-json":
            if not isinstance(value, str):
                return False
            try:
                json.loads(value)
            except ValueError:
                return False
            return True
        return isinstance(value, str)
    return isinstance(value, expected)


def validate(ocel: dict) -> dict:
    strict_type_mismatches = 0
    duplicate_ids = 0
    dangling_refs = 0

    object_types = ocel.get("objectTypes", [])
    # Map: type name -> {attr name -> declared ocel type string}
    type_attr_defs: dict[str, dict[str, str]] = {}
    known_object_type_names: set[str] = set()
    for ot in object_types:
        name = ot.get("name")
        known_object_type_names.add(name)
        attr_defs: dict[str, str] = {}
        for attr in ot.get("attributes", []):
            attr_defs[attr.get("name")] = attr.get("type")
        type_attr_defs[name] = attr_defs

    objects = ocel.get("objects", [])
    events = ocel.get("events", [])

    # --- duplicate id check (objects + events share id-namespace concerns
    # separately per OCEL 2.0: object ids must be unique among objects,
    # event ids must be unique among events) ---
    seen_object_ids: set[str] = set()
    object_id_set: set[str] = set()
    for obj in objects:
        oid = obj.get("id")
        if oid in seen_object_ids:
            duplicate_ids += 1
        else:
            seen_object_ids.add(oid)
        object_id_set.add(oid)

    seen_event_ids: set[str] = set()
    for ev in events:
        eid = ev.get("id")
        if eid in seen_event_ids:
            duplicate_ids += 1
        else:
            seen_event_ids.add(eid)

    # --- object type + attribute type validation ---
    for obj in objects:
        otype = obj.get("type")
        if otype not in known_object_type_names:
            strict_type_mismatches += 1
            continue  # can't check attrs against an unknown type definition
        attr_defs = type_attr_defs.get(otype, {})
        for attr_val in obj.get("attributes", []):
            attr_name = attr_val.get("name")
            value = attr_val.get("value")
            declared_type = attr_defs.get(attr_name)
            if declared_type is None:
                # attribute not declared for this object type at all
                strict_type_mismatches += 1
                continue
            if not _python_type_matches(value, declared_type):
                strict_type_mismatches += 1

    # --- dangling relationship/objectId reference check ---
    for ev in events:
        for rel in ev.get("relationships", []):
            ref_id = rel.get("objectId")
            if ref_id not in object_id_set:
                dangling_refs += 1

    return {
        "strict_type_mismatches": strict_type_mismatches,
        "duplicate_ids": duplicate_ids,
        "dangling_refs": dangling_refs,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"error": "usage: validate.py <file.json>"}))
        return 1

    path = argv[1]
    with open(path, "r", encoding="utf-8") as f:
        ocel = json.load(f)

    summary = validate(ocel)
    print(json.dumps(summary))

    if all(v == 0 for v in summary.values()):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
