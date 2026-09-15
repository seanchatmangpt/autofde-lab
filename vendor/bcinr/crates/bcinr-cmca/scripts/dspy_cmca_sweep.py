"""Tamper-magnitude calibration sweep for the CMCA allocation DSPy verifier.

Reuses `CmcaAllocationVerifier`, `run_case`, `threshold`, `judge_model_id` from
`dspy_cmca_verifier.py` -- no duplication of judging or subprocess logic here,
only the sweep loop, aggregation, and reporting around them.

Scope note: every tampered call in this sweep perturbs the SAME index (0) used
by `dspy_cmca_verifier.py`'s single-run baseline, varying only the magnitude of
the perturbation (`delta_millionths`). This calibrates sensitivity to
perturbation *size* at one fixed index, not sensitivity across different
indices/positions in the allocation -- that is a distinct, unexplored axis.

Each judge call is a real, distinct LLM call against the live Groq-hosted
`judge_model_id` -- nothing here is cached or reused across repeats.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dspy_cmca_verifier import (  # noqa: E402
    CmcaAllocationVerifier,
    run_case,
)

# delta_millionths applied to index 0's share: +0.3 down to +0.00001 absolute
# shift, matching the tamper index already used in dspy_cmca_verifier.py's
# single-run baseline (index 0), for continuity across the two scripts.
MAGNITUDES = [300000, 100000, 30000, 10000, 3000, 1000, 300, 100, 30, 10]
REPEATS = 3
BASELINE_REPEATS = 5
TAMPER_INDEX = 0


def _binary_path() -> str:
    return os.environ.get(
        "CMCA_ALLOCATE_CLI_BIN",
        "/Users/sac/bcinr/target/debug/cmca_allocate_cli",
    )


def _judge_one(
    verifier: CmcaAllocationVerifier,
    binary_path: str,
    request: dict[str, Any],
    *,
    magnitude: int | None,
    repeat_index: int,
    is_baseline: bool,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "magnitude": magnitude,
        "repeat_index": repeat_index,
        "is_baseline": is_baseline,
    }
    try:
        response = run_case(binary_path, request)
        passed, score, reason = verifier.judge(
            response["reference_allocation"], response["claimed_allocation"]
        )
        entry["suspicion_score"] = score
        entry["passed"] = passed
        entry["reason"] = reason
        entry["error"] = None
    except Exception as exc:  # noqa: BLE001 - deliberately broad: network/subprocess/judge
        entry["suspicion_score"] = None
        entry["passed"] = None
        entry["reason"] = None
        entry["error"] = f"{type(exc).__name__}: {exc}"
    return entry


def run_sweep(
    *, magnitudes: list[int], repeats: int, baseline_repeats: int
) -> list[dict[str, Any]]:
    binary_path = _binary_path()
    verifier = CmcaAllocationVerifier()
    results: list[dict[str, Any]] = []

    untampered_request = {"case": "case_studies", "tamper": None}
    for i in range(baseline_repeats):
        results.append(
            _judge_one(
                verifier,
                binary_path,
                untampered_request,
                magnitude=None,
                repeat_index=i,
                is_baseline=True,
            )
        )

    for magnitude in magnitudes:
        tampered_request = {
            "case": "case_studies",
            "tamper": {"index": TAMPER_INDEX, "delta_millionths": magnitude},
        }
        for i in range(repeats):
            results.append(
                _judge_one(
                    verifier,
                    binary_path,
                    tampered_request,
                    magnitude=magnitude,
                    repeat_index=i,
                    is_baseline=False,
                )
            )

    return results


def summarize(results: list[dict[str, Any]]) -> tuple[dict[Any, dict[str, Any]], int]:
    """Returns (per-magnitude stats keyed by magnitude or 'baseline', error_count)."""
    error_count = sum(1 for r in results if r["error"] is not None)

    groups: dict[Any, list[dict[str, Any]]] = {}
    for r in results:
        key = "baseline" if r["is_baseline"] else r["magnitude"]
        groups.setdefault(key, []).append(r)

    stats: dict[Any, dict[str, Any]] = {}
    for key, entries in groups.items():
        scored = [e for e in entries if e["error"] is None]
        n_total = len(entries)
        n_scored = len(scored)
        scores = [e["suspicion_score"] for e in scored]
        if key == "baseline":
            # false-positive rate: fraction incorrectly flagged as suspicious
            # (passed == False on a genuine, untampered allocation)
            flagged = sum(1 for e in scored if e["passed"] is False)
            rate_label = "false_positive_rate"
            rate = flagged / n_scored if n_scored else None
        else:
            # detection rate: fraction correctly flagged as suspicious
            flagged = sum(1 for e in scored if e["passed"] is False)
            rate_label = "detection_rate"
            rate = flagged / n_scored if n_scored else None

        stats[key] = {
            "n_total": n_total,
            "n_scored": n_scored,
            "n_errors": n_total - n_scored,
            "mean_score": statistics.mean(scores) if scores else None,
            "median_score": statistics.median(scores) if scores else None,
            rate_label: rate,
        }

    return stats, error_count


def print_table(stats: dict[Any, dict[str, Any]], magnitudes: list[int]) -> None:
    print("=== CMCA tamper-magnitude calibration sweep (index 0 only) ===")
    print()
    baseline = stats.get("baseline")
    if baseline is not None:
        fpr = baseline["false_positive_rate"]
        fpr_str = f"{fpr:.2f}" if fpr is not None else "n/a"
        print(
            f"baseline (untampered, n={baseline['n_scored']}/{baseline['n_total']}): "
            f"mean={baseline['mean_score']}, median={baseline['median_score']}, "
            f"false_positive_rate={fpr_str}"
        )
        print()

    header = f"{'magnitude':>10} | {'mean score':>10} | {'median score':>13} | {'detection rate':>14} | note"
    print(header)
    print("-" * len(header))

    first_below_100: int | None = None
    first_zero: int | None = None
    for magnitude in magnitudes:
        s = stats.get(magnitude)
        if s is None:
            continue
        rate = s["detection_rate"]
        rate_str = f"{rate:.2f}" if rate is not None else "n/a"
        mean_str = f"{s['mean_score']:.1f}" if s["mean_score"] is not None else "n/a"
        median_str = (
            f"{s['median_score']:.1f}" if s["median_score"] is not None else "n/a"
        )
        note = ""
        if rate is not None:
            if rate < 1.0 and first_below_100 is None:
                first_below_100 = magnitude
                note = "first < 100% detection"
            if rate == 0.0 and first_zero is None:
                first_zero = magnitude
                note = (note + "; " if note else "") + "first 0% detection"
        if s["n_errors"]:
            note = (note + "; " if note else "") + f"{s['n_errors']} error(s)"
        print(
            f"{magnitude:>10} | {mean_str:>10} | {median_str:>13} | {rate_str:>14} | {note}"
        )

    print()
    print(
        f"approx magnitude where detection first drops below 100%: "
        f"{first_below_100 if first_below_100 is not None else 'not observed in this sweep'}"
    )
    print(
        f"approx magnitude where detection first drops to 0%: "
        f"{first_zero if first_zero is not None else 'not observed in this sweep'}"
    )


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv

    if not os.environ.get("GROQ_API_KEY"):
        print(
            "GROQ_API_KEY is not set in the environment; refusing to run.",
            file=sys.stderr,
        )
        return 1

    magnitudes = [300000] if smoke_test else MAGNITUDES
    repeats = 1 if smoke_test else REPEATS
    baseline_repeats = 0 if smoke_test else BASELINE_REPEATS

    results = run_sweep(
        magnitudes=magnitudes, repeats=repeats, baseline_repeats=baseline_repeats
    )

    out_path = Path(__file__).resolve().parent / "sweep_results.json"
    if not smoke_test:
        out_path.write_text(json.dumps(results, indent=2))
        print(f"wrote {len(results)} raw results to {out_path}")
        print()

    stats, error_count = summarize(results)
    print_table(stats, magnitudes)
    print()
    print(f"failed/errored calls: {error_count} / {len(results)}")

    if smoke_test:
        r = results[0]
        print()
        print(
            f"SMOKE TEST RESULT: magnitude={r['magnitude']} "
            f"suspicion_score={r['suspicion_score']} passed={r['passed']} "
            f"error={r['error']}"
        )
        return 0 if r["error"] is None else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
