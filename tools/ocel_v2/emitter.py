#!/usr/bin/env python3
"""
emitter.py — Append-only OCEL 2.0 JSON log writer for the "Crown-2" process.

OCEL 2.0 JSON structure produced by this module:

{
  "objectTypes": [ {"name": str, "attributes": [{"name": str, "type": str}, ...]}, ... ],
  "eventTypes":  [ {"name": str, "attributes": [{"name": str, "type": str}, ...]}, ... ],
  "objects": [
     {"id": str, "type": str, "attributes": [{"name": str, "value": <typed>, "time": iso8601}, ...]}
  ],
  "events": [
     {"id": str, "type": str, "time": iso8601,
      "attributes": [{"name": str, "value": <typed>}, ...],
      "relationships": [{"objectId": str, "qualifier": str}, ...]}
  ]
}

Design rules enforced by this emitter:

1. Every object type and event type declares its attribute names AND types up
   front in objectTypes/eventTypes, before any object/event referencing that
   type is written. Adding an object/event with an attribute name not
   declared for its type is a hard error (fail-closed schema).

2. No attribute is ever typed "string" while actually holding nested JSON
   (a dict or list). Attribute values must be one of OCEL 2.0's primitive
   types: string, int, float (aliases: "float"/"time"/"boolean" honored),
   OR the value must be pre-serialized into the single documented escape
   hatch: an attribute whose declared type is exactly
   "string:canonical-json" — the value is then required to be a
   json.dumps(..., sort_keys=True) string, so nested structure is
   findable/auditable without silently masquerading as an ordinary string.
   Passing a live dict/list for any attribute NOT declared
   "string:canonical-json" is a hard error.

3. Append-only: init() creates a fresh log; add_object/add_event only ever
   append to the objects/events arrays (and, the first time a given type is
   seen at runtime, attribute declarations are validated against the
   up-front schema — never silently widened).

CLI:
    python3 emitter.py init <out.json>
    python3 emitter.py add-object <out.json> <type> <id> <json-attrs>
    python3 emitter.py add-event <out.json> <type> <id> <json-attrs> <comma-sep-related-object-ids>

<json-attrs> is a JSON object string, e.g. '{"branch": "main", "sha": "abc123"}'.
For an attribute that is genuinely nested JSON, declare its type in the
schema as "string:canonical-json" and pass the JSON as a STRING value, e.g.
'{"payload_json": "{\\"k\\": 1}"}' — the emitter will validate it parses.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Schema: object types
# ---------------------------------------------------------------------------

OBJECT_TYPES: dict[str, list[dict[str, str]]] = {
    "Composition": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "description", "type": "string"},
    ],
    "Repository": [
        {"name": "path", "type": "string"},
        {"name": "remote_url", "type": "string"},
        {"name": "default_branch", "type": "string"},
    ],
    "Commit": [
        {"name": "sha", "type": "string"},
        {"name": "author", "type": "string"},
        {"name": "message", "type": "string"},
        {"name": "committed_at", "type": "time"},
    ],
    "Worktree": [
        {"name": "path", "type": "string"},
        {"name": "branch", "type": "string"},
        {"name": "base_ref", "type": "string"},
    ],
    "Domain": [
        {"name": "name", "type": "string"},
        {"name": "description", "type": "string"},
    ],
    "WorldState": [
        {"name": "label", "type": "string"},
        {"name": "observed_at", "type": "time"},
        {"name": "state_json", "type": "string:canonical-json"},
    ],
    "SolverImplementation": [
        {"name": "name", "type": "string"},
        {"name": "kind", "type": "string"},
        {"name": "version", "type": "string"},
        # Crown-2 attempt 2: explicit nativeness assertion ('native' | 'python'),
        # append-only extension; the falsifier keys on implementation == 'native'.
        {"name": "implementation", "type": "string"},
    ],
    "Policy": [
        {"name": "name", "type": "string"},
        {"name": "policy_json", "type": "string:canonical-json"},
    ],
    "Plan": [
        {"name": "summary", "type": "string"},
        {"name": "steps_json", "type": "string:canonical-json"},
        {"name": "cost_estimate", "type": "float"},
    ],
    "PredictionReceipt": [
        {"name": "prediction_json", "type": "string:canonical-json"},
        {"name": "confidence", "type": "float"},
        {"name": "frozen_at", "type": "time"},
    ],
    "AuthorityDecision": [
        {"name": "decision", "type": "string"},
        {"name": "rationale", "type": "string"},
        {"name": "decided_at", "type": "time"},
    ],
    "Action": [
        {"name": "name", "type": "string"},
        {"name": "kind", "type": "string"},
        {"name": "args_json", "type": "string:canonical-json"},
    ],
    "QualificationRun": [
        {"name": "name", "type": "string"},
        {"name": "result", "type": "string"},
        {"name": "metrics_json", "type": "string:canonical-json"},
    ],
    "Receipt": [
        {"name": "kind", "type": "string"},
        {"name": "digest", "type": "string"},
        {"name": "issued_at", "type": "time"},
    ],
    "ClaudeSession": [
        {"name": "session_url", "type": "string"},
        {"name": "model", "type": "string"},
        {"name": "started_at", "type": "time"},
    ],
    "ClaudeToolInvocation": [
        {"name": "tool_name", "type": "string"},
        {"name": "args_json", "type": "string:canonical-json"},
        {"name": "result_summary", "type": "string"},
    ],
    "ClaudeSubagent": [
        {"name": "name", "type": "string"},
        {"name": "role", "type": "string"},
    ],
    "ProcessEpisode": [
        {"name": "label", "type": "string"},
        {"name": "started_at", "type": "time"},
        {"name": "ended_at", "type": "time"},
    ],
    # Crown-2 Task H: hook-to-ocel.py relates every Claude.* event to a
    # Machine:<hostname> object; declared here so those relationships resolve.
    "Machine": [
        {"name": "hostname", "type": "string"},
    ],
}

# ---------------------------------------------------------------------------
# Schema: event types
# ---------------------------------------------------------------------------

EVENT_TYPES: dict[str, list[dict[str, str]]] = {
    "CompositionCreated": [
        {"name": "name", "type": "string"},
    ],
    "WorldStateObserved": [
        {"name": "label", "type": "string"},
        {"name": "state_json", "type": "string:canonical-json"},
    ],
    "PlannerInvoked": [
        {"name": "solver_name", "type": "string"},
    ],
    "PlanProduced": [
        {"name": "summary", "type": "string"},
        {"name": "cost_estimate", "type": "float"},
    ],
    "PlanRefused": [
        {"name": "reason", "type": "string"},
    ],
    "PredictionFrozen": [
        {"name": "confidence", "type": "float"},
    ],
    "AuthorityEvaluated": [
        {"name": "rationale", "type": "string"},
    ],
    "AuthorityGranted": [
        {"name": "rationale", "type": "string"},
    ],
    "AuthorityRefused": [
        {"name": "rationale", "type": "string"},
    ],
    "ActionStarted": [
        {"name": "name", "type": "string"},
    ],
    "ActionCompleted": [
        {"name": "name", "type": "string"},
        {"name": "result_summary", "type": "string"},
    ],
    "ActionFailed": [
        {"name": "name", "type": "string"},
        {"name": "error", "type": "string"},
    ],
    "ActionRefused": [
        {"name": "name", "type": "string"},
        {"name": "reason", "type": "string"},
    ],
    "QualificationObserved": [
        {"name": "result", "type": "string"},
        {"name": "metrics_json", "type": "string:canonical-json"},
    ],
    "PredictionCompared": [
        {"name": "delta_json", "type": "string:canonical-json"},
    ],
    "ReceiptIssued": [
        {"name": "digest", "type": "string"},
    ],
    "LoopStarted": [
        {"name": "label", "type": "string"},
    ],
    "LoopClosed": [
        {"name": "label", "type": "string"},
    ],
    "LoopBlocked": [
        {"name": "reason", "type": "string"},
    ],
    # Native planner bootstrap (Crown-2 Task C): one Started, then one
    # Completed OR one Failed per bootstrap episode; per-step detail rides on
    # ActionStarted/ActionCompleted/ActionFailed against Action objects.
    "NativePlannerBootstrapStarted": [
        {"name": "worktree", "type": "string"},
        {"name": "sha", "type": "string"},
    ],
    "NativePlannerBootstrapCompleted": [
        {"name": "extension_path", "type": "string"},
        {"name": "solve_summary_json", "type": "string:canonical-json"},
    ],
    "NativePlannerBootstrapFailed": [
        {"name": "failing_step", "type": "string"},
        {"name": "error", "type": "string"},
    ],
    # Crown-2 Task H: control-heartbeat episode (validate.py over the growing
    # sink every 10s). Never carries production semantics.
    "HeartbeatObserved": [
        {"name": "seq", "type": "int"},
        {"name": "monotonic_seconds", "type": "float"},
        {"name": "events_so_far", "type": "int"},
        {"name": "validate_json", "type": "string:canonical-json"},
    ],
    # Crown-2 Task H: Claude Code hook events, built by the real
    # ~/.claude/scripts/hook-to-ocel.py build_ocel_event(payload). Nested
    # tool_input/tool_response ride on canonical-json attributes; hook_event_id
    # is the adapter's own uuid so the two records are cross-referenceable.
    "Claude.PreToolUse": [
        {"name": "hook_event_id", "type": "string"},
        {"name": "hook_event_name", "type": "string"},
        {"name": "tool_name", "type": "string"},
        {"name": "cwd", "type": "string"},
        {"name": "permission_mode", "type": "string"},
        {"name": "tool_input", "type": "string:canonical-json"},
    ],
    "Claude.PostToolUse": [
        {"name": "hook_event_id", "type": "string"},
        {"name": "hook_event_name", "type": "string"},
        {"name": "tool_name", "type": "string"},
        {"name": "cwd", "type": "string"},
        {"name": "permission_mode", "type": "string"},
        {"name": "tool_input", "type": "string:canonical-json"},
        {"name": "tool_response", "type": "string:canonical-json"},
        {"name": "is_error", "type": "boolean"},
    ],
}

# OCEL 2.0 primitive attribute types this emitter accepts, plus the one
# documented escape hatch for pre-serialized nested JSON.
_PRIMITIVE_TYPES = {"string", "int", "float", "boolean", "time"}
_CANONICAL_JSON_TYPE = "string:canonical-json"
_ALLOWED_TYPES = _PRIMITIVE_TYPES | {_CANONICAL_JSON_TYPE}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_type_decls(schema: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    decls = []
    for name, attrs in schema.items():
        for a in attrs:
            if a["type"] not in _ALLOWED_TYPES:
                raise ValueError(
                    f"schema error: {name}.{a['name']} has unsupported type "
                    f"{a['type']!r} (allowed: {sorted(_ALLOWED_TYPES)})"
                )
        decls.append({"name": name, "attributes": copy.deepcopy(attrs)})
    return decls


def _attr_schema_for(schema: dict[str, list[dict[str, str]]], type_name: str) -> dict[str, str]:
    if type_name not in schema:
        raise ValueError(f"unknown type {type_name!r}; declared types: {sorted(schema)}")
    return {a["name"]: a["type"] for a in schema[type_name]}


def _validate_and_wrap_value(attr_name: str, declared_type: str, value: Any) -> Any:
    """
    Enforce rule 2: reject live dict/list for any attribute not declared
    string:canonical-json. For string:canonical-json attributes, the value
    must already be a JSON string that parses cleanly (i.e. the caller
    pre-serialized it) — this keeps nested structure explicit and auditable
    rather than silently masquerading as an ordinary "string" attribute.
    """
    if declared_type == _CANONICAL_JSON_TYPE:
        if isinstance(value, (dict, list)):
            # Convenience: caller passed live JSON for a canonical-json field —
            # canonicalize it here rather than forcing a pre-stringified value.
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        if not isinstance(value, str):
            raise ValueError(
                f"attribute {attr_name!r} is declared {_CANONICAL_JSON_TYPE!r}; "
                f"value must be a JSON string or a dict/list, got {type(value).__name__}"
            )
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"attribute {attr_name!r} declared {_CANONICAL_JSON_TYPE!r} but its "
                f"string value is not valid JSON: {e}"
            ) from e
        # Re-canonicalize for determinism (sorted keys, no incidental whitespace).
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"))

    # Non-canonical-json attribute: nested JSON is never allowed here.
    if isinstance(value, (dict, list)):
        raise ValueError(
            f"attribute {attr_name!r} is declared {declared_type!r} but a "
            f"dict/list was passed — nested JSON must use an attribute "
            f"declared {_CANONICAL_JSON_TYPE!r} instead of masquerading as "
            f"{declared_type!r}"
        )

    if declared_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"attribute {attr_name!r} declared int, got {type(value).__name__}")
    elif declared_type == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"attribute {attr_name!r} declared float, got {type(value).__name__}")
        value = float(value)
    elif declared_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"attribute {attr_name!r} declared boolean, got {type(value).__name__}")
    elif declared_type in ("string", "time"):
        if not isinstance(value, str):
            raise ValueError(f"attribute {attr_name!r} declared {declared_type}, got {type(value).__name__}")

    return value


def init(out_path: str) -> dict[str, Any]:
    """Create a fresh, empty-but-valid OCEL 2.0 log at out_path (overwrites)."""
    log = {
        "objectTypes": _build_type_decls(OBJECT_TYPES),
        "eventTypes": _build_type_decls(EVENT_TYPES),
        "objects": [],
        "events": [],
    }
    _write(out_path, log)
    return log


def _read(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, log: dict[str, Any]) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp_path, path)


def add_object(out_path: str, obj_type: str, obj_id: str, attrs: dict[str, Any]) -> dict[str, Any]:
    log = _read(out_path)
    schema = _attr_schema_for(OBJECT_TYPES, obj_type)

    unknown = set(attrs) - set(schema)
    if unknown:
        raise ValueError(
            f"object type {obj_type!r} has no declared attribute(s) {sorted(unknown)}; "
            f"declared: {sorted(schema)}"
        )

    ts = _now_iso()
    wrapped_attrs = []
    for name, value in attrs.items():
        wrapped_attrs.append(
            {"name": name, "value": _validate_and_wrap_value(name, schema[name], value), "time": ts}
        )

    if any(o["id"] == obj_id for o in log["objects"]):
        raise ValueError(f"object id {obj_id!r} already exists (append-only log; ids must be unique)")

    log["objects"].append({"id": obj_id, "type": obj_type, "attributes": wrapped_attrs})
    _write(out_path, log)
    return log


def add_event(
    out_path: str,
    event_type: str,
    event_id: str,
    attrs: dict[str, Any],
    related_object_ids: list[str],
    qualifiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """qualifiers: optional {object_id: qualifier}; ids absent from it keep the
    historical empty qualifier, so every prior caller is unchanged."""
    log = _read(out_path)
    schema = _attr_schema_for(EVENT_TYPES, event_type)

    unknown = set(attrs) - set(schema)
    if unknown:
        raise ValueError(
            f"event type {event_type!r} has no declared attribute(s) {sorted(unknown)}; "
            f"declared: {sorted(schema)}"
        )

    known_object_ids = {o["id"] for o in log["objects"]}
    missing = [oid for oid in related_object_ids if oid not in known_object_ids]
    if missing:
        raise ValueError(f"event {event_id!r} references unknown object id(s): {missing}")

    if any(e["id"] == event_id for e in log["events"]):
        raise ValueError(f"event id {event_id!r} already exists (append-only log; ids must be unique)")

    wrapped_attrs = []
    for name, value in attrs.items():
        wrapped_attrs.append({"name": name, "value": _validate_and_wrap_value(name, schema[name], value)})

    qualifiers = qualifiers or {}
    relationships = [{"objectId": oid, "qualifier": qualifiers.get(oid, "")} for oid in related_object_ids]

    log["events"].append(
        {
            "id": event_id,
            "type": event_type,
            "time": _now_iso(),
            "attributes": wrapped_attrs,
            "relationships": relationships,
        }
    )
    _write(out_path, log)
    return log


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _usage() -> None:
    print(__doc__)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _usage()
        return 2

    cmd = argv[1]
    try:
        if cmd == "init":
            if len(argv) != 3:
                raise ValueError("usage: emitter.py init <out.json>")
            out_path = argv[2]
            log = init(out_path)
            print(json.dumps(log, indent=2))

        elif cmd == "add-object":
            if len(argv) != 6:
                raise ValueError("usage: emitter.py add-object <out.json> <type> <id> <json-attrs>")
            out_path, obj_type, obj_id, json_attrs = argv[2], argv[3], argv[4], argv[5]
            attrs = json.loads(json_attrs)
            if not isinstance(attrs, dict):
                raise ValueError("<json-attrs> must be a JSON object")
            log = add_object(out_path, obj_type, obj_id, attrs)
            print(json.dumps(log, indent=2))

        elif cmd == "add-event":
            if len(argv) != 7:
                raise ValueError(
                    "usage: emitter.py add-event <out.json> <type> <id> <json-attrs> <comma-sep-related-object-ids>"
                )
            out_path, event_type, event_id, json_attrs, related_csv = (
                argv[2],
                argv[3],
                argv[4],
                argv[5],
                argv[6],
            )
            attrs = json.loads(json_attrs)
            if not isinstance(attrs, dict):
                raise ValueError("<json-attrs> must be a JSON object")
            related_ids = [x.strip() for x in related_csv.split(",") if x.strip()]
            log = add_event(out_path, event_type, event_id, attrs, related_ids)
            print(json.dumps(log, indent=2))

        else:
            _usage()
            return 2

    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
