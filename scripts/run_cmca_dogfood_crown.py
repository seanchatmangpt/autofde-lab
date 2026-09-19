#!/usr/bin/env python3
"""Run the v26.9.17 CMCA self-dogfood crown and emit a demo receipt."""

from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path

from autofde_lab.agent.cmca_dogfood_crown import run_cmca_dogfood_crown


def _hosted_subject_identity() -> dict[str, str] | None:
    head_sha = os.environ.get("CROWN_HEAD_SHA")
    if not head_sha:
        return None

    identity = {
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "head_sha": head_sha,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "runner_arch": os.environ.get("RUNNER_ARCH", ""),
        "python_version": platform.python_version(),
        "uv_version": os.environ.get("CROWN_UV_VERSION", ""),
    }
    missing = sorted(key for key, value in identity.items() if not value)
    if missing:
        raise RuntimeError(
            "hosted crown identity is incomplete: " + ", ".join(missing)
        )
    return identity


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
    subject_identity = _hosted_subject_identity()
    payload = result.to_dict(subject_identity=subject_identity)
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
            f"Replay inference avoidance: {result.replay_inference_avoidance_rate:.0%}"
        )
        print(f"Crown receipt: {result.crown_receipt_hash}")
        if "artifact_receipt_hash" in payload:
            print(f"Hosted artifact receipt: {payload['artifact_receipt_hash']}")
        print(f"Standing: {result.standing}")

    return 0 if result.is_alive else 1


if __name__ == "__main__":
    raise SystemExit(main())
