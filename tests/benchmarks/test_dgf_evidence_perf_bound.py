"""Regression bounds for PR #194's evidence benchmarks (Chicago, real inputs).

Bounds are set well above the recorded medians in
receipts/v26.9.26/autofde-lab-194-dgf-evidence-bench.json (arm64, py3.13) so a
slower CI host passes, but below the pre-hardening quadratic cost so the
regression the hardening removed would fail:

- 20000 duplicate-observation, identical-acceptance cases: recorded
  0.08-0.15 s after hardening (idle vs loaded host),
  6.65 s before (every case rescanned the whole bucket).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks"))

import dgf_evidence_bench as bench  # noqa: E402

from autofde_lab.evidence.information_obstruction import (  # noqa: E402
    DecisionCase,
    find_information_obstruction,
)

DUP_BOUND_S = 1.5
UNIQUE_BOUND_S = 2.0
DATASET_PER_CASE_BOUND_US = 5000.0


def test_duplicate_bucket_scan_is_not_quadratic() -> None:
    rows = [
        DecisionCase(f"d{i}", {"docs": ["same"]}, frozenset({"GO", "HOLD"}))
        for i in range(20000)
    ]
    elapsed = bench.median_seconds(lambda: find_information_obstruction(rows), 3)
    assert elapsed < DUP_BOUND_S, elapsed


def test_benchmark_report_within_bounds(tmp_path: Path) -> None:
    report = bench.run(cases=100, gates=8, obstruction_n=20000, bucket_n=500, repeats=3)
    results = report["results"]
    assert report["llm_calls"] == 0
    assert results["obstruction_unique"]["median_s"] < UNIQUE_BOUND_S
    assert results["obstruction_single_bucket_dup"]["median_s"] < DUP_BOUND_S
    assert results["dgf_dataset_load_once"]["per_item_us"] < DATASET_PER_CASE_BOUND_US


def test_obstruction_found_early_in_large_input() -> None:
    rows = [DecisionCase(f"u{i}", {"id": i}, frozenset({"GO"})) for i in range(20000)]
    rows.insert(1, DecisionCase("clash", {"id": 0}, frozenset({"NO_GO"})))
    witness = find_information_obstruction(rows)
    assert witness is not None
    assert (witness.left_case_id, witness.right_case_id) == ("u0", "clash")
