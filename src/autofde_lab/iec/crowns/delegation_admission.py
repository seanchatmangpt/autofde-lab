"""Delegation/admission calculus derived from AASEE judgment obligations.

The court generalizes Explain/Verify/Modify/Account into a machine-checkable
admission boundary.  Delegation is never admitted merely because an artifact
works: every evidence obligation is exact-subject bound and declares the amount
of delegated scope it can independently support.

Law:
    delegation_units <= min(explain, verify, modify, account scope_units)

The minimum is intentional.  A large verification harness cannot compensate for
missing authority, replay, provenance, or changed-requirement evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "evaluate_delegation",
    "compare_delegation",
    "main",
]

SCHEMA = "autofde-lab.delegation-admission/1"
RECEIPT_SCHEMA = "autofde-lab.delegation-admission-receipt/1"
OBLIGATIONS = ("explain", "verify", "modify", "account")
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "explain": ("provenance_id", "ontology_id", "rationale_id"),
    "verify": ("verifier_set_id", "receipt_id"),
    "modify": ("change_id", "result_id", "replay_id"),
    "account": (
        "authority_id",
        "consequence_id",
        "receipt_id",
        "replay_id",
        "standing",
    ),
}


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"{name} must be a non-negative integer",
        )
    return value


def _required_string(row: Mapping[str, Any], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"{where}.{field} must be a non-empty string",
        )
    return value.strip()


def _obligation_result(
    name: str,
    raw: Any,
    *,
    subject: str,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "verdict": Verdict.COUNTEREXAMPLE.value,
            "scope_units": 0,
            "issues": [f"{name.upper()}_EVIDENCE_MISSING"],
        }

    issues: list[str] = []
    verdict = str(raw.get("verdict", ""))
    if verdict != Verdict.PASS.value:
        issues.append(f"{name.upper()}_NOT_PASS")

    evidence_subject = str(raw.get("subject", "")).strip()
    if evidence_subject != subject:
        issues.append(f"{name.upper()}_SUBJECT_MISMATCH")

    scope_raw = raw.get("scope_units", 0)
    if isinstance(scope_raw, bool) or not isinstance(scope_raw, int) or scope_raw < 0:
        issues.append(f"{name.upper()}_SCOPE_INVALID")
        scope_units = 0
    else:
        scope_units = scope_raw

    for field in REQUIRED_FIELDS[name]:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{name.upper()}_{field.upper()}_MISSING")

    if name == "verify" and raw.get("independent") is not True:
        issues.append("VERIFY_NOT_INDEPENDENT")

    result_verdict = (
        Verdict.PASS.value if not issues else Verdict.COUNTEREXAMPLE.value
    )
    return {
        "verdict": result_verdict,
        "scope_units": scope_units if result_verdict == Verdict.PASS.value else 0,
        "issues": sorted(set(issues)),
    }


def evaluate_delegation(document: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one exact-subject delegation artifact and emit a deterministic receipt."""
    if document.get("schema") != SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"schema must be {SCHEMA}, got {document.get('schema')!r}",
        )

    subject = _required_string(document, "subject", "document")
    delegation = document.get("delegation")
    if not isinstance(delegation, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            "delegation must be an object",
        )
    units = _nonnegative_int(delegation.get("units"), "delegation.units")
    boundary_id = _required_string(delegation, "boundary_id", "delegation")
    authority_scope_id = _required_string(
        delegation, "authority_scope_id", "delegation"
    )

    obligations_raw = document.get("obligations")
    if not isinstance(obligations_raw, Mapping):
        obligations_raw = {}

    obligations = {
        name: _obligation_result(
            name,
            obligations_raw.get(name),
            subject=subject,
        )
        for name in OBLIGATIONS
    }

    all_issues = sorted(
        {
            issue
            for result in obligations.values()
            for issue in result["issues"]
        }
    )
    capacity = min(result["scope_units"] for result in obligations.values())
    debt_units = max(0, units - capacity)
    if debt_units:
        all_issues.append("DELEGATION_EXCEEDS_ADMISSION_CAPACITY")

    debt = {
        "units": debt_units,
        "provenance": any(i.startswith("EXPLAIN_") for i in all_issues),
        "verification": any(i.startswith("VERIFY_") for i in all_issues),
        "modification": any(i.startswith("MODIFY_") for i in all_issues),
        "authority_receipt_replay": any(
            i.startswith("ACCOUNT_") for i in all_issues
        ),
    }

    gate = Verdict.PASS.value if not all_issues else Verdict.COUNTEREXAMPLE.value
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "subject": subject,
        "boundary_id": boundary_id,
        "authority_scope_id": authority_scope_id,
        "delegation_units": units,
        "admission_capacity_units": capacity,
        "admission_debt": debt,
        "obligations": obligations,
        "falsifiers": sorted(set(all_issues)),
        "gate": gate,
        "claim_ceiling": (
            "exact-subject evidence obligation admission only; "
            "PASS does not grant production authority"
        ),
    }
    receipt["receipt_id"] = content_id(receipt)
    return receipt


def compare_delegation(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two versions while refusing subject/boundary/authority drift."""
    left = evaluate_delegation(reference)
    right = evaluate_delegation(candidate)

    for field, code in (
        ("subject", "REFUSED_EXACT_SUBJECT_MISMATCH"),
        ("boundary_id", "REFUSED_BOUNDARY_MISMATCH"),
        ("authority_scope_id", "REFUSED_AUTHORITY_SCOPE_MISMATCH"),
    ):
        if left[field] != right[field]:
            raise IECRefusal(
                code,
                f"reference {field}={left[field]!r}, candidate={right[field]!r}",
            )

    delegation_delta = right["delegation_units"] - left["delegation_units"]
    capacity_delta = (
        right["admission_capacity_units"] - left["admission_capacity_units"]
    )
    growth_law = delegation_delta <= capacity_delta
    falsifiers = list(right["falsifiers"])
    if not growth_law:
        falsifiers.append("DELEGATION_GROWTH_OUTRUNS_ADMISSION_GROWTH")

    result: dict[str, Any] = {
        "schema": "autofde-lab.delegation-admission-comparison/1",
        "subject": right["subject"],
        "reference_receipt_id": left["receipt_id"],
        "candidate_receipt_id": right["receipt_id"],
        "delta": {
            "delegation_units": delegation_delta,
            "admission_capacity_units": capacity_delta,
            "admission_debt_units": (
                right["admission_debt"]["units"]
                - left["admission_debt"]["units"]
            ),
        },
        "growth_law": {
            "law": "delta(delegation) <= delta(admission_capacity)",
            "verdict": (
                Verdict.PASS.value
                if growth_law
                else Verdict.COUNTEREXAMPLE.value
            ),
        },
        "falsifiers": sorted(set(falsifiers)),
    }
    result["gate"] = (
        Verdict.PASS.value
        if right["gate"] == Verdict.PASS.value and growth_law
        else Verdict.COUNTEREXAMPLE.value
    )
    result["receipt_id"] = content_id(result)
    return result


def _load(path: str) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"{path}: top-level JSON value must be an object",
        )
    return value


def _write(path: str, value: Mapping[str, Any]) -> None:
    Path(path).write_text(canonical_json(value) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("receipt")
    parser.add_argument("--reference")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)

    try:
        candidate = _load(args.candidate)
        result = (
            compare_delegation(_load(args.reference), candidate)
            if args.reference
            else evaluate_delegation(candidate)
        )
        _write(args.receipt, result)
    except (IECRefusal, OSError, json.JSONDecodeError) as exc:
        return 2

    if args.gate and result["gate"] != Verdict.PASS.value:
        return 3
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
