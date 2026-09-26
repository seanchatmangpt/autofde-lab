#!/usr/bin/env python3
"""Deterministic timing benchmark for PR #194's evidence capabilities.

Measures, on synthetic but real on-disk inputs (a real evaluator.py and real
case JSON files, zero model calls):

- dgf_dataset_load_once: run_dgf_dataset, kernel loaded once per run;
- dgf_dataset_reload_per_case: the pre-hardening shape (evaluator re-read,
  re-hashed and re-executed for every case), kept as the comparison baseline;
- obstruction_unique: find_information_obstruction over N distinct observations;
- obstruction_single_bucket_dup: N cases, one observation, identical overlapping
  acceptance (deduplicated per bucket);
- obstruction_single_bucket_distinct: N cases, one observation, pairwise
  overlapping but distinct acceptance sets (quadratic worst case).

Timing = median of --repeats wall-clock runs (time.perf_counter). The JSON
report carries sizes, medians, per-item costs and the platform identity.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from autofde_lab.evidence.dgf_substitution import (
    load_dgf_kernel,
    run_dgf_case,
    run_dgf_dataset,
)
from autofde_lab.evidence.information_obstruction import (
    DecisionCase,
    find_information_obstruction,
)

EVALUATOR = """
def evaluate_route(case, occurrences):
    out = []
    for occurrence, decision in zip(occurrences, case["decisions"], strict=True):
        row = dict(decision)
        row["occurrence_id"] = occurrence["occurrence_id"]
        row["position"] = occurrence["position"]
        out.append(row)
    return out
"""


def build_dataset(root: Path, cases: int, gates: int) -> tuple[Path, Path]:
    dgf_root = root / "dgf"
    dgf_root.mkdir(parents=True)
    (dgf_root / "evaluator.py").write_text(EVALUATOR.strip() + "\n", encoding="utf-8")
    dataset = root / "dataset"
    for c in range(cases):
        case_dir = dataset / f"case-{c:05d}"
        case_dir.mkdir(parents=True)
        occurrences = [
            {"occurrence_id": f"c{c}-o{g}", "position": g} for g in range(gates)
        ]
        decisions = [
            {"gate": f"g{g}", "phase": "governance", "disposition": "GO"}
            for g in range(gates)
        ]
        reference = [
            {**d, "occurrence_id": o["occurrence_id"], "position": o["position"]}
            for d, o in zip(decisions, occurrences)
        ]
        (case_dir / "01_route_manifest.json").write_text(
            json.dumps({"occurrences": occurrences}), encoding="utf-8"
        )
        (case_dir / "99_hidden_ground_truth.json").write_text(
            json.dumps(
                {
                    "case_id": f"case-{c:05d}",
                    "canonical_truth": {"decisions": decisions},
                    "reference_decisions": reference,
                }
            ),
            encoding="utf-8",
        )
    return dgf_root, dataset


def median_seconds(fn: Callable[[], object], repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def run(
    cases: int, gates: int, obstruction_n: int, bucket_n: int, repeats: int
) -> dict:
    results: dict[str, dict[str, float | int]] = {}
    with tempfile.TemporaryDirectory(prefix="dgf-bench-") as tmp:
        dgf_root, dataset = build_dataset(Path(tmp), cases, gates)

        def load_once() -> None:
            scores, summary = run_dgf_dataset(dataset, dgf_root=dgf_root)
            assert summary.routes_passed == cases, summary

        def reload_per_case() -> None:
            dirs = sorted(p for p in dataset.iterdir())
            scores = [run_dgf_case(d, dgf_root=dgf_root) for d in dirs]
            assert all(s.route_match for s in scores)

        # sanity: both paths bind the same kernel digest
        assert load_dgf_kernel(dgf_root).digest.startswith("sha256:")

        for name, fn in (
            ("dgf_dataset_load_once", load_once),
            ("dgf_dataset_reload_per_case", reload_per_case),
        ):
            t = median_seconds(fn, repeats)
            results[name] = {
                "n": cases,
                "gates_per_case": gates,
                "median_s": t,
                "per_item_us": t / cases * 1e6,
            }

    unique = [
        DecisionCase(f"u{i}", {"id": i, "docs": ["a", "b"]}, frozenset({"GO"}))
        for i in range(obstruction_n)
    ]
    dup = [
        DecisionCase(f"d{i}", {"docs": ["same"]}, frozenset({"GO", "HOLD"}))
        for i in range(obstruction_n)
    ]
    distinct = [
        DecisionCase(f"x{i}", {"docs": ["same"]}, frozenset({"SHARED", f"o{i}"}))
        for i in range(bucket_n)
    ]
    for name, rows in (
        ("obstruction_unique", unique),
        ("obstruction_single_bucket_dup", dup),
        ("obstruction_single_bucket_distinct", distinct),
    ):

        def scan(rows: list[DecisionCase] = rows) -> None:
            assert find_information_obstruction(rows) is None

        t = median_seconds(scan, repeats)
        results[name] = {
            "n": len(rows),
            "median_s": t,
            "per_item_us": t / len(rows) * 1e6,
        }

    return {
        "benchmark": "autofde-lab PR #194 DGF substitution + evidence ceiling",
        "llm_calls": 0,
        "repeats": repeats,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "results": results,
        "speedup_load_once_vs_reload": (
            results["dgf_dataset_reload_per_case"]["median_s"]
            / results["dgf_dataset_load_once"]["median_s"]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=int, default=500)
    parser.add_argument("--gates", type=int, default=8)
    parser.add_argument("--obstruction-n", type=int, default=20000)
    parser.add_argument("--bucket-n", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run(
        args.cases, args.gates, args.obstruction_n, args.bucket_n, args.repeats
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
