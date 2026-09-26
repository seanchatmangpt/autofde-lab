#!/usr/bin/env python3
"""Run the DGF-Bench deterministic-control substitution from AutoFDE Lab."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autofde_lab.evidence.dgf_substitution import run_receipted_dgf_dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-evaluate DGF-Bench canonical facts with the benchmark's own "
            "executable evaluator.py; performs zero model calls."
        )
    )
    parser.add_argument("--dgf-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--expect-kernel-digest",
        help="optional exact sha256:<hex> pin for evaluator.py; drift refuses the run",
    )
    args = parser.parse_args()

    scores, summary, receipt = run_receipted_dgf_dataset(
        args.dataset_root,
        dgf_root=args.dgf_root,
        expected_evaluator_digest=args.expect_kernel_digest,
    )
    print(
        json.dumps(
            {
                "kernel": "DGF evaluator.py",
                "receipt": receipt.to_dict(),
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
    return 0 if receipt.standing == "ALIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
