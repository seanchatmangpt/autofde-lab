"""Core plan kinds K1/K2/K3/K7 through run_kind(), K2-vs-K3 differential, covering-array sanity."""
import itertools
import os

import pytest

import coverage_cover as cc
from plankinds import Skip, registry, run_kind
from plankinds import k01_aries, k02_minizinc, k03_cpsat, k07_ledger

KINDS = [k01_aries, k02_minizinc, k03_cpsat, k07_ledger]


def test_seed_is_set():
    assert os.environ["PLAN_TEST_SEED"].isdigit()


def test_registry_contains_core_kinds():
    assert {"K1", "K2", "K3", "K7"} <= set(registry())


@pytest.mark.parametrize("mod", KINDS, ids=lambda m: m.KIND)
def test_kind_rows_match_expectation(mod):
    rows = run_kind(mod)
    if rows[0]["status"] == "SKIP":
        pytest.skip(rows[0]["detail"])
    bad = [r for r in rows if not r["ok"]]
    assert rows and not bad, bad


def test_ledger_refusal_classes():
    for c in k07_ledger.cases():
        o = k07_ledger.run(c)
        if c.payload["refusal"]:
            assert c.payload["refusal"] in o.detail, (c.id, o)


def test_k2_k3_differential_every_disagreement_registered():
    if k03_cpsat.probe() or k02_minizinc.probe():
        pytest.skip("cpsat or minizinc not runnable")
    rows = k03_cpsat.differential()
    assert rows
    unregistered = [r for r in rows if not r["agree"] and r["case"] not in k03_cpsat.REGISTERED_DIVERGENCES]
    assert not unregistered, unregistered
    for r in rows:
        print("DIFF", r)


@pytest.mark.parametrize("t,label", [(2, "pairwise"), (3, "order-3")])
def test_covering_array_exhaustive_tuple_coverage(t, label):
    sp = cc.space()
    rows, gen = cc.generate(t)
    print(f"{label}: size={len(rows)} generator={gen} valid_space={len(sp)}")
    assert all(cc.valid(dict(zip(cc.NAMES, r))) for r in rows)
    assert len(rows) < len(sp)
    # independent exhaustive check, not via cc.uncovered
    for idx in itertools.combinations(range(len(cc.NAMES)), t):
        want = {tuple(r[i] for i in idx) for r in sp}
        got = {tuple(r[i] for i in idx) for r in rows}
        assert want <= got, (idx, want - got)


def test_order3_not_smaller_than_pairwise():
    assert len(cc.generate(3)[0]) >= len(cc.generate(2)[0])
