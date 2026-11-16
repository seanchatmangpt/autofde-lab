"""store_cli over a real store file, real MiniZinc/planner/ledger. No mocks."""
import json
import os
import random
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from enterprise_pipeline import store

PIPE = Path(__file__).resolve().parents[1]


def nm(tag):
    return f"{random.choice('abcdefghijklmnopqrstuvwxyz')}{uuid.uuid4().hex[:8]}_{tag}"


def cli(cmd, store_file, payload=None, clock="1000000000"):
    env = {**os.environ, "PLAN_STORE": str(store_file), "PLAN_CLOCK_NOW": clock,
           "PYTHONPATH": str(PIPE)}
    r = subprocess.run([sys.executable, "-m", "enterprise_pipeline.store_cli", cmd],
                       input=json.dumps(payload or {}), capture_output=True, text=True, env=env,
                       cwd=PIPE.parent, timeout=900)
    return r.returncode, json.loads(r.stdout), r.stderr


SEQ = [
    ("admin", "entity", lambda o: {"name": o["ent"], "dba": o["dba"]}),
    ("admin", "taxonomy", lambda o: {"type": "trade", "name": o["trade"]}),
    ("admin", "client", lambda o: {"name": o["cli"], "kind": "secondary_client",
                                   "delivery_mode": store.domain_constants("delivery_channel")[0],
                                   "payment_terms_days": 30}),
]


def _o():
    return {k: nm(k) for k in ("ent", "dba", "trade", "cli")}


def test_parity_reduce_cli_vs_direct(tmp_path, monkeypatch):
    o = _o()
    cli_store, direct_store = tmp_path / "cli.ndjson", tmp_path / "direct.ndjson"
    for av, kind, mk in SEQ:
        rc, ev, _ = cli("append", cli_store, {"avatar": av, "kind": kind, "payload": mk(o)})
        assert rc == 0 and ev["kind"] == kind
        store.append(av, kind, mk(o), path=direct_store, now=ev["ts"])
    monkeypatch.setenv("PLAN_CLOCK_NOW", "1000000000")
    direct = json.loads(json.dumps(store.reduce(store.read(direct_store)), sort_keys=True, default=str))
    rc, via_cli, _ = cli("reduce", cli_store)
    assert rc == 0 and via_cli == direct
    assert store.read(cli_store) == store.read(direct_store)


def test_refusal_passes_through_typed(tmp_path):
    f = tmp_path / "e.ndjson"
    ghost = nm("ghost")
    rc, out, _ = cli("append", f, {"avatar": "coord", "kind": "checkin", "payload": {"wo": ghost}})
    assert rc == 2 and isinstance(out["refused"], str) and out["refused"]
    with pytest.raises(store.Refused) as e:
        store.append("coord", "checkin", {"wo": ghost}, path=tmp_path / "d.ndjson")
    assert out["refused"] == str(e.value)
    assert not f.exists() or store.read(f) == []


def test_missing_and_bad_input_refuse(tmp_path):
    f = tmp_path / "e.ndjson"
    rc, out, _ = cli("append", f, {"avatar": "admin"})
    assert rc == 2 and "MISSING[kind]" in out["refused"]
    rc, out, _ = cli("plan", f, {})
    assert rc == 2 and "MISSING[wo_id]" in out["refused"]


def test_taxonomy_shape(tmp_path):
    rc, out, _ = cli("taxonomy", tmp_path / "e.ndjson")
    assert rc == 0
    assert set(out["subtypes"]) == {"doc_slot", "media_artifact", "taxonomy", "client", "provider"}
    assert out["subtypes"]["client"] == store.subtypes("client")
    assert out["constants"]["delivery_channel"] == store.domain_constants("delivery_channel")
    from enterprise_pipeline import align
    assert out["dims"] == align.DIMS


def _toolchain_or_skip():
    if shutil.which("minizinc") is None:
        print("[SKIP] minizinc not on PATH")
        pytest.skip("minizinc not on PATH")


def test_dispatch_refuses_unknown_wo_and_ineligible(tmp_path):
    f = tmp_path / "e.ndjson"
    rc, out, _ = cli("dispatch", f, {"wo_id": nm("w"), "provider": nm("p")})
    assert rc == 2 and "UNKNOWN" in out["refused"]


def test_settle_without_visit_is_typed_refusal(tmp_path):
    f = tmp_path / "e.ndjson"
    rc, out, _ = cli("settle", f, {"wo_id": nm("w")})
    assert rc == 2 and out["refused"]


def test_end_to_end_dispatch_plan_settle_over_cli(tmp_path):
    _toolchain_or_skip()
    import hashlib
    import test_staged as ts
    f = tmp_path / "e.ndjson"
    A, o, _ = ts.build(f)
    import time
    ck = str(time.time() + 3600)
    rc, out, _ = cli("dispatch", f, {"wo_id": o["wo"], "provider": o["prov"]}, clock=ck)
    assert rc == 0 and out["kind"] == "dispatch", out
    for k in ("geofence_attest", "checkin", "checkout"):
        A("field", k, {"wo": o["wo"]})
    q = 120
    A("coord", "proposal_quote", {"wo": o["wo"], "minutes": q})
    A("coord", "client_attest", {"wo": o["wo"], "minutes": q})
    for ty in ("before_media", "after_media"):
        A("field", "media", {"wo": o["wo"], "media_type": ty, "name": nm(ty),
                             "sha256": hashlib.sha256(os.urandom(8)).hexdigest()})
    rc, out, _ = cli("plan", f, {"wo_id": o["wo"]}, clock=ck)
    assert rc == 0 and out["rc"] == 0 and out["observed"]["kind"] == "plan_closed", out
    rc, out, _ = cli("settle", f, {"wo_id": o["wo"]}, clock=ck)
    assert rc == 0 and out["observed"]["kind"] == "ledger_settled", out
    rc, st, _ = cli("reduce", f)
    assert rc == 0


def test_events_equal_appended_sequence(tmp_path):
    o = _o()
    f = tmp_path / "e.ndjson"
    rc, evs, _ = cli("events", f)
    assert rc == 0 and evs == []
    appended = []
    for av, kind, mk in SEQ:
        rc, ev, _ = cli("append", f, {"avatar": av, "kind": kind, "payload": mk(o)})
        assert rc == 0
        appended.append(ev)
    rc, evs, _ = cli("events", f)
    assert rc == 0 and evs == appended == store.read(f)
    assert [e["seq"] for e in evs] == [1, 2, 3]
    assert all(set(e) == {"seq", "ts", "avatar", "kind", "payload"} for e in evs)


def test_concurrent_appends_unique_seq(tmp_path):
    sf = tmp_path / "s.ndjson"
    env = {**os.environ, "PLAN_STORE": str(sf), "PYTHONPATH": str(PIPE)}
    procs = [subprocess.Popen([sys.executable, "-m", "enterprise_pipeline.store_cli", "append"],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=env, cwd=PIPE.parent)
             for _ in range(12)]
    for i, p in enumerate(procs):
        p.stdin.write(json.dumps({"avatar": "admin", "kind": "taxonomy",
                                  "payload": {"type": "trade", "name": f"t{i}"}}).encode())
        p.stdin.close()
    for p in procs:
        assert p.wait(timeout=60) == 0
    seqs = [json.loads(l)["seq"] for l in sf.read_text().splitlines()]
    assert sorted(seqs) == list(range(1, 13))


def test_torn_tail_healed_and_bad_inputs_typed(tmp_path):
    sf = tmp_path / "s.ndjson"
    assert cli("append", sf, {"avatar": "admin", "kind": "taxonomy",
                              "payload": {"type": "trade", "name": "t1"}})[0] == 0
    with sf.open("a") as f:
        f.write("torn{")
    rc, out, _ = cli("reduce", sf)
    assert rc == 0 and len(store.read(sf)) == 1
    assert cli("append", sf, {"avatar": "a", "kind": "entity", "payload": [1]})[:2] == (
        2, {"refused": "REFUSED[TypeError: payload must be a JSON object]"})
    for c in ("plan", "settle"):
        rc, out, _ = cli(c, sf, {"wo_id": "nope"})
        assert rc == 2 and out["refused"] == "UNKNOWN[wo nope]"
