"""Regression bound for the doctrine lab benchmark (real run, real timing).

Runs ``benchmarks/doctrine_lab_bench.py`` on a small workload and enforces its
per-unit REGRESSION_BOUNDS; also checks the committed bench receipt still binds
the pinned catalog and the same bounds. Evidence ceiling REPO_LOCAL_FIXTURE.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from autofde_lab.simulation.doctrine_lab import CATALOG_SHA256

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "doctrine_lab_bench.py"
RECEIPT = ROOT / "receipts" / "v26.9.26" / "doctrine-lab-bench.json"


def _bench_module():
    spec = importlib.util.spec_from_file_location("doctrine_lab_bench", BENCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bench_is_within_regression_bounds(tmp_path: Path):
    bench = _bench_module()
    receipt = bench.run_bench(seeds=[2030], worlds=3, samples=1, workdir=tmp_path)
    assert receipt["workload"]["episodes"] == 1 * 3 * 14
    assert receipt["subject"]["catalog_sha256"] == CATALOG_SHA256
    assert receipt["within_bounds"] == {k: True for k in bench.REGRESSION_BOUNDS}, (
        receipt["per_unit_ms"]
    )
    assert receipt["passed"] is True


def test_committed_bench_receipt_binds_catalog_and_bounds():
    bench = _bench_module()
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["schema"] == bench.SCHEMA
    assert receipt["subject"]["catalog_sha256"] == CATALOG_SHA256
    assert receipt["regression_bounds_ms"] == bench.REGRESSION_BOUNDS
    assert receipt["passed"] is True
    assert (receipt["authority"], receipt["authority_ceiling"]) == ("NONE", "CONSTRUCT")
    for key, bound in bench.REGRESSION_BOUNDS.items():
        assert 0 < receipt["per_unit_ms"][key] <= bound
