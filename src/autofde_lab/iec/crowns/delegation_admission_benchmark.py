"""Mutation and capacity-stress court for delegation/admission evidence.

This benchmark tests the *court*, not a product. It starts from one known-good
exact-subject artifact, applies one semantic mutation at a time, and requires the
delegation admission evaluator to kill every mutation with a specific typed
falsifier. It also sweeps the delegation/capacity boundary exhaustively over a
bounded integer grid.

A green result therefore means:
- the clean witness is admitted;
- every declared semantic mutation is detected;
- the numeric law delegation <= min(obligation scopes) has no false positives or
  false negatives inside the tested bound;
- receipts are content-addressed and byte-replayable by construction.

It does not prove production behavior or grant DO authority.
"""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .delegation_admission import SCHEMA, evaluate_delegation
from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = [
    "BENCHMARK_SCHEMA",
    "Mutation",
    "capacity_sweep",
    "mutation_court",
    "run_benchmark",
    "main",
]

BENCHMARK_SCHEMA = "autofde-lab.delegation-admission-benchmark/1"


@dataclass(frozen=True)
class Mutation:
    name: str
    expected_falsifier: str
    apply: Callable[[dict[str, Any]], None]


def _delete(path: Sequence[str]) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        target: dict[str, Any] = document
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return mutate


def _set(path: Sequence[str], value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        target: dict[str, Any] = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


MUTATIONS = (
    Mutation(
        "explain-provenance-deleted",
        "EXPLAIN_PROVENANCE_ID_MISSING",
        _delete(("obligations", "explain", "provenance_id")),
    ),
    Mutation(
        "verify-self-grading",
        "VERIFY_NOT_INDEPENDENT",
        _set(("obligations", "verify", "independent"), False),
    ),
    Mutation(
        "verify-receipt-deleted",
        "VERIFY_RECEIPT_ID_MISSING",
        _delete(("obligations", "verify", "receipt_id")),
    ),
    Mutation(
        "modify-change-deleted",
        "MODIFY_CHANGE_ID_MISSING",
        _delete(("obligations", "modify", "change_id")),
    ),
    Mutation(
        "modify-counterexample",
        "MODIFY_NOT_PASS",
        _set(("obligations", "modify", "verdict"), "COUNTEREXAMPLE"),
    ),
    Mutation(
        "account-authority-deleted",
        "ACCOUNT_AUTHORITY_ID_MISSING",
        _delete(("obligations", "account", "authority_id")),
    ),
    Mutation(
        "account-replay-deleted",
        "ACCOUNT_REPLAY_ID_MISSING",
        _delete(("obligations", "account", "replay_id")),
    ),
    Mutation(
        "verify-subject-drift",
        "VERIFY_SUBJECT_MISMATCH",
        _set(("obligations", "verify", "subject"), "git:other/repo@different"),
    ),
)


def _require_clean_baseline(document: Mapping[str, Any]) -> dict[str, Any]:
    baseline = evaluate_delegation(document)
    if baseline["gate"] != Verdict.PASS.value:
        raise IECRefusal(
            "REFUSED_INVALID_BENCHMARK_BASELINE",
            "mutation benchmark requires a PASS baseline",
        )
    return baseline


def mutation_court(document: Mapping[str, Any]) -> dict[str, Any]:
    """Apply every fixed semantic mutation and require its typed falsifier."""
    baseline = _require_clean_baseline(document)
    cases: list[dict[str, Any]] = []
    killed = 0

    for mutation in MUTATIONS:
        candidate = copy.deepcopy(dict(document))
        mutation.apply(candidate)
        result = evaluate_delegation(candidate)
        falsifiers = result["falsifiers"]
        detected = (
            result["gate"] == Verdict.COUNTEREXAMPLE.value
            and mutation.expected_falsifier in falsifiers
        )
        if detected:
            killed += 1
        cases.append(
            {
                "mutation": mutation.name,
                "expected_falsifier": mutation.expected_falsifier,
                "gate": result["gate"],
                "falsifiers": falsifiers,
                "killed": detected,
                "receipt_id": result["receipt_id"],
            }
        )

    report: dict[str, Any] = {
        "schema": "autofde-lab.delegation-admission-mutation-court/1",
        "subject": baseline["subject"],
        "baseline_receipt_id": baseline["receipt_id"],
        "mutations": len(MUTATIONS),
        "killed": killed,
        "kill_rate": killed / len(MUTATIONS),
        "cases": cases,
        "gate": (
            Verdict.PASS.value
            if killed == len(MUTATIONS)
            else Verdict.COUNTEREXAMPLE.value
        ),
    }
    report["receipt_id"] = content_id(report)
    return report


def _set_all_scopes(document: dict[str, Any], scope: int) -> None:
    for obligation in ("explain", "verify", "modify", "account"):
        document["obligations"][obligation]["scope_units"] = scope


def capacity_sweep(
    document: Mapping[str, Any],
    *,
    max_units: int = 32,
) -> dict[str, Any]:
    """Exhaustively check the scalar admission boundary on [0, max_units]."""
    if isinstance(max_units, bool) or not isinstance(max_units, int) or max_units < 0:
        raise IECRefusal(
            "REFUSED_INVALID_BENCHMARK_BOUND",
            "max_units must be a non-negative integer",
        )
    _require_clean_baseline(document)

    checked = 0
    false_accepts: list[dict[str, int]] = []
    false_rejects: list[dict[str, int]] = []

    for delegation_units in range(max_units + 1):
        for scope_units in range(max_units + 1):
            candidate = copy.deepcopy(dict(document))
            candidate["delegation"]["units"] = delegation_units
            _set_all_scopes(candidate, scope_units)
            result = evaluate_delegation(candidate)
            observed_pass = result["gate"] == Verdict.PASS.value
            expected_pass = delegation_units <= scope_units
            checked += 1
            if observed_pass and not expected_pass:
                false_accepts.append(
                    {
                        "delegation_units": delegation_units,
                        "scope_units": scope_units,
                    }
                )
            elif not observed_pass and expected_pass:
                false_rejects.append(
                    {
                        "delegation_units": delegation_units,
                        "scope_units": scope_units,
                    }
                )

    gate = (
        Verdict.PASS.value
        if not false_accepts and not false_rejects
        else Verdict.COUNTEREXAMPLE.value
    )
    report: dict[str, Any] = {
        "schema": "autofde-lab.delegation-admission-capacity-sweep/1",
        "subject": str(document.get("subject", "")),
        "max_units": max_units,
        "checked_pairs": checked,
        "expected_pairs": (max_units + 1) ** 2,
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "gate": gate,
    }
    report["receipt_id"] = content_id(report)
    return report


def run_benchmark(
    document: Mapping[str, Any],
    *,
    max_units: int = 32,
) -> dict[str, Any]:
    """Run mutation + numeric-boundary courts and aggregate one receipt."""
    mutations = mutation_court(document)
    sweep = capacity_sweep(document, max_units=max_units)
    falsifiers: list[str] = []
    if mutations["gate"] != Verdict.PASS.value:
        falsifiers.append("MUTATION_KILL_INCOMPLETE")
    if sweep["gate"] != Verdict.PASS.value:
        falsifiers.append("CAPACITY_BOUNDARY_MISMATCH")

    report: dict[str, Any] = {
        "schema": BENCHMARK_SCHEMA,
        "subject": str(document.get("subject", "")),
        "mutation_court": mutations,
        "capacity_sweep": sweep,
        "falsifiers": falsifiers,
        "gate": (
            Verdict.PASS.value
            if not falsifiers
            else Verdict.COUNTEREXAMPLE.value
        ),
        "claim_ceiling": (
            "bounded court robustness only; not production or actuation standing"
        ),
    }
    report["receipt_id"] = content_id(report)
    return report


def _load(path: str) -> Mapping[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"{path}: top-level JSON value must be an object",
        )
    if document.get("schema") != SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_ADMISSION",
            f"{path}: expected schema {SCHEMA}",
        )
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("receipt")
    parser.add_argument("--max-units", type=int, default=32)
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = run_benchmark(_load(args.candidate), max_units=args.max_units)
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
