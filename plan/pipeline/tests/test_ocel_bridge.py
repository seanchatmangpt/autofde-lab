"""Chicago-style: real store file, real pm4pytest session/CLI; names and numbers generated."""
import json
import os
import random
import subprocess
import sys
import uuid
from datetime import date, timedelta

import pytest

pytest.importorskip("pm4pytest")
import pm4py
from pm4pytest.conformance import ConformanceSpec
from pm4pytest.plugin import PM4PySession

from enterprise_pipeline import ocel_bridge as ob
from enterprise_pipeline import store


def nm(tag):
    return f"{random.choice('abcdefghijklmnopqrstuvwxyz')}{uuid.uuid4().hex[:8]}_{tag}"


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.ndjson"


def build(sp, visit=True):
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    o = {k: nm(k) for k in ("ent", "dba", "ss4", "cli", "site", "asset", "coord", "prov", "w9p",
                            "trade", "sub", "st", "prio", "wo", "photo")}
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "entity_doc", {"doc_type": "ss4_doc", "name": o["ss4"]})
    for ty, k in (("trade", "trade"), ("sub_trade", "sub"), ("state_jurisdiction", "st"),
                  ("priority_tier", "prio")):
        A("admin", "taxonomy", {"type": ty, "name": o[k]})
    o["par"] = nm("par")
    A("admin", "client", {"name": o["par"], "kind": store.subtypes("client")[0]})
    A("admin", "client", {"name": o["cli"], "kind": "secondary_client", "parent": o["par"]})
    A("admin", "client_rate", {"client": o["cli"], "trade": o["trade"],
                               "cents": random.randint(9000, 20000)})
    A("admin", "site", {"name": o["site"], "client": o["cli"], "state": o["st"],
                        "territory_client": o["cli"]})
    A("admin", "asset", {"name": o["asset"], "site": o["site"]})
    A("coord", "coordinator", {"name": o["coord"]})
    A("align", "provider", {"name": o["prov"], "kind": "sub_1099"})
    A("align", "provider_doc", {"provider": o["prov"], "doc_type": "w9_doc", "name": o["w9p"],
                                "valid": True})
    A("align", "provider_approval", {"provider": o["prov"], "trade": o["trade"],
                                     "sub_trade": o["sub"]})
    A("coord", "work_order", {
        "name": o["wo"], "kind": "reactive_wo", "wo_type": "reactive", "client": o["cli"],
        "site": o["site"], "trade": o["trade"], "sub_trade": o["sub"], "priority": o["prio"],
        "coordinator": o["coord"], "nte_cents": random.randint(50000, 400000),
        "onsite_sla_min": random.randint(600, 3000), "complete_sla_min": random.randint(3100, 6000)})
    if visit:
        A("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]})
        A("field", "geofence_attest", {"wo": o["wo"]})
        A("field", "checkin", {"wo": o["wo"]})
        mt = store.subtypes("media_artifact")[0]
        A("field", "media", {"wo": o["wo"], "media_type": mt, "name": o["photo"],
                             "sha256": uuid.uuid4().hex})
        A("field", "checkout", {"wo": o["wo"]})
    return A, o


def discovered_spec(path):
    """ConformanceSpec.from_fsm builds timestamps as f'10:0{step_idx}:00', which is invalid for
    paths of >= 10 steps (pm4pytest nit); discover the same net with valid timestamps."""
    import pandas as pd
    base = pd.Timestamp("2026-10-04 10:00:00")
    df = pd.DataFrame([{"case:concept:name": "c0", "concept:name": a,
                        "time:timestamp": base + pd.Timedelta(seconds=i)}
                       for i, a in enumerate(path)])
    net, im, fm = pm4py.discover_petri_net_inductive(df)
    return ConformanceSpec(petri_net=net, initial_marking=im, final_marking=fm, min_fitness=1.0)


def build_short(sp):
    """<= 9 events so the CLI's from_fsm (single-digit step index) can parse the path."""
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    o = {k: nm(k) for k in ("ent", "dba", "trade", "coord", "prov")}
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "taxonomy", {"type": "trade", "name": o["trade"]})
    A("coord", "coordinator", {"name": o["coord"]})
    A("align", "provider", {"name": o["prov"], "kind": "sub_1099"})
    A("align", "device_attested", {"provider": o["prov"]})
    return o


def session_for(sp):
    s = PM4PySession(nm("t"))
    ob.replay_into_session(s, sp)
    return s


def test_every_store_kind_lands_as_activity_and_media_is_typed(sp):
    A, o = build(sp)
    evs = store.read(sp)
    s = session_for(sp)
    got = [e.type for e in s.collector.events]
    assert len(got) == len(evs)
    assert set(got) == ob.alphabet(sp)
    for e in evs:
        assert (f"media:{e['payload']['media_type']}" if e["kind"] == "media" else e["kind"]) in got
    assert "media" not in got
    ids = {x.id: x.type for x in s.collector.objects}
    assert ids[o["wo"]] == "work_order" and ids[o["photo"]] == "media"
    assert ids[o["trade"]] == "trade" and ids[o["dba"]] == "dba"
    dispatch = next(e for e in s.collector.events if e.type == "dispatch")
    assert {(r["objectId"], r["qualifier"]) for r in dispatch.relationships} >= {
        (o["wo"], "wo"), (o["prov"], "provider")}
    assert dispatch.attributes["avatar"] == "coord" and dispatch.time.tzinfo is not None
    times = [e.time for e in s.collector.events]
    assert times == sorted(times) and len(set(times)) == len(times)


def test_refused_event_never_projected(sp):
    A, o = build(sp)
    before = ob.trace(sp)
    with pytest.raises(store.Refused):
        A("field", "checkin", {"wo": o["wo"]})        # wrong stage
    with pytest.raises(store.Refused):
        A("coord", "dispatch", {"wo": nm("ghost"), "provider": o["prov"]})
    with pytest.raises(store.Refused):
        A("admin", "coordinator", {"name": o["coord"]})  # duplicate
    s = session_for(sp)
    assert [e.type for e in s.collector.events] == before
    assert ob.trace(sp).count("checkin") == 1


def test_rogue_kind_fails_bounded_spec_but_legal_passes(sp):
    A, o = build(sp)
    legal = ob.trace(sp)
    bound = ob.bounded_transitions(ob.alphabet(sp))
    spec = discovered_spec(legal)
    spec.allowed_transitions = bound
    s = session_for(sp)
    ok = spec.evaluate([{"concept:name": e.type, "time:timestamp": e.time}
                        for e in s.collector.events])
    assert ok.success, ok.violations
    rogue = nm("rogue")
    with sp.open("a") as f:   # bypasses store.append on purpose: a foreign writer
        f.write(json.dumps({"seq": len(legal) + 1, "ts": store.read(sp)[-1]["ts"] + 1,
                            "avatar": "x", "kind": rogue, "payload": {}}) + "\n")
    s2 = session_for(sp)
    bad = spec.evaluate([{"concept:name": e.type, "time:timestamp": e.time}
                         for e in s2.collector.events])
    assert not bad.success
    assert any("FSM_INVALID_TRANSITION" in v and rogue in v for v in bad.violations)


def cli(*args):
    env = dict(os.environ)
    return subprocess.run([sys.executable, "-m", "pm4pytest.cli", *args], capture_output=True,
                          text=True, env=env, timeout=300)


def test_sqlite_roundtrips_through_pm4pytest_cli(sp, tmp_path):
    build_short(sp)
    out = ob.write_sqlite(sp, tmp_path / "live.sqlite")
    ocel = pm4py.read_ocel2_sqlite(str(out))
    assert set(ocel.events["ocel:activity"]) == ob.alphabet(sp)
    legal = ",".join(ob.trace(sp))
    r = cli("check-conformance", "-l", str(out), "--fsm", legal, "--format", "json")
    assert r.returncode == 0, r.stdout + r.stderr
    t = ob.trace(sp)
    t[1], t[2] = t[2], t[1]          # swap two steps: violated path
    r2 = cli("check-conformance", "-l", str(out), "--fsm", ",".join(t), "--format", "json")
    assert r2.returncode == 1, r2.stdout + r2.stderr
