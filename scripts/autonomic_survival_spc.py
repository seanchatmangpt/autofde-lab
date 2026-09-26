#!/usr/bin/env python3
"""Run configured CUSUM drift monitoring over ordered survival batch artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autofde_lab.iec.crowns.survival_io import (
    load_episode_file,
    render_report_json,
    write_report_json,
)
from autofde_lab.iec.crowns.survival_spc import CusumConfig, survival_spc_report


def _batch(value: str) -> tuple[str, Path]:
    label, sep, path = value.partition("=")
    if not sep or not label.strip() or not path.strip():
        raise argparse.ArgumentTypeError("batch must be LABEL=PATH")
    return label.strip(), Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch",
        action="append",
        type=_batch,
        required=True,
        help="ordered LABEL=JSON_OR_JSONL_PATH; may be repeated",
    )
    parser.add_argument("--series-id", required=True)
    parser.add_argument(
        "--metric",
        choices=(
            "failure_probability_observed",
            "rmst_steps",
            "llm_dependency_fraction",
            "receipt_coverage",
            "replay_coverage",
        ),
        required=True,
    )
    parser.add_argument("--target", type=float, required=True)
    parser.add_argument("--allowance", type=float, required=True)
    parser.add_argument("--decision-interval", type=float, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        batches = [
            (label, load_episode_file(path))
            for label, path in args.batch
        ]
        report = survival_spc_report(
            batches,
            series_id=args.series_id,
            metric=args.metric,
            config=CusumConfig(
                target=args.target,
                allowance=args.allowance,
                decision_interval=args.decision_interval,
            ),
        )
    except Exception as exc:
        print(f"survival-spc-refused: {exc}", file=sys.stderr)
        return 2

    if args.output is None:
        sys.stdout.write(render_report_json(report))
    else:
        write_report_json(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
