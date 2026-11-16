"""Diataxis fixtures: a fresh blank store path per test."""
import pytest


@pytest.fixture()
def blank_store(tmp_path):
    return tmp_path / "events.ndjson"


def build_world(sp, part=True, client_kind=None):
    """Blank store -> entity, client, provider, WO via the real store (independent of
    helpers_world so R2 multi-entity edits there cannot break the tutorial)."""
    import random
    from datetime import date, timedelta
    from helpers_world import nm
    from enterprise_pipeline import store
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    o = {k: nm(k) for k in ("ent", "dba", "ss4", "w9e", "cli", "site", "asset", "coord", "prov",
                            "w9p", "coi", "lic", "con", "trade", "sub", "st", "prio", "wo")}
    far = (date.today() + timedelta(days=random.randint(200, 900))).isoformat()
    cr = random.randint(9000, 20000)
    pr = random.randint(3000, cr - 1000)
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "entity_doc", {"doc_type": "ss4_doc", "name": o["ss4"]})
    A("admin", "entity_doc", {"doc_type": "w9_doc", "name": o["w9e"]})
    A("admin", "templates_bound", {})
    for ty, k in (("trade", "trade"), ("sub_trade", "sub"), ("state_jurisdiction", "st"),
                  ("priority_tier", "prio")):
        A("admin", "taxonomy", {"type": ty, "name": o[k]})
    kind = client_kind or next(k for k in store.subtypes("client") if k != "secondary_client")
    A("admin", "client", {"name": o["cli"], "kind": kind,
                          "delivery_mode": store.domain_constants("delivery_channel")[0],
                          "payment_terms_days": random.randint(15, 90)})
    A("admin", "client_rate", {"client": o["cli"], "trade": o["trade"], "cents": cr})
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
    A("align", "provider_rate", {"provider": o["prov"], "trade": o["trade"], "cents": pr})
    A("align", "device_attested", {"provider": o["prov"]})
    wo = {"name": o["wo"], "kind": "reactive_wo", "wo_type": "reactive", "client": o["cli"],
          "site": o["site"], "trade": o["trade"], "sub_trade": o["sub"], "priority": o["prio"],
          "coordinator": o["coord"], "nte_cents": random.randint(50000, 400000),
          "onsite_sla_min": random.randint(600, 3000), "complete_sla_min": random.randint(3100, 6000)}
    if part:
        wo["part_asset"] = o["asset"]
    A("coord", "work_order", wo)
    return A, o, {"client_rate": cr, "prov_rate": pr}
