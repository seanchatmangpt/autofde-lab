"""Batch court for generated delegation/admission artifacts.

The ggen marketplace projection emits this schema. The batch court intentionally
does not add semantics beyond the single-artifact court: it removes transport
friction while preserving one receipt per exact subject and an aggregate receipt
that cannot hide a failing member.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .delegation_admission import evaluate_delegation
from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = ["BATCH_SCHEMA", "evaluate_batch", "main"]

BATCH_SCHEMA = "autofde-lab.delegation-admission-batch/1"


def evaluate_batch(document: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a non-empty generated batch without cross-subject averaging."""
    if document.get("schema") != BATCH_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_BATCH",
            f"schema must be {BATCH_SCHEMA}",
        )
    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise IECRefusal(
            "REFUSED_EMPTY_DELEGATION_BATCH",
            "cases must be a non-empty list",
        )

    receipts: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str]] = set()
    for index, case in enumerate(raw_cases):
        if not isinstance(case, Mapping):
            raise IECRefusal(
                "REFUSED_INVALID_DELEGATION_BATCH",
                f"case {index} must be an object",
            )
        receipt = evaluate_delegation(case)
        identity = (
            receipt["subject"],
            receipt["boundary_id"],
            receipt["authority_scope_id"],
        )
        if identity in identities:
            raise IECRefusal(
                "REFUSED_DUPLICATE_DELEGATION_SUBJECT",
                (
                    f"case {index}: duplicate exact subject/boundary/authority "
                    f"identity {identity!r}"
                ),
            )
        identities.add(identity)
        receipts.append(receipt)

    failing = [
        {
            "subject": receipt["subject"],
            "receipt_id": receipt["receipt_id"],
            "falsifiers": receipt["falsifiers"],
        }
        for receipt in receipts
        if receipt["gate"] != Verdict.PASS.value
    ]
    gate = Verdict.PASS.value if not failing else Verdict.COUNTEREXAMPLE.value

    report: dict[str, Any] = {
        "schema": "autofde-lab.delegation-admission-batch-receipt/1",
        "case_count": len(receipts),
        "pass_count": len(receipts) - len(failing),
        "counterexample_count": len(failing),
        "case_receipts": [
            {
                "subject": receipt["subject"],
                "boundary_id": receipt["boundary_id"],
                "authority_scope_id": receipt["authority_scope_id"],
                "producer_id": receipt["producer_id"],
                "delegation_units": receipt["delegation_units"],
                "admission_capacity_units": receipt["admission_capacity_units"],
                "gate": receipt["gate"],
                "receipt_id": receipt["receipt_id"],
            }
            for receipt in receipts
        ],
        "metrics": {
            "total_delegation_units": sum(
                receipt["delegation_units"] for receipt in receipts
            ),
            "total_admission_debt_units": sum(
                receipt["admission_debt"]["units"] for receipt in receipts
            ),
        },
        "failing_cases": failing,
        "gate": gate,
        "claim_ceiling": (
            "aggregate transport receipt only; each exact-subject member retains "
            "its own authority and standing boundary"
        ),
    }
    report["receipt_id"] = content_id(report)
    return report


def _load(path: str) -> Mapping[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_BATCH",
            f"{path}: top-level JSON value must be an object",
        )
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch")
    parser.add_argument("receipt")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = evaluate_batch(_load(args.batch))
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
