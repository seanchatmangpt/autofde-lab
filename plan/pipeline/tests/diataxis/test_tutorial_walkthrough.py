"""Tutorial walkthrough: blank store -> settled work order, judged by pm4pytest, fail-closed.

Real store, solvers and ledger; every name/number is generated; bounds come from
diataxis_envelopes.toml. Twin: model tag omitted => MISSING[...] and a fitness violation."""
import hashlib
import os
import random
import tomllib
from pathlib import Path

import pytest
from pm4pytest.conformance import ConformanceSpec
from pm4pytest.ocpq import OCPQ
from pm4pytest.temporal import TemporalSLA

from enterprise_pipeline import ocel_bridge, staged, store
from conftest import build_world
from helpers_world import nm, run_visit

ENV = tomllib.loads((Path(__file__).resolve().parent / "diataxis_envelopes.toml").read_text())
ACT, OBJ, RATIO, SLA = ENV["activities"], ENV["objects"], ENV["ratios"], ENV["sla_seconds"]
MEDIA, QUOTE = ENV["media"], ENV["quote"]


def _media(A, wo, ty):
    A("field", "media", {"wo": wo, "media_type": ty, "name": nm(ty),
                         "sha256": hashlib.sha256(os.urandom(MEDIA["bytes_len"])).hexdigest()})


def journey(sp, include_model_tag):
    """Blank store -> entity..provider..WO -> dispatch -> visit -> evidence -> plan -> settle."""
    A, o, nums = build_world(sp, part=True)
    st = store.reduce(store.read(sp))
    r = staged.plan_wo(st, o["wo"])
    assert r["rc"] == 0, r["out"]
    k, p = staged.observe_plan(st, o["wo"], r)
    store.append("system", k, p, path=sp)
    run_visit(A, o)
    q = random.randint(QUOTE["minutes_lo"], QUOTE["minutes_hi"])
    A("coord", "proposal_quote", {"wo": o["wo"], "minutes": q})
    A("coord", "client_attest", {"wo": o["wo"], "minutes": q})
    for ty in MEDIA["visit_types"]:
        _media(A, o["wo"], ty)
    if include_model_tag:
        _media(A, o["wo"], MEDIA["tag_type"])
    return A, o, nums


def finish(sp, wo):
    """Plan at qa-review (plan_closed) then settle (ledger_settled); returns (plan, rc, out)."""
    st = store.reduce(store.read(sp))
    r = staged.plan_wo(st, wo)
    if r["rc"] != 0:
        return r, None, None
    k, p = staged.observe_plan(st, wo, r)
    store.append("system", k, p, path=sp)
    st = store.reduce(store.read(sp))
    rc, out = staged.settle(st, wo)
    if rc == 0:
        k, p = staged.observe_settle(wo, rc, out)
        store.append("system", k, p, path=sp)
    return r, rc, out


def judge(session, sp, ref):
    ocel_bridge.replay_into_session(session, sp)
    spec = ConformanceSpec.from_fsm([ocel_bridge.trace(ref)], min_fitness=ENV["fitness"]["min"])
    spec.allowed_transitions = ocel_bridge.bounded_transitions(
        ocel_bridge.alphabet(sp) | ocel_bridge.alphabet(ref))
    session.set_conformance(spec)
    return spec


@pytest.fixture()
def settled(blank_store):
    A, o, nums = journey(blank_store, include_model_tag=True)
    r, rc, out = finish(blank_store, o["wo"])
    assert rc == 0, (r["out"], out)
    return blank_store, o, nums, out


@pytest.mark.conformance
@pytest.mark.ocpq
@pytest.mark.temporal_sla
def test_tutorial_blank_store_to_settled_fitness_one(pm4py_session, settled):
    sp, o, nums, out = settled
    judge(pm4py_session, sp, sp)
    pm4py_session.set_ocpq(
        OCPQ().require_object_type(*OBJ["required"]).traverse(*OBJ["traversal"])
        .require_activity(ACT["model_tag_media"])
        .require_balanced_ratio(ACT["checkin"], ACT["checkout"], RATIO["checkin_to_checkout"])
        .require_balanced_ratio(ACT["plan_closed"], ACT["ledger_settled"],
                                RATIO["plan_closed_to_ledger_settled"]))
    pm4py_session.set_temporal_sla(
        TemporalSLA()
        .require_max_latency(ACT["dispatch"], ACT["checkin"], SLA["dispatch_to_checkin"])
        .require_max_latency(ACT["checkin"], ACT["checkout"], SLA["checkin_to_checkout"])
        .require_max_latency(ACT["work_order"], ACT["ledger_settled"],
                             SLA["work_order_to_ledger_settled"]))


def test_tutorial_settled_state_and_ledger(settled):
    sp, o, nums, out = settled
    kinds = [e["kind"] for e in store.read(sp)]
    assert kinds[0] == "entity" and kinds.count("ledger_settled") == 1
    assert kinds.index("plan_closed") < kinds.index("ledger_settled")
    st = store.reduce(store.read(sp))
    assert (o["wo"], "ledger_settled") in st["observed"]


@pytest.mark.conformance
@pytest.mark.expected_conformance_violation("PETRI_NET_FITNESS_VIOLATION")
def test_tutorial_twin_model_tag_omitted_violates_fitness(pm4py_session, blank_store, tmp_path):
    ref = tmp_path / "ref.ndjson"
    A, o, _ = journey(ref, include_model_tag=True)
    finish(ref, o["wo"])
    A2, o2, _ = journey(blank_store, include_model_tag=False)
    finish(blank_store, o2["wo"])
    judge(pm4py_session, blank_store, ref)


def test_tutorial_twin_model_tag_omitted_is_missing(blank_store):
    A, o, _ = journey(blank_store, include_model_tag=False)
    st = store.reduce(store.read(blank_store))
    c = staged.compile_wo(st, o["wo"])
    r, rc, out = finish(blank_store, o["wo"])
    assert rc is None and r["rc"] != 0
    assert any(m.startswith("MISSING[") for m in c.missing) or "MISSING[" in r["out"], (c.missing, r["out"])
    assert "ledger_settled" not in [e["kind"] for e in store.read(blank_store)]
