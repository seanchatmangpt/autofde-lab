#!/usr/bin/env python3
"""Run the DGF-Bench deterministic-control substitution from AutoFDE Lab."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autofde_lab.evidence.dgf_substitution import (
    dgf_evaluator_digest,
    run_dgf_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-evaluate DGF-Bench canonical facts with the benchmark's own "
            "executable evaluator.py; performs zero model calls."
        )
    )
    parser.add_argument("--dgf-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    args = parser.parse_args()

    scores, summary = run_dgf_dataset(
        args.dataset_root,
        dgf_root=args.dgf_root,
    )
    print(
        json.dumps(
            {
                "kernel": "DGF evaluator.py",
                "kernel_digest": dgf_evaluator_digest(args.dgf_root),
                "llm_calls": 0,
                "summary": summary.to_dict(),
                "cases": [
                    {
                        **asdict(score),
                        "gate_success_rate": score.gate_success_rate,
                    }
                    for score in scores
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary.routes_passed == summary.cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
