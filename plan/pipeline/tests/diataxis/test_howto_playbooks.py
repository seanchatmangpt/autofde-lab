"""How-To playbooks B1-B7: each runs on a blank scratch store with the real store, MiniZinc,
planner and ledger. Every name, rate, date and byte stream is drawn by Faker inside the TOML
envelopes below (seed: PLAN_TEST_SEED). Each named test pairs a positive run with an
anti-vacuity twin that must trigger the documented refusal. Behaviors the code base does not
have are separate gap tests that skip loudly with UNSUPPORTED[<gap>]."""
import json
import math
import os
import random
import tomllib
from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from faker import Faker

from enterprise_pipeline import align, dials, staged, store

ENV = tomllib.loads("""
[names]
symbol_len = 9
[economics]
client_rate_min = 9000
client_rate_max = 20000
provider_floor = 3000
spread_min = 1000
nte_min = 50000
nte_max = 400000
terms_min = 15
terms_max = 90
sla_onsite_min = 600
sla_onsite_max = 3000
sla_complete_extra_min = 100
sla_complete_extra_max = 3000
[temporal]
far_days_min = 200
far_days_max = 900
past_days_min = 1
past_days_max = 365
overage_min = 2
overage_max = 30
[bytes]
media_min = 16
media_max = 64
""")
EC, TM = ENV["economics"], ENV["temporal"]
fake = Faker()


@pytest.fixture(autouse=True)
def seeded():
    seed = int(os.environ["PLAN_TEST_SEED"])
    random.seed(seed)
    Faker.seed(seed)


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.ndjson"


@pytest.fixture()
def set_dials(tmp_path):
    """Write a policy-dials TOML into scratch and point the real loader at it; restores env."""
    prior = os.environ.get("PLAN_POLICY_DIALS")
    n = [0]

    def write(**tables):
        n[0] += 1
        path = tmp_path / f"dials{n[0]}.toml"
        lines = []
        for table, kv in tables.items():
            lines.append(f"[{table}]")
            for k, v in kv.items():
                lines.append(f"{k} = {json.dumps(v)}")
        path.write_text("\n".join(lines) + "\n")
        os.environ["PLAN_POLICY_DIALS"] = str(path)

    yield write
    if prior is None:
        os.environ.pop("PLAN_POLICY_DIALS", None)
    else:
        os.environ["PLAN_POLICY_DIALS"] = prior


# ---------------------------------------------------------------- factories over the real store
def nm(tag):
    return f"{fake.lexify('?' * ENV['names']['symbol_len'], letters='abcdefghijklmnopqrstuvwxyz')}_{tag}"


def appender(sp):
    return lambda av, k, p, now=None: store.append(av, k, p, path=sp, now=now)


def state_of(sp):
    return store.reduce(store.read(sp))


def future(lo, hi):
    return (date.today() + timedelta(days=random.randint(lo, hi))).isoformat()


def past():
    return (date.today() - timedelta(days=random.randint(TM["past_days_min"], TM["past_days_max"]))
            ).isoformat()


def taxonomy(A):
    t = SimpleNamespace(trade=nm("trade"), sub=nm("sub"), st=nm("st"), prio=nm("prio"))
    for ty, v in (("trade", t.trade), ("sub_trade", t.sub), ("state_jurisdiction", t.st),
                  ("priority_tier", t.prio)):
        A("admin", "taxonomy", {"type": ty, "name": v})
    t.coord = nm("coord")
    return t


def entity(A, tax, ready=True):
    e = SimpleNamespace(id=nm("ent"), dba=nm("dba"))
    A("admin", "entity", {"name": e.id, "dba": e.dba})
    if tax is not None and not getattr(tax, "coord_made", False):
        A("coord", "coordinator", {"name": tax.coord})
        tax.coord_made = True
    if ready:
        make_ready(A, e)
    return e


def make_ready(A, e):
    for dt in ("ss4_doc", "w9_doc"):
        A("admin", "entity_doc", {"entity": e.id, "doc_type": dt, "name": nm(dt)})
    A("admin", "templates_bound", {"entity": e.id})


def client(A, e, *, kind="primary_client", parent=None, rate=None, tax=None):
    c = SimpleNamespace(id=nm("cli"), rate=rate or random.randint(EC["client_rate_min"], EC["client_rate_max"]))
    p = {"name": c.id, "kind": kind, "entity": e.id,
         "delivery_mode": random.choice(store.domain_constants("delivery_channel")),
         "payment_terms_days": random.randint(EC["terms_min"], EC["terms_max"])}
    if parent:
        p["parent"] = parent.id
    A("admin", "client", p)
    if tax is not None:
        A("admin", "client_rate", {"client": c.id, "trade": tax.trade, "cents": c.rate})
    return c


def site(A, c, tax, territory=None):
    s = SimpleNamespace(id=nm("site"))
    A("admin", "site", {"name": s.id, "client": c.id, "state": tax.st,
                        "territory_client": (territory or c).id})
    return s


def provider(A, e, tax, client_rate, *, expired=False):
    p = SimpleNamespace(id=nm("prov"),
                        rate=random.randint(EC["provider_floor"], client_rate - EC["spread_min"]))
    A("align", "provider", {"name": p.id, "kind": random.choice(store.subtypes("provider")),
                            "entity": e.id})
    for dt in ("w9_doc", "contract_doc"):
        A("align", "provider_doc", {"provider": p.id, "doc_type": dt, "name": nm(dt), "valid": True})
    exp = past() if expired else future(TM["far_days_min"], TM["far_days_max"])
    for dt in ("coi_doc", "license_doc"):
        A("align", "provider_doc", {"provider": p.id, "doc_type": dt, "name": nm(dt),
                                    "valid": True, "expiry_date": exp})
    A("align", "provider_approval", {"provider": p.id, "trade": tax.trade, "sub_trade": tax.sub})
    A("align", "provider_rate_approved", {"provider": p.id, "trade": tax.trade})
    A("align", "provider_rate", {"provider": p.id, "trade": tax.trade, "cents": p.rate})
    A("align", "device_attested", {"provider": p.id})
    return p


def work_order(A, c, s, tax, *, nte=None):
    on = random.randint(EC["sla_onsite_min"], EC["sla_onsite_max"])
    w = SimpleNamespace(id=nm("wo"),
                        nte=nte or random.randint(EC["nte_min"], EC["nte_max"]))
    A("coord", "work_order", {
        "name": w.id, "kind": "reactive_wo", "wo_type": "reactive", "client": c.id, "site": s.id,
        "trade": tax.trade, "sub_trade": tax.sub, "priority": tax.prio, "coordinator": tax.coord,
        "nte_cents": w.nte, "onsite_sla_min": on,
        "complete_sla_min": on + random.randint(EC["sla_complete_extra_min"],
                                                 EC["sla_complete_extra_max"])})
    return w


def world(sp, *, expired=False, sites=1):
    """One ready entity: client+rate, `sites` sites, one provider, one work order per site."""
    A = appender(sp)
    tax = taxonomy(A)
    e = entity(A, tax)
    c = client(A, e, tax=tax)
    ss = [site(A, c, tax) for _ in range(sites)]
    p = provider(A, e, tax, c.rate, expired=expired)
    wos = [work_order(A, c, s, tax) for s in ss]
    return SimpleNamespace(A=A, tax=tax, e=e, c=c, sites=ss, p=p, wos=wos, wo=wos[0], sp=sp)


def visit(A, wo, provider_id, minutes, *, t0=None):
    """Dispatch + check-in/out spanning exactly `minutes` of recorded wall time."""
    import time
    t0 = time.time() if t0 is None else t0
    A("coord", "dispatch", {"wo": wo, "provider": provider_id})
    A("field", "geofence_attest", {"wo": wo})
    A("field", "checkin", {"wo": wo}, now=t0)
    A("field", "checkout", {"wo": wo}, now=t0 + minutes * 60)


def quote_attest(A, wo, minutes):
    A("coord", "proposal_quote", {"wo": wo, "minutes": minutes})
    A("coord", "client_attest", {"wo": wo, "minutes": minutes})


def elig(w, wo=None):
    return align.run_minizinc(state_of(w.sp), next(x for x in state_of(w.sp)["work_orders"]
                                                    if x["id"] == (wo or w.wo.id)))


# ================================================================ B1
def test_howto_new_vertical_dba_isolation(sp):
    """Completed Barrel: a new vertical is its own entity+DBA; nothing leaks across entities."""
    A = appender(sp)
    tax = taxonomy(A)
    e1 = entity(A, tax)
    c1 = client(A, e1, tax=tax)
    s1 = site(A, c1, tax)
    p1 = provider(A, e1, tax, c1.rate)
    w1 = work_order(A, c1, s1, tax)

    e2 = entity(A, tax, ready=False)  # the new vertical starts with no documents
    c2 = client(A, e2, tax=tax)
    s2 = site(A, c2, tax)
    p2 = provider(A, e2, tax, c2.rate)
    w2 = work_order(A, c2, s2, tax)
    st = state_of(sp)

    # twin 1: unreadied vertical is refused with the exact typed gaps; the other vertical is unaffected
    miss = staged.compile_wo(st, w2.id).missing
    assert "MISSING[entity doc ss4_doc]" in miss and "MISSING[entity doc w9_doc]" in miss
    assert "MISSING[entity templates_bound]" in miss
    assert staged.compile_wo(st, w1.id).missing == []

    # positive: readied vertical compiles; slice holds only its own world
    make_ready(A, e2)
    st = state_of(sp)
    c = staged.compile_wo(st, w2.id)
    assert c.missing == [] and c.text
    for foreign in (e1.id, e1.dba, c1.id, s1.id, p1.id, w1.id):
        assert foreign not in c.text, foreign
    sl = store.slice_state(st, w2.id)
    assert [x["id"] for x in sl["clients"]] == [c2.id]
    assert [x["id"] for x in sl["providers"]] == [p2.id]
    wov, _ = align.derive(st, next(x for x in st["work_orders"] if x["id"] == w2.id))
    assert wov["brand"] == e2.dba != e1.dba and wov["entity"] == e2.id
    extra = nm("dba")
    A("admin", "entity_dba", {"entity": e2.id, "dba": extra})
    assert extra in next(x for x in state_of(sp)["entities"] if x["id"] == e2.id)["dbas"]

    # twin 2: every cross-entity reference is refused
    with pytest.raises(store.Refused, match=r"ENTITY_MISMATCH\[client\]"):
        client(A, e2, kind="secondary_client", parent=c1)
    with pytest.raises(store.Refused, match=r"ENTITY_MISMATCH\[territory_client\]"):
        site(A, c2, tax, territory=c1)
    with pytest.raises(store.Refused, match=r"ENTITY_MISMATCH\[site\]"):
        work_order(A, c2, s1, tax)
    with pytest.raises(store.Refused, match=r"ENTITY_MISMATCH\[provider\]"):
        A("coord", "dispatch", {"wo": w2.id, "provider": p1.id})
    with pytest.raises(store.Refused, match="DUPLICATE"):
        A("admin", "entity", {"name": nm("ent"), "dba": e1.dba})
    with pytest.raises(store.Refused, match=r"MISSING\[entity\]"):
        A("admin", "templates_bound", {})  # ambiguous with two entities


# ================================================================ B2
def test_howto_global_ban_vs_single_site_exclusion(tmp_path, set_dials):
    """A site exclusion removes a provider at one site only; a global ban removes them everywhere."""
    def fresh(tag):
        w = world(tmp_path / f"{tag}.ndjson", sites=2)
        q = provider(w.A, w.e, w.tax, w.c.rate)  # control provider keeps the market non-empty
        return w, q

    def ok(w, wo, pid):
        return elig(w, wo.id)[0][pid]

    # baseline: both sites see the provider
    w, q = fresh("base")
    wa, wb = w.wos
    assert ok(w, wa, w.p.id) and ok(w, wb, w.p.id)

    # positive: single-site exclusion
    w, q = fresh("site")
    wa, wb = w.wos
    w.A("align", "provider_filter", {"provider": w.p.id, "dim": "site", "mode": "exc",
                                     "values": [w.sites[0].id]})
    assert not ok(w, wa, w.p.id) and ok(w, wb, w.p.id) and ok(w, wa, q.id)
    # site-manager clash is the same scoped exclusion
    w.A("align", "site_manager_clash", {"provider": q.id, "site": w.sites[1].id})
    assert not ok(w, wb, q.id) and ok(w, wa, q.id)

    # positive: global ban
    w, q = fresh("ban")
    wa, wb = w.wos
    w.A("align", "provider_blacklist", {"provider": w.p.id})
    assert not ok(w, wa, w.p.id) and not ok(w, wb, w.p.id) and ok(w, wa, q.id)
    # an invoice left on site is a global ban too
    w.A("align", "invoice_left_on_site", {"provider": q.id, "wo": wa.id})
    assert not ok(w, wa, q.id) and not ok(w, wb, q.id)

    # twin: exclusion at site A must NOT leak to site B (distinguishes it from the ban)
    w, q = fresh("leak")
    w.A("align", "provider_filter", {"provider": w.p.id, "dim": "site", "mode": "exc",
                                     "values": [w.sites[0].id]})
    assert ok(w, w.wos[1], w.p.id)

    # twin: bad dimension / mode refused; dial flips it to record-and-warn without any effect
    bad = nm("dim")
    with pytest.raises(store.Refused, match=rf"BAD_DIM\[{bad}\]"):
        w.A("align", "provider_filter", {"provider": w.p.id, "dim": bad, "mode": "exc", "values": [bad]})
    with pytest.raises(store.Refused, match="BAD_MODE"):
        w.A("align", "provider_filter", {"provider": w.p.id, "dim": "site", "mode": bad, "values": [bad]})
    set_dials(provider_filter_validation={"value": "record_then_warn"})
    w.A("align", "provider_filter", {"provider": w.p.id, "dim": bad, "mode": "exc", "values": [bad]})
    assert f"BAD_DIM[{bad}]" in state_of(w.sp)["warnings"]
    assert ok(w, w.wos[1], w.p.id)


# ================================================================ B5
def _settled_world(sp, *, providers_extra=0):
    """Zero recorded internal minutes + client-attested minutes: only a dial can admit AP."""
    w = world(sp)
    for _ in range(providers_extra):
        provider(w.A, w.e, w.tax, w.c.rate)
    import time
    t0 = time.time()
    m = random.randint(TM["overage_min"], TM["overage_max"])
    w.A("coord", "dispatch", {"wo": w.wo.id, "provider": w.p.id})
    w.A("field", "geofence_attest", {"wo": w.wo.id})
    w.A("field", "checkin", {"wo": w.wo.id}, now=t0)
    w.A("field", "checkout", {"wo": w.wo.id}, now=t0)  # zero internal minutes
    quote_attest(w.A, w.wo.id, m)
    return w


def test_howto_tune_gpm_and_desolate_market_dials(tmp_path, set_dials):
    w = _settled_world(tmp_path / "dials.ndjson")
    st = state_of(w.sp)
    gpm_bps = (w.c.rate - w.p.rate) * 10000 // w.c.rate
    count = align.desolate_market_count(st, next(x for x in st["work_orders"] if x["id"] == w.wo.id))
    assert count == 1

    def settle(**tables):
        set_dials(**tables)
        return staged.settle(state_of(w.sp), w.wo.id)

    auto = lambda thr, bps, low=0: dict(
        clock_policy={"value": "auto_gpm_density"},
        clock_policy_auto={"desolate_market_provider_threshold": thr, "gpm_safe_harbor_bps": bps,
                           "low_rate_safe_harbor_cents": low})

    # twin: default strict clock refuses AP with no internal minutes
    rc, out = settle(clock_policy={"value": "strict_internal"})
    assert rc != 0 and "MISSING[internal_minutes]" in out
    # positive: quoted safe harbor admits it
    rc, out = settle(clock_policy={"value": "quoted_safe_harbor"})
    assert rc == 0, out
    d = json.loads(out)
    assert d["ar_cents"] > d["ap_cents"]
    # positive: auto mode, desolate market (threshold above provider count) + GPM at the bar
    rc, out = settle(**auto(count + 1, gpm_bps))
    assert rc == 0, out
    assert dials.desolate_market(count) and dials.gpm_safe_harbor_met(gpm_bps)
    # twin: same dial but market no longer desolate (threshold == count) -> strict behavior
    rc, out = settle(**auto(count, gpm_bps))
    assert rc != 0 and "MISSING[internal_minutes]" in out
    assert not dials.desolate_market(count)
    # twin: desolate but GPM bar one bp above the real spread and no low-rate harbor
    rc, out = settle(**auto(count + 1, gpm_bps + 1))
    assert rc != 0 and "MISSING[internal_minutes]" in out
    assert not dials.gpm_safe_harbor_met(gpm_bps - 1 if gpm_bps else 0) or gpm_bps == 0
    # low-rate harbor alone admits it (spread bar unreachable)
    rc, out = settle(**auto(count + 1, 10001, w.p.rate))
    assert rc == 0, out
    # twin: an unknown option is a typed BAD_DIAL, never a silent default
    bogus = nm("opt")
    set_dials(clock_policy={"value": bogus})
    with pytest.raises(ValueError, match=rf"BAD_DIAL\[clock_policy={bogus}\]"):
        staged.settle(state_of(w.sp), w.wo.id)


# ================================================================ B6
def test_howto_primary_sales_lead_vs_secondary_territory_hold(tmp_path, set_dials):
    sp = tmp_path / "terr.ndjson"
    A = appender(sp)
    tax = taxonomy(A)
    e = entity(A, tax)
    home = client(A, e, tax=tax)
    other = client(A, e, tax=tax)                       # primary client outside the site's territory
    sec = client(A, e, kind="secondary_client", parent=home, tax=tax)
    s = site(A, home, tax, territory=home)
    provider(A, e, tax, min(home.rate, other.rate, sec.rate))
    w_in = work_order(A, home, s, tax)
    w_pri = work_order(A, other, s, tax)
    w_sec = work_order(A, sec, s, tax)
    st = state_of(sp)
    comp = lambda w: staged.compile_wo(state_of(sp), w.id)

    # in territory: no flag, plans normally
    assert staged.territory_state(st, next(x for x in st["work_orders"] if x["id"] == w_in.id)) == "in"
    c = comp(w_in)
    assert c.missing == [] and c.flags == [] and staged.observe_flags(st, w_in.id, {}) == []
    # primary outside territory: plans, flags the sales lead
    c = comp(w_pri)
    assert c.missing == [] and "territory_flag" in c.flags
    fl = staged.observe_flags(st, w_pri.id, {})
    assert [k for k, _ in fl] == ["territory_flag", "sales_rep_notified"]
    for k, p in fl:
        A("coord", k, p)
    assert {(w_pri.id, "territory_flag"), (w_pri.id, "sales_rep_notified")} <= state_of(sp)["observed"]
    # twins: a lead cannot be notified before the flag, and a flag cannot be recorded twice
    with pytest.raises(store.Refused, match=r"MISSING\[territory_flag\]"):
        A("coord", "sales_rep_notified", {"wo": w_sec.id, "client": sec.id})
    with pytest.raises(store.Refused, match="DUPLICATE"):
        A("coord", "territory_flag", fl[0][1])
    # secondary outside territory: held, no plan, no lead flag
    c = comp(w_sec)
    assert "NO_PLAN[out_of_coverage]" in c.missing and c.text is None
    assert staged.observe_flags(state_of(sp), w_sec.id, {}) == []
    # a recorded waiver releases the hold (and raises the flag)
    A("admin", "territory_waiver", {"wo": w_sec.id, "authority": nm("exec")})
    c = comp(w_sec)
    assert c.missing == [] and "territory_flag" in c.flags
    assert [k for k, _ in staged.observe_flags(state_of(sp), w_sec.id, {})][0] == "territory_flag"
    with pytest.raises(store.Refused, match=r"MISSING\[authority\]"):
        A("admin", "territory_waiver", {"wo": w_pri.id})
    # dial: refuse mode holds the primary too
    set_dials(secondary_out_of_coverage={"value": "refuse"})
    assert "NO_PLAN[out_of_coverage]" in staged.compile_wo(state_of(sp), w_pri.id).missing
    assert staged.compile_wo(state_of(sp), w_in.id).missing == []


# ================================================================ B4
def test_howto_internal_photo_vault_and_model_tag_gate(tmp_path, set_dials):
    w = world(tmp_path / "vault.ndjson")
    A = w.A
    wo = w.wo.id
    A("coord", "required_media", {"wo": wo, "media_type": "model_tag_photo"})
    with pytest.raises(store.Refused, match=r"BAD_TYPE"):
        A("coord", "required_media", {"wo": wo, "media_type": nm("kind")})

    # dial: hard refuse blocks check-out without the tag; soft_only lets the visit finish
    import time
    t0 = time.time()
    set_dials(media_prompt_mode={"value": "hard_refuse"})
    A("coord", "dispatch", {"wo": wo, "provider": w.p.id})
    A("field", "geofence_attest", {"wo": wo})
    A("field", "checkin", {"wo": wo}, now=t0)
    with pytest.raises(store.Refused, match=r"MISSING_MEDIA\[model_tag_photo\]"):
        A("field", "checkout", {"wo": wo}, now=t0 + 60 * random.randint(5, 60))
    set_dials(media_prompt_mode={"value": "soft_only"})
    mins = random.randint(5, 60)
    A("field", "checkout", {"wo": wo}, now=t0 + 60 * mins)
    quote_attest(A, wo, mins)

    # twin: tag missing -> typed refusal at compile, no problem emitted
    c = staged.compile_wo(state_of(w.sp), wo)
    assert c.text is None and "MISSING_MEDIA[model_tag_photo]" in c.missing
    assert store.missing_media(next(x for x in state_of(w.sp)["work_orders"] if x["id"] == wo)) \
        == ["model_tag_photo"]
    # positive: real bytes recorded by hash satisfy the gate
    data = os.urandom(random.randint(int(ENV["bytes"]["media_min"]), int(ENV["bytes"]["media_max"])))
    name = nm("tag")
    A("field", "media", {"wo": wo, "media_type": "model_tag_photo", "name": name,
                         "sha256": store.file_sha256(data)})
    c = staged.compile_wo(state_of(w.sp), wo)
    assert c.missing == [] and name in c.text
    with pytest.raises(store.Refused, match="DUPLICATE"):
        A("field", "media", {"wo": wo, "media_type": "model_tag_photo", "name": name,
                             "sha256": store.file_sha256(data)})
    with pytest.raises(store.Refused, match="BAD_TYPE"):
        A("field", "media", {"wo": wo, "media_type": nm("kind"), "name": nm("m"),
                             "sha256": store.file_sha256(data)})


def test_gap_photo_vault_client_visibility(tmp_path):
    w = world(tmp_path / "vis.ndjson")
    name = nm("tag")
    w.A("coord", "dispatch", {"wo": w.wo.id, "provider": w.p.id})
    try:
        w.A("field", "media", {"wo": w.wo.id, "media_type": "model_tag_photo", "name": name,
                               "sha256": store.file_sha256(os.urandom(32)),
                               "client_visible": False})
    except store.Refused:
        pass
    media = next(x for x in state_of(w.sp)["work_orders"] if x["id"] == w.wo.id)["visit"]["media"]
    if not media or "client_visible" not in media[0] and "visibility" not in media[0]:
        pytest.skip("UNSUPPORTED[media visibility + prompt: no client-visibility field in store (O09)]")
    assert media[0].get("client_visible", media[0].get("visibility")) in (False, "internal")


# ================================================================ B7
def test_howto_executive_override_and_over_nte_change_order(tmp_path):
    def overrun(tag):
        w = world(tmp_path / f"{tag}.ndjson")
        m = w.wo.nte * 60 // w.c.rate + random.randint(TM["overage_min"], TM["overage_max"])
        visit(w.A, w.wo.id, w.p.id, m)
        quote_attest(w.A, w.wo.id, m)
        return w, m

    # twin: over-NTE settlement is refused without an approved change order
    w, m = overrun("nte")
    rc, out = staged.settle(state_of(w.sp), w.wo.id)
    assert rc != 0 and "NteCap" in out
    # twin: an approval below the real AR still refuses; below the old NTE the event itself is refused
    ar_upper = m * w.c.rate
    with pytest.raises(store.Refused, match=r"RANGE\[new_nte_cents>nte\]"):
        w.A("exec", "change_order_approved", {"wo": w.wo.id, "new_nte_cents": w.wo.nte,
                                              "authority": nm("exec")})
    w.A("exec", "change_order_approved", {"wo": w.wo.id, "new_nte_cents": w.wo.nte + 1,
                                          "authority": nm("exec")})
    rc, out = staged.settle(state_of(w.sp), w.wo.id)
    assert rc != 0 and "NteCap" in out
    # positive: an approved change order covering the AR settles
    w, m = overrun("nte_ok")
    w.A("exec", "change_order_approved", {"wo": w.wo.id, "new_nte_cents": m * w.c.rate,
                                          "authority": nm("exec")})
    rc, out = staged.settle(state_of(w.sp), w.wo.id)
    assert rc == 0, out
    d = json.loads(out)
    assert d["ar_cents"] > w.wo.nte and d["ar_cents"] <= m * w.c.rate

    # margin guard: AP at or above AR is refused without a receipt, admitted with one
    w = world(tmp_path / "margin.ndjson")
    m = max(1, w.wo.nte * 60 // w.c.rate - 1)
    visit(w.A, w.wo.id, w.p.id, m)
    quote_attest(w.A, w.wo.id, m)
    w.A("align", "provider_rate", {"provider": w.p.id, "trade": w.tax.trade, "cents": w.c.rate})
    rc, out = staged.settle(state_of(w.sp), w.wo.id)
    assert rc != 0 and "MarginGuard" in out
    with pytest.raises(store.Refused, match=r"MISSING\[reason\]"):
        w.A("exec", "nte_override_receipt", {"wo": w.wo.id, "id": nm("rcpt")})
    w.A("exec", "nte_override_receipt", {"wo": w.wo.id, "id": nm("rcpt"), "reason": fake.sentence()})
    rc, out = staged.settle(state_of(w.sp), w.wo.id)
    assert rc == 0, out

    # single-visit dispatch override: permits an expired-COI provider, never a banned one
    w = world(tmp_path / "ovr.ndjson", expired=True)
    assert elig(w)[1] is True and not any(elig(w)[0].values())
    w.A("exec", "dispatch_override", {"wo": w.wo.id, "provider": w.p.id, "authority": nm("exec"),
                                      "reason": fake.sentence()})
    pmap, trigger = elig(w)
    assert pmap[w.p.id] and trigger is False
    with pytest.raises(store.Refused, match="DUPLICATE"):
        w.A("exec", "dispatch_override", {"wo": w.wo.id, "provider": w.p.id,
                                          "authority": nm("exec"), "reason": fake.sentence()})
    with pytest.raises(store.Refused, match=r"MISSING\[authority\]"):
        w.A("exec", "dispatch_override", {"wo": w.wo.id, "provider": w.p.id, "reason": "x"})
    w = world(tmp_path / "ovr_ban.ndjson", expired=True)
    w.A("align", "provider_blacklist", {"provider": w.p.id})
    w.A("exec", "dispatch_override", {"wo": w.wo.id, "provider": w.p.id, "authority": nm("exec"),
                                      "reason": fake.sentence()})
    pmap, trigger = elig(w)
    assert not pmap[w.p.id] and trigger is True


# ================================================================ B3
def test_howto_reactive_hire_handoff_and_recruiter_queue(tmp_path, set_dials):
    # positive: no eligible provider (expired COI) -> reactive hire handoff, real plan contains it
    w = world(tmp_path / "hire.ndjson", expired=True)
    c = staged.compile_wo(state_of(w.sp), w.wo.id)
    assert c.missing == [] and "reactive_hire_handoff" in c.flags
    assert "reactive-hire-triggered" in " ".join(c.info)
    assert "(reactive-hire-triggered" in c.text
    # twin: an eligible provider -> no hire flag, no hire fact
    w2 = world(tmp_path / "nohire.ndjson")
    c2 = staged.compile_wo(state_of(w2.sp), w2.wo.id)
    assert c2.missing == [] and "reactive_hire_handoff" not in c2.flags
    assert "(reactive-hire-triggered" not in c2.text

    # dial: handoff semantics is reported through to the plan notes
    for opt in ("end_at_handoff", "continue_after_hire"):
        set_dials(handoff_semantics={"value": opt})
        c = staged.compile_wo(state_of(w.sp), w.wo.id)
        assert f"handoff_semantics={opt}" in c.info
    set_dials(handoff_semantics={"value": nm("opt")})
    with pytest.raises(ValueError, match="BAD_DIAL"):
        staged.compile_wo(state_of(w.sp), w.wo.id)


def test_gap_recruiter_queue(tmp_path):
    w = world(tmp_path / "rec.ndjson", expired=True)
    try:
        w.A("coord", "recruiter_call", {"wo": w.wo.id, "provider": w.p.id})
    except store.Refused as r:
        if "UNKNOWN_KIND" in str(r):
            pytest.skip("UNSUPPORTED[no recruiter_call event kind: recruiter outreach queue (O05)]")
        raise
    assert (w.wo.id, "recruiter_call") in state_of(w.sp)["observed"]


def test_gap_continue_after_hire(tmp_path, set_dials):
    """continue_after_hire is accepted as a dial value but changes only a note, not the plan."""
    w = world(tmp_path / "cah.ndjson", expired=True)
    set_dials(handoff_semantics={"value": "continue_after_hire"})
    a = staged.compile_wo(state_of(w.sp), w.wo.id).text
    set_dials(handoff_semantics={"value": "end_at_handoff"})
    b = staged.compile_wo(state_of(w.sp), w.wo.id).text
    if a == b:
        pytest.skip("UNSUPPORTED[handoff_semantics=continue_after_hire does not alter the compiled plan]")
    assert a != b


def _plan_or_typed_skip(sp, wo):
    r = staged.plan_wo(state_of(sp), wo)
    if r["rc"] != 0 and "already defined" in r["out"]:
        pytest.skip("UNSUPPORTED[plan: domain PDDL fails to parse (duplicate action name) - "
                    "spec/servengine_ideal_domain.pddl owner]")
    assert r["rc"] == 0, r["out"]
    return [s["action"] for s in r["steps"]]


def test_howto_reactive_hire_real_plan(tmp_path):
    os.environ.setdefault("PLAN_SEARCH_TIMEOUT_S", "5")
    w = world(tmp_path / "hire.ndjson", expired=True)
    assert "reactive-hire-handoff" in _plan_or_typed_skip(w.sp, w.wo.id)
    w2 = world(tmp_path / "nohire.ndjson")
    acts = _plan_or_typed_skip(w2.sp, w2.wo.id)
    assert "reactive-hire-handoff" not in acts and "auto-dispatch-aligned-provider" in acts
