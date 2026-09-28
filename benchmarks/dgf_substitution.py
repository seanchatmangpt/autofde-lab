#!/usr/bin/env python3
"""Run the DGF-Bench deterministic-control substitution from AutoFDE Lab."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autofde_lab.evidence.dgf_substitution import (
    DGFAdmissionError,
    run_receipted_dgf_dataset,
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
    parser.add_argument(
        "--expected-kernel-digest",
        "--expect-kernel-digest",
        dest="expected_kernel_digest",
        default=None,
        help=(
            "exact sha256:<hex> pin for evaluator.py; drift refuses the run "
            "(KERNEL_DIGEST_MISMATCH)"
        ),
    )
    args = parser.parse_args()

    try:
        scores, summary, receipt = run_receipted_dgf_dataset(
            args.dataset_root,
            dgf_root=args.dgf_root,
            expected_kernel_digest=args.expected_kernel_digest,
        )
    except DGFAdmissionError as exc:
        if exc.refusal_code != "DGF_EMPTY_DATASET":
            raise
        print(
            json.dumps(
                {
                    "refusal": "EMPTY_DATASET",
                    "dataset_root": str(args.dataset_root),
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "kernel": "DGF evaluator.py",
                "kernel_digest": summary.kernel_digest,
                "llm_calls": receipt.llm_calls,
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
