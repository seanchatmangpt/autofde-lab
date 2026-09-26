#!/usr/bin/env python3
"""Generate autonomic-survival reports from JSON or JSONL episode artifacts.

Examples:

  PYTHONPATH=src python scripts/autonomic_survival_report.py \
      --mode recurrent --input episodes.jsonl

  PYTHONPATH=src python scripts/autonomic_survival_report.py \
      --mode compare --input formal.jsonl --input llm.jsonl

  PYTHONPATH=src python scripts/autonomic_survival_report.py \
      --mode strata --factor authority --input campaign.jsonl

  PYTHONPATH=src python scripts/autonomic_survival_report.py \
      --mode ocel --input campaign.jsonl --output campaign.ocel.json

Input files may contain one episode object, a JSON array of episode objects, or
newline-delimited episode objects. Compare mode groups episodes by declared
policy_id. Strata mode uses explicit GymAct campaign metadata. OCEL mode emits
the repository's canonical validated OCEL 2.0 projection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from autofde_lab.iec.crowns.recurrent_survival import recurrent_survival_report
from autofde_lab.iec.crowns.survival import survival_report
from autofde_lab.iec.crowns.survival_compare import compare_survival_policies
from autofde_lab.iec.crowns.survival_ocel import survival_episodes_to_ocel
from autofde_lab.iec.crowns.survival_strata import stratified_survival_report
from autofde_lab.iec.crowns.survival_uncertainty import survival_uncertainty_report


def _load(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        rows = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSONL: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: episode must be an object")
            rows.append(value)
        return rows

    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return list(value)
    raise ValueError(f"{path}: expected episode object or array of episode objects")


def _load_all(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(_load(path))
    return rows


def _group_by_policy(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        policy_id = row.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id:
            raise ValueError("every episode requires non-empty policy_id")
        groups.setdefault(policy_id, []).append(row)
    return groups


def build_report(
    mode: str,
    rows: list[dict[str, Any]],
    *,
    factor_names: tuple[str, ...] = (),
    stratify_fault: bool = True,
) -> dict[str, Any]:
    if mode == "first":
        return survival_report(rows)
    if mode == "recurrent":
        return recurrent_survival_report(rows)
    if mode == "uncertainty":
        return survival_uncertainty_report(rows)
    if mode == "compare":
        return compare_survival_policies(_group_by_policy(rows))
    if mode == "strata":
        return stratified_survival_report(
            rows,
            factor_names=factor_names,
            stratify_fault=stratify_fault,
        )
    if mode == "ocel":
        return survival_episodes_to_ocel(tuple(rows)).to_ocel2_json()
    raise ValueError(f"unknown mode {mode!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("first", "recurrent", "uncertainty", "compare", "strata", "ocel"),
        default="recurrent",
    )
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="JSON/JSONL episode file; may be repeated",
    )
    parser.add_argument(
        "--factor",
        action="append",
        default=[],
        help="GymAct factor name used by strata mode; may be repeated",
    )
    parser.add_argument(
        "--no-stratify-fault",
        action="store_true",
        help="strata mode: pool fault-plan identities instead of separating them",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        rows = _load_all(args.input)
        report = build_report(
            args.mode,
            rows,
            factor_names=tuple(args.factor),
            stratify_fault=not args.no_stratify_fault,
        )
    except Exception as exc:
        print(f"survival-report-refused: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
