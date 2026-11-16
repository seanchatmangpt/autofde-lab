"""Court K-L2: territory. Primary out-of-coverage plans + territory_flag + sales_rep_notified;
secondary needs a waiver else NO_PLAN[out_of_coverage]; quick_add is primary-only; L09 parent.
Real store, real compile, real planner; each positive law has an in-coverage / no-waiver twin."""
import random

import pytest

import jtbd_factories as jf
from helpers_world import nm
from enterprise_pipeline import staged, store

ECON, TEMP = jf.ECON, jf.TEMP


def _w(sp, secondary, in_coverage, parent=True):
    """One entity, primary P, secondary S contracted through P; wo is on P's (or S's) client."""
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    o = {k: nm(k) for k in ("ent", "dba", "ss4", "w9e", "prim", "sec", "site", "other", "coord",
                            "prov", "w9p", "coi", "lic", "con", "trade", "sub", "st", "prio", "wo")}
    rg = random.Random()
    far = jf.date.today() + jf.timedelta(days=rg.randint(TEMP["doc_valid_future_days_min"],
                                                         TEMP["doc_valid_future_days_max"]))
    kinds = store.subtypes("client")
    pk, sk = kinds[0], kinds[1]
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "entity_doc", {"doc_type": "ss4_doc", "name": o["ss4"]})
    A("admin", "entity_doc", {"doc_type": "w9_doc", "name": o["w9e"]})
    A("admin", "templates_bound", {})
    for ty, k in (("trade", "trade"), ("sub_trade", "sub"), ("state_jurisdiction", "st"),
                  ("priority_tier", "prio")):
        A("admin", "taxonomy", {"type": ty, "name": o[k]})
    ch = store.domain_constants("delivery_channel")[0]
    terms = rg.randint(ECON["payment_terms_days_min"], ECON["payment_terms_days_max"])
    base = {"delivery_mode": ch, "payment_terms_days": terms}
    A("admin", "client", {"name": o["prim"], "kind": pk, **base})
    A("admin", "client", {"name": o["other"], "kind": pk, **base})
    A("admin", "client", {"name": o["sec"], "kind": sk, "parent": o["prim"], **base})
    client = o["sec"] if secondary else o["prim"]
    prov_rate = rg.randint(ECON["provider_rate_min_cents"], ECON["provider_rate_max_cents"])
    rate = prov_rate * ECON["nte_headroom_multiplier_min"]  # client charge above provider cost
    for c in (o["prim"], o["sec"], o["other"]):
        A("admin", "client_rate", {"client": c, "trade": o["trade"], "cents": rate})
    terr = client if in_coverage else o["other"]
    A("admin", "site", {"name": o["site"], "client": client, "state": o["st"], "territory_client": terr})
    A("coord", "coordinator", {"name": o["coord"]})
    A("align", "provider", {"name": o["prov"], "kind": "sub_1099"})
    for dt, k in (("w9_doc", "w9p"), ("contract_doc", "con")):
        A("align", "provider_doc", {"provider": o["prov"], "doc_type": dt, "name": o[k], "valid": True})
    for dt, k in (("coi_doc", "coi"), ("license_doc", "lic")):
        A("align", "provider_doc", {"provider": o["prov"], "doc_type": dt, "name": o[k], "valid": True,
                                    "expiry_date": far.isoformat()})
    A("align", "provider_approval", {"provider": o["prov"], "trade": o["trade"], "sub_trade": o["sub"]})
    A("align", "provider_rate_approved", {"provider": o["prov"], "trade": o["trade"]})
    A("align", "provider_rate", {"provider": o["prov"], "trade": o["trade"], "cents": prov_rate})
    A("align", "device_attested", {"provider": o["prov"]})
    A("coord", "work_order", {
        "name": o["wo"], "kind": "reactive_wo", "wo_type": "reactive", "client": client,
        "site": o["site"], "trade": o["trade"], "sub_trade": o["sub"], "priority": o["prio"],
        "coordinator": o["coord"], "nte_cents": rate * rg.randint(ECON["nte_headroom_multiplier_min"],
                                                                  ECON["nte_headroom_multiplier_max"]),
        "onsite_sla_min": rg.randint(TEMP["onsite_sla_min_floor"], TEMP["onsite_sla_min_ceil"]),
        "complete_sla_min": rg.randint(TEMP["onsite_sla_min_ceil"] + 1, TEMP["onsite_sla_min_ceil"] * 2)})
    return A, o


def _state(sp):
    return store.reduce(store.read(sp))


def _flag_seen(res_or_c):
    info = getattr(res_or_c, "info", None) or res_or_c.get("info", [])
    flags = res_or_c.get("flags", []) if isinstance(res_or_c, dict) else getattr(res_or_c, "flags", [])
    return "territory_flag" in flags or any("territory_flag" in i for i in info)


def test_primary_out_of_coverage_plans_flags_and_notifies(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=False, in_coverage=False)
    st = _state(sp)
    r = staged.plan_wo(st, o["wo"])
    assert r["rc"] == 0 and not r["missing"], r["missing"]
    assert _flag_seen(r)
    assert "(territory-flag" in r["problem"]
    kinds = [k for k, _ in staged.observe_flags(st, o["wo"], r)]
    assert kinds == ["territory_flag", "sales_rep_notified"]


def test_twin_in_coverage_primary_has_no_flag(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=False, in_coverage=True)
    st = _state(sp)
    r = staged.plan_wo(st, o["wo"])
    assert r["rc"] == 0, r["missing"]
    assert not _flag_seen(r) and "(territory-flag" not in r["problem"]
    assert staged.observe_flags(st, o["wo"], r) == []


def test_secondary_out_of_coverage_is_no_plan(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=True, in_coverage=False)
    c = staged.compile_wo(_state(sp), o["wo"])
    assert "NO_PLAN[out_of_coverage]" in c.missing and c.text is None


def test_twin_secondary_in_coverage_plans(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=True, in_coverage=True)
    c = staged.compile_wo(_state(sp), o["wo"])
    assert not c.missing and c.text


def test_secondary_waiver_plans_with_flag_and_empty_authority_refused(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=True, in_coverage=False)
    with pytest.raises(store.Refused, match=r"MISSING\[authority\]"):
        A("admin", "territory_waiver", {"wo": o["wo"], "authority": ""})
    A("admin", "territory_waiver", {"wo": o["wo"], "authority": nm("auth")})
    c = staged.compile_wo(_state(sp), o["wo"])
    assert not c.missing and c.text and _flag_seen(c)


def test_l09_parent_and_quick_add(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=False, in_coverage=True)
    kinds = store.subtypes("client")
    ch = store.domain_constants("delivery_channel")[0]
    base = {"delivery_mode": ch, "payment_terms_days": 30}
    orphan, qa_sec, qa_pri = nm("c"), nm("c"), nm("c")
    with pytest.raises(store.Refused, match=r"NO_PARENT\[" + orphan):
        A("admin", "client", {"name": orphan, "kind": kinds[1], **base})
    with pytest.raises(store.Refused, match=r"QUICK_ADD_SECONDARY\[" + qa_sec):
        A("admin", "client", {"name": qa_sec, "kind": kinds[1], "parent": o["prim"],
                              "quick_add": True, **base})
    A("admin", "client", {"name": qa_pri, "kind": kinds[0], "quick_add": True, **base})
    cl = {c["id"]: c for c in _state(sp)["clients"]}
    assert cl[qa_pri]["quick_add"] is True
    assert orphan not in cl and qa_sec not in cl


def test_flag_observation_laws(tmp_path):
    sp = tmp_path / "s.jsonl"
    A, o = _w(sp, secondary=False, in_coverage=False)
    p = {"wo": o["wo"], "client": o["prim"], "site": o["site"]}
    with pytest.raises(store.Refused, match=r"MISSING\[territory_flag\]"):
        A("coord", "sales_rep_notified", {"wo": o["wo"], "client": o["prim"]})
    A("coord", "territory_flag", p)
    with pytest.raises(store.Refused, match=r"DUPLICATE\[territory_flag"):
        A("coord", "territory_flag", p)
    A("coord", "sales_rep_notified", {"wo": o["wo"], "client": o["prim"]})
    obs = _state(sp)["observed"]
    assert (o["wo"], "territory_flag") in obs and (o["wo"], "sales_rep_notified") in obs
