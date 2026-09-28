#!/usr/bin/env python3
"""Evaluate a PTD experiment manifest without constructor access."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from autofde_lab.ptd import PTDCriteria, PhaseTrial, summarize_trials

SCHEMA = "autofde-lab.ptd.experiment/v1"


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA!r}")
    return data


def evaluate_manifest(data: dict[str, Any]) -> dict[str, object]:
    criteria = PTDCriteria(**data["criteria"])
    trials = [PhaseTrial(**row) for row in data["trials"]]
    report = summarize_trials(trials, criteria)
    report["experiment_id"] = data["experiment_id"]
    report["input_schema"] = SCHEMA
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = evaluate_manifest(load_manifest(args.manifest))
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        print(f"sha256:{digest} {args.out}")
    print(encoded, end="")
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
