"""Regression bound for benchmarks/architecture_qualification.py.

Chicago style: runs the real benchmark script as a real subprocess over the real court
and asserts on its emitted JSON. The committed host receipt
(receipts/v26.9.26/architecture-qualification-bench.json) records the observed numbers;
the bounds below give ~25x headroom over them so CI noise does not flap, while an
algorithmic regression (e.g. quadratic frontier, per-call recompilation) still fails.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "benchmarks" / "architecture_qualification.py"
RECEIPT = ROOT / "receipts" / "v26.9.26" / "architecture-qualification-bench.json"

QUALIFY_MEDIAN_NS_BOUND = 5_000_000
REPLAY_MEDIAN_NS_BOUND = 10_000_000
FRONTIER64_MEDIAN_NS_BOUND = 1_000_000_000


def _run_bench(*args: str) -> tuple[int, dict]:
    env = dict(os.environ)
    src = str(ROOT / "src")
    env["PYTHONPATH"] = (
        src + os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else src
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=300,
    )
    assert proc.stdout, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


def test_bench_replay_determinism_falsifier_coverage_and_time_bound():
    returncode, report = _run_bench("--repeats", "5", "--replays", "300")
    assert returncode == 0
    assert report["authority"] == "NONE"
    assert report["replay_determinism"]["distinct_receipt_digests"] == 1
    assert report["replay_determinism"]["clean_replays"] == 200
    assert report["replay_determinism"]["qualified"] is True
    assert report["frontier_order_invariant"] is True
    coverage = report["falsifier_coverage"]
    assert coverage["coverage"] == 1.0
    assert coverage["operators"] >= 23
    assert all(r["refusal_codes"] for r in coverage["results"].values())
    timing = report["throughput_ns"]
    assert 0 < timing["qualify_median"] < QUALIFY_MEDIAN_NS_BOUND
    assert 0 < timing["replay_median"] < REPLAY_MEDIAN_NS_BOUND
    assert 0 < timing["frontier64_median"] < FRONTIER64_MEDIAN_NS_BOUND


def test_committed_bench_receipt_is_within_bound_and_names_the_court_source():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == "autofde.architecture-qualification-bench.v1"
    assert receipt["authority"] == "NONE"
    assert receipt["falsifier_coverage"]["coverage"] == 1.0
    assert receipt["replay_determinism"]["distinct_receipt_digests"] == 1
    assert receipt["throughput_ns"]["qualify_median"] < QUALIFY_MEDIAN_NS_BOUND
    assert receipt["throughput_ns"]["frontier64_median"] < FRONTIER64_MEDIAN_NS_BOUND
    _, live = _run_bench("--repeats", "1", "--replays", "10")
    # The receipt is stale the moment the court source changes: re-run the bench.
    assert receipt["court_source_sha256"] == live["court_source_sha256"]
    assert (
        receipt["falsifier_coverage"]["results"]
        == live["falsifier_coverage"]["results"]
    )
