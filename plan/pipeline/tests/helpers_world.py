"""Shared world builders over the real store (promoted from test_staged.py)."""
import random
import uuid
from datetime import date, timedelta

from enterprise_pipeline import store


def nm(tag):
    return f"{random.choice('abcdefghijklmnopqrstuvwxyz')}{uuid.uuid4().hex[:8]}_{tag}"


def build(sp, part=False):
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    o = {k: nm(k) for k in ("ent", "dba", "ss4", "w9e", "cli", "site", "asset", "coord", "prov",
                            "w9p", "coi", "lic", "con", "trade", "sub", "st", "prio", "wo")}
    far = (date.today() + timedelta(days=random.randint(200, 900))).isoformat()
    client_rate = random.randint(9000, 20000)
    prov_rate = random.randint(3000, client_rate - 1000)
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "entity_doc", {"doc_type": "ss4_doc", "name": o["ss4"]})
    A("admin", "entity_doc", {"doc_type": "w9_doc", "name": o["w9e"]})
    A("admin", "templates_bound", {})
    for ty, k in (("trade", "trade"), ("sub_trade", "sub"), ("state_jurisdiction", "st"),
                  ("priority_tier", "prio")):
        A("admin", "taxonomy", {"type": ty, "name": o[k]})
    ch = store.domain_constants("delivery_channel")[0]
    terms = random.randint(15, 90)
    pk = store.subtypes("client")[0]
    o["par"] = nm("par")
    A("admin", "client", {"name": o["par"], "kind": pk, "delivery_mode": ch})
    A("admin", "client", {"name": o["cli"], "kind": "secondary_client", "parent": o["par"],
                          "delivery_mode": ch,
                          "payment_terms_days": terms})
    A("admin", "client_rate", {"client": o["cli"], "trade": o["trade"], "cents": client_rate})
    A("admin", "site", {"name": o["site"], "client": o["cli"], "state": o["st"],
                        "territory_client": o["cli"]})
    A("admin", "asset", {"name": o["asset"], "site": o["site"]})
    A("coord", "coordinator", {"name": o["coord"]})
    A("align", "provider", {"name": o["prov"], "kind": "sub_1099"})
    for dt, k in (("w9_doc", "w9p"), ("contract_doc", "con")):
        A("align", "provider_doc", {"provider": o["prov"], "doc_type": dt, "name": o[k], "valid": True})
    for dt, k in (("coi_doc", "coi"), ("license_doc", "lic")):
        A("align", "provider_doc", {"provider": o["prov"], "doc_type": dt, "name": o[k],
                                    "valid": True, "expiry_date": far})
    A("align", "provider_approval", {"provider": o["prov"], "trade": o["trade"], "sub_trade": o["sub"]})
    A("align", "provider_rate_approved", {"provider": o["prov"], "trade": o["trade"]})
    A("align", "provider_rate", {"provider": o["prov"], "trade": o["trade"], "cents": prov_rate})
    A("align", "device_attested", {"provider": o["prov"]})
    wo = {"name": o["wo"], "kind": "reactive_wo", "wo_type": "reactive", "client": o["cli"],
          "site": o["site"], "trade": o["trade"], "sub_trade": o["sub"], "priority": o["prio"],
          "coordinator": o["coord"], "nte_cents": random.randint(50000, 400000),
          "onsite_sla_min": random.randint(600, 3000), "complete_sla_min": random.randint(3100, 6000)}
    if part:
        wo["part_asset"] = o["asset"]
    A("coord", "work_order", wo)
    return A, o, {"client_rate": client_rate, "prov_rate": prov_rate, "terms": terms}


def run_visit(A, o):
    A("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]})
    A("field", "geofence_attest", {"wo": o["wo"]})
    A("field", "checkin", {"wo": o["wo"]})
    A("field", "checkout", {"wo": o["wo"]})
