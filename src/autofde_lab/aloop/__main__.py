# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``python -m autofde_lab.aloop LOG.ocel.json [--out RECEIPT.json]``.

Exit codes: 0 qualified, 3 not qualified (typed), 2 refused (malformed or
forged log). The receipt is printed to stdout when ``--out`` is omitted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autofde_lab.aloop.court import evaluate_path, write_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m autofde_lab.aloop")
    parser.add_argument("log", type=Path, help="OCEL 2.0 JSON log")
    parser.add_argument("--out", type=Path, default=None, help="receipt output path")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--subject-sha", default=None, help="exact court subject SHA")
    parser.add_argument(
        "--locator", default=None, help="provenance locator for the log bytes"
    )
    args = parser.parse_args(argv)
    code, receipt = evaluate_path(
        args.log,
        profile_path=args.profile,
        court_subject_sha=args.subject_sha,
        log_locator=args.locator,
    )
    if args.out is not None:
        write_receipt(receipt, args.out)
    else:
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    sys.stderr.write(f"{receipt['court']} verdict={receipt['verdict']} exit={code}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
