"""L6 multi-entity court: real store, planner, ledger. Positive + anti-vacuity twins."""
import hashlib
import os
import random
from datetime import date, timedelta

import pytest

from enterprise_pipeline import staged, store
from helpers_world import nm

ENTITY_KINDS = ("entity_doc", "templates_bound", "client", "provider")


def _vertical(sp, bind=True, docs=True, share=None):
    """Second vertical in a store that already holds an entity: entity-tagged events."""
    o = {k: nm(k) for k in ("ent", "dba", "ss4", "w9e", "cli", "site", "coord", "prov", "w9p",
                            "coi", "lic", "con", "trade", "sub", "st", "prio", "wo")}

    def A(av, k, p):
        if k in ENTITY_KINDS:
            p = {**p, "entity": o["ent"]}
        return store.append(av, k, p, path=sp)

    if share:  # global taxonomy is reused, so the first vertical problem text stays byte-identical
        o.update({k: share[k] for k in ("trade", "sub", "st", "prio")})
    far = (date.today() + timedelta(days=random.randint(200, 900))).isoformat()
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    if docs:
        A("admin", "entity_doc", {"doc_type": "ss4_doc", "name": o["ss4"]})
        A("admin", "entity_doc", {"doc_type": "w9_doc", "name": o["w9e"]})
    if bind:
        A("admin", "templates_bound", {})
    for ty, k in (("trade", "trade"), ("sub_trade", "sub"), ("state_jurisdiction", "st"),
                  ("priority_tier", "prio")):
        if not share:
            A("admin", "taxonomy", {"type": ty, "name": o[k]})
    ch = store.domain_constants("delivery_channel")[0]
    A("admin", "client", {"name": o["cli"], "kind": "primary_client", "delivery_mode": ch,
                          "payment_terms_days": random.randint(15, 90)})
    A("admin", "client_rate", {"client": o["cli"], "trade": o["trade"], "cents": 15000})
    A("admin", "site", {"name": o["site"], "client": o["cli"], "state": o["st"],
                        "territory_client": o["cli"]})
    A("coord", "coordinator", {"name": o["coord"]})
    A("align", "provider", {"name": o["prov"], "kind": "sub_1099"})
    for dt, k in (("w9_doc", "w9p"), ("contract_doc", "con")):
        A("align", "provider_doc", {"provider": o["prov"], "doc_type": dt, "name": o[k], "valid": True})
    for dt, k in (("coi_doc", "coi"), ("license_doc", "lic")):
        A("align", "provider_doc", {"provider": o["prov"], "doc_type": dt, "name": o[k],
                                    "valid": True, "expiry_date": far})
    A("align", "provider_approval", {"provider": o["prov"], "trade": o["trade"], "sub_trade": o["sub"]})
    A("align", "provider_rate_approved", {"provider": o["prov"], "trade": o["trade"]})
    A("align", "provider_rate", {"provider": o["prov"], "trade": o["trade"], "cents": 5000})
    A("align", "device_attested", {"provider": o["prov"]})
    A("coord", "work_order", {"name": o["wo"], "kind": "reactive_wo", "wo_type": "reactive",
                              "client": o["cli"], "site": o["site"], "trade": o["trade"],
                              "sub_trade": o["sub"], "priority": o["prio"], "coordinator": o["coord"],
                              "nte_cents": 200000, "onsite_sla_min": 1200, "complete_sla_min": 4000})
    return A, o


def _state(sp):
    return store.reduce(store.read(sp))


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.ndjson"


def test_second_vertical_dispatches_first_byte_identical(sp):
    _, o1 = _vertical(sp)
    before = staged.compile_wo(_state(sp), o1["wo"])
    assert before.text is not None and not before.missing
    A2, o2 = _vertical(sp, share=o1)
    st = _state(sp)
    assert len(st["entities"]) == 2 and "entity" not in st  # SINGLE_ENTITY_STORE gone
    after = staged.compile_wo(st, o1["wo"])
    assert after.text == before.text and after.missing == before.missing  # byte-identical
    assert hashlib.sha256(after.text.encode()).digest() == hashlib.sha256(before.text.encode()).digest()
    assert store.entity_of(st, o2["wo"]) == o2["ent"] and store.entity_of(st, o1["wo"]) == o1["ent"]
    r = staged.plan_wo(st, o2["wo"])
    assert r["missing"] == [] and r["rc"] == 0, r["out"]
    assert any(s["action"] for s in r["steps"])
    sl = store.slice_state(st, next(w for w in st["work_orders"] if w["id"] == o2["wo"]))
    assert {c["id"] for c in sl["clients"]} == {o2["cli"]}
    assert o1["cli"] not in {c["id"] for c in sl["clients"]}


def test_second_vertical_settles(sp):
    _vertical(sp)
    A2, o2 = _vertical(sp)
    A2("coord", "dispatch", {"wo": o2["wo"], "provider": o2["prov"]})
    A2("field", "geofence_attest", {"wo": o2["wo"]})
    A2("field", "checkin", {"wo": o2["wo"]})
    A2("field", "checkout", {"wo": o2["wo"]})
    q = random.randint(30, 400)
    A2("coord", "proposal_quote", {"wo": o2["wo"], "minutes": q})
    A2("coord", "client_attest", {"wo": o2["wo"], "minutes": q})
    for ty in ("before_media", "after_media"):
        A2("field", "media", {"wo": o2["wo"], "media_type": ty, "name": nm(ty),
                              "sha256": hashlib.sha256(os.urandom(8)).hexdigest()})
    st = _state(sp)
    rc, out = staged.settle(st, o2["wo"])
    assert rc == 0, out


def test_twin_templates_bound_withheld_refuses(sp):
    _, o1 = _vertical(sp)
    _, o2 = _vertical(sp, bind=False)
    st = _state(sp)
    c = staged.compile_wo(st, o2["wo"])
    assert c.text is None and "MISSING[entity templates_bound]" in c.missing
    assert not staged.compile_wo(st, o1["wo"]).missing  # other vertical unaffected


def test_twin_docs_withheld_refuses(sp):
    _vertical(sp)
    _, o2 = _vertical(sp, docs=False)
    c = staged.compile_wo(_state(sp), o2["wo"])
    assert c.text is None and "MISSING[entity doc ss4_doc]" in c.missing


def test_twin_entity_omitted_refused_when_multiple(sp):
    _vertical(sp)
    _vertical(sp)
    for kind, p in (("templates_bound", {}), ("client", {"name": nm("c"), "kind": "primary_client"}),
                    ("provider", {"name": nm("p"), "kind": "sub_1099"}),
                    ("entity_doc", {"doc_type": "ss4_doc", "name": nm("d")})):
        with pytest.raises(store.Refused, match=r"MISSING\[entity\]"):
            store.append("admin", kind, p, path=sp)


def test_twin_cross_entity_site_refused(sp):
    _, o1 = _vertical(sp)
    _, o2 = _vertical(sp)
    with pytest.raises(store.Refused, match=r"ENTITY_MISMATCH\[territory_client\]"):
        store.append("admin", "site", {"name": nm("s"), "client": o2["cli"], "state": o2["st"],
                                       "territory_client": o1["cli"]}, path=sp)
