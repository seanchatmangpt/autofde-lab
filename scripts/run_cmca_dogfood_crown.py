#!/usr/bin/env python3
"""Run the v26.9.17 CMCA self-dogfood crown and emit a demo receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autofde_lab.agent.cmca_dogfood_crown import run_cmca_dogfood_crown


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the eight-use-case CMCA UNKNOWN->KNOWN dogfood crown."
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path for the canonical crown receipt JSON.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only JSON (suitable for machine consumers).",
    )
    args = parser.parse_args()

    result = run_cmca_dogfood_crown()
    payload = result.to_dict()
    rendered = json.dumps(payload, sort_keys=True, indent=2)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")

    if args.json:
        print(rendered)
    else:
        print("CMCA v26.9.17 — SELF-DOGFOOD CROWN")
        print("=" * 72)
        for case in result.cases:
            discovery = "PASS" if case.discovery.verified else "FAIL"
            replay = "PASS" if case.replay.verified else "FAIL"
            reuse = "IDENTICAL" if case.replay_identical else "DIVERGED"
            print(
                f"{case.case_id:>4}  {case.title:<46} "
                f"E1={discovery:<4}  E2={replay:<4}  {reuse}"
            )
        print("-" * 72)
        print(
            "Frontier resolution calls: "
            f"Episode 1={result.frontier_resolution_calls_episode_1}, "
            f"Episode 2={result.frontier_resolution_calls_episode_2}"
        )
        print(f"Compiled experience rules: {result.compiled_experience_rules}")
        print(
            "Replay inference avoidance: "
            f"{result.replay_inference_avoidance_rate:.0%}"
        )
        print(f"Crown receipt: {result.crown_receipt_hash}")
        print(f"Standing: {result.standing}")

    return 0 if result.is_alive else 1


if __name__ == "__main__":
    raise SystemExit(main())
