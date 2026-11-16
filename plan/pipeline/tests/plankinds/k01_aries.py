"""K1: temporal PDDL 2.1 through the real planner (aries) over real store-built enterprise states.

Also hosts the shared world builder used by k02/k03 (kind modules are the only files in this lane)."""
from __future__ import annotations

import hashlib
import os
import tempfile
import zlib
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K1"
TITLE = "temporal PDDL 2.1 (aries) stage-1/stage-2 compile+plan"

os.environ.setdefault("PLAN_TEST_SEED", str(int.from_bytes(os.urandom(4), "big")))


def seed() -> int:
    return int(os.environ["PLAN_TEST_SEED"])


def draw_world(case_id: str, **params) -> dict:
    """World drawn by factory_boy inside the TOML envelopes; seeded per case id, order-independent."""
    import jtbd_factories as jf
    jf.reseed(seed() + zlib.crc32(case_id.encode()))
    w = dict(jf.WorldFactory(**params))
    w["part"] = params.get("part", True)  # factory Params are not dict keys
    return w


def build_store(w: dict, sp: Path, *, providers=1, blacklist=False, expired=False, filtered=False,
                unapproved=False, rate_gte_client=False, rate_eq_client=False, territory_out=False, stage=1,
                tag=True, nte_below=False) -> dict:
    """Append real events into the store at sp; returns the ids used."""
    from enterprise_pipeline import store
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    A("admin", "entity", {"name": w["ent"], "dba": w["dba"]})
    for dt, nm in zip(("ss4_doc", "w9_doc"), (w["ss4"], w["w9e"])):
        A("admin", "entity_doc", {"doc_type": dt, "name": nm})
    A("admin", "templates_bound", {})
    for ty, nm in zip(("trade", "sub_trade", "state_jurisdiction", "priority_tier"),
                      (w["trade"], w["sub"], w["state"], w["prio"])):
        A("admin", "taxonomy", {"type": ty, "name": nm})
    A("admin", "client", {"name": w["cli"], "kind": w["client_kind"], "delivery_mode": w["channel"],
                          "payment_terms_days": w["terms"]})
    cli_rate = w["cli_rate"]
    prov_rate = cli_rate + 1 if rate_gte_client else cli_rate if rate_eq_client else w["prov_rate"]
    A("admin", "client_rate", {"client": w["cli"], "trade": w["trade"], "cents": cli_rate})
    terr = w["cli"]
    if territory_out:
        A("admin", "client", {"name": w["prov2"], "kind": w["client_kind"],
                              "delivery_mode": w["channel"], "payment_terms_days": w["terms"]})
        terr = w["prov2"]
    A("admin", "site", {"name": w["site"], "client": w["cli"], "state": w["state"],
                        "territory_client": terr})
    A("admin", "asset", {"name": w["asset"], "site": w["site"]})
    A("coord", "coordinator", {"name": w["coord"]})
    names = [w["prov"], w["prov2"] + "_p" if not territory_out else w["prov"] + "_p"][:providers]
    for i, pv in enumerate(names):
        A("align", "provider", {"name": pv, "kind": w["provider_kind"]})
        for dt, nm in (("w9_doc", f"{pv}_w9"), ("contract_doc", f"{pv}_con")):
            A("align", "provider_doc", {"provider": pv, "doc_type": dt, "name": nm, "valid": True})
        for dt, nm in (("coi_doc", f"{pv}_coi"), ("license_doc", f"{pv}_lic")):
            doc = {"provider": pv, "doc_type": dt, "name": nm, "valid": True,
                   "expiry_date": w["expiry"].isoformat()}
            A("align", "provider_doc", doc)
        if not (unapproved and i == 0):
            A("align", "provider_approval", {"provider": pv, "trade": w["trade"], "sub_trade": w["sub"]})
            A("align", "provider_rate_approved", {"provider": pv, "trade": w["trade"]})
        A("align", "provider_rate", {"provider": pv, "trade": w["trade"], "cents": prov_rate})
        A("align", "device_attested", {"provider": pv})
        if i == 0 and blacklist:
            A("align", "provider_blacklist", {"provider": pv})
        if i == 0 and filtered:
            A("align", "provider_filter", {"provider": pv, "dim": "trade", "mode": "exc",
                                           "values": [w["trade"]]})
    wo = {"name": w["wo"], "kind": w["wo_kind"], "wo_type": w["wotype"], "client": w["cli"],
          "site": w["site"], "trade": w["trade"], "sub_trade": w["sub"], "priority": w["prio"],
          "coordinator": w["coord"], "nte_cents": max(w["nte"], prov_rate),
          "onsite_sla_min": w["onsite"], "complete_sla_min": w["complete"]}
    if w.get("part"):
        wo["part_asset"] = w["asset"]
    A("coord", "work_order", wo)
    if stage == 2:
        A("coord", "dispatch", {"wo": w["wo"], "provider": w["prov"]})
        A("field", "geofence_attest", {"wo": w["wo"]})
        A("field", "checkin", {"wo": w["wo"]})
        A("field", "checkout", {"wo": w["wo"]})
        A("coord", "proposal_quote", {"wo": w["wo"], "minutes": w["quoted"]})
        A("field", "client_attest", {"wo": w["wo"], "minutes": w["attest"]})
        for ty, nm, data in (("before_media", w["bef"], w["bef_bytes"]),
                             ("after_media", w["aft"], w["aft_bytes"])):
            A("field", "media", {"wo": w["wo"], "media_type": ty, "name": nm,
                                 "sha256": hashlib.sha256(data).hexdigest()})
        if w.get("part") and tag:
            A("field", "media", {"wo": w["wo"], "media_type": "model_tag_photo", "name": w["tag"],
                                 "sha256": hashlib.sha256(w["tag_bytes"]).hexdigest()})
    return {"wo": w["wo"], "providers": names}


def plan_wo(state, wo_id, timeout=900) -> dict:
    """staged.plan_wo with the solve routed through enterprise_pipeline.planner.solve_files
    (coprocessor temporal_pddl; PLAN_ORACLE=1 selects the old plan.py oracle)."""
    from enterprise_pipeline import planner, staged
    c = staged.compile_wo(state, wo_id)
    res = {"rc": None, "out": "", "steps": [], "missing": c.missing, "info": c.info,
           "goal": c.goal, "problem": c.text, "flags": c.flags}
    if c.text is None:
        return res
    with tempfile.TemporaryDirectory() as td:
        prob, dom = Path(td) / "problem.pddl", Path(td) / "domain.pddl"
        prob.write_text(c.text)
        dtext, dropped = staged.project_domain(planner.DOMAIN.read_text(), c.text)
        dom.write_text(dtext)
        res["info"] = c.info + dropped
        rc, out = planner.solve_files(dom, prob, timeout=timeout)
    res["rc"], res["out"] = rc, out.strip()
    res["steps"] = planner.parse_plan(out) if rc == 0 else []
    return res


def probe():
    from enterprise_pipeline import planner
    if planner.oracle_enabled():
        if not (planner.RUN_SH.exists() and os.access(planner.RUN_SH, os.X_OK)):
            return Skip(f"oracle planner absent at {planner.RUN_SH}", "planner/REPAIRS.md")
        return None
    from enterprise_pipeline import autofde_backend as ab
    if not os.path.exists(ab.backend_python()):
        return Skip("autofde-lab venv python missing", "uv venv .venv at the autofde-lab root")
    return None


def cases():
    return [
        Case("stage1_ok", "PLAN", {"w": {}, "stage": 1, "opts": {}}),
        Case("stage1_territory_out", "NO_PLAN", {"w": {}, "stage": 1, "opts": {"territory_out": True}}),
        Case("stage2_ok", "PLAN", {"w": {"part": True}, "stage": 2, "opts": {}}),
        Case("stage2_tag_withheld", "NO_PLAN", {"w": {"part": True}, "stage": 2, "opts": {"tag": False}}),
        Case("stage2_attest_mismatch", "NO_PLAN",
             {"w": {"part": False, "attest_mismatch": True}, "stage": 2, "opts": {}}),
    ]


def run(case) -> Outcome:
    from enterprise_pipeline import store
    p = case.payload
    w = draw_world(case.id, **p["w"])
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "events.ndjson"
        old = os.environ.get("PLAN_STORE")
        os.environ["PLAN_STORE"] = str(sp)
        try:
            ids = build_store(w, sp, stage=p["stage"], **p["opts"])
            state = store.reduce(store.read(sp))
            r = plan_wo(state, ids["wo"])
        finally:
            if old is None:
                os.environ.pop("PLAN_STORE", None)
            else:
                os.environ["PLAN_STORE"] = old
    if r["rc"] == 0:
        st = "PLAN"
    elif r["rc"] == 2:
        st = "NO_PLAN"
    else:
        st = "REFUSED"
    detail = f"rc={r['rc']} steps={len(r['steps'])} missing={r['missing']}"
    return Outcome(st, detail, hashlib.sha256(r["out"].encode()).hexdigest()[:16])
