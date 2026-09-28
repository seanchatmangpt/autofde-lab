#!/usr/bin/env python3
"""Audit a finite decision corpus for information obstruction."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autofde_lab.evidence.information_obstruction import (
    DecisionCase,
    analyze_information_obstruction,
)


def _load_cases(path: Path) -> tuple[DecisionCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("CORPUS_MUST_BE_JSON_ARRAY")

    cases = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"CORPUS_ROW_MUST_BE_OBJECT:{index}")
        accepted = row.get("accepted_outputs")
        if not isinstance(accepted, list):
            raise ValueError(f"ACCEPTED_OUTPUTS_MUST_BE_ARRAY:{index}")
        cases.append(
            DecisionCase(
                case_id=str(row.get("case_id", "")),
                observation=row.get("observation"),
                accepted_outputs=frozenset(str(value) for value in accepted),
            )
        )
    return tuple(cases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    report = analyze_information_obstruction(_load_cases(args.corpus))
    payload = {
        "schema": "autofde.information-obstruction/1",
        "standing": report.standing,
        "case_count": report.case_count,
        "observation_class_count": report.observation_class_count,
        "collision_class_count": report.collision_class_count,
        "obstruction_count": report.obstruction_count,
        "observation_classes": [asdict(row) for row in report.observation_classes],
        "witnesses": [asdict(row) for row in report.witnesses],
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report.information_sufficient else 2


if __name__ == "__main__":
    raise SystemExit(main())
