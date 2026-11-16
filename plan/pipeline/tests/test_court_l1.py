"""K-L1 court: dispatch laws L01/L02/L04 over real store, MiniZinc, planner. Names generated."""
import pytest

from enterprise_pipeline import align, staged, store
import helpers_world
from helpers_world import nm


def build(sp, part=False):
    """helpers_world.build with a PRIMARY client (store.py NO_PARENT refuses the helper's
    parentless secondary_client); derived from the helper's own source so it tracks it."""
    import inspect
    src = inspect.getsource(helpers_world.build).replace('"secondary_client"', '"primary_client"')
    ns = dict(vars(helpers_world))
    exec(src, ns)  # noqa: S102 - same module source, one literal swapped
    return ns["build"](sp, part)


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.ndjson"


def _state(sp):
    return store.reduce(store.read(sp))


def _wo(state, wid):
    return next(w for w in state["work_orders"] if w["id"] == wid)


def _elig(sp, wid):
    st = _state(sp)
    return staged.eligibility(st, _wo(st, wid), store.slice_state(st, _wo(st, wid))["providers"])


def _second_wo(A, o):
    """Second site + work order for the same client/provider (anti-leak twin subject)."""
    site2, wo2 = nm("site"), nm("wo")
    A("admin", "site", {"name": site2, "client": o["cli"], "state": o["st"],
                        "territory_client": o["cli"]})
    A("coord", "work_order", {
        "name": wo2, "kind": "reactive_wo", "wo_type": "reactive", "client": o["cli"],
        "site": site2, "trade": o["trade"], "sub_trade": o["sub"], "priority": o["prio"],
        "coordinator": o["coord"], "nte_cents": 100000, "onsite_sla_min": 1000,
        "complete_sla_min": 4000})
    return site2, wo2


def _world(sp):
    A, o, _ = build(sp)
    o["_sp"] = sp
    return A, o


# --- L01 BAD_DIM -------------------------------------------------------------------------
def test_filter_dim_outside_dim_set_refused_bad_dim(sp):
    A, o = _world(sp)
    bad = nm("dim")
    assert bad not in align.DIMS
    with pytest.raises(store.Refused, match=r"BAD_DIM\[%s\]" % bad):
        A("align", "provider_filter", {"provider": o["prov"], "dim": bad, "mode": "exc",
                                       "values": [o["site"]]})


@pytest.mark.parametrize("dim", align.DIMS)
def test_every_declared_dim_is_accepted_twin(sp, dim):
    A, o = _world(sp)
    A("align", "provider_filter", {"provider": o["prov"], "dim": dim, "mode": "inc",
                                   "values": [nm("v")]})
    assert dim in "".join(_state(sp)["providers"][0]["filters"])


def test_bad_mode_still_refused_and_dim_check_does_not_mask_it(sp):
    A, o = _world(sp)
    with pytest.raises(store.Refused, match="BAD_MODE"):
        A("align", "provider_filter", {"provider": o["prov"], "dim": "site", "mode": nm("m"),
                                       "values": [o["site"]]})


# --- L02 global ban vs site exclusion ----------------------------------------------------
def test_baseline_provider_eligible_at_both_sites(sp):
    A, o = _world(sp)
    _, wo2 = _second_wo(A, o)
    assert _elig(sp, o["wo"])[0][o["prov"]] is True
    assert _elig(sp, wo2)[0][o["prov"]] is True


def test_invoice_left_on_site_is_global_ban_blocking_every_site(sp):
    A, o = _world(sp)
    _, wo2 = _second_wo(A, o)
    A("coord", "invoice_left_on_site", {"provider": o["prov"], "wo": o["wo"]})
    st = _state(sp)
    assert st["providers"][0]["blacklisted"] is True
    for w in (o["wo"], wo2):
        el, trigger = _elig(sp, w)
        assert el[o["prov"]] is False and trigger is True


def test_ban_payout_leg_pddl_carries_blacklist_fact(sp):
    A, o = _world(sp)
    A("coord", "invoice_left_on_site", {"provider": o["prov"], "wo": o["wo"]})
    c = staged.compile_wo(_state(sp), o["wo"])
    assert f"(provider-blacklisted {o['prov']})" in c.text


def test_ban_events_refuse_unknown_refs(sp):
    A, o = _world(sp)
    with pytest.raises(store.Refused, match=r"UNKNOWN\[provider"):
        A("coord", "invoice_left_on_site", {"provider": nm("p"), "wo": o["wo"]})
    with pytest.raises(store.Refused, match=r"UNKNOWN\[work_order"):
        A("coord", "invoice_left_on_site", {"provider": o["prov"], "wo": nm("w")})


def test_site_manager_clash_excludes_that_site_only_no_leak(sp):
    A, o = _world(sp)
    site2, wo2 = _second_wo(A, o)
    A("coord", "site_manager_clash", {"provider": o["prov"], "site": o["site"]})
    p = _state(sp)["providers"][0]
    assert p["filters"]["exc_site"] == [o["site"]] and p["blacklisted"] is False
    assert _elig(sp, o["wo"])[0][o["prov"]] is False
    assert _elig(sp, wo2)[0][o["prov"]] is True  # twin: second site not leaked


def test_site_clash_refuses_unknown_site_and_provider(sp):
    A, o = _world(sp)
    with pytest.raises(store.Refused, match=r"UNKNOWN\[site"):
        A("coord", "site_manager_clash", {"provider": o["prov"], "site": nm("s")})
    with pytest.raises(store.Refused, match=r"UNKNOWN\[provider"):
        A("coord", "site_manager_clash", {"provider": nm("p"), "site": o["site"]})


# --- L04 reactive-hire handoff -----------------------------------------------------------
def test_nobody_eligible_triggers_handoff_in_pddl_and_info(sp):
    A, o = _world(sp)
    A("coord", "site_manager_clash", {"provider": o["prov"], "site": o["site"]})
    c = staged.compile_wo(_state(sp), o["wo"])
    assert f"(reactive-hire-triggered {o['wo']})" in c.text
    assert any("reactive-hire-triggered" in i for i in c.info)


def test_eligible_provider_does_not_trigger_handoff_twin(sp):
    A, o = _world(sp)
    c = staged.compile_wo(_state(sp), o["wo"])
    assert f"(reactive-hire-triggered {o['wo']})" not in c.text
    assert not any("reactive-hire-triggered" in i for i in c.info)


def test_plan_wo_handoff_flag_when_nobody_eligible(sp, monkeypatch):
    monkeypatch.setenv("PLAN_SEARCH_TIMEOUT_S", "5")
    A, o = _world(sp)
    A("coord", "invoice_left_on_site", {"provider": o["prov"], "wo": o["wo"]})
    r = staged.plan_wo(_state(sp), o["wo"], timeout=120)
    assert "reactive_hire_handoff" in r.get("flags", [])


def test_plan_wo_no_handoff_flag_when_eligible_twin(sp, monkeypatch):
    monkeypatch.setenv("PLAN_SEARCH_TIMEOUT_S", "5")
    A, o = _world(sp)
    r = staged.plan_wo(_state(sp), o["wo"], timeout=120)
    assert "reactive_hire_handoff" not in r.get("flags", [])


# --- flip-trait twins --------------------------------------------------------------------
def test_flip_filter_mode_flips_eligibility(sp):
    A, o = _world(sp)
    A("align", "provider_filter", {"provider": o["prov"], "dim": "site", "mode": "inc",
                                   "values": [o["site"]]})
    assert _elig(sp, o["wo"])[0][o["prov"]] is True
    sp2 = sp.parent / "flip.ndjson"
    A2, o2 = _world(sp2)
    A2("align", "provider_filter", {"provider": o2["prov"], "dim": "site", "mode": "exc",
                                    "values": [o2["site"]]})
    assert _elig(sp2, o2["wo"])[0][o2["prov"]] is False


def test_flip_ban_event_flips_eligibility_same_world(sp):
    A, o = _world(sp)
    before = _elig(sp, o["wo"])[0][o["prov"]]
    A("coord", "invoice_left_on_site", {"provider": o["prov"], "wo": o["wo"]})
    after = _elig(sp, o["wo"])[0][o["prov"]]
    assert (before, after) == (True, False)
