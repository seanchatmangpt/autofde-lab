"""Temporal court for delegation/admission capacity histories.

Snapshot admission is necessary but insufficient for a long-running system. This
court evaluates an ordered history, conserves exact subject/boundary/authority
identity, applies the positive-growth law between adjacent snapshots, and detects
standing that survives after its supporting evidence has been revoked.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .delegation_admission import compare_delegation, evaluate_delegation
from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = ["HISTORY_SCHEMA", "evaluate_history", "main"]

HISTORY_SCHEMA = "autofde-lab.delegation-admission-history/1"
LIVE_STANDINGS = {"ALIVE", "PARTIAL_ALIVE"}


def _artifact(row: Mapping[str, Any], sequence: int) -> Mapping[str, Any]:
    artifact = row.get("artifact")
    if not isinstance(artifact, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY",
            f"snapshot {sequence}: artifact must be an object",
        )
    return artifact


def _account_standing(artifact: Mapping[str, Any]) -> str | None:
    obligations = artifact.get("obligations")
    if not isinstance(obligations, Mapping):
        return None
    account = obligations.get("account")
    if not isinstance(account, Mapping):
        return None
    standing = account.get("standing")
    return standing if isinstance(standing, str) and standing else None


def evaluate_history(document: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate an ordered evidence/delegation history."""
    if document.get("schema") != HISTORY_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY",
            f"schema must be {HISTORY_SCHEMA}",
        )
    rows = document.get("snapshots")
    if not isinstance(rows, list) or not rows:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY",
            "snapshots must be a non-empty list",
        )

    artifacts: list[Mapping[str, Any]] = []
    snapshot_receipts: list[dict[str, Any]] = []
    for expected, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise IECRefusal(
                "REFUSED_INVALID_DELEGATION_HISTORY",
                f"snapshot {expected} must be an object",
            )
        sequence = raw.get("sequence")
        if sequence != expected:
            raise IECRefusal(
                "REFUSED_HISTORY_SEQUENCE",
                f"expected sequence {expected}, got {sequence!r}",
            )
        artifact = _artifact(raw, expected)
        artifacts.append(artifact)
        receipt = evaluate_delegation(artifact)
        snapshot_receipts.append(
            {
                "sequence": expected,
                "subject": receipt["subject"],
                "producer_id": receipt["producer_id"],
                "receipt_id": receipt["receipt_id"],
                "gate": receipt["gate"],
                "delegation_units": receipt["delegation_units"],
                "admission_capacity_units": receipt["admission_capacity_units"],
                "admission_debt_units": receipt["admission_debt"]["units"],
                "standing": _account_standing(artifact),
                "falsifiers": receipt["falsifiers"],
            }
        )

    transitions: list[dict[str, Any]] = []
    falsifiers: set[str] = set()
    debt_area = 0

    for snapshot in snapshot_receipts:
        debt_area += snapshot["admission_debt_units"]
        if snapshot["gate"] != Verdict.PASS.value:
            falsifiers.add("SNAPSHOT_ADMISSION_FAILURE")
            if snapshot["standing"] in LIVE_STANDINGS:
                falsifiers.add("STANDING_SURVIVED_ADMISSION_FAILURE")

    for index in range(1, len(artifacts)):
        comparison = compare_delegation(artifacts[index - 1], artifacts[index])
        left = snapshot_receipts[index - 1]
        right = snapshot_receipts[index]
        capacity_loss = (
            right["admission_capacity_units"] < left["admission_capacity_units"]
        )
        uncovered_after_loss = (
            capacity_loss
            and right["delegation_units"] > right["admission_capacity_units"]
        )
        if comparison["gate"] != Verdict.PASS.value:
            falsifiers.update(comparison["falsifiers"])
        if uncovered_after_loss:
            falsifiers.add("CAPACITY_REVOKED_WITH_LIVE_DELEGATION")

        transition = {
            "from_sequence": index - 1,
            "to_sequence": index,
            "previous_snapshot_receipt_id": left["receipt_id"],
            "snapshot_receipt_id": right["receipt_id"],
            "comparison_receipt_id": comparison["receipt_id"],
            "delegation_delta": comparison["delta"]["delegation_units"],
            "capacity_delta": comparison["delta"]["admission_capacity_units"],
            "growth_law": comparison["growth_law"]["verdict"],
            "capacity_loss": capacity_loss,
            "uncovered_after_loss": uncovered_after_loss,
            "gate": comparison["gate"],
        }
        transition["receipt_id"] = content_id(transition)
        transitions.append(transition)

    gate = Verdict.PASS.value if not falsifiers else Verdict.COUNTEREXAMPLE.value
    report: dict[str, Any] = {
        "schema": "autofde-lab.delegation-admission-history-receipt/1",
        "subject": snapshot_receipts[0]["subject"],
        "snapshot_count": len(snapshot_receipts),
        "transition_count": len(transitions),
        "snapshots": snapshot_receipts,
        "transitions": transitions,
        "metrics": {
            "peak_delegation_units": max(
                row["delegation_units"] for row in snapshot_receipts
            ),
            "minimum_admission_capacity_units": min(
                row["admission_capacity_units"] for row in snapshot_receipts
            ),
            "admission_debt_area": debt_area,
            "capacity_loss_events": sum(
                transition["capacity_loss"] for transition in transitions
            ),
        },
        "falsifiers": sorted(falsifiers),
        "gate": gate,
        "claim_ceiling": (
            "ordered exact-subject admission history only; no production authority"
        ),
    }
    report["receipt_id"] = content_id(report)
    return report


def _load(path: str) -> Mapping[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY",
            f"{path}: top-level JSON value must be an object",
        )
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history")
    parser.add_argument("receipt")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = evaluate_history(_load(args.history))
        Path(args.receipt).write_text(
            canonical_json(report) + "\n",
            encoding="utf-8",
        )
    except (IECRefusal, OSError, json.JSONDecodeError):
        return 2

    if args.gate and report["gate"] != Verdict.PASS.value:
        return 3
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
