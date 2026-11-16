"""K-L4 court: lineage, visits, change order / override receipts, dispatch override, NTE cap.

Real store + real store_cli (MiniZinc/ledger subprocesses). No mocks; numbers are drawn, not literal."""
import math
import random
import time

import pytest

from enterprise_pipeline import store
import helpers_world as hw
from helpers_world import nm
from test_store_cli import cli


def build(sp):
    """hw.build, with the client declared primary (secondary now requires a parent: R2)."""
    orig = store.append

    def shim(avatar, kind, payload, path=None, now=None):
        if kind == "client" and payload.get("kind") == "secondary_client" and not payload.get("parent"):
            payload = {**payload, "kind": "primary_client"}
        return orig(avatar, kind, payload, path=path, now=now)
    store.append = shim
    try:
        return hw.build(sp)
    finally:
        store.append = orig


def _state(sp):
    return store.reduce(store.read(sp))


def _child(A, o, **extra):
    """Second work order in the same entity/client/site as the world's one."""
    name = nm("wo")
    p = {"name": name, "kind": "reactive_wo", "wo_type": "reactive", "client": o["cli"],
         "site": o["site"], "trade": o["trade"], "sub_trade": o["sub"], "priority": o["prio"],
         "coordinator": o["coord"], "nte_cents": random.randint(50000, 400000),
         "onsite_sla_min": random.randint(600, 3000), "complete_sla_min": random.randint(3100, 6000)}
    p.update(extra)
    A("coord", "work_order", p)
    return name


def _refusal(fn):
    with pytest.raises(store.Refused) as e:
        fn()
    return str(e.value)


# ------------------------------------------------------------------ lineage
def test_link_kind_requires_parent(tmp_path):
    A, o, _ = build(tmp_path / "s.ndjson")
    msg = _refusal(lambda: _child(A, o, kind="change_order_wo", link_kind="change_order"))
    assert "MISSING[parent_wo]" in msg


def test_link_to_unknown_parent_refused(tmp_path):
    A, o, _ = build(tmp_path / "s.ndjson")
    ghost = nm("ghost")
    msg = _refusal(lambda: _child(A, o, kind="change_order_wo", link_kind="change_order", parent_wo=ghost))
    assert f"UNKNOWN[work_order:{ghost}]" in msg


def test_change_order_links_parent_and_state_carries_fields(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, _ = build(sp)
    kid = _child(A, o, kind="change_order_wo", link_kind="change_order", parent_wo=o["wo"])
    w = next(x for x in _state(sp)["work_orders"] if x["id"] == kid)
    assert w["link_kind"] == "change_order" and w["parent_wo"] == o["wo"]


def test_kind_link_kind_mismatch_is_bad_link_kind(tmp_path):
    A, o, _ = build(tmp_path / "s.ndjson")
    msg = _refusal(lambda: _child(A, o, kind="recall_wo", link_kind="change_order", parent_wo=o["wo"]))
    assert "BAD_LINK[kind]" in msg


def test_change_order_on_settled_parent_refused_but_recall_allowed(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, _ = build(sp)
    # drive the parent to ledger_settled observation through the real store gates
    t0 = time.time()
    store.append("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]}, path=sp, now=t0)
    store.append("field", "checkin", {"wo": o["wo"]}, path=sp, now=t0 + 1)
    store.append("field", "checkout", {"wo": o["wo"]}, path=sp, now=t0 + 61)
    store.append("coord", "plan_closed", {"wo": o["wo"], "goal": "g", "planner_rc": 0, "plan_sha256": "x"}, path=sp)
    store.append("coord", "ledger_settled", {"wo": o["wo"], "ledger_sha256": "y"}, path=sp)
    msg = _refusal(lambda: _child(A, o, kind="change_order_wo", link_kind="change_order", parent_wo=o["wo"]))
    assert "BAD_LINK[parent_settled]" in msg
    kid = _child(A, o, kind="recall_wo", link_kind="recall", parent_wo=o["wo"])
    assert any(x["id"] == kid for x in _state(sp)["work_orders"])


# ------------------------------------------------------------------ visits
def test_visit_open_appends_and_alias_tracks_last(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, _ = build(sp)
    t0 = time.time()
    store.append("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]}, path=sp, now=t0)
    msg = _refusal(lambda: A("coord", "visit_open", {"wo": o["wo"]}))
    assert "STAGE[visit open]" in msg
    store.append("field", "checkin", {"wo": o["wo"]}, path=sp, now=t0 + 1)
    store.append("field", "checkout", {"wo": o["wo"]}, path=sp, now=t0 + 61)
    A("coord", "visit_open", {"wo": o["wo"]})
    w = next(x for x in _state(sp)["work_orders"] if x["id"] == o["wo"])
    assert len(w["visits"]) == 2 and w["visit"] is w["visits"][-1] or w["visit"] == w["visits"][-1]
    assert w["visits"][0]["id"] == f"{o['wo']}_visit" and w["visits"][1]["id"] == f"{o['wo']}_visit2"
    assert f"{o['wo']}_visit2" in store._names(_state(sp))


# ------------------------------------------------------------------ change order + override receipt
def test_change_order_approved_range_and_state(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, _ = build(sp)
    nte = next(x for x in _state(sp)["work_orders"])["nte_limit"]
    msg = _refusal(lambda: A("coord", "change_order_approved",
                             {"wo": o["wo"], "new_nte_cents": nte - random.randint(0, nte - 1), "authority": nm("a")}))
    assert "RANGE" in msg
    new = nte + random.randint(1, 100000)
    A("coord", "change_order_approved", {"wo": o["wo"], "new_nte_cents": new, "authority": nm("a")})
    w = next(x for x in _state(sp)["work_orders"] if x["id"] == o["wo"])
    assert w["change_order"] == {"approved": True, "new_nte_limit_cents": new}


def test_override_receipt_needs_id_and_reason_and_reaches_state(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, _ = build(sp)
    assert "MISSING" in _refusal(lambda: A("coord", "nte_override_receipt", {"wo": o["wo"], "id": nm("r"), "reason": ""}))
    assert "MISSING" in _refusal(lambda: A("coord", "nte_override_receipt", {"wo": o["wo"], "id": "", "reason": nm("r")}))
    rid, why = nm("rid"), nm("why")
    A("coord", "nte_override_receipt", {"wo": o["wo"], "id": rid, "reason": why})
    w = next(x for x in _state(sp)["work_orders"] if x["id"] == o["wo"])
    assert w["override_receipt"] == {"id": rid, "reason": why}


# ------------------------------------------------------------------ ledger reach + NteCap
def _visit_minutes(sp, o, ext_min, now0):
    store.append("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]}, path=sp, now=now0)
    store.append("field", "checkin", {"wo": o["wo"]}, path=sp, now=now0 + 1)
    internal = random.randint(10, 60)
    store.append("field", "checkout", {"wo": o["wo"]}, path=sp, now=now0 + 1 + 60 * internal)
    store.append("coord", "client_attest", {"wo": o["wo"], "minutes": ext_min}, path=sp)
    store.append("coord", "plan_closed", {"wo": o["wo"], "goal": "g", "planner_rc": 0, "plan_sha256": "x"}, path=sp)


def _over_nte_world(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, rates = build(sp)
    nte = _state(sp)["work_orders"][0]["nte_limit"]
    ext = math.ceil(nte * 60 / rates["client_rate"]) + random.randint(5, 60)
    _visit_minutes(sp, o, ext, time.time() - 7200)
    return sp, A, o, rates, nte, ext


def test_over_nte_without_change_order_is_ntecap(tmp_path):
    sp, A, o, rates, nte, ext = _over_nte_world(tmp_path)
    rc, out, _ = cli("settle", sp, {"wo_id": o["wo"]})
    assert rc == 2 and "NteCap" in str(out.get("refused", "")) + str(out.get("out", ""))
    assert ("ledger_settled" not in [e["kind"] for e in store.read(sp)])


def test_over_nte_receipt_alone_does_not_lift_cap_antivacuity(tmp_path):
    """Twin: an override receipt is not a change order; cap still refuses."""
    sp, A, o, rates, nte, ext = _over_nte_world(tmp_path)
    A("coord", "nte_override_receipt", {"wo": o["wo"], "id": nm("r"), "reason": nm("w")})
    rc, out, _ = cli("settle", sp, {"wo_id": o["wo"]})
    assert rc == 2 and "NteCap" in str(out.get("refused", "")) + str(out.get("out", ""))


def test_change_order_and_receipt_reach_ledger_and_settle(tmp_path):
    sp, A, o, rates, nte, ext = _over_nte_world(tmp_path)
    ar = math.ceil(ext * rates["client_rate"] / 60)
    A("coord", "change_order_approved", {"wo": o["wo"], "new_nte_cents": ar + random.randint(0, 5000), "authority": nm("a")})
    A("coord", "nte_override_receipt", {"wo": o["wo"], "id": nm("r"), "reason": nm("w")})
    rc, out, err = cli("settle", sp, {"wo_id": o["wo"]})
    assert rc == 0, (out, err)
    assert out["ledger"]["ar_cents"] == ar and out["observed"]["kind"] == "ledger_settled"
    assert out["observed"]["payload"]["ar_cents"] == ar
    assert "ledger_settled" in [e["kind"] for e in store.read(sp)]


def test_change_order_below_ar_still_ntecap_antivacuity(tmp_path):
    sp, A, o, rates, nte, ext = _over_nte_world(tmp_path)
    ar = math.ceil(ext * rates["client_rate"] / 60)
    A("coord", "change_order_approved", {"wo": o["wo"], "new_nte_cents": nte + 1, "authority": nm("a")})
    assert ar > nte + 1
    rc, out, _ = cli("settle", sp, {"wo_id": o["wo"]})
    assert rc == 2 and "NteCap" in str(out.get("refused", "")) + str(out.get("out", ""))


# ------------------------------------------------------------------ dispatch override
def _banned(tmp_path):
    sp = tmp_path / "s.ndjson"
    A, o, _ = build(sp)
    A("align", "provider_blacklist", {"provider": o["prov"]})
    return sp, A, o


def test_banned_provider_dispatch_refused(tmp_path):
    sp, A, o = _banned(tmp_path)
    rc, out, _ = cli("dispatch", sp, {"wo_id": o["wo"], "provider": o["prov"]})
    assert rc == 2 and "REFUSED" in out["refused"]
    assert "dispatch" not in [e["kind"] for e in store.read(sp)]


def test_dispatch_override_permits_banned_provider_and_is_unique(tmp_path):
    sp, A, o = _banned(tmp_path)
    args = {"wo": o["wo"], "provider": o["prov"], "authority": nm("a"), "reason": nm("r")}
    A("coord", "dispatch_override", args)
    w = next(x for x in _state(sp)["work_orders"] if x["id"] == o["wo"])
    assert w["dispatch_override"]["provider"] == o["prov"]
    assert f"DUPLICATE[dispatch_override:{o['wo']}]" in _refusal(lambda: A("coord", "dispatch_override", args))
    rc, out, err = cli("dispatch", sp, {"wo_id": o["wo"], "provider": o["prov"]})
    assert rc == 0, (out, err)
    assert "dispatch" in [e["kind"] for e in store.read(sp)]


def test_override_for_other_provider_does_not_permit_antivacuity(tmp_path):
    sp, A, o = _banned(tmp_path)
    other = nm("otherprov")
    A("align", "provider", {"name": other, "kind": "sub_1099"})
    A("coord", "dispatch_override", {"wo": o["wo"], "provider": other, "authority": nm("a"), "reason": nm("r")})
    rc, out, _ = cli("dispatch", sp, {"wo_id": o["wo"], "provider": o["prov"]})
    assert rc == 2 and "REFUSED" in out["refused"]
