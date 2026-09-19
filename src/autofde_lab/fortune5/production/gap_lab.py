"""Adversarial gap simulation for the Fortune-5 evidence court.

A production court is only useful if its falsifiers can fire.  These mutations
take a known-good OCEL document, inject one concrete failure mode at a time,
and require the independent OCEL court to reject every mutated subject.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from .ocel import verify_ocel2


@dataclass(frozen=True, slots=True)
class GapCase:
    gap_id: str
    description: str
    document: dict[str, object]
    expected_violation_prefixes: tuple[str, ...]


def _attrs(row: dict[str, object]) -> dict[str, object]:
    return {
        str(item["name"]): item["value"]
        for item in row.get("attributes", [])
        if isinstance(item, dict)
    }


def _set_attr(row: dict[str, object], name: str, value: object) -> None:
    attributes = row.setdefault("attributes", [])
    for item in attributes:
        if isinstance(item, dict) and item.get("name") == name:
            item["value"] = value
            return
    attributes.append({"name": name, "value": value})


def _first_actuation(document: dict[str, object]) -> dict[str, object]:
    for event in document.get("events", []):
        if isinstance(event, dict) and event.get("type") == "actuate":
            return event
    raise ValueError("REFUSED:GAP_LAB_REQUIRES_ACTUATION")


def _command_id(event: dict[str, object]) -> str:
    command_id = str(_attrs(event).get("command_id", ""))
    if not command_id:
        raise ValueError("REFUSED:GAP_LAB_ACTUATION_WITHOUT_COMMAND")
    return command_id


def _events_for_command(
    document: dict[str, object], command_id: str
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for event in document.get("events", []):
        if isinstance(event, dict) and str(_attrs(event).get("command_id", "")) == command_id:
            result.append(event)
    return result


def _remove_authorize(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    command_id = _command_id(_first_actuation(mutated))
    mutated["events"] = [
        event
        for event in mutated.get("events", [])
        if not (
            isinstance(event, dict)
            and event.get("type") == "authorize"
            and str(_attrs(event).get("command_id", "")) == command_id
        )
    ]
    return mutated


def _strip_permission(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    actuation = _first_actuation(mutated)
    actuation["relationships"] = [
        relation
        for relation in actuation.get("relationships", [])
        if not (
            isinstance(relation, dict)
            and relation.get("qualifier") == "permission"
        )
    ]
    return mutated


def _drop_final_receipt(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    command_id = _command_id(_first_actuation(mutated))
    receipt_ids = {
        str(row.get("id"))
        for row in mutated.get("objects", [])
        if isinstance(row, dict)
        and row.get("type") == "Receipt"
        and str(_attrs(row).get("command_id", "")) == command_id
    }
    mutated["objects"] = [
        row
        for row in mutated.get("objects", [])
        if not (isinstance(row, dict) and str(row.get("id")) in receipt_ids)
    ]
    return mutated


def _drop_prepared_event(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    command_id = _command_id(_first_actuation(mutated))
    mutated["events"] = [
        event
        for event in mutated.get("events", [])
        if not (
            isinstance(event, dict)
            and event.get("type") == "prepare_receipt"
            and str(_attrs(event).get("command_id", "")) == command_id
        )
    ]
    return mutated


def _duplicate_actuation(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    original = _first_actuation(mutated)
    duplicate = deepcopy(original)
    duplicate["id"] = str(original.get("id", "")) + ":duplicate"
    duplicate["time"] = int(original.get("time", 0)) + 1
    mutated.setdefault("events", []).append(duplicate)
    return mutated


def _reorder_receipt(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    actuation = _first_actuation(mutated)
    command_id = _command_id(actuation)
    for event in _events_for_command(mutated, command_id):
        if event.get("type") == "receipt":
            event["time"] = int(actuation.get("time", 0)) - 1
            return mutated
    raise ValueError("REFUSED:GAP_LAB_MISSING_RECEIPT_EVENT")


def _retarget_receipt(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    command_id = _command_id(_first_actuation(mutated))
    for row in mutated.get("objects", []):
        if (
            isinstance(row, dict)
            and row.get("type") == "Receipt"
            and str(_attrs(row).get("command_id", "")) == command_id
        ):
            _set_attr(row, "target_service", "urn:gap:wrong-target")
            return mutated
    raise ValueError("REFUSED:GAP_LAB_MISSING_RECEIPT_OBJECT")


def _break_pre_post_chain(document: dict[str, object]) -> dict[str, object]:
    mutated = deepcopy(document)
    command_id = _command_id(_first_actuation(mutated))
    for row in mutated.get("objects", []):
        if (
            isinstance(row, dict)
            and row.get("type") == "Receipt"
            and str(_attrs(row).get("command_id", "")) == command_id
        ):
            _set_attr(row, "pre_state_digest", "gap:wrong-pre-state")
            return mutated
    raise ValueError("REFUSED:GAP_LAB_MISSING_RECEIPT_OBJECT")


_GAPS: tuple[
    tuple[str, str, Callable[[dict[str, object]], dict[str, object]], tuple[str, ...]],
    ...,
] = (
    (
        "forged-permission-reference",
        "Actuation retains a permission object reference but the real authorize event is gone.",
        _remove_authorize,
        ("COMMAND_PHASE_CARDINALITY:",),
    ),
    (
        "permission-stripped",
        "Actuation is present without a permission binding.",
        _strip_permission,
        ("ACTUATION_WITHOUT_PERMISSION:",),
    ),
    (
        "final-receipt-lost",
        "DO occurred but the final receipt object is absent.",
        _drop_final_receipt,
        ("FINAL_RECEIPT_CARDINALITY:",),
    ),
    (
        "prepared-phase-lost",
        "Prepared receipt object may exist, but its causal prepare event is absent.",
        _drop_prepared_event,
        ("COMMAND_PHASE_CARDINALITY:",),
    ),
    (
        "duplicate-do",
        "The same command produces a second actuation event.",
        _duplicate_actuation,
        ("DUPLICATE_EFFECTS:",),
    ),
    (
        "receipt-before-do",
        "Receipt event is timestamped before the actuation it claims to receipt.",
        _reorder_receipt,
        ("CAUSAL_ORDER:",),
    ),
    (
        "receipt-target-drift",
        "Receipt subject is changed to a different target after execution.",
        _retarget_receipt,
        ("RECEIPT_TARGET_MISMATCH:",),
    ),
    (
        "pre-post-chain-drift",
        "Final receipt no longer binds to the prepared receipt's pre-state.",
        _break_pre_post_chain,
        ("PRE_POST_CHAIN_MISMATCH:",),
    ),
)


def simulate_evidence_gaps(document: dict[str, object]) -> tuple[GapCase, ...]:
    baseline = verify_ocel2(document)
    if not baseline["ok"]:
        raise ValueError(
            "REFUSED:GAP_LAB_BASELINE_NOT_ADMITTED:"
            + ",".join(str(item) for item in baseline["violations"])
        )
    return tuple(
        GapCase(
            gap_id=gap_id,
            description=description,
            document=mutator(document),
            expected_violation_prefixes=prefixes,
        )
        for gap_id, description, mutator, prefixes in _GAPS
    )


def run_gap_court(document: dict[str, object]) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for case in simulate_evidence_gaps(document):
        verdict = verify_ocel2(case.document)
        violations = tuple(str(item) for item in verdict["violations"])
        expected_seen = all(
            any(item.startswith(prefix) for item in violations)
            for prefix in case.expected_violation_prefixes
        )
        detected = not verdict["ok"] and expected_seen
        results.append(
            {
                "gap_id": case.gap_id,
                "detected": detected,
                "expected_violation_prefixes": list(
                    case.expected_violation_prefixes
                ),
                "violations": list(violations),
            }
        )
    return {
        "all_detected": all(bool(item["detected"]) for item in results),
        "gap_count": len(results),
        "detected_count": sum(bool(item["detected"]) for item in results),
        "results": results,
    }


__all__ = ["GapCase", "run_gap_court", "simulate_evidence_gaps"]
