"""OCEL 2.0 projection and independent invariant court for Fortune-5 simulation."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .model import EventRecord, FinalReceipt, KnownRoute, PreparedReceipt, WorldSpec


def _attr_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    return "string"


def project_events_to_ocel2(
    *,
    run_id: str,
    world: WorldSpec,
    events: tuple[EventRecord, ...],
    prepared: tuple[PreparedReceipt, ...],
    final: tuple[FinalReceipt, ...],
    routes: tuple[KnownRoute, ...],
) -> dict[str, object]:
    object_rows: dict[str, dict[str, object]] = {}

    def add_object(object_id: str, object_type: str, attrs: dict[str, object]) -> None:
        object_rows.setdefault(
            object_id,
            {
                "id": object_id,
                "type": object_type,
                "attributes": [
                    {"name": key, "time": 0, "value": value}
                    for key, value in sorted(attrs.items())
                ],
                "relationships": [],
            },
        )

    add_object(run_id, "Episode", {"world_digest": world.world_digest})
    add_object(
        world.world_digest,
        "World",
        {"scenario_id": world.scenario_id, "ontology_version": world.ontology_version},
    )
    for region in world.regions:
        add_object(
            region.region_id,
            "Region",
            {"cloud": region.cloud, "failure_domain": region.failure_domain},
        )
    for service in world.services:
        add_object(
            service.service_id,
            "Service",
            {
                "name": service.name,
                "region_id": service.region_id,
                "layer": service.layer,
                "criticality": service.criticality,
            },
        )
    for fault in world.faults:
        add_object(
            fault.fault_id,
            "Fault",
            {
                "kind": fault.kind,
                "target_service": fault.target_service,
                "severity": fault.severity,
                "round_index": fault.round_index,
            },
        )
    for receipt in prepared:
        add_object(
            receipt.receipt_id,
            "PreparedReceipt",
            {
                "command_id": receipt.command_id,
                "authority_grant_id": receipt.authority_grant_id,
                "target_service": receipt.target_service,
                "pre_state_digest": receipt.pre_state_digest,
            },
        )
    for receipt in final:
        add_object(
            receipt.receipt_id,
            "Receipt",
            {
                "command_id": receipt.command_id,
                "target_service": receipt.target_service,
                "success": receipt.success,
                "postcondition_verified": receipt.postcondition_verified,
                "pre_state_digest": receipt.pre_state_digest,
                "post_state_digest": receipt.post_state_digest,
            },
        )
    for route in routes:
        add_object(
            route.route_id,
            "KnownRoute",
            {
                "signature": route.signature,
                "action": route.action,
                "qualification_receipt_id": route.qualification_receipt_id,
                "successful_replays": route.successful_replays,
            },
        )

    ref_type = {
        "message": "A2AMessage",
        "command": "Command",
        "permission": "Permission",
        "prepared_receipt": "PreparedReceipt",
        "receipt": "Receipt",
        "route": "KnownRoute",
        "fault": "Fault",
    }
    for event in events:
        for object_id, qualifier in event.object_refs:
            add_object(
                object_id, ref_type.get(qualifier, "Entity"), {"qualifier": qualifier}
            )

    event_rows: list[dict[str, object]] = []
    event_types: dict[str, dict[str, str]] = {}
    for event in sorted(events, key=lambda item: (item.timestamp_ns, item.event_id)):
        attrs = dict(event.attributes)
        event_types.setdefault(
            event.event_type, {key: _attr_type(value) for key, value in attrs.items()}
        )
        event_rows.append(
            {
                "id": event.event_id,
                "type": event.event_type,
                "time": event.timestamp_ns,
                "attributes": [
                    {"name": key, "value": value}
                    for key, value in sorted(attrs.items())
                ],
                "relationships": [
                    {"objectId": object_id, "qualifier": qualifier}
                    for object_id, qualifier in sorted(event.object_refs)
                ],
            }
        )

    type_to_attrs: dict[str, dict[str, str]] = defaultdict(dict)
    for row in object_rows.values():
        for attr in row["attributes"]:
            type_to_attrs[str(row["type"])][str(attr["name"])] = _attr_type(
                attr["value"]
            )

    return {
        "objectTypes": [
            {
                "name": object_type,
                "attributes": [
                    {"name": key, "type": attr_type}
                    for key, attr_type in sorted(attributes.items())
                ],
            }
            for object_type, attributes in sorted(type_to_attrs.items())
        ],
        "eventTypes": [
            {
                "name": event_type,
                "attributes": [
                    {"name": key, "type": attr_type}
                    for key, attr_type in sorted(attributes.items())
                ],
            }
            for event_type, attributes in sorted(event_types.items())
        ],
        "objects": [object_rows[key] for key in sorted(object_rows)],
        "events": event_rows,
    }


def _event_attrs(event: dict[str, Any]) -> dict[str, object]:
    return {str(item["name"]): item["value"] for item in event.get("attributes", [])}


def _event_refs(event: dict[str, Any]) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = defaultdict(set)
    for item in event.get("relationships", []):
        refs[str(item["qualifier"])].add(str(item["objectId"]))
    return refs


def verify_ocel2(document: dict[str, object]) -> dict[str, object]:
    """Re-derive authority, receipt, idempotency and causal invariants from OCEL only."""
    required = {"objectTypes", "eventTypes", "objects", "events"}
    missing = sorted(required - set(document))
    if missing:
        return {
            "ok": False,
            "violations": [f"MISSING_TOP_LEVEL:{name}" for name in missing],
            "actuations": 0,
            "unreceipted_actuations": 0,
            "authority_violations": 0,
            "duplicate_effects": 0,
        }

    events = list(document.get("events", []))
    objects = {
        str(row["id"]): row
        for row in document.get("objects", [])
        if isinstance(row, dict) and "id" in row
    }
    receipts_by_command: dict[str, set[str]] = defaultdict(set)
    for object_id, row in objects.items():
        if row.get("type") != "Receipt":
            continue
        attrs = {str(item["name"]): item["value"] for item in row.get("attributes", [])}
        command_id = str(attrs.get("command_id", ""))
        if command_id:
            receipts_by_command[command_id].add(object_id)

    actuation_commands: list[str] = []
    unreceipted = 0
    authority_violations = 0
    violations: list[str] = []
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "actuate":
            continue
        attrs = _event_attrs(event)
        refs = _event_refs(event)
        command_id = str(attrs.get("command_id", ""))
        actuation_commands.append(command_id)
        if not command_id:
            violations.append(f"ACTUATION_WITHOUT_COMMAND:{event.get('id')}")
        if not refs.get("permission"):
            authority_violations += 1
            violations.append(f"ACTUATION_WITHOUT_PERMISSION:{event.get('id')}")
        if not refs.get("prepared_receipt"):
            unreceipted += 1
            violations.append(f"ACTUATION_WITHOUT_PREPARED_RECEIPT:{event.get('id')}")
        if not receipts_by_command.get(command_id):
            unreceipted += 1
            violations.append(f"ACTUATION_WITHOUT_FINAL_RECEIPT:{event.get('id')}")

    duplicates = sum(
        count - 1 for count in Counter(actuation_commands).values() if count > 1
    )
    if duplicates:
        violations.append(f"DUPLICATE_EFFECTS:{duplicates}")

    by_command: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            continue
        attrs = _event_attrs(event)
        command_id = str(attrs.get("command_id", ""))
        if command_id:
            by_command[command_id].append(
                (int(event.get("time", 0)), str(event.get("type", "")))
            )
    precedence = ("authorize", "prepare_receipt", "actuate", "receipt", "verify")
    for command_id, rows in by_command.items():
        rows.sort()
        observed = [kind for _, kind in rows if kind in precedence]
        if "actuate" in observed:
            positions = {kind: observed.index(kind) for kind in observed}
            for before, after in zip(precedence, precedence[1:]):
                if (
                    before in positions
                    and after in positions
                    and positions[before] > positions[after]
                ):
                    violations.append(f"CAUSAL_ORDER:{command_id}:{before}>{after}")

    return {
        "ok": not violations,
        "violations": violations,
        "actuations": len(actuation_commands),
        "unreceipted_actuations": unreceipted,
        "authority_violations": authority_violations,
        "duplicate_effects": duplicates,
        "objects": len(objects),
        "events": len(events),
    }


__all__ = ["project_events_to_ocel2", "verify_ocel2"]
