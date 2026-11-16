"""PDDL problem emitter + s-expression parser/normalizer for semantic comparison."""
import re


def _domain_has_territory():
    from .planner import DOMAIN
    return "(territory-flag" in DOMAIN.read_text()


def emit(state, elig):
    if len(state.get("entities", [])) > 1:  # multi-entity: slice to the entity owning the WOs
        from .store import slice_state
        state = slice_state(state, state["work_orders"][0])
    ent = state["entity"]
    objs = []  # (id, type)
    f = []     # init lines
    objs += [(ent["id"], "tenant_entity"), (ent["dba"], "dba_brand")]
    f.append(f"(= (current-clock) {state.get('clock', 0)})")
    f.append(f"(belongs-to-entity {ent['dba']} {ent['id']})")
    for d in ent["docs"]:
        objs.append((d["id"], d["type"]))
        f.append(f"(entity-doc-verified {ent['id']} {d['id']})")
    if ent.get("templates_bound"):
        f.append(f"(entity-templates-bound {ent['id']})")
    for c in state["clients"]:
        objs.append((c["id"], c["kind"]))
        f.append(f"(client-bound-to-entity {c['id']} {ent['id']})")
        if c.get("contracted_through"):
            f.append(f"(contracted-through {c['id']} {c['contracted_through']})")
        if c.get("delivery_mode"):
            f.append(f"(client-delivery-mode {c['id']} {c['delivery_mode']})")
        for t, r in c.get("labor_rates", {}).items():
            f.append(f"(= (client-labor-rate {c['id']} {t}) {r})")
        if "payment_terms_days" in c:
            f.append(f"(= (client-payment-terms-days {c['id']}) {c['payment_terms_days']})")
    for s in state["sites"]:
        objs.append((s["id"], "site"))
        f.append(f"(site-belongs-to {s['id']} {s['client']})")
        f.append(f"(site-in-state {s['id']} {s['state']})")
        f.append(f"(site-in-territory {s['id']} {s['territory_client']})")
        for a in s.get("assets", []):
            objs.append((a, "asset"))
            f.append(f"(asset-at-site {a} {s['id']})")
    for c in state["coordinators"]:
        objs.append((c["id"], "coordinator"))
    objs += [(t, "trade") for t in state["trades"]]
    objs += [(t, "sub_trade") for t in state["sub_trades"]]
    objs += [(t, "state_jurisdiction") for t in state["states"]]
    objs += [(t, "priority_tier") for t in state["priorities"]]
    for p in state["providers"]:
        objs.append((p["id"], p["kind"]))
        f.append(f"(provider-onboarded {p['id']} {ent['id']})")
        for d in p["docs"]:
            objs.append((d["id"], d["type"]))
            if d.get("valid"):
                f.append(f"(provider-doc-valid {p['id']} {d['id']})")
            if d.get("expiry") is not None:
                f.append(f"(= (doc-expiry-time {p['id']} {d['id']}) {d['expiry']})")
        for a in p["trade_approvals"]:
            f.append(f"(provider-trade-approved {p['id']} {a['trade']} {a['sub_trade']})")
        for t in p.get("rate_approved", []):
            f.append(f"(provider-rate-approved {p['id']} {t})")
        for t, r in p.get("rates", {}).items():
            f.append(f"(= (provider-agreed-rate {p['id']} {t}) {r})")
        for t, r in p.get("dispatch_rank", {}).items():
            f.append(f"(= (provider-dispatch-rank {p['id']} {t}) {r})")
    goals, timed = [], []
    clients = {c["id"]: c for c in state["clients"]}
    for p in state["providers"]:
        for d in p["docs"]:
            if d.get("expiry_event") and d.get("expiry") is not None and d.get("valid"):
                timed.append(f"(at {d['expiry']} (not (provider-doc-valid {p['id']} {d['id']})))")
    for wo in state["work_orders"]:
        w, v = wo["id"], wo["visit"]
        objs += [(w, wo["kind"]), (v["id"], "visit"), (wo["proposal"], "proposal"),
                 (wo["invoice"], "invoice"), (wo["payout"], "ap_payout")]
        pmap, trigger = elig[w]
        for pid, ok in pmap.items():
            if ok:
                f.append(f"(eligible-for-wo {pid} {w})")
        if trigger:
            f.append(f"(reactive-hire-triggered {w})")
        f += [f"(wo-state-intake {w})", f"(wo-under-entity {w} {ent['id']})",
              f"(wo-for-client {w} {wo['client']})", f"(wo-at-site {w} {wo['site']})",
              f"(wo-requires-trade {w} {wo['trade']} {wo['sub_trade']})",
              f"(wo-priority {w} {wo['priority']})"]
        if wo.get("requires_part_replacement"):
            f.append(f"(requires-part-replacement {w} {wo['requires_part_replacement']})")
        site_rec = next(x for x in state["sites"] if x["id"] == wo["site"])
        if wo["client"] != site_rec["territory_client"] and _domain_has_territory():
            f += [f"(territory-flag {w})", f"(sales-rep-notified {w})"]
            if w in state.get("waivers", {}):
                f.append(f"(territory-waived {w})")
        f += [f"(visit-of-wo {v['id']} {w})", f"(= (wo-nte-limit {w}) {wo['nte_limit']})",
              f"(= (wo-onsite-sla {w}) {wo['onsite_sla']})",
              f"(= (wo-complete-sla {w}) {wo['complete_sla']})"]
        for m in v["media"]:
            objs.append((m["id"], m["type"]))
    for c in state["coordinators"]:
        f.append(f"(= (coordinator-active-load {c['id']}) {c['active_load']})")
    for p in state["providers"]:
        if p.get("device_attested"):
            f.append(f"(device-integrity-attested {p['id']})")
    for wo in state["work_orders"]:
        w, v = wo["id"], wo["visit"]
        site = wo["site"]
        f.append(f"(geofence-attested {v['id']} {v['geofence_provider']} {site})")
        for m in v["media"]:
            if m.get("captured"):
                f.append(f"(media-captured {v['id']} {m['id']})")
        f += [f"(= (internal-actual-duration {v['id']}) {v['internal_actual_duration']})",
              f"(= (proposal-quoted-duration {w}) {v['proposal_quoted_duration']})",
              f"(= (external-client-duration {v['id']}) {v['external_client_duration']})"]
        mode = clients[wo["client"]].get("delivery_mode", "ch_email")
        goals += [f"(wo-state-closed {w})", f"(ai-vision-verified {v['id']})",
                  f"(invoice-delivered {wo['invoice']} {mode})",
                  f"(ap-payout-settled {wo['payout']})"]
    f += timed
    by_type = {}
    for i, t in objs:
        by_type.setdefault(t, [])
        if i not in by_type[t]:
            by_type[t].append(i)
    obj_lines = "\n".join(f"    {' '.join(ids)} - {t}" for t, ids in by_type.items())
    init = "\n".join(f"    {x}" for x in f)
    return (f"(define (problem {state['problem_name']})\n  (:domain {state['domain_name']})\n"
            f"  (:objects\n{obj_lines})\n  (:init\n{init})\n"
            f"  (:goal (and {' '.join(goals)}))\n  (:metric minimize (total-time)))\n")


def parse_sexp(text):
    text = re.sub(r";[^\n]*", "", text)
    toks = re.findall(r"\(|\)|[^\s()]+", text)
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            out = []
            while toks[pos] != ")":
                out.append(rd())
            pos += 1
            return out
        return t
    return rd()


def _tup(x):
    return tuple(_tup(i) for i in x) if isinstance(x, list) else x


def normalize(text):
    """-> dict(name, domain, objects:set[(id,type)], init:set, goal:set, metric)"""
    tree = parse_sexp(text)
    sec = {s[0]: s[1:] for s in tree[2:] if isinstance(s, list)}
    objs, pending = set(), []
    toks = sec[":objects"]
    i = 0
    while i < len(toks):
        if toks[i] == "-":
            objs |= {(n, toks[i + 1]) for n in pending}
            pending, i = [], i + 2
        else:
            pending.append(toks[i])
            i += 1
    assert not pending, "untyped objects"
    goal = sec[":goal"][0]
    goal_set = {_tup(g) for g in goal[1:]} if goal[0] == "and" else {_tup(goal)}
    return {"name": tree[1][1], "domain": sec[":domain"][0], "objects": objs,
            "init": {_tup(x) for x in sec[":init"]}, "goal": goal_set,
            "metric": _tup(sec[":metric"])}


def diff(a_text, b_text):
    a, b = normalize(a_text), normalize(b_text)
    out = []
    for k in ("name", "domain", "metric"):
        if a[k] != b[k]:
            out.append(f"{k}: {a[k]} != {b[k]}")
    for k in ("objects", "init", "goal"):
        for x in sorted(a[k] - b[k], key=str):
            out.append(f"only in A {k}: {x}")
        for x in sorted(b[k] - a[k], key=str):
            out.append(f"only in B {k}: {x}")
    return out
