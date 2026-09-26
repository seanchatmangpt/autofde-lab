"""Deterministic repair planning for delegation admission debt.

This planner handles the numeric capacity case only. It never fabricates missing
provenance, verifier independence, changed-requirement evidence, authority, or
receipts. If those semantic obligations fail, repair is typed UNSUPPORTED and must
be satisfied by the machinery that owns that evidence.

For a clean artifact with insufficient scope, the exact minimum repair is trivial
and closed-form: every obligation below delegated scope must be raised to the
delegated scope. Costs are additive per evidence-scope unit.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .delegation_admission import OBLIGATIONS, evaluate_delegation
from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = ["PLAN_SCHEMA", "plan_capacity_repair", "main"]

PLAN_SCHEMA = "autofde-lab.delegation-admission-repair-plan/1"


def _costs(raw: Mapping[str, Any] | None) -> dict[str, float]:
    source = raw or {}
    unknown = set(source) - set(OBLIGATIONS)
    if unknown:
        raise IECRefusal(
            "REFUSED_INVALID_REPAIR_COST",
            f"unknown obligation costs: {sorted(unknown)}",
        )
    result: dict[str, float] = {}
    for obligation in OBLIGATIONS:
        value = source.get(obligation, 1.0)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise IECRefusal(
                "REFUSED_INVALID_REPAIR_COST",
                f"{obligation} unit cost must be finite and non-negative",
            )
        result[obligation] = float(value)
    return result


def _raw_scopes(document: Mapping[str, Any]) -> dict[str, int]:
    obligations = document.get("obligations")
    if not isinstance(obligations, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            "obligations must be an object",
        )
    scopes: dict[str, int] = {}
    for obligation in OBLIGATIONS:
        evidence = obligations.get(obligation)
        if not isinstance(evidence, Mapping):
            raise IECRefusal(
                "REFUSED_NON_CAPACITY_REPAIR",
                f"{obligation}: evidence object missing",
            )
        scope = evidence.get("scope_units")
        if isinstance(scope, bool) or not isinstance(scope, int) or scope < 0:
            raise IECRefusal(
                "REFUSED_NON_CAPACITY_REPAIR",
                f"{obligation}: scope_units is not a valid capacity",
            )
        scopes[obligation] = scope
    return scopes


def plan_capacity_repair(
    document: Mapping[str, Any],
    *,
    unit_costs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute the minimum additive scope repair for one exact subject."""
    receipt = evaluate_delegation(document)
    costs = _costs(unit_costs)
    scopes = _raw_scopes(document)
    target = receipt["delegation_units"]

    semantic_issues = sorted(
        {
            issue
            for obligation in receipt["obligations"].values()
            for issue in obligation["issues"]
        }
    )
    if semantic_issues:
        report: dict[str, Any] = {
            "schema": PLAN_SCHEMA,
            "subject": receipt["subject"],
            "source_receipt_id": receipt["receipt_id"],
            "standing": Verdict.UNSUPPORTED.value,
            "reason": "NON_CAPACITY_EVIDENCE_REPAIR_REQUIRED",
            "semantic_issues": semantic_issues,
            "actions": [],
            "total_cost": None,
            "target_delegation_units": target,
            "claim_ceiling": "candidate repair plan only; no evidence is manufactured",
        }
        report["receipt_id"] = content_id(report)
        return report

    actions: list[dict[str, Any]] = []
    total_cost = 0.0
    for obligation in OBLIGATIONS:
        current = scopes[obligation]
        increment = max(0, target - current)
        cost = increment * costs[obligation]
        total_cost += cost
        if increment:
            actions.append(
                {
                    "obligation": obligation,
                    "from_scope_units": current,
                    "to_scope_units": target,
                    "increment_units": increment,
                    "unit_cost": costs[obligation],
                    "cost": cost,
                }
            )

    actions.sort(key=lambda action: (action["cost"], action["obligation"]))
    expected_capacity = min(max(scopes[name], target) for name in OBLIGATIONS)
    expected_debt = max(0, target - expected_capacity)
    standing = (
        Verdict.PASS.value
        if expected_debt == 0
        else Verdict.COUNTEREXAMPLE.value
    )
    report = {
        "schema": PLAN_SCHEMA,
        "subject": receipt["subject"],
        "source_receipt_id": receipt["receipt_id"],
        "standing": standing,
        "reason": "CAPACITY_REPAIR_PLAN",
        "target_delegation_units": target,
        "current_capacity_units": receipt["admission_capacity_units"],
        "expected_capacity_units": expected_capacity,
        "expected_admission_debt_units": expected_debt,
        "unit_costs": costs,
        "actions": actions,
        "total_increment_units": sum(
            action["increment_units"] for action in actions
        ),
        "total_cost": total_cost,
        "claim_ceiling": (
            "closed-form candidate plan over declared scope costs; executing evidence "
            "acquisition remains external"
        ),
    }
    report["receipt_id"] = content_id(report)
    return report


def _load(path: str) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"{path}: top-level JSON value must be an object",
        )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("receipt")
    parser.add_argument("--costs")
    args = parser.parse_args(argv)

    try:
        costs = _load(args.costs) if args.costs else None
        report = plan_capacity_repair(_load(args.candidate), unit_costs=costs)
        Path(args.receipt).write_text(
            canonical_json(report) + "\n",
            encoding="utf-8",
        )
    except (IECRefusal, OSError, json.JSONDecodeError):
        return 2
    return 0 if report["standing"] in {Verdict.PASS.value, Verdict.UNSUPPORTED.value} else 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
