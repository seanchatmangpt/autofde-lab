"""factory_boy factories for end-to-end JTBD plans.

A Scenario is a world (symbols, rates, dates, bytes drawn inside the envelopes of
ui_envelopes.toml) plus an ordered plan of UI steps. Eight traits give eight different plans:
four are built to run to settlement, four are built to be refused by a real gate. Nothing here is a
fixture value: reseed with PLAN_TEST_SEED to replay exactly."""
from __future__ import annotations

import math
import os
import string
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import factory
import factory.random
from faker import Faker

from enterprise_pipeline import store

HERE = Path(__file__).resolve().parent
UIENV = tomllib.loads((HERE / "ui_envelopes.toml").read_text())
SENV = tomllib.loads((HERE / "scenario_envelopes.toml").read_text())
D, EXPECT = SENV["domain"], SENV["expect"]
ECON, TEMP, UI = UIENV["bounds"]["economics"], UIENV["bounds"]["temporal"], UIENV["ui"]
VIEWS = UIENV["views"]
LETTERS = string.ascii_lowercase
SYMBOL_LEN = UIENV["generators"]["symbol_length"]

# the vocabulary named in scenario_envelopes.toml must exist in the static domain
_media = set(store.subtypes("media_artifact"))
_docs = set(store.subtypes("doc_slot"))
_tax = set(store.subtypes("taxonomy"))
assert {D["media_before"], D["media_after"], D["media_tag"]} <= _media
assert set(D["entity_docs"]) | set(D["provider_docs"]) <= _docs
assert set(D["taxonomy"]) <= _tax


def rg():
    return factory.random.randgen


def reseed(seed: int) -> None:
    factory.random.reseed_random(seed)
    Faker.seed(seed)


def seed_from_env() -> int:
    return int(os.environ.get("PLAN_TEST_SEED") or int.from_bytes(os.urandom(4), "big"))


# ---------------------------------------------------------------- steps
@dataclass(frozen=True)
class Step:
    action: str                  # form | dispatch | upload | compile | settle
    view: str = ""
    heading: str = ""            # form heading, or the submit button label for dispatch
    fields: tuple = ()           # ((label, widget, value), ...) widget: text number select date check
    expect: str = EXPECT["recorded"]
    kind: str = ""               # store kind this step appends on success ("" if none)
    stage: int = 0               # compile only: 1 = intake, 2 = qa-review
    data: bytes = b""            # upload only


def form(view, heading, kind, *fields, expect=EXPECT["recorded"]):
    return Step("form", VIEWS[view], heading, tuple(fields), expect, kind)


def T(label, v): return (label, "text", v)
def N(label, v): return (label, "number", v)
def S(label, v): return (label, "select", v)
def C(label): return (label, "check", True)
def Dt(label, v): return (label, "date", v)


@dataclass
class Scenario:
    name: str
    verdict: str                 # pass | fail
    gate: str                    # the real layer that decides the outcome
    fault: str | None
    part: bool
    second_provider: bool
    world: dict = field(repr=False)
    steps: list = field(default_factory=list, repr=False)
    intended: list = field(default_factory=list, repr=False)


def activities(steps) -> list[str]:
    """Store activities a plan produces when every step succeeds as expected."""
    out = []
    for s in steps:
        if s.action == "form" and s.expect == EXPECT["recorded"]:
            out.append(s.kind)
        elif s.action == "dispatch" and s.expect == EXPECT["recorded"]:
            out.append("dispatch")
        elif s.action == "upload":
            out.append(f"media:{s.heading}")
        elif s.action == "compile" and s.expect == EXPECT["plan_ok"]:
            out.append("plan_dispatched" if s.stage == 1 else "plan_closed")
        elif s.action == "settle" and s.expect == EXPECT["ledger_ok"]:
            out.append("ledger_settled")
    return out


def build_steps(w: dict, part: bool, second_provider: bool, fault: str | None) -> list[Step]:
    """The plan: setup, work order, stage-1 plan, dispatch, visit, evidence, stage-2 plan, ledger."""
    st: list[Step] = [form("super_admin", "entity", "entity", T("name", w["ent"]), T("dba", w["dba"]))]
    for dt, nm in zip(D["entity_docs"], (w["ss4"], w["w9e"])):
        st.append(form("super_admin", "entity_doc", "entity_doc", S("doc_type", dt), T("name", nm)))
    st.append(form("super_admin", "templates_bound", "templates_bound"))
    for ty, nm in zip(D["taxonomy"], (w["trade"], w["sub"], w["state"], w["prio"])):
        st.append(form("super_admin", "taxonomy", "taxonomy", S("type", ty), T("name", nm)))
    st += [
        form("super_admin", "client", "client", T("name", w["cli"]), S("kind", w["client_kind"]),
             S("delivery_mode", w["channel"]), N("payment_terms_days", w["terms"])),
        form("super_admin", "client_rate", "client_rate", S("client", w["cli"]),
             S("trade", w["trade"]), N("cents", w["cli_rate"])),
        form("super_admin", "site", "site", T("name", w["site"]), S("client", w["cli"]),
             S("state", w["state"]), S("territory_client", w["cli"])),
        form("super_admin", "asset", "asset", T("name", w["asset"]), S("site", w["site"])),
        form("super_admin", "coordinator", "coordinator", T("name", w["coord"])),
    ]
    providers = [w["prov"]] + ([w["prov2"]] if second_provider else [])
    for pv in providers:
        st.append(form("alignment", "provider", "provider", T("name", pv), S("kind", w["provider_kind"])))
    # prov2 stays document-less: the eligible provider is always prov
    docs = list(zip(D["provider_docs"], (w["w9p"], w["con"], w["coi"], w["lic"])))
    for dt, nm in docs:
        flds = [S("provider", w["prov"]), S("doc_type", dt), T("name", nm), C("valid")]
        if dt in D["expiring_provider_docs"]:
            flds.append(Dt("expiry_date", w["expiry"]))
        st.append(form("alignment", "provider_doc", "provider_doc", *flds))
    st += [
        form("alignment", "provider_approval", "provider_approval", S("provider", w["prov"]),
             S("trade", w["trade"]), S("sub_trade", w["sub"])),
        form("alignment", "provider_rate", "provider_rate", S("provider", w["prov"]),
             S("trade", w["trade"]), N("cents", w["prov_rate"])),
        form("alignment", "provider_rate_approved", "provider_rate_approved", S("provider", w["prov"]),
             S("trade", w["trade"])),
        form("alignment", "device_attested", "device_attested", S("provider", w["prov"])),
    ]
    wo = [T("name", w["wo"]), S("kind", w["wo_kind"]), T("wo_type", w["wotype"]),
          S("client", w["cli"]), S("site", w["site"]), S("trade", w["trade"]),
          S("sub_trade", w["sub"]), S("priority", w["prio"]), S("coordinator", w["coord"]),
          N("nte_cents", w["nte"]), N("onsite_sla_min", w["onsite"]), N("complete_sla_min", w["complete"])]
    if part:
        wo.append(S("part_asset", w["asset"]))
    st.append(form("coordinator", "work_order", "work_order", *wo))

    expired = fault == "expired_coi"
    st.append(Step("compile", stage=1, expect=EXPECT["no_plan"] if expired else EXPECT["plan_ok"],
                   heading=w["wo"]))
    if expired:  # the only candidate provider is expired: dispatch is refused by MiniZinc eligibility
        st.append(Step("dispatch", VIEWS["coordinator"], UI["submit_dispatch"],
                       (("wo", "select", w["wo"]), ("provider", "select", w["prov"])),
                       EXPECT["refused"]))
        return st
    st.append(form("coordinator", "proposal_quote", "proposal_quote", S("wo", w["wo"]),
                   N("minutes", w["quoted"])))
    st.append(Step("dispatch", VIEWS["coordinator"], UI["submit_dispatch"],
                   (("wo", "select", w["wo"]), ("provider", "select", w["prov"])),
                   EXPECT["recorded"], "dispatch"))
    for kind in ("geofence_attest", "checkin", "checkout"):
        st.append(form("field_qa", kind, kind, S("wo", w["wo"])))
    st.append(form("field_qa", "client_attest", "client_attest", S("wo", w["wo"]),
                   N("minutes", w["attest"])))
    st.append(Step("upload", VIEWS["field_qa"], D["media_before"], (("wo", "select", w["wo"]),
                   ("name", "text", w["bef"])), data=w["bef_bytes"]))
    st.append(Step("upload", VIEWS["field_qa"], D["media_after"], (("wo", "select", w["wo"]),
                   ("name", "text", w["aft"])), data=w["aft_bytes"]))
    needs_tag = part
    if fault == "withhold_tag" or fault == "attest_mismatch":
        st.append(Step("compile", stage=2, expect=EXPECT["no_plan"], heading=w["wo"]))
        return st
    if fault == "refuse_then_flip":
        st.append(Step("compile", stage=2, expect=EXPECT["no_plan"], heading=w["wo"]))
    if needs_tag:
        st.append(Step("upload", VIEWS["field_qa"], D["media_tag"], (("wo", "select", w["wo"]),
                       ("name", "text", w["tag"])), data=w["tag_bytes"]))
    st.append(Step("compile", stage=2, expect=EXPECT["plan_ok"], heading=w["wo"]))
    st.append(Step("settle", expect=EXPECT["ledger_refused"] if fault == "nte_below" else EXPECT["ledger_ok"]))
    return st


# ---------------------------------------------------------------- factories
def sym():
    return factory.Faker("lexify", text="?" * SYMBOL_LEN, letters=LETTERS)


class WorldFactory(factory.DictFactory):
    class Params:
        part = True
        coi_expired = False
        nte_below = False
        attest_mismatch = False

    ent, dba, ss4, w9e, trade, sub, state, prio = (sym() for _ in range(8))
    cli, site, asset, coord, prov, prov2 = (sym() for _ in range(6))
    w9p, con, coi, lic, wo, wotype, bef, aft, tag = (sym() for _ in range(9))
    channel = factory.LazyFunction(lambda: rg().choice(store.domain_constants("delivery_channel")))
    client_kind = factory.LazyFunction(lambda: rg().choice([k for k in store.subtypes("client") if k != "secondary_client"]))
    provider_kind = factory.LazyFunction(lambda: rg().choice(store.subtypes("provider")))
    wo_kind = factory.LazyFunction(lambda: rg().choice(store.subtypes("work_order")))
    terms = factory.LazyFunction(
        lambda: rg().randint(ECON["payment_terms_days_min"], ECON["payment_terms_days_max"]))
    prov_rate = factory.LazyFunction(
        lambda: rg().randint(ECON["provider_rate_min_cents"], ECON["provider_rate_max_cents"]))
    cli_rate = factory.LazyAttribute(lambda o: o.prov_rate + rg().randint(
        ECON["margin_spread_min_cents"], ECON["margin_spread_max_cents"]))
    quoted = factory.LazyFunction(lambda: rg().randint(
        TEMP["quoted_duration_min_floor"], TEMP["quoted_duration_min_ceil"]))
    attest = factory.LazyAttribute(lambda o: o.quoted + (
        rg().randint(SENV["bounds"]["attest_mismatch_extra_min"],
                     SENV["bounds"]["attest_mismatch_extra_max"]) if o.attest_mismatch else 0))

    @factory.lazy_attribute
    def nte(o):
        charge = math.ceil(o.quoted * o.cli_rate / 60)
        if o.nte_below:  # above the provider rate (still eligible), below the client charge
            return rg().randint(o.prov_rate, charge - 1)
        mult = rg().randint(ECON["nte_headroom_multiplier_min"], ECON["nte_headroom_multiplier_max"])
        return max(o.cli_rate * mult, charge + o.prov_rate)

    onsite = factory.LazyFunction(lambda: rg().randint(TEMP["onsite_sla_min_floor"], TEMP["onsite_sla_min_ceil"]))
    complete = factory.LazyAttribute(lambda o: o.onsite + rg().randint(
        TEMP["complete_sla_spread_min"], TEMP["complete_sla_spread_max"]))

    @factory.lazy_attribute
    def expiry(o):
        if o.coi_expired:
            return date.today() - timedelta(days=rg().randint(
                SENV["bounds"]["expired_days_min"], SENV["bounds"]["expired_days_max"]))
        return date.today() + timedelta(days=rg().randint(
            TEMP["doc_valid_future_days_min"], TEMP["doc_valid_future_days_max"]))

    bef_bytes = factory.LazyFunction(lambda: rg().randbytes(TEMP["upload_bytes_size"]))
    aft_bytes = factory.LazyFunction(lambda: rg().randbytes(TEMP["upload_bytes_size"]))
    tag_bytes = factory.LazyFunction(lambda: rg().randbytes(TEMP["upload_bytes_size"]))


class ScenarioFactory(factory.Factory):
    class Meta:
        model = Scenario

    class Params:
        part_with_tag = factory.Trait(name="part_with_tag")
        no_part = factory.Trait(name="no_part", part=False)
        refuse_then_flip = factory.Trait(name="refuse_then_flip", fault="refuse_then_flip",
                                         gate="stage2_plan_then_pass")
        two_providers = factory.Trait(name="two_providers", second_provider=True,
                                      gate="dispatch_eligibility")
        withhold_tag = factory.Trait(name="withhold_tag", fault="withhold_tag", verdict="fail",
                                     gate="stage2_plan")
        expired_coi = factory.Trait(name="expired_coi", fault="expired_coi", verdict="fail",
                                    gate="stage1_plan_and_dispatch")
        attest_mismatch = factory.Trait(name="attest_mismatch", fault="attest_mismatch",
                                        verdict="fail", gate="stage2_plan_dual_clock")
        nte_below_charge = factory.Trait(name="nte_below_charge", fault="nte_below",
                                         verdict="fail", gate="ledger")

    name = ""
    verdict = "pass"
    gate = "none"
    fault = None
    part = True
    second_provider = False
    world = factory.SubFactory(
        WorldFactory,
        part=factory.SelfAttribute("..part"),
        coi_expired=factory.LazyAttribute(lambda o: o.factory_parent.fault == "expired_coi"),
        nte_below=factory.LazyAttribute(lambda o: o.factory_parent.fault == "nte_below"),
        attest_mismatch=factory.LazyAttribute(lambda o: o.factory_parent.fault == "attest_mismatch"),
    )
    steps = factory.LazyAttribute(
        lambda o: build_steps(o.world, o.part, o.second_provider, o.fault))
    intended = factory.LazyAttribute(
        lambda o: activities(build_steps(o.world, o.part, o.second_provider, None)))


TRAITS = ("part_with_tag", "no_part", "refuse_then_flip", "two_providers",
          "withhold_tag", "expired_coi", "attest_mismatch", "nte_below_charge")


def batch(seed: int) -> list[Scenario]:
    """The 8 plans for one seed: same seed, same plans."""
    reseed(seed)
    return [ScenarioFactory(**{t: True}) for t in TRAITS]
