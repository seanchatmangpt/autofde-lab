"""Artifact copies must stay byte-identical to their canonical source.

Canonical PDDL: spec/ (authored domain+problem; executor/fixtures/ are copies).
Canonical MiniZinc: alignment/alignment_dispatch.mzn (the copy exercised by
alignment/run_tests.sh against expected.json; spec/ and pipeline copies follow it).
courts/mzn/alignment_repaired.mzn must equal it; courts/mzn/alignment_dispatch.mzn is the
deliberately unrepaired court input and is excluded.
"""
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PAIRS = [
    ("spec/servengine_ideal_domain.pddl", "executor/fixtures/servengine_ideal_domain.pddl"),
    ("spec/problem_enterprise_ops.pddl", "executor/fixtures/problem_enterprise_ops.pddl"),
    ("alignment/alignment_dispatch.mzn", "spec/alignment_dispatch.mzn"),
    ("alignment/alignment_dispatch.mzn", "pipeline/enterprise_pipeline/alignment_dispatch.mzn"),
    ("alignment/alignment_dispatch.mzn", "courts/mzn/alignment_repaired.mzn"),
]


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


@pytest.mark.parametrize("canonical,copy", PAIRS)
def test_copy_is_byte_identical(canonical, copy):
    assert sha(canonical) == sha(copy), f"{copy} drifted from {canonical}"
