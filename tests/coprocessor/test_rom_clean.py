"""ROM-clean proof tests: real subprocesses against a read-only copy of the package."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("verify_rom_clean", REPO / "scripts" / "verify_rom_clean.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)


def test_all_kinds_leave_readonly_tree_untouched():
    with tempfile.TemporaryDirectory(prefix="rom-test-") as td:
        tdp = Path(td)
        V.copy_tree(tdp)
        try:
            proof = V.prove_tree(tdp, readonly=True)
        finally:
            V.make_writable(tdp)
    assert "pddl" in proof["kinds"]
    assert not V.is_dirty(proof["diff"]), proof["diff"]
    assert all(r["status"] != "UNPARSEABLE" for r in proof["results"])
    # BLOCKED kinds are surfaced with their dependency, never hidden.
    for r in proof["results"]:
        if r["status"] == "BLOCKED":
            assert r["blocked_on"]


def test_writing_shim_is_caught_when_tree_is_writable():
    court = V.court_shim()
    assert court["caught_when_writable"], court
    assert "coprocessor/shim_dropping.txt" in court["writable"]["added"]


def test_writing_shim_cannot_write_into_readonly_tree():
    court = V.court_shim()
    assert court["blocked_when_readonly"], court


def test_snapshot_detects_content_change(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    before = V.snapshot(tmp_path)
    (tmp_path / "a.txt").write_text("y")
    assert V.diff_snapshots(before, V.snapshot(tmp_path))["changed"] == ["a.txt"]
