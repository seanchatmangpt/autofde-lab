"""K-L3 court: clock clamp, media soft/hard gate, expiry matrix, 5-copy minizinc unexpired diff.

Written against docs/jira/v26.11.11/CONTRACT-LAWS.md (L3 compliance, L14 clock). Real store, real
MiniZinc, real dials file; no mocks, no sleeps. Every positive has an anti-vacuity twin."""
import os
import random
import shutil
from datetime import date, timedelta

import pytest

from enterprise_pipeline import align, staged, store
import helpers_world
from helpers_world import nm, run_visit


def build(sp, part=False):
    """helpers_world.build with a PRIMARY client: L09 (store.py NO_PARENT) refuses the helper's
    parentless secondary_client. Derived from the helper's own source, so it tracks the helper
    until the helpers owner fixes helpers_world.py:25."""
    import inspect
    src = inspect.getsource(helpers_world.build).replace('"secondary_client"', '"primary_client"')
    ns = dict(vars(helpers_world))
    exec(src, ns)  # noqa: S102 - same module source, one literal swapped
    return ns["build"](sp, part)

DAY = 86400


@pytest.fixture()
def sp(tmp_path):
    return tmp_path / "events.jsonl"


@pytest.fixture()
def dials_file(tmp_path, monkeypatch):
    """Write a dials TOML for one switch value and point PLAN_POLICY_DIALS at it."""
    def put(switch, value):
        f = tmp_path / "dials.toml"
        f.write_text(f'[{switch}]\nvalue = "{value}"\n')
        monkeypatch.setenv("PLAN_POLICY_DIALS", str(f))
        return f
    return put


def _iso(days):
    return (date.today() + timedelta(days=days)).isoformat()


def _add_provider(A, o, docs):
    """docs: {doc_type: expiry_date|None|False(absent)} -> provider id, fully approved."""
    p = nm("prov")
    A("align", "provider", {"name": p, "kind": "sub_1099"})
    for dt, exp in docs.items():
        if exp is False:
            continue
        pl = {"provider": p, "doc_type": dt, "name": nm(dt), "valid": True}
        if exp:
            pl["expiry_date"] = exp
        A("align", "provider_doc", pl)
    A("align", "provider_approval", {"provider": p, "trade": o["trade"], "sub_trade": o["sub"]})
    A("align", "provider_rate_approved", {"provider": p, "trade": o["trade"]})
    A("align", "provider_rate", {"provider": p, "trade": o["trade"], "cents": random.randint(3000, 8000)})
    A("align", "device_attested", {"provider": p})
    return p


def _prov(state, pid):
    return next(p for p in state["providers"] if p["id"] == pid)


# ------------------------------------------------------------------ L14 clock clamp
def test_clock_clamps_up_to_last_event(sp, monkeypatch):
    A, o, _ = build(sp)
    ev = store.read(sp)
    last = ev[-1]["ts"]
    monkeypatch.setenv("PLAN_CLOCK_NOW", str(ev[0]["ts"] - random.randint(2, 9) * DAY))
    st = store.reduce(ev)
    assert st["clock"] == store.minutes(last, ev[0]["ts"])  # clamped, never earlier than last event
    assert st["clock"] >= 0


def test_clock_clamp_twin_pinned_later_is_not_clamped(sp, monkeypatch):
    A, o, _ = build(sp)
    ev = store.read(sp)
    pinned = ev[-1]["ts"] + random.randint(2, 9) * DAY
    monkeypatch.setenv("PLAN_CLOCK_NOW", str(pinned))
    st = store.reduce(ev)
    assert st["clock"] == store.minutes(pinned, ev[0]["ts"])
    assert st["clock"] > store.minutes(ev[-1]["ts"], ev[0]["ts"])  # twin: clamp must not flatten later pins


def test_clamped_clock_lets_old_pin_still_veto_expired_doc(sp, monkeypatch):
    """Without the clamp an old pin would make a just-expired doc look live."""
    A, o, _ = build(sp)
    p = _add_provider(A, o, {"coi_doc": _iso(-1), "license_doc": _iso(300),
                             "w9_doc": None, "contract_doc": None})
    ev = store.read(sp)
    monkeypatch.setenv("PLAN_CLOCK_NOW", str(ev[0]["ts"] - 30 * DAY))
    st = store.reduce(ev)
    assert _prov(st, p)["docs"], "provider recorded"
    wo = st["work_orders"][0]
    _, provs = align.derive(st, wo)
    assert not next(x for x in provs if x["id"] == p)["unexpired"]


# ------------------------------------------------------------------ L10 expiry matrix
def test_record_time_accepts_past_expiry(sp):
    A, o, _ = build(sp)
    p = _add_provider(A, o, {"coi_doc": _iso(-random.randint(1, 400)),
                             "license_doc": _iso(-random.randint(1, 400)),
                             "w9_doc": None, "contract_doc": None})
    assert _prov(store.reduce(store.read(sp)), p)["docs"]


def test_expiry_matrix_coi_license_enforced(sp):
    A, o, _ = build(sp)
    live = _iso(random.randint(100, 700))
    dead = _iso(-random.randint(1, 400))
    cases = {}
    for coi in (live, dead):
        for lic in (live, dead):
            cases[_add_provider(A, o, {"coi_doc": coi, "license_doc": lic,
                                       "w9_doc": None, "contract_doc": None})] = (coi == live and lic == live)
    st = store.reduce(store.read(sp))
    _, provs = align.derive(st, st["work_orders"][0])
    got = {p["id"]: p["unexpired"] for p in provs}
    for pid, want in cases.items():
        assert got[pid] is want
    assert any(cases.values()) and not all(cases.values())  # twin: matrix is not constant


def test_w9_contract_undated_never_expire(sp, monkeypatch):
    A, o, _ = build(sp)
    p = _add_provider(A, o, {"coi_doc": _iso(100), "license_doc": _iso(100),
                             "w9_doc": None, "contract_doc": None})
    ev = store.read(sp)
    monkeypatch.setenv("PLAN_CLOCK_NOW", str(ev[-1]["ts"] + random.randint(300, 600) * DAY))
    st = store.reduce(ev)
    _, provs = align.derive(st, st["work_orders"][0])
    row = next(x for x in provs if x["id"] == p)
    assert row["aligned"]  # undated w9/contract: non-expiring even years later
    assert not row["unexpired"]  # twin: dated coi/license (100d) at the same clock DO expire


def test_w9_contract_dated_expired_vetoes_by_default(sp, dials_file):
    A, o, _ = build(sp)
    dead = _add_provider(A, o, {"coi_doc": _iso(500), "license_doc": _iso(500),
                                "w9_doc": _iso(-5), "contract_doc": None})
    ok = _add_provider(A, o, {"coi_doc": _iso(500), "license_doc": _iso(500),
                              "w9_doc": _iso(500), "contract_doc": _iso(500)})
    st = store.reduce(store.read(sp))
    _, provs = align.derive(st, st["work_orders"][0])
    by = {p["id"]: p for p in provs}
    assert by[dead]["aligned"] is False
    assert by[ok]["aligned"] is True


def test_w9_contract_dated_expired_record_and_warn_ignores_expiry(sp, dials_file):
    dials_file("document_expiry_enforcement", "record_and_warn")
    A, o, _ = build(sp)
    dead = _add_provider(A, o, {"coi_doc": _iso(500), "license_doc": _iso(500),
                                "w9_doc": _iso(-5), "contract_doc": _iso(-5)})
    st = store.reduce(store.read(sp))
    _, provs = align.derive(st, st["work_orders"][0])
    assert next(p for p in provs if p["id"] == dead)["aligned"] is True
    c = staged.compile_wo(st, st["work_orders"][0]["id"])
    assert any(f"DOC_EXPIRED" in str(i) for i in c.info)


# ------------------------------------------------------------------ 5-copy minizinc unexpired diff
@pytest.mark.skipif(shutil.which("minizinc") is None, reason="minizinc absent")
def test_five_copy_minizinc_matches_python_unexpired(sp):
    A, o, _ = build(sp)
    live, dead = _iso(random.randint(100, 700)), _iso(-random.randint(1, 400))
    pool = [(live, live), (dead, live), (live, dead), (dead, dead), (live, live)]
    random.shuffle(pool)
    want = {}
    for coi, lic in pool:
        want[_add_provider(A, o, {"coi_doc": coi, "license_doc": lic,
                                  "w9_doc": None, "contract_doc": None})] = (coi == live and lic == live)
    st = store.reduce(store.read(sp))
    wo = st["work_orders"][0]
    elig, _ = align.run_minizinc(st, wo)
    _, provs = align.derive(st, wo)
    py = {p["id"]: p["unexpired"] for p in provs}
    for pid, w in want.items():
        assert py[pid] is w
        assert elig[pid] is w, "minizinc eligibility must equal python unexpired for undisturbed providers"
    assert any(want.values()) and not all(want.values())


# ------------------------------------------------------------------ L13 media
def _media_world(sp, n=1):
    A, o, _ = build(sp)
    types = store.subtypes("media_artifact")
    req = random.sample(types, min(n, len(types)))
    for t in req:
        A("coord", "required_media", {"wo": o["wo"], "media_type": t})
    return A, o, req, types


def test_required_media_bad_type_refused(sp):
    A, o, _, _ = _media_world(sp)
    with pytest.raises(store.Refused, match="BAD_TYPE"):
        A("coord", "required_media", {"wo": o["wo"], "media_type": nm("nomedia")})


def test_missing_media_derived_and_cleared_by_upload(sp):
    A, o, req, _ = _media_world(sp, 2)
    st = store.reduce(store.read(sp))
    wo = st["work_orders"][0]
    assert sorted(store.missing_media(wo)) == sorted(req)
    A("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]})
    A("field", "checkin", {"wo": o["wo"]})
    A("field", "media", {"wo": o["wo"], "media_type": req[0], "name": nm("m"), "sha256": nm("h")})
    wo = store.reduce(store.read(sp))["work_orders"][0]
    assert store.missing_media(wo) == [req[1]] if len(req) > 1 else store.missing_media(wo) == []
    assert req[0] not in store.missing_media(wo)  # twin: uploaded type leaves the missing set


def test_soft_prompt_does_not_refuse_checkout_by_default(sp):
    A, o, req, _ = _media_world(sp)
    A("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]})
    A("field", "geofence_attest", {"wo": o["wo"]})
    A("field", "checkin", {"wo": o["wo"]})
    A("field", "checkout", {"wo": o["wo"]})  # soft_only: accepted
    assert store.reduce(store.read(sp))["work_orders"][0]["stage"] == "qa-review"


def test_hard_refuse_mode_blocks_checkout(sp, dials_file):
    dials_file("media_prompt_mode", "hard_refuse")
    A, o, req, _ = _media_world(sp)
    A("coord", "dispatch", {"wo": o["wo"], "provider": o["prov"]})
    A("field", "geofence_attest", {"wo": o["wo"]})
    A("field", "checkin", {"wo": o["wo"]})
    with pytest.raises(store.Refused, match="MISSING_MEDIA"):
        A("field", "checkout", {"wo": o["wo"]})
    A("field", "media", {"wo": o["wo"], "media_type": req[0], "name": nm("m"), "sha256": nm("h")})
    A("field", "checkout", {"wo": o["wo"]})  # twin: satisfied -> accepted


def test_stage2_hard_gate_in_every_mode(sp):
    A, o, req, _ = _media_world(sp)
    run_visit(A, o)
    st = store.reduce(store.read(sp))
    c = staged.compile_wo(st, o["wo"])
    assert any(m.startswith("MISSING_MEDIA") for m in c.missing)
    A("field", "media", {"wo": o["wo"], "media_type": req[0], "name": nm("m"), "sha256": nm("h")})
    st = store.reduce(store.read(sp))
    c = staged.compile_wo(st, o["wo"])
    assert not any(m.startswith("MISSING_MEDIA") for m in c.missing)  # twin: gate lifts when satisfied
