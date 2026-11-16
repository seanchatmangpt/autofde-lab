"""Blank-slate flow over the real store, MiniZinc, planner and ledger. Every name and number
is generated at test time; nothing recorded here is a fixture."""
import hashlib
import json
import math
import os
import random
import subprocess
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from enterprise_pipeline import staged, store
from helpers_world import build, nm, run_visit

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.ndjson"


def test_blank_store_is_typed_missing_not_exception(sp):
    state = store.reduce(store.read(sp))
    assert state["work_orders"] == [] and "entity" not in state
    c = staged.compile_wo(state, "none")
    assert c.text is None and c.missing == ["MISSING[entity]"]
    with pytest.raises(store.Refused, match=r"MISSING\[entity\]"):
        store.append("coord", "coordinator", {"name": nm("c")}, path=sp)


def test_events_refuse_bad_references(sp):
    A, o, _ = build(sp)
    with pytest.raises(store.Refused, match="DUPLICATE"):
        A("admin", "coordinator", {"name": o["coord"]})
    with pytest.raises(store.Refused, match="UNKNOWN"):
        A("coord", "checkin", {"wo": nm("ghost")})
    with pytest.raises(store.Refused, match="STAGE"):
        A("field", "checkin", {"wo": o["wo"]})


def test_stage_one_has_no_prebaked_future_and_plans_dispatch(sp):
    A, o, _ = build(sp)
    c = staged.compile_wo(store.reduce(store.read(sp)), o["wo"])
    assert c.missing == [] and c.text
    for banned in ("media-captured", "geofence-attested", "internal-actual-duration",
                   "external-client-duration", "internal-checked", "ai-vision-verified"):
        assert banned not in c.text, banned
    r = staged.plan_wo(store.reduce(store.read(sp)), o["wo"])
    assert r["rc"] == 0, r["out"]
    names = [s["action"] for s in r["steps"]]
    assert "auto-dispatch-aligned-provider" in names and "settle-provider-ap-payout" not in names


def test_full_flow_refusal_flips_and_money_matches_ledger(sp):
    A, o, nums = build(sp)
    run_visit(A, o)
    st = store.reduce(store.read(sp))
    assert staged.compile_wo(st, o["wo"]).missing  # quote + attest not yet recorded
    q = random.randint(30, 400)
    A("coord", "proposal_quote", {"wo": o["wo"], "minutes": q})
    A("coord", "client_attest", {"wo": o["wo"], "minutes": q})
    for ty in ("before_media", "after_media"):
        pass
    r0 = staged.plan_wo(store.reduce(store.read(sp)), o["wo"])
    assert r0["missing"] == [] and r0["rc"] == 2, r0["out"]  # no before/after evidence: refused
    for ty in ("before_media", "after_media"):
        data = os.urandom(32)
        A("field", "media", {"wo": o["wo"], "media_type": ty, "name": nm(ty),
                             "sha256": hashlib.sha256(data).hexdigest()})
    st = store.reduce(store.read(sp))
    r1 = staged.plan_wo(st, o["wo"])
    assert r1["rc"] == 0, r1["out"]
    names = [s["action"] for s in r1["steps"]]
    assert "emit-and-deliver-client-invoice" in names and "settle-provider-ap-payout" in names
    rc, out = staged.settle(st, o["wo"])
    assert rc == 0, out
    mins = staged.internal_minutes(st["work_orders"][0]["visit"])
    ar = math.ceil(q * nums["client_rate"] / 60)
    ap = math.ceil(mins * nums["prov_rate"] / 60)
    assert str(ar) in out and str(ap) in out, (ar, ap, out)


def test_part_replacement_needs_model_tag(sp):
    A, o, _ = build(sp, part=True)
    run_visit(A, o)
    q = random.randint(30, 400)
    A("coord", "proposal_quote", {"wo": o["wo"], "minutes": q})
    A("coord", "client_attest", {"wo": o["wo"], "minutes": q})
    for ty in ("before_media", "after_media"):
        A("field", "media", {"wo": o["wo"], "media_type": ty, "name": nm(ty),
                             "sha256": hashlib.sha256(os.urandom(8)).hexdigest()})
    r0 = staged.plan_wo(store.reduce(store.read(sp)), o["wo"])
    assert r0["rc"] == 2 or (r0["rc"] is None and r0["missing"]), r0
    A("field", "media", {"wo": o["wo"], "media_type": "model_tag_photo", "name": nm("tag"),
                         "sha256": hashlib.sha256(os.urandom(8)).hexdigest()})
    r1 = staged.plan_wo(store.reduce(store.read(sp)), o["wo"])
    assert r1["rc"] == 0, r1["out"]


def _kinds(sp, kind):
    return [e for e in store.read(sp) if e["kind"] == kind]


def test_terminal_events_only_on_success_once(sp):
    A, o, _ = build(sp)
    wo = o["wo"]
    # refusal: unplannable problem (rc != 0) records nothing
    bad = {"rc": 2, "out": "x", "goal": "g"}
    assert staged.observe_plan(store.reduce(store.read(sp)), wo, bad) is None
    assert staged.observe_settle(wo, -1, "MISSING[x]") is None
    assert store.read(sp) == [] or not _kinds(sp, "plan_dispatched")
    # success at intake -> exactly one plan_dispatched
    r = staged.plan_wo(store.reduce(store.read(sp)), wo)
    assert r["rc"] == 0, r["out"]
    kind, pl = staged.observe_plan(store.reduce(store.read(sp)), wo, r)
    assert kind == "plan_dispatched" and pl["plan_sha256"] == hashlib.sha256(r["out"].encode()).hexdigest()
    n0 = len(store.read(sp))
    store.append("system", kind, pl, path=sp)
    assert len(store.read(sp)) == n0 + 1 and len(_kinds(sp, "plan_dispatched")) == 1
    with pytest.raises(store.Refused, match="DUPLICATE"):
        store.append("system", kind, pl, path=sp)
    assert len(_kinds(sp, "plan_dispatched")) == 1
    # stage derivation untouched by observation
    assert store.reduce(store.read(sp))["work_orders"][0]["stage"] == "intake"
    # ledger before plan_closed refused; plan_closed outside qa-review refused
    with pytest.raises(store.Refused, match=r"MISSING\[plan_closed\]"):
        store.append("system", "ledger_settled", {"wo": wo, "ledger_sha256": "0" * 64}, path=sp)
    with pytest.raises(store.Refused, match="STAGE"):
        store.append("system", "plan_closed", {**pl}, path=sp)
    with pytest.raises(store.Refused, match="UNKNOWN"):
        store.append("system", "plan_dispatched", {**pl, "wo": nm("ghost")}, path=sp)
    # full visit -> plan_closed -> ledger_settled
    run_visit(A, o)
    q = random.randint(30, 400)
    A("coord", "proposal_quote", {"wo": wo, "minutes": q})
    A("coord", "client_attest", {"wo": wo, "minutes": q})
    for ty in ("before_media", "after_media"):
        A("field", "media", {"wo": wo, "media_type": ty, "name": nm(ty),
                             "sha256": hashlib.sha256(os.urandom(8)).hexdigest()})
    st = store.reduce(store.read(sp))
    with pytest.raises(store.Refused, match="DUPLICATE|STAGE"):
        store.append("system", "plan_dispatched", pl, path=sp)
    r2 = staged.plan_wo(st, wo)
    assert r2["rc"] == 0, r2["out"]
    k2, p2 = staged.observe_plan(st, wo, r2)
    assert k2 == "plan_closed"
    store.append("system", k2, p2, path=sp)
    rc, out = staged.settle(st, wo)
    assert rc == 0, out
    k3, p3 = staged.observe_settle(wo, rc, out)
    assert p3["ledger_sha256"] == hashlib.sha256(out.encode()).hexdigest()
    assert p3["ar_cents"] == json.loads(out)["ar_cents"]
    store.append("system", k3, p3, path=sp)
    with pytest.raises(store.Refused, match="DUPLICATE"):
        store.append("system", k3, p3, path=sp)
    assert [len(_kinds(sp, k)) for k in ("plan_dispatched", "plan_closed", "ledger_settled")] == [1, 1, 1]
    assert store.reduce(store.read(sp))["work_orders"][0]["stage"] == "qa-review"

