#!/usr/bin/env python3
# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real CLI wrapper for RFC-SA2A-002 Appendix D Chicago Crown Qualification.

Wraps the existing convenience function
``autofde_lab.sa2a.conformance.runner.run_chicago_qualification`` in an
argparse CLI. Prints the resulting ``StandingReceipt.to_dict()`` as JSON to
stdout, writes it to ``--receipt-path``, and exits 0 iff
``all_gates_passed`` is true (1 otherwise).

This script writes to a NEW receipt path by default
(``reports/rfc_sa2a_002_chicago_crown_receipt.json``), distinct from the
existing ``reports/chicago_conformance_receipt.json``, which belongs to a
different, older court (see ``.claude/rules/testing-chicago-style.md`` and
commit f5727fa9) and must never be overwritten by this runner.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autofde_lab.sa2a.conformance.runner import run_chicago_qualification

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECEIPT_PATH = REPO_ROOT / "reports" / "rfc_sa2a_002_chicago_crown_receipt.json"
DEFAULT_OCEL_PATH = REPO_ROOT / "reports" / "rfc_sa2a_002_chicago_crown.ocel.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_chicago_qualification",
        description=(
            "Execute the RFC-SA2A-002 Appendix D Canonical Chicago Definition "
            "of Done Court (all 12 Chicago Crown Gates, CHI-ID to CHI-KNOWN) "
            "and issue an authenticated StandingReceipt."
        ),
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=REPO_ROOT,
        help=f"Git workspace root to qualify (default: {REPO_ROOT}).",
    )
    parser.add_argument(
        "--receipt-path",
        type=Path,
        default=DEFAULT_RECEIPT_PATH,
        help=(
            "Path to write the StandingReceipt JSON "
            f"(default: {DEFAULT_RECEIPT_PATH}). Distinct from the older "
            "reports/chicago_conformance_receipt.json court's file — never "
            "point this at that path."
        ),
    )
    parser.add_argument(
        "--ocel-path",
        type=Path,
        default=DEFAULT_OCEL_PATH,
        help=f"Path to write the OCEL 2.0 execution trace (default: {DEFAULT_OCEL_PATH}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    receipt = run_chicago_qualification(
        workspace_root=args.workspace_root,
        receipt_path=args.receipt_path,
        ocel_path=args.ocel_path,
    )

    receipt_dict = receipt.to_dict()
    payload = json.dumps(receipt_dict, indent=2, sort_keys=True)

    print(payload)

    args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_path.write_text(payload, encoding="utf-8")

    return 0 if receipt_dict["all_gates_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
