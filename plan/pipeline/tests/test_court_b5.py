"""K-B5 dials differential court: auto_gpm_density polices dense high-rate markets to internal
(real) time and pays high-margin low-rate and sole-provider desolate markets unpoliced; the
runtime flip is an edit of a temp dial TOML. Real store, real ledger subprocess, no mocks."""
import json
import math
import random
from datetime import date, timedelta

import pytest

from enterprise_pipeline import dials, staged, store
from helpers_world import nm


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.ndjson"


@pytest.fixture()
def dial_file(tmp_path, monkeypatch):
    p = tmp_path / "dials.toml"
    monkeypatch.setenv("PLAN_POLICY_DIALS", str(p))

    def write(policy):
        auto = dials.switches()["clock_policy_auto"]
        p.write_text(
            f'[clock_policy]\nvalue = "{policy}"\n\n[clock_policy_auto]\n'
            f'desolate_market_provider_threshold = {auto["desolate_market_provider_threshold"]}\n'
            f'gpm_safe_harbor_bps = {auto["gpm_safe_harbor_bps"]}\n'
            f'low_rate_safe_harbor_cents = {auto["low_rate_safe_harbor_cents"]}\n')
    return write


def _provider(A, o, rate, far):
    p = {k: nm(k) for k in ("prov", "w9p", "coi", "lic", "con")}
    A("align", "provider", {"name": p["prov"], "kind": "sub_1099"})
    for dt, k in (("w9_doc", "w9p"), ("contract_doc", "con")):
        A("align", "provider_doc", {"provider": p["prov"], "doc_type": dt, "name": p[k], "valid": True})
    for dt, k in (("coi_doc", "coi"), ("license_doc", "lic")):
        A("align", "provider_doc", {"provider": p["prov"], "doc_type": dt, "name": p[k],
                                    "valid": True, "expiry_date": far})
    A("align", "provider_approval", {"provider": p["prov"], "trade": o["trade"], "sub_trade": o["sub"]})
    A("align", "provider_rate_approved", {"provider": p["prov"], "trade": o["trade"]})
    A("align", "provider_rate", {"provider": p["prov"], "trade": o["trade"], "cents": rate})
    A("align", "device_attested", {"provider": p["prov"]})
    return p["prov"]


def world(sp, providers, prov_rate, client_rate):
    """Market with `providers` approved providers; returns (state, wo, internal_min, external_min)."""
    A = lambda av, k, p, **kw: store.append(av, k, p, path=sp, **kw)
    o = {k: nm(k) for k in ("ent", "dba", "ss4", "w9e", "cli", "site", "coord", "trade", "sub",
                            "st", "prio", "wo")}
    far = (date.today() + timedelta(days=random.randint(200, 900))).isoformat()
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "entity_doc", {"doc_type": "ss4_doc", "name": o["ss4"]})
    A("admin", "entity_doc", {"doc_type": "w9_doc", "name": o["w9e"]})
    A("admin", "templates_bound", {})
    for ty, k in (("trade", "trade"), ("sub_trade", "sub"), ("state_jurisdiction", "st"),
                  ("priority_tier", "prio")):
        A("admin", "taxonomy", {"type": ty, "name": o[k]})
    A("admin", "client", {"name": o["cli"], "kind": "primary_client",
                          "delivery_mode": store.domain_constants("delivery_channel")[0],
                          "payment_terms_days": random.randint(15, 90)})
    A("admin", "client_rate", {"client": o["cli"], "trade": o["trade"], "cents": client_rate})
    A("admin", "site", {"name": o["site"], "client": o["cli"], "state": o["st"],
                        "territory_client": o["cli"]})
    A("coord", "coordinator", {"name": o["coord"]})
    provs = [_provider(A, o, prov_rate, far) for _ in range(providers)]
    A("coord", "work_order", {"name": o["wo"], "kind": "reactive_wo", "wo_type": "reactive",
                              "client": o["cli"], "site": o["site"], "trade": o["trade"],
                              "sub_trade": o["sub"], "priority": o["prio"],
                              "coordinator": o["coord"], "nte_cents": 10**7,
                              "onsite_sla_min": random.randint(600, 3000),
                              "complete_sla_min": random.randint(3100, 6000)})
    internal = random.randint(30, 120)
    external = internal + random.randint(30, 200)
    A("coord", "dispatch", {"wo": o["wo"], "provider": provs[0]})
    A("field", "geofence_attest", {"wo": o["wo"]})
    A("coord", "proposal_quote", {"wo": o["wo"], "minutes": external})
    A("coord", "client_attest", {"wo": o["wo"], "minutes": external})
    return store.reduce(store.read(sp)), o["wo"], internal, external


def outcome(state, wo):
    """Real settle with internal (checkin/checkout) minutes absent: policed -> typed MISSING for
    internal_minutes (AP refused until real time exists); unpoliced -> AP from external minutes."""
    rc, out = staged.settle(state, wo)
    if rc != 0:
        assert "MISSING[internal_minutes" in out, out
        return "POLICED"
    return json.loads(out[out.index("{"):])["ap_cents"]


def rates(kind):
    bps, low = dials.gpm_safe_harbor_bps(), dials.low_rate_safe_harbor_cents()
    if kind == "dense_high_rate":
        p = low + random.randint(500, 1500)
        g = bps - 1000
    elif kind in ("desolate_high_margin_low_rate", "dense_high_margin_low_rate"):
        p = low - random.randint(500, 1500)
        g = bps + 500
    else:  # desolate_sole_provider_high_rate: margin under harbor, only provider count differs
        p = low + random.randint(500, 1500)
        g = bps - 1000
    return p, math.ceil(p * 10000 / (10000 - g))


def providers_for(kind):
    t = dials.desolate_market_min_providers()
    return 1 if kind.startswith("desolate") else t + random.randint(0, 2)


def pay(sp, kind):
    p, c = rates(kind)
    st, wo, i, e = world(sp, providers_for(kind), p, c)
    return outcome(st, wo), math.ceil(i * p / 60), math.ceil(e * p / 60)


def test_dials_module_reads_runtime_toml(dial_file):
    dial_file("auto_gpm_density")
    assert dials.clock_policy() == "auto_gpm_density"
    dial_file("strict_internal")
    assert dials.clock_policy() == "strict_internal"


@pytest.mark.parametrize("kind", ["dense_high_margin_low_rate", "desolate_sole_provider_high_rate"])
def test_waiver_needs_desolate_and_harbor_both(sp, dial_file, kind):
    """Differential: harbor without desolation, or desolation without harbor, stays policed."""
    dial_file("auto_gpm_density")
    assert pay(sp, kind)[0] == "POLICED"


def test_dense_market_high_rate_policed_to_real_time(sp, dial_file):
    dial_file("auto_gpm_density")
    assert pay(sp, "dense_high_rate")[0] == "POLICED"


@pytest.mark.parametrize("kind", ["desolate_high_margin_low_rate"])
def test_waived_markets_paid_unpoliced(sp, dial_file, kind):
    dial_file("auto_gpm_density")
    ap, _, unpoliced = pay(sp, kind)
    assert ap == unpoliced


@pytest.mark.parametrize("kind", ["desolate_high_margin_low_rate"])
def test_anti_vacuity_flip_to_strict_polices_same_market(sp, dial_file, kind):
    """Twin: the waiver is the dial's doing; strict_internal polices the identical market."""
    p, c = rates(kind)
    dial_file("auto_gpm_density")
    st, wo, i, e = world(sp, providers_for(kind), p, c)
    assert outcome(st, wo) == math.ceil(e * p / 60)
    dial_file("strict_internal")  # runtime flip: edit the temp TOML, same store state
    assert outcome(st, wo) == "POLICED"


def test_anti_vacuity_dense_unpoliced_under_quoted_safe_harbor(sp, dial_file):
    p, c = rates("dense_high_rate")
    dial_file("auto_gpm_density")
    st, wo, i, e = world(sp, providers_for("dense_high_rate"), p, c)
    assert outcome(st, wo) == "POLICED"
    dial_file("quoted_safe_harbor")
    assert outcome(st, wo) == math.ceil(e * p / 60)


def test_threshold_flip_makes_dense_market_desolate(sp, dial_file, tmp_path):
    """Raising the desolate threshold above the provider count waives a previously policed market."""
    p, c = rates("dense_high_margin_low_rate")
    n = providers_for("dense_high_margin_low_rate")
    dial_file("auto_gpm_density")
    st, wo, i, e = world(sp, n, p, c)
    assert outcome(st, wo) == "POLICED"
    f = tmp_path / "dials.toml"
    f.write_text(f'[clock_policy]\nvalue = "auto_gpm_density"\n\n[clock_policy_auto]\n'
                 f'desolate_market_provider_threshold = {n + 1}\n')
    assert outcome(st, wo) == math.ceil(e * p / 60)
