"""Stage-aware compile: recorded state -> PDDL problem. Facts exist only because an event was
recorded; anything absent is reported as a typed MISSING[...] instead of being invented."""
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import align, store
from .planner import DOMAIN, RUN_SH, parse_plan
from .store import ROOT

PROVIDER_DOC_TYPES = ("w9_doc", "coi_doc", "license_doc", "contract_doc")


@dataclass
class Compiled:
    text: str | None
    goal: str | None
    missing: list = field(default_factory=list)
    info: list = field(default_factory=list)
    flags: list = field(default_factory=list)


def _wo(state, wo_id):
    return next(w for w in state.get("work_orders", []) if w["id"] == wo_id)


def internal_minutes(v):
    if v.get("checkin_ts") is None or v.get("checkout_ts") is None:
        return None
    return math.ceil((v["checkout_ts"] - v["checkin_ts"]) / 60)


OPEN_DEFAULTS = {"secondary_out_of_coverage": "flag_and_plan", "handoff_semantics": "end_at_handoff",
                 "document_expiry_enforcement": "veto_dispatch_when_expired",
                 "clock_policy": "strict_internal"}


def _dial(switch):
    try:
        from . import dials
    except ImportError:
        return OPEN_DEFAULTS[switch]
    return dials.clock_policy() if switch == "clock_policy" else dials.get(switch)


def visits_of(wo):
    return wo.get("visits") or [wo["visit"]]


def missing_media(wo):
    """Derived: required media types absent from every visit's media (store.missing_media if present)."""
    if hasattr(store, "missing_media"):
        return store.missing_media(wo)
    have = {m["type"] for v in visits_of(wo) for m in v.get("media", [])}
    return [t for t in wo.get("required_media", []) if t not in have]


def territory_state(state, wo):
    """-> 'in' | 'out_primary' | 'out_secondary' | 'waived' (L06: wo.client != site.territory_client)."""
    site = next(s for s in state["sites"] if s["id"] == wo["site"])
    if wo["client"] == site["territory_client"]:
        return "in"
    client = next(x for x in state["clients"] if x["id"] == wo["client"])
    if wo["id"] in state.get("waivers", {}):
        return "waived"
    secondary = bool(client.get("parent") or client.get("contracted_through"))
    return "out_secondary" if secondary else "out_primary"


def _provider_gap(p):
    """-> reason string if provider cannot be planned with, else None."""
    types = {d["type"] for d in p["docs"]}
    for t in PROVIDER_DOC_TYPES:
        if t not in types:
            return f"no {t} recorded"
    for d in p["docs"]:
        if d["type"] in ("coi_doc", "license_doc") and d.get("expiry") is None:
            return f"{d['id']} has no expiry"
    return None


def eligibility(state, wo, providers):
    """Real MiniZinc eligibility over the planned-with providers; empty -> reactive hire."""
    if not providers:
        return {}, True
    sub = {**state, "providers": providers, "work_orders": [wo]}
    return align.run_minizinc(sub, wo)


def compile_wo(state, wo_id) -> Compiled:
    c = Compiled(None, None)
    if not state.get("entities"):
        c.missing.append("MISSING[entity]")
        return c
    try:
        wo = _wo(state, wo_id)
    except StopIteration:
        c.missing.append(f"MISSING[work_order {wo_id}]")
        return c
    state = store.slice_state(state, wo)  # entity_of(wo) slice: one entity's world
    ent = state["entity"]
    v, stage = wo["visit"], wo["stage"]
    client = next(x for x in state["clients"] if x["id"] == wo["client"])
    etypes = {d["type"] for d in ent["docs"]}
    for t in ("ss4_doc", "w9_doc"):
        if t not in etypes and stage == "intake":
            c.missing.append(f"MISSING[entity doc {t}]")
    if not ent.get("templates_bound"):
        c.missing.append("MISSING[entity templates_bound]")

    usable = []
    for p in state["providers"]:
        gap = _provider_gap(p)
        if gap and stage == "intake":
            c.info.append(f"provider {p['id']} excluded: {gap}")
        elif stage != "intake" or not gap:
            usable.append(p)
    if stage == "intake" and not usable:
        c.missing.append("MISSING[provider with w9/coi/license/contract docs and expiries]")

    if stage in ("dispatched", "on-site"):
        c.missing.append("MISSING[checkout]: internal-actual-duration is unknown until check-out")
        c.goal = None
    elif stage == "intake":
        c.goal = f"(wo-state-dispatched {wo_id})"
    else:
        c.goal = "closed"
        mins = internal_minutes(v)
        if not mins or mins <= 0:
            c.missing.append("MISSING[internal minutes > 0]")
        if v.get("quoted_min") is None:
            c.missing.append("MISSING[proposal_quote]")
        if v.get("external_min") is None:
            c.missing.append("MISSING[client_attest]")
        if not client.get("delivery_mode"):
            c.missing.append(f"MISSING[client delivery_mode {client['id']}]")
        if wo["trade"] not in client.get("labor_rates", {}):
            c.missing.append(f"MISSING[client labor rate {client['id']}/{wo['trade']}]")
        if client.get("payment_terms_days") is None:
            c.missing.append(f"MISSING[client payment_terms_days {client['id']}]")
        pv = next((p for p in state["providers"] if p["id"] == v.get("provider")), None)
        if pv is None or wo["trade"] not in pv["rates"]:
            c.missing.append(f"MISSING[provider rate {v.get('provider')}/{wo['trade']}]")
    terr = territory_state(state, wo)
    if terr in ("out_primary", "out_secondary", "waived"):
        if terr == "out_secondary" or (terr == "out_primary" and _dial("secondary_out_of_coverage") == "refuse"):
            c.missing.append("NO_PLAN[out_of_coverage]")
        else:
            c.info.append(f"territory_flag: {wo_id} client {wo['client']} outside territory")
            c.flags.append("territory_flag")
    if stage == "qa-review":
        for t in missing_media(wo):
            c.missing.append(f"MISSING_MEDIA[{t}]")
        if wo.get("requires_part_replacement") and not any(
                m["type"] == "model_tag_photo" for vv in visits_of(wo) for m in vv.get("media", [])):
            c.missing.append("MISSING[model_tag_photo]: part replacement requires the model-tag photo")
    if _dial("document_expiry_enforcement") == "record_and_warn":
        for p in state["providers"]:
            for d in p["docs"]:
                if d["type"] in ("w9_doc", "contract_doc") and d.get("expiry") is not None and d["expiry"] <= state["clock"]:
                    c.info.append(f"DOC_EXPIRED[{d['id']}]")
    if c.missing:
        return c

    elig = {}
    if stage == "intake":
        elig, trigger = eligibility(state, wo, usable)
        if trigger:
            c.info.append("reactive-hire-triggered: no eligible provider")
            c.info.append(f"handoff_semantics={_dial('handoff_semantics')}")
            c.flags.append("reactive_hire_handoff")

    objs, f = [], []
    site = next(s for s in state["sites"] if s["id"] == wo["site"])
    # relevance slice: ground only what this work order can touch (keeps aries inside its budget)
    rel_clients = [x for x in state["clients"] if x["id"] in {wo["client"], client.get("contracted_through"), site["territory_client"]}]
    rel_coords = [x for x in state["coordinators"] if x["id"] == wo["coordinator"]]
    if stage == "intake":
        rel_provs = [p for p in usable if elig.get(p["id"])] or usable
    else:
        rel_provs = [p for p in usable if p["id"] == v.get("provider")]
    objs += [(ent["id"], "tenant_entity"), (ent["dba"], "dba_brand")]
    f.append(f"(= (current-clock) {state['clock']})")
    f.append(f"(belongs-to-entity {ent['dba']} {ent['id']})")
    for d in ent["docs"]:
        objs.append((d["id"], d["type"]))
        f.append(f"(entity-doc-verified {ent['id']} {d['id']})")
    f.append(f"(entity-templates-bound {ent['id']})")
    for cl in rel_clients:
        objs.append((cl["id"], cl["kind"]))
        f.append(f"(client-bound-to-entity {cl['id']} {ent['id']})")
        if cl.get("contracted_through"):
            f.append(f"(contracted-through {cl['id']} {cl['contracted_through']})")
        if cl.get("delivery_mode"):
            f.append(f"(client-delivery-mode {cl['id']} {cl['delivery_mode']})")
        for t, r in cl["labor_rates"].items():
            f.append(f"(= (client-labor-rate {cl['id']} {t}) {r})")
        if cl.get("payment_terms_days") is not None:
            f.append(f"(= (client-payment-terms-days {cl['id']}) {cl['payment_terms_days']})")
    for s in [site]:
        objs.append((s["id"], "site"))
        f += [f"(site-belongs-to {s['id']} {s['client']})", f"(site-in-state {s['id']} {s['state']})",
              f"(site-in-territory {s['id']} {s['territory_client']})"]
        for a in s["assets"]:
            objs.append((a, "asset"))
            f.append(f"(asset-at-site {a} {s['id']})")
    for co in rel_coords:
        objs.append((co["id"], "coordinator"))
        f.append(f"(= (coordinator-active-load {co['id']}) {co['active_load']})")
    objs += [(t, "trade") for t in state["trades"]] + [(t, "sub_trade") for t in state["sub_trades"]]
    objs += [(t, "state_jurisdiction") for t in state["states"]]
    objs += [(t, "priority_tier") for t in state["priorities"]]
    for p in rel_provs:
        objs.append((p["id"], p["kind"]))
        f.append(f"(provider-onboarded {p['id']} {ent['id']})")
        for d in p["docs"]:
            objs.append((d["id"], d["type"]))
            if d["valid"]:
                f.append(f"(provider-doc-valid {p['id']} {d['id']})")
            if d.get("expiry") is not None:
                f.append(f"(= (doc-expiry-time {p['id']} {d['id']}) {max(d['expiry'], 0)})")  # fluents are >= 0; an earlier expiry is expired at clock 0 as well
        f += [f"(provider-trade-approved {p['id']} {a['trade']} {a['sub_trade']})" for a in p["trade_approvals"]]
        f += [f"(provider-rate-approved {p['id']} {t})" for t in p["rate_approved"]]
        f += [f"(= (provider-agreed-rate {p['id']} {t}) {r})" for t, r in p["rates"].items()]
        f += [f"(= (provider-dispatch-rank {p['id']} {t}) {r})" for t, r in p["dispatch_rank"].items()]
        if p["blacklisted"]:
            f.append(f"(provider-blacklisted {p['id']})")
        if p["device_attested"]:
            f.append(f"(device-integrity-attested {p['id']})")
    w = wo_id
    objs += [(w, wo["kind"]), (v["id"], "visit"), (wo["proposal"], "proposal"),
             (wo["invoice"], "invoice"), (wo["payout"], "ap_payout")]
    for pid, ok in elig.items():
        if ok:
            f.append(f"(eligible-for-wo {pid} {w})")
    if stage == "intake" and not any(elig.values()):
        f.append(f"(reactive-hire-triggered {w})")
    if "(territory-flag" in DOMAIN.read_text():  # emitted only once the domain declares the predicates
        if terr in ("out_primary", "waived"):
            f += [f"(territory-flag {w})", f"(sales-rep-notified {w})"]
        if terr == "waived":
            f.append(f"(territory-waived {w})")
    f += [f"(wo-under-entity {w} {ent['id']})", f"(wo-for-client {w} {wo['client']})",
          f"(wo-at-site {w} {site['id']})", f"(wo-requires-trade {w} {wo['trade']} {wo['sub_trade']})",
          f"(wo-priority {w} {wo['priority']})", f"(visit-of-wo {v['id']} {w})",
          f"(= (wo-nte-limit {w}) {wo['nte_limit']})",
          f"(= (wo-onsite-sla {w}) {wo['created_min'] + wo['onsite_sla_min']})",
          f"(= (wo-complete-sla {w}) {wo['created_min'] + wo['complete_sla_min']})"]
    if wo.get("requires_part_replacement"):
        f.append(f"(requires-part-replacement {w} {wo['requires_part_replacement']})")
    else:
        f.append(f"(wo-no-part-replacement {w})")
    goal = []
    if stage == "intake":
        f.append(f"(wo-state-intake {w})")
        goal = [f"(reactive-hire-handed-off {w})" if "reactive_hire_handoff" in c.flags else c.goal]
        c.goal = " ".join(goal)
    else:
        f.append(f"(wo-state-qa-review {w})")
        f += [f"(visit-assigned {v['id']} {v['provider']})", f"(internal-checked-in {v['id']})",
              f"(internal-checked-out {v['id']})"]
        if v["geofence"]:
            f.append(f"(geofence-attested {v['id']} {v['provider']} {site['id']})")
        for m in v["media"]:
            objs.append((m["id"], m["type"]))
            f.append(f"(media-captured {v['id']} {m['id']})")
        f += [f"(= (internal-actual-duration {v['id']}) {internal_minutes(v)})",
              f"(= (proposal-quoted-duration {w}) {v['quoted_min']})",
              f"(= (external-client-duration {v['id']}) {v['external_min']})"]
        goal = [f"(wo-state-closed {w})", f"(ai-vision-verified {v['id']})",
                f"(invoice-delivered {wo['invoice']} {client['delivery_mode']})",
                f"(ap-payout-settled {wo['payout']})"]
        c.goal = " ".join(goal)
    by_type = {}
    for i, t in objs:
        by_type.setdefault(t, [])
        if i not in by_type[t]:
            by_type[t].append(i)
    c.text = (f"(define (problem staged_{w})\n  (:domain servengine-autonomous-fm)\n  (:objects\n"
              + "\n".join(f"    {' '.join(ids)} - {t}" for t, ids in by_type.items())
              + "\n  )\n  (:init\n" + "\n".join(f"    {x}" for x in f)
              + f"\n  )\n  (:goal (and {' '.join(goal)}))\n  (:metric minimize (total-time)))\n")
    return c


def _blocks(text):
    """Yield (start, end) of every top-level (:durative-action ...) block by paren matching."""
    i = 0
    while True:
        i = text.find("(:durative-action", i)
        if i < 0:
            return
        depth, j = 0, i
        while True:
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            j += 1
            if depth == 0:
                break
        yield i, j
        i = j


def project_domain(domain_text, problem_text):
    """Drop actions that read a numeric fluent with no recorded initial value (unknown is not
    admitted). -> (projected domain text, [info lines])."""
    import re
    recorded = set(re.findall(r"\(=\s*\(([^\s()]+)", problem_text))
    recorded.add("current-clock")
    declared = set(re.findall(r"\(([a-z][a-z0-9-]*)\s+\?", domain_text.split("(:functions", 1)[1].split("(:durative-action", 1)[0]))
    out, dropped, last = [], [], 0
    for a, b in _blocks(domain_text):
        blk = domain_text[a:b]
        name = blk.split()[1]
        body = re.sub(r"\((assign|increase)\s+\(([^\s()]+)", r"(\1 (@target", blk)
        used = {f for f in declared if re.search(r"\(" + re.escape(f) + r"[\s)]", body)}
        gap = sorted(used - recorded)
        out.append(domain_text[last:a])
        last = b
        if gap:
            dropped.append(f"action {name} dropped: unrecorded fluent {', '.join(gap)}")
        else:
            out.append(blk)
    out.append(domain_text[last:])
    return "".join(out), dropped


def plan_wo(state, wo_id, timeout=900) -> dict:
    """Compile then run the real planner. -> {rc, out, steps, missing, info, goal, problem}"""
    c = compile_wo(state, wo_id)
    res = {"rc": None, "out": "", "steps": [], "missing": c.missing, "info": c.info,
           "goal": c.goal, "problem": c.text, "flags": c.flags}
    if c.text is None:
        return res
    with tempfile.TemporaryDirectory() as td:
        prob, dom = Path(td) / "problem.pddl", Path(td) / "domain.pddl"
        prob.write_text(c.text)
        dtext, dropped = project_domain(DOMAIN.read_text(), c.text)
        dom.write_text(dtext)
        res["info"] = c.info + dropped
        r = subprocess.run(["bash", str(RUN_SH), str(dom), str(prob), str(Path(td) / "out.soln")],
                           capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    res["rc"], res["out"] = r.returncode, (r.stdout + "\n" + r.stderr).strip()
    res["steps"] = parse_plan(r.stdout) if r.returncode == 0 else []
    return res


def _clock_use_external(state, wo, client_rate, provider_rate):
    """True when AP minutes fall back to external (quoted) minutes when internal is absent."""
    pol = _dial("clock_policy")
    if pol == "quoted_safe_harbor":
        return True
    if pol != "auto_gpm_density":
        return False
    from . import dials
    if not align.is_desolate(state, wo):
        return False
    gpm_bps = (client_rate - provider_rate) * 10000 // client_rate if client_rate else 0
    return (gpm_bps >= int(dials.param("clock_policy_auto", "gpm_safe_harbor_bps"))
            or provider_rate <= int(dials.param("clock_policy_auto", "low_rate_safe_harbor_cents")))


def settle(state, wo_id) -> tuple[int, str]:
    """Money only from the exact ledger over recorded values; NOT EXECUTED-equivalent if missing.
    AR/AP are summed over every visit; change_order/override_receipt are forwarded to the ledger."""
    wo = _wo(state, wo_id)
    client = next(x for x in state["clients"] if x["id"] == wo["client"])
    results = []
    for v in visits_of(wo):
        pv = next((p for p in state["providers"] if p["id"] == v.get("provider")), None)
        mins = internal_minutes(v)
        crate = client.get("labor_rates", {}).get(wo["trade"])
        prate = (pv or {}).get("rates", {}).get(wo["trade"])
        if not mins and v.get("external_min") and crate and prate and \
                _clock_use_external(state, wo, crate, prate):
            mins = v["external_min"]
        need = {"internal_minutes": mins, "external_minutes": v.get("external_min"),
                "client_rate": crate, "provider_rate": prate,
                "terms_days": client.get("payment_terms_days")}
        gaps = [k for k, x in need.items() if not x]
        if gaps:
            return -1, "MISSING[" + ", ".join(gaps) + "]"
        inp = {"clock_minutes": state["clock"], "terms_days": need["terms_days"],
               "external_minutes": need["external_minutes"], "internal_minutes": need["internal_minutes"],
               "client_rate_cents_per_hour": crate,
               "provider_rate_cents_per_hour": prate, "nte_limit_cents": wo["nte_limit"]}
        if wo.get("change_order"):
            inp["change_order"] = wo["change_order"]
        if wo.get("override_receipt"):
            inp["override_receipt"] = wo["override_receipt"]
        r = subprocess.run(["python3", "-m", "ledger", "settle"], input=json.dumps(inp), cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout + "\n" + r.stderr).strip()
        if r.returncode != 0:
            return r.returncode, out
        results.append(out)
    if len(results) == 1:
        return 0, results[0]
    ar = ap = 0
    for out in results:
        d = json.loads(out)
        ar += d["ar_cents"]
        ap += d["ap_cents"]
    return 0, json.dumps({"ar_cents": ar, "ap_cents": ap, "margin_cents": ar - ap,
                          "visits": [json.loads(o) for o in results]})


def _sha(text) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def observe_plan(state, wo_id, r):
    """-> (kind, payload) for a successful real plan, else None. Only rc==0 is observed."""
    if r.get("rc") != 0:
        return None
    stage = _wo(state, wo_id)["stage"]
    kind = {"intake": "plan_dispatched", "qa-review": "plan_closed"}.get(stage)
    if kind is None:
        return None
    return kind, {"wo": wo_id, "goal": r["goal"], "planner_rc": r["rc"], "plan_sha256": _sha(r["out"])}


def observe_flags(state, wo_id, r):
    """Automatic territory notifications for a plan result -> [(kind, payload)]."""
    wo = _wo(state, wo_id)
    st = store.slice_state(state, wo)
    if territory_state(st, wo) not in ("out_primary", "waived"):
        return []
    site = next(x for x in st["sites"] if x["id"] == wo["site"])
    base = {"wo": wo_id, "client": wo["client"]}
    return [("territory_flag", {**base, "site": site["id"]}), ("sales_rep_notified", base)]


def observe_settle(wo_id, rc, out):
    """-> ('ledger_settled', payload) for rc==0 only; ar/ap only if parseable from ledger JSON."""
    if rc != 0:
        return None
    p = {"wo": wo_id, "ledger_sha256": _sha(out)}
    try:
        d = json.loads(out)
        for k in ("ar_cents", "ap_cents", "margin_cents"):
            if isinstance(d.get(k), int):
                p[k] = d[k]
        if "margin_cents" not in p and "ar_cents" in p and "ap_cents" in p:
            p["margin_cents"] = p["ar_cents"] - p["ap_cents"]
    except (ValueError, AttributeError):
        pass
    return "ledger_settled", p
