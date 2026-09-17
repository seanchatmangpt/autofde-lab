#!/usr/bin/env python3
# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CLI wrapper for RFC-SA2A-002 Conformance Benchmarks (SA2A-B1..B10).

Runs `autofde_lab.sa2a.conformance.benchmarks.harness.run_all_benchmarks()` and
writes/prints the resulting formal Environment Receipt (RFC-SA2A-002 Appendix E).

This script does not implement any benchmark logic itself — it is a thin
argparse front end over the existing `BenchmarkHarness` / `run_all_benchmarks`
convenience function. See `src/autofde_lab/sa2a/conformance/benchmarks/harness.py`
for the real Chicago Zero-Mock benchmark implementations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autofde_lab.sa2a.conformance.benchmarks.harness import (
    ALL_BENCHMARKS,
    run_all_benchmarks,
)

DEFAULT_OUTPUT = Path("reports/rfc_sa2a_002_benchmarks.json")


def _benchmark_list(raw: str) -> list[str]:
    """argparse type: parse a comma-separated benchmark-id list, validated against ALL_BENCHMARKS."""
    ids = [b.strip() for b in raw.split(",") if b.strip()]
    unknown = sorted(set(ids) - set(ALL_BENCHMARKS))
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown benchmark id(s): {', '.join(unknown)}; valid ids: {', '.join(ALL_BENCHMARKS)}"
        )
    return ids


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_sa2a_benchmarks.py",
        description=(
            "Run RFC-SA2A-002 conformance benchmarks (SA2A-B1..SA2A-B10) via the existing "
            "BenchmarkHarness and emit a formal Environment Receipt (Appendix E)."
        ),
    )
    parser.add_argument(
        "--benchmarks",
        type=_benchmark_list,
        default=None,
        help=(
            "Comma-separated benchmark IDs to run (e.g. SA2A-B1,SA2A-B4). "
            f"Default: all of {', '.join(ALL_BENCHMARKS)}."
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Iteration count passed to each iteration-sensitive benchmark (default: 20).",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default=None,
        help=(
            "Working directory for real-disk plant collaborators (journal files, etc). "
            "Default: a fresh temporary directory managed by the harness."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Path to write the Environment Receipt JSON (default: {DEFAULT_OUTPUT}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    receipt = run_all_benchmarks(
        benchmarks=args.benchmarks,
        iterations=args.iterations,
        work_dir=args.work_dir,
    )

    receipt_json = json.dumps(receipt.to_dict(), indent=2)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(receipt_json, encoding="utf-8")

    print(receipt_json)

    return 0 if receipt.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
