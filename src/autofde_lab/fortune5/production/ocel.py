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


def _object_attrs(row: dict[str, Any]) -> dict[str, object]:
    return {str(item["name"]): item["value"] for item in row.get("attributes", [])}


def verify_ocel2(document: dict[str, object]) -> dict[str, object]:
    """Re-derive execution invariants from OCEL only.

    A permission reference is not sufficient evidence of authority.  For every
    attempted DO the court requires one matching authorize event, one prepared
    receipt, one final receipt, one verification event, exact subject/object
    binding, and strict causal order.
    """
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
            "causal_violations": 0,
            "receipt_binding_violations": 0,
        }

    events = [
        event for event in document.get("events", []) if isinstance(event, dict)
    ]
    objects = {
        str(row["id"]): row
        for row in document.get("objects", [])
        if isinstance(row, dict) and "id" in row
    }

    receipts_by_command: dict[str, set[str]] = defaultdict(set)
    prepared_by_command: dict[str, set[str]] = defaultdict(set)
    for object_id, row in objects.items():
        attrs = _object_attrs(row)
        command_id = str(attrs.get("command_id", ""))
        if not command_id:
            continue
        if row.get("type") == "Receipt":
            receipts_by_command[command_id].add(object_id)
        elif row.get("type") == "PreparedReceipt":
            prepared_by_command[command_id].add(object_id)

    by_command: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        command_id = str(_event_attrs(event).get("command_id", ""))
        if command_id:
            by_command[command_id].append(event)

    actuation_events = [event for event in events if event.get("type") == "actuate"]
    actuation_commands = [
        str(_event_attrs(event).get("command_id", "")) for event in actuation_events
    ]
    duplicates = sum(
        count - 1 for count in Counter(actuation_commands).values() if count > 1
    )

    violations: list[str] = []
    unreceipted = 0
    authority_violations = 0
    causal_violations = 0
    receipt_binding_violations = 0

    if duplicates:
        violations.append(f"DUPLICATE_EFFECTS:{duplicates}")

    phase_order = ("authorize", "prepare_receipt", "actuate", "receipt", "verify")
    actuated_commands = {command_id for command_id in actuation_commands if command_id}

    for event in actuation_events:
        event_id = str(event.get("id", ""))
        attrs = _event_attrs(event)
        refs = _event_refs(event)
        command_id = str(attrs.get("command_id", ""))
        subject_id = str(event.get("subject_id", ""))

        if not command_id:
            violations.append(f"ACTUATION_WITHOUT_COMMAND:{event_id}")
            authority_violations += 1
            unreceipted += 1
            continue

        command_events = by_command.get(command_id, [])
        phases: dict[str, list[dict[str, Any]]] = {
            phase: [candidate for candidate in command_events if candidate.get("type") == phase]
            for phase in phase_order
        }

        for phase in phase_order:
            count = len(phases[phase])
            if count != 1:
                violations.append(
                    f"COMMAND_PHASE_CARDINALITY:{command_id}:{phase}:{count}"
                )
                if phase == "authorize":
                    authority_violations += 1
                if phase in {"prepare_receipt", "receipt"}:
                    unreceipted += 1
                else:
                    causal_violations += 1

        authorize = phases["authorize"][0] if len(phases["authorize"]) == 1 else None
        prepare = (
            phases["prepare_receipt"][0]
            if len(phases["prepare_receipt"]) == 1
            else None
        )
        receipt_event = (
            phases["receipt"][0] if len(phases["receipt"]) == 1 else None
        )
        verify = phases["verify"][0] if len(phases["verify"]) == 1 else None

        permission_refs = refs.get("permission", set())
        if not permission_refs:
            authority_violations += 1
            violations.append(f"ACTUATION_WITHOUT_PERMISSION:{event_id}")

        if authorize is not None:
            authorize_attrs = _event_attrs(authorize)
            authorize_refs = _event_refs(authorize)
            authorized_permissions = authorize_refs.get("permission", set())
            if authorize_attrs.get("code") != "AUTHORIZED":
                authority_violations += 1
                violations.append(f"ACTUATION_WITHOUT_AUTHORIZED_DECISION:{command_id}")
            if not authorized_permissions or permission_refs != authorized_permissions:
                authority_violations += 1
                violations.append(f"PERMISSION_BINDING_MISMATCH:{command_id}")
            grant_id = str(authorize_attrs.get("grant_id", ""))
            if grant_id and grant_id not in authorized_permissions:
                authority_violations += 1
                violations.append(f"GRANT_ID_NOT_IN_PERMISSION_REFS:{command_id}")

        prepared_refs = refs.get("prepared_receipt", set())
        if not prepared_refs:
            unreceipted += 1
            violations.append(f"ACTUATION_WITHOUT_PREPARED_RECEIPT:{event_id}")

        command_prepared = prepared_by_command.get(command_id, set())
        if len(command_prepared) != 1:
            unreceipted += 1
            receipt_binding_violations += 1
            violations.append(
                f"PREPARED_RECEIPT_CARDINALITY:{command_id}:{len(command_prepared)}"
            )
        elif prepared_refs != command_prepared:
            unreceipted += 1
            receipt_binding_violations += 1
            violations.append(f"PREPARED_RECEIPT_BINDING_MISMATCH:{command_id}")

        if prepare is not None:
            prepare_refs = _event_refs(prepare).get("prepared_receipt", set())
            prepare_attrs = _event_attrs(prepare)
            if prepare_refs != command_prepared:
                receipt_binding_violations += 1
                violations.append(f"PREPARE_EVENT_BINDING_MISMATCH:{command_id}")
            declared = str(prepare_attrs.get("prepared_receipt_id", ""))
            if declared and declared not in prepare_refs:
                receipt_binding_violations += 1
                violations.append(f"PREPARE_EVENT_ID_MISMATCH:{command_id}")

        final_receipts = receipts_by_command.get(command_id, set())
        if len(final_receipts) != 1:
            unreceipted += 1
            receipt_binding_violations += 1
            violations.append(
                f"FINAL_RECEIPT_CARDINALITY:{command_id}:{len(final_receipts)}"
            )

        if receipt_event is not None:
            receipt_refs = _event_refs(receipt_event).get("receipt", set())
            receipt_attrs = _event_attrs(receipt_event)
            if receipt_refs != final_receipts:
                receipt_binding_violations += 1
                violations.append(f"FINAL_RECEIPT_BINDING_MISMATCH:{command_id}")
            declared = str(receipt_attrs.get("receipt_id", ""))
            if declared and declared not in receipt_refs:
                receipt_binding_violations += 1
                violations.append(f"FINAL_RECEIPT_EVENT_ID_MISMATCH:{command_id}")

        if verify is not None and final_receipts:
            verify_refs = _event_refs(verify).get("receipt", set())
            if verify_refs != final_receipts:
                receipt_binding_violations += 1
                violations.append(f"VERIFY_RECEIPT_BINDING_MISMATCH:{command_id}")

        if len(command_prepared) == 1 and len(final_receipts) == 1:
            prepared_id = next(iter(command_prepared))
            receipt_id = next(iter(final_receipts))
            prepared_attrs = _object_attrs(objects[prepared_id])
            receipt_attrs = _object_attrs(objects[receipt_id])
            if str(prepared_attrs.get("command_id", "")) != command_id:
                receipt_binding_violations += 1
                violations.append(f"PREPARED_COMMAND_MISMATCH:{command_id}")
            if str(receipt_attrs.get("command_id", "")) != command_id:
                receipt_binding_violations += 1
                violations.append(f"RECEIPT_COMMAND_MISMATCH:{command_id}")
            if str(prepared_attrs.get("target_service", "")) != subject_id:
                receipt_binding_violations += 1
                violations.append(f"PREPARED_TARGET_MISMATCH:{command_id}")
            if str(receipt_attrs.get("target_service", "")) != subject_id:
                receipt_binding_violations += 1
                violations.append(f"RECEIPT_TARGET_MISMATCH:{command_id}")
            if prepared_attrs.get("pre_state_digest") != receipt_attrs.get(
                "pre_state_digest"
            ):
                receipt_binding_violations += 1
                violations.append(f"PRE_POST_CHAIN_MISMATCH:{command_id}")
            if authorize is not None:
                authorized_permissions = _event_refs(authorize).get("permission", set())
                authority_grant_id = str(
                    prepared_attrs.get("authority_grant_id", "")
                )
                if authority_grant_id not in authorized_permissions:
                    authority_violations += 1
                    violations.append(
                        f"PREPARED_RECEIPT_AUTHORITY_MISMATCH:{command_id}"
                    )

        bound_events = [
            candidate
            for phase in phase_order
            for candidate in phases[phase]
        ]
        if any(str(candidate.get("subject_id", "")) != subject_id for candidate in bound_events):
            receipt_binding_violations += 1
            violations.append(f"COMMAND_SUBJECT_DRIFT:{command_id}")

        if all(len(phases[phase]) == 1 for phase in phase_order):
            times = [int(phases[phase][0].get("time", 0)) for phase in phase_order]
            if any(left >= right for left, right in zip(times, times[1:])):
                causal_violations += 1
                violations.append(f"CAUSAL_ORDER:{command_id}")

    for command_id in sorted(receipts_by_command):
        if command_id not in actuated_commands:
            receipt_binding_violations += 1
            violations.append(f"ORPHAN_FINAL_RECEIPT:{command_id}")
    for command_id in sorted(prepared_by_command):
        if command_id not in actuated_commands:
            receipt_binding_violations += 1
            violations.append(f"ORPHAN_PREPARED_RECEIPT:{command_id}")

    return {
        "ok": not violations,
        "violations": violations,
        "actuations": len(actuation_events),
        "unreceipted_actuations": unreceipted,
        "authority_violations": authority_violations,
        "duplicate_effects": duplicates,
        "causal_violations": causal_violations,
        "receipt_binding_violations": receipt_binding_violations,
        "objects": len(objects),
        "events": len(events),
    }


__all__ = ["project_events_to_ocel2", "verify_ocel2"]
