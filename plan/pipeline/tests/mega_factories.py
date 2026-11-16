"""factory_boy world for the single mega JTBD run: every example Vince gave, in one entity.

One entity, four clients (three primary, one secondary contracted through a primary), seven
sites, three providers (premium, budget, escalated), eight work orders, each driven by its own
trait. Symbols are drawn without replacement; every number comes from the TOML envelopes.
Reseed with PLAN_TEST_SEED to replay exactly."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import factory

import jtbd_factories as jf
from jtbd_factories import (C, D, ECON, EXPECT, N, S, SENV, T, TEMP, UI, VIEWS, Dt, Scenario, Step,
                            activities, form, rg, store)

M = SENV["mega"]
_USED: set[str] = set()


def fresh_symbol() -> str:
    while True:
        s = "".join(rg().choice(jf.LETTERS) for _ in range(jf.SYMBOL_LEN))
        if s not in _USED:
            _USED.add(s)
            return s


def sym():
    return factory.LazyFunction(fresh_symbol)


class ProviderFactory(factory.DictFactory):
    class Params:
        premium = False

    name, w9, con, coi, lic = (sym() for _ in range(5))
    kind = factory.LazyFunction(lambda: rg().choice(store.subtypes("provider")))
    rate = factory.LazyAttribute(lambda o: rg().randint(
        M["premium_rate_min_cents"] if o.premium else M["budget_rate_min_cents"],
        M["premium_rate_max_cents"] if o.premium else M["budget_rate_max_cents"]))
    expiry = factory.LazyFunction(lambda: date.today() + timedelta(days=rg().randint(
        TEMP["doc_valid_future_days_min"], TEMP["doc_valid_future_days_max"])))


class WoFactory(factory.DictFactory):
    class Params:
        nte_below = False

    name, wotype = sym(), sym()
    bef, aft, tag = sym(), sym(), sym()
    quoted = factory.LazyFunction(lambda: rg().randint(
        TEMP["quoted_duration_min_floor"], TEMP["quoted_duration_min_ceil"]))
    onsite = factory.LazyFunction(lambda: rg().randint(TEMP["onsite_sla_min_floor"], TEMP["onsite_sla_min_ceil"]))
    complete = factory.LazyAttribute(lambda o: o.onsite + rg().randint(
        TEMP["complete_sla_spread_min"], TEMP["complete_sla_spread_max"]))
    bef_bytes = factory.LazyFunction(lambda: rg().randbytes(TEMP["upload_bytes_size"]))
    aft_bytes = factory.LazyFunction(lambda: rg().randbytes(TEMP["upload_bytes_size"]))
    tag_bytes = factory.LazyFunction(lambda: rg().randbytes(TEMP["upload_bytes_size"]))


@dataclass
class Mega:
    world: dict
    steps: list = field(repr=False)
    intended: list = field(repr=False)
    expected: dict = field(default_factory=dict)   # wo name -> (label, outcome, gate)
    name: str = "mega"


def _dispatch(w, prov, expect):
    return Step("dispatch", VIEWS["coordinator"], UI["submit_dispatch"],
                (("wo", "select", w), ("provider", "select", prov)), expect,
                "dispatch" if expect == EXPECT["recorded"] else "")


def _journey(wo, w, cli_rate, prov, prov_rate, *, refused=(), stage1=True, tag=None, stage2=True,
             settle=True, coord=None):
    """One work order from intake to ledger; the flags choose which real gate ends it."""
    st = [Step("compile", stage=1, heading=wo["name"],
               expect=EXPECT["plan_ok"] if stage1 else EXPECT["no_plan"])]
    if not stage1:
        return st
    st.append(form("coordinator", "proposal_quote", "proposal_quote", S("wo", wo["name"]), N("minutes", wo["quoted"])))
    for p in refused:
        st.append(_dispatch(wo["name"], p, EXPECT["refused"]))
    st.append(_dispatch(wo["name"], prov, EXPECT["recorded"]))
    for kind in ("geofence_attest", "checkin", "checkout"):
        st.append(form("field_qa", kind, kind, S("wo", wo["name"])))
    st.append(form("field_qa", "client_attest", "client_attest", S("wo", wo["name"]), N("minutes", wo["quoted"])))
    st.append(Step("upload", VIEWS["field_qa"], D["media_before"],
                   (("wo", "select", wo["name"]), ("name", "text", wo["bef"])), data=wo["bef_bytes"]))
    st.append(Step("upload", VIEWS["field_qa"], D["media_after"],
                   (("wo", "select", wo["name"]), ("name", "text", wo["aft"])), data=wo["aft_bytes"]))
    if tag:
        st.append(Step("upload", VIEWS["field_qa"], D["media_tag"],
                       (("wo", "select", wo["name"]), ("name", "text", wo["tag"])), data=wo["tag_bytes"]))
    st.append(Step("compile", stage=2, heading=wo["name"],
                   expect=EXPECT["plan_ok"] if stage2 else EXPECT["no_plan"]))
    if stage2:
        st.append(Step("settle", fields=(("wo", "select", wo["name"]),),
                       expect=EXPECT["ledger_ok"] if settle else EXPECT["ledger_refused"]))
    return st


def build() -> Mega:
    """Draw the world and assemble the full ordered plan; call after jf.reseed(seed)."""
    _USED.clear()
    n = {k: fresh_symbol() for k in (
        "ent", "dba", "ss4", "w9e", "trade", "sub_a", "sub_b", "st_in", "st_out", "prio",
        "cvs", "amc", "nestle", "cvs_sub", "coord_a", "coord_b",
        "s_amc", "s_nestle", "s_in", "s_out", "s_sub", "a_tagged", "a_untagged", "a_cvs")}
    premium, budget, escalated = (ProviderFactory(premium=True), ProviderFactory(),
                                  ProviderFactory(premium=True))
    top = max(premium["rate"], escalated["rate"])
    cli_rate = top + rg().randint(M["client_spread_min_cents"], M["client_spread_max_cents"])
    terms = lambda: rg().randint(ECON["payment_terms_days_min"], ECON["payment_terms_days_max"])
    chan = lambda: rg().choice(store.domain_constants("delivery_channel"))
    kinds = store.subtypes("client")
    pk, sk = kinds[0], kinds[1]
    assert "primary" in pk and "secondary" in sk, kinds

    def wo(**kw):
        d = WoFactory(**kw)
        nte = max(cli_rate * rg().randint(ECON["nte_headroom_multiplier_min"],
                                          ECON["nte_headroom_multiplier_max"]),
                  math.ceil(d["quoted"] * cli_rate / 60) + top)
        if kw.get("nte_below"):
            nte = rg().randint(top, math.ceil(d["quoted"] * cli_rate / 60) - 1)
        d["nte"] = nte
        return d

    w_amc, w_nes_ok, w_nes_no, w_out, w_rep, w_proj, w_sole = (wo() for _ in range(7))
    w_nte = wo(nte_below=True)
    st: list[Step] = [form("super_admin", "entity", "entity", T("name", n["ent"]), T("dba", n["dba"]))]
    for dt, nm in zip(D["entity_docs"], (n["ss4"], n["w9e"])):
        st.append(form("super_admin", "entity_doc", "entity_doc", S("doc_type", dt), T("name", nm)))
    st.append(form("super_admin", "templates_bound", "templates_bound"))
    for ty, nm in zip(("trade", "sub_trade", "sub_trade", "state_jurisdiction", "state_jurisdiction",
                       "priority_tier"),
                      (n["trade"], n["sub_a"], n["sub_b"], n["st_in"], n["st_out"], n["prio"])):
        st.append(form("super_admin", "taxonomy", "taxonomy", S("type", ty), T("name", nm)))
    for c, kind, parent in ((n["cvs"], pk, None), (n["amc"], pk, None), (n["nestle"], pk, None),
                            (n["cvs_sub"], sk, n["cvs"])):
        f = [T("name", c), S("kind", kind), S("delivery_mode", chan()), N("payment_terms_days", terms())]
        if parent:
            f.insert(2, S("parent", parent))
        st.append(form("super_admin", "client", "client", *f))
        st.append(form("super_admin", "client_rate", "client_rate", S("client", c),
                       S("trade", n["trade"]), N("cents", cli_rate)))
    # (site, client, state, territory holder): s_out is a CVS site outside the pilot's coverage
    for s, c, stt, terr in ((n["s_amc"], n["amc"], n["st_in"], n["amc"]),
                            (n["s_nestle"], n["nestle"], n["st_in"], n["nestle"]),
                            (n["s_in"], n["cvs"], n["st_in"], n["cvs"]),
                            (n["s_out"], n["cvs"], n["st_out"], n["cvs_sub"]),
                            (n["s_sub"], n["cvs_sub"], n["st_in"], n["cvs_sub"])):
        st.append(form("super_admin", "site", "site", T("name", s), S("client", c), S("state", stt),
                       S("territory_client", terr)))
    for a, s in ((n["a_tagged"], n["s_nestle"]), (n["a_untagged"], n["s_nestle"]), (n["a_cvs"], n["s_in"])):
        st.append(form("super_admin", "asset", "asset", T("name", a), S("site", s)))
    for c in (n["coord_a"], n["coord_b"]):
        st.append(form("super_admin", "coordinator", "coordinator", T("name", c)))
    for p in (premium, budget, escalated):
        st.append(form("alignment", "provider", "provider", T("name", p["name"]), S("kind", p["kind"])))
        for dt, nm in zip(D["provider_docs"], (p["w9"], p["con"], p["coi"], p["lic"])):
            f = [S("provider", p["name"]), S("doc_type", dt), T("name", nm), C("valid")]
            if dt in D["expiring_provider_docs"]:
                f.append(Dt("expiry_date", p["expiry"]))
            st.append(form("alignment", "provider_doc", "provider_doc", *f))
        for sub in (n["sub_a"], n["sub_b"]):
            st.append(form("alignment", "provider_approval", "provider_approval",
                           S("provider", p["name"]), S("trade", n["trade"]), S("sub_trade", sub)))
        st += [form("alignment", "provider_rate", "provider_rate", S("provider", p["name"]),
                    S("trade", n["trade"]), N("cents", p["rate"])),
               form("alignment", "provider_rate_approved", "provider_rate_approved",
                    S("provider", p["name"]), S("trade", n["trade"])),
               form("alignment", "device_attested", "device_attested", S("provider", p["name"]))]

    def new_wo(w, kind, client, site, sub, coord, part=None):
        f = [T("name", w["name"]), S("kind", kind), T("wo_type", w["wotype"]), S("client", client),
             S("site", site), S("trade", n["trade"]), S("sub_trade", sub), S("priority", n["prio"]),
             S("coordinator", coord), N("nte_cents", w["nte"]), N("onsite_sla_min", w["onsite"]),
             N("complete_sla_min", w["complete"])]
        if part:
            f.append(S("part_asset", part))
        return form("coordinator", "work_order", "work_order", *f)

    wk = {k: k for k in store.subtypes("work_order")}
    expected, ledger = {}, {}

    def run(label, w, kind, client, site, sub, coord, prov, outcome, gate, part=None, **jk):
        st.append(new_wo(w, kind, client, site, sub, coord, part))
        pr = {premium["name"]: premium["rate"], budget["name"]: budget["rate"],
              escalated["name"]: escalated["rate"]}[prov]
        st.extend(_journey(w, w["name"], cli_rate, prov, pr, **jk))
        expected[w["name"]] = (label, outcome, gate)
        ledger[w["name"]] = {"attest": w["quoted"], "cli_rate": cli_rate, "prov_rate": pr}

    # 1 AMC lighting survey: inspection, no part, premium technician, clean close
    run("amc_survey", w_amc, "inspection_wo", n["amc"], n["s_amc"], n["sub_a"], n["coord_a"],
        premium["name"], "settled", "none")
    # 2 Nestle cold-storage survey, unit with a serial tag: tag photo satisfies the AI gate
    run("nestle_tagged", w_nes_ok, "inspection_wo", n["nestle"], n["s_nestle"], n["sub_b"], n["coord_b"],
        premium["name"], "settled", "none", part=n["a_tagged"], tag=True)
    # 3 Nestle unit with no serial tag: model-tag evidence withheld, stage-2 plan refused
    run("nestle_untagged", w_nes_no, "inspection_wo", n["nestle"], n["s_nestle"], n["sub_b"], n["coord_a"],
        premium["name"], "refused", "stage2_plan", part=n["a_untagged"], stage2=False)
    # 4 CVS (primary) job outside the pilot's coverage: still plans, territory flag + sales rep notified
    run("cvs_out_of_coverage", w_out, "reactive_wo", n["cvs"], n["s_out"], n["sub_a"], n["coord_b"],
        premium["name"], "settled", "territory_flag")
    # 5 CVS repair: the escalated provider (left an invoice on site) is banned, premium closes it
    st.append(form("alignment", "provider_blacklist", "provider_blacklist", S("provider", escalated["name"])))
    run("cvs_repair", w_rep, "reactive_wo", n["cvs"], n["s_in"], n["sub_a"], n["coord_a"],
        premium["name"], "settled", "escalated_ban", part=n["a_cvs"], tag=True,
        refused=(escalated["name"],))
    # 6 the repair becomes a project; budget tech was clashing with the site manager: excluded there
    st.append(form("alignment", "provider_filter", "provider_filter", S("provider", budget["name"]),
                   S("dim", "site"), S("mode", "exc"), ("values", "list", n["s_in"])))
    run("cvs_project", w_proj, "project_wo", n["cvs"], n["s_in"], n["sub_a"], n["coord_b"],
        premium["name"], "settled", "site_exclusion", refused=(budget["name"],))
    # 7 sole local provider on a secondary client: the budget tech works the site he is not excluded from
    run("cvs_sub_sole_provider", w_sole, "reactive_wo", n["cvs_sub"], n["s_sub"], n["sub_a"], n["coord_a"],
        budget["name"], "settled", "none")
    # 8 recall whose NTE sits under the client charge: the exact ledger refuses
    run("nestle_recall_nte", w_nte, "recall_wo", n["nestle"], n["s_nestle"], n["sub_a"], n["coord_b"],
        premium["name"], "refused", "ledger", settle=False)
    world = {"names": n, "cli_rate": cli_rate, "ledger": ledger,
             "providers": {"premium": premium, "budget": budget, "escalated": escalated}}
    return Mega(world, st, activities(st), expected)
