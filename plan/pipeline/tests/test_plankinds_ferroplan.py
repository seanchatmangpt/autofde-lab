"""Runs K11-K13 (ferroplan) end to end; every runnable case must hit its expected outcome."""
import pytest

from plankinds import run_kind
from plankinds import k11_hddl_fond, k12_pddl_classic, k13_ppddl

MODS = [k11_hddl_fond, k12_pddl_classic, k13_ppddl]


@pytest.mark.parametrize("mod", MODS, ids=[m.KIND for m in MODS])
def test_kind_rows(mod):
    rows = run_kind(mod)
    assert rows, "every kind yields at least one row"
    if mod.probe():
        assert [r["status"] for r in rows] == ["SKIP"], rows
        return
    assert all(r["status"] != "SKIP" for r in rows)
    bad = [r for r in rows if r["status"] != r["expect"]]
    assert not bad, bad
