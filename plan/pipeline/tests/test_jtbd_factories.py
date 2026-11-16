"""Browserless court for the factories: determinism, distinctness, and trait semantics."""
import re

import pytest

import jtbd_factories as jf
from enterprise_pipeline import store


def test_same_seed_same_plans_different_seed_different_plans():
    seed = jf.seed_from_env()
    a, b, c = jf.batch(seed), jf.batch(seed), jf.batch(seed + 1)
    assert [(s.name, s.world, s.intended) for s in a] == [(s.name, s.world, s.intended) for s in b]
    assert [s.world for s in a] != [s.world for s in c]


def test_eight_distinct_plans_with_a_pass_fail_mix():
    plans = jf.batch(jf.seed_from_env())
    assert len(plans) == 8 and [p.name for p in plans] == list(jf.TRAITS)
    assert len({p.world["ent"] for p in plans}) == 8
    verdicts = [p.verdict for p in plans]
    assert verdicts.count("pass") == 4 and verdicts.count("fail") == 4
    assert len({p.gate for p in plans if p.verdict == "fail"}) == 4


def test_every_symbol_is_a_valid_store_name_and_unique_within_a_world():
    for p in jf.batch(jf.seed_from_env()):
        syms = [v for k, v in p.world.items() if isinstance(v, str) and len(v) == jf.SYMBOL_LEN]
        assert all(store.NAME_RE.match(s) for s in syms)
        assert len(set(syms)) == len(syms)


def test_failing_plans_are_strict_prefix_like_gates_of_the_intended_path():
    for p in jf.batch(jf.seed_from_env()):
        done = jf.activities(p.steps)
        if p.verdict == "pass":
            assert done == p.intended, p.name
        else:
            assert done != p.intended, p.name


def test_trait_semantics_follow_the_world():
    by = {p.name: p for p in jf.batch(jf.seed_from_env())}
    import math
    charge = lambda w: math.ceil(w["quoted"] * w["cli_rate"] / 60)
    w = by["nte_below_charge"].world
    assert w["prov_rate"] <= w["nte"] < charge(w)
    assert by["attest_mismatch"].world["attest"] != by["attest_mismatch"].world["quoted"]
    assert all(p.world["attest"] == p.world["quoted"] for n, p in by.items() if n != "attest_mismatch")
    assert by["expired_coi"].world["expiry"] < jf.date.today()
    assert all(p.world["expiry"] > jf.date.today() for n, p in by.items() if n != "expired_coi")
    assert not any(s.heading == "model_tag_photo" for s in by["no_part"].steps)
    assert any(s.heading == jf.D["media_tag"] for s in by["part_with_tag"].steps)
    assert not any(s.heading == jf.D["media_tag"] for s in by["withhold_tag"].steps)
    assert all(p.world["cli_rate"] > p.world["prov_rate"] for p in by.values())
