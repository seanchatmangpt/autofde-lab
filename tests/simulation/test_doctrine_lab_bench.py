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


def test_committed_bench_receipt_names_the_exact_source_it_timed():
    """R identity: the receipt's source_tree_sha256 must recompute from the tree it
    is committed in; any change to the timed code requires re-running the bench."""
    bench = _bench_module()
    receipt = json.loads(RECEIPT.read_text())
    assert (
        receipt["subject"]["source_tree_sha256"]
        == (bench.source_identity(ROOT)["source_tree_sha256"])
    ), "timed source changed: re-run benchmarks/doctrine_lab_bench.py --out <receipt>"
    assert (
        receipt["subject"]["source_files"]
        == bench.source_identity(ROOT)["source_files"]
    )


def test_source_identity_changes_with_any_timed_file(tmp_path: Path):
    bench = _bench_module()
    for rel in bench.SOURCE_ROOTS:
        src = ROOT / rel
        dst = tmp_path / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        else:
            for p in src.rglob("*"):
                if (
                    p.is_file()
                    and p.suffix in bench.SOURCE_SUFFIXES
                    and "__pycache__" not in p.parts
                ):
                    target = dst / p.relative_to(src)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(p.read_bytes())
    before = bench.source_identity(tmp_path)
    assert before == bench.source_identity(ROOT)
    seal = tmp_path / "src/autofde_lab/simulation/doctrine_lab/seal.py"
    seal.write_bytes(seal.read_bytes() + b"\n")
    assert (
        bench.source_identity(tmp_path)["source_tree_sha256"]
        != before["source_tree_sha256"]
    )
