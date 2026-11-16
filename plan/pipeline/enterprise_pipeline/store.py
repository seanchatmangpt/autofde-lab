"""Append-only event store and reducer. The store starts empty; state exists only because an
avatar recorded an event. No defaults except empty collections."""
import hashlib
import json
import math
import os
import re
import time
from datetime import date, datetime, time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "spec" / "servengine_ideal_domain.pddl"
DEFAULT_STORE = ROOT / "store" / "events.ndjson"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def store_path(path=None) -> Path:
    return Path(path or os.environ.get("PLAN_STORE") or DEFAULT_STORE)


# ---------------------------------------------------------------- domain introspection
def domain_types(domain=DOMAIN) -> dict:
    """-> {type: parent} parsed from the (:types ...) block of the static domain."""
    text = re.sub(r";[^\n]*", "", Path(domain).read_text())
    m = re.search(r"\(:types(.*?)\n\s*\)\s*\n\s*\(:constants", text, re.S) or \
        re.search(r"\(:types(.*?)\)\s*\(:constants", text, re.S)
    body = m.group(1)
    out, pending = {}, []
    toks = body.split()
    i = 0
    while i < len(toks):
        if toks[i] == "-":
            for n in pending:
                out[n] = toks[i + 1]
            pending, i = [], i + 2
        else:
            pending.append(toks[i])
            i += 1
    for n in pending:
        out[n] = "object"
    return out


def subtypes(root: str, domain=DOMAIN) -> list[str]:
    t = domain_types(domain)
    kids = [n for n, p in t.items() if p == root]
    leaves = []
    for k in kids:
        sub = subtypes(k, domain)
        leaves += sub or [k]
    return leaves


def domain_constants(type_name: str, domain=DOMAIN) -> list[str]:
    text = re.sub(r";[^\n]*", "", Path(domain).read_text())
    m = re.search(r"\(:constants(.*?)\)", text, re.S)
    toks = m.group(1).split() if m else []
    out, pending, i = [], [], 0
    while i < len(toks):
        if toks[i] == "-":
            if toks[i + 1] == type_name:
                out += pending
            pending, i = [], i + 2
        else:
            pending.append(toks[i])
            i += 1
    return out


# ---------------------------------------------------------------- append / read
class Refused(Exception):
    """Typed refusal of an event; message names the broken term."""


def read(path=None) -> list[dict]:
    p = store_path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _dial(name, default):
    """Policy dial via dials.py (B5); falls back to the OPEN.md default while dials.py is absent."""
    try:
        from . import dials
        return getattr(dials, name)()
    except (ImportError, AttributeError):
        return default


_DIMS_PIN = ("brand", "client", "entity", "prio", "coord", "site", "state", "sub", "trade",
             "wotype")


def _dims():
    try:
        from . import align
        return list(align.DIMS)
    except Exception:
        return list(_DIMS_PIN)


ROLES = ("super_user", "entity_lead", "team_lead", "coordinator", "provider_ops")
LINK_KINDS = ("change_order", "recall")
_LINK_WO_KIND = {"change_order": "change_order_wo", "recall": "recall_wo"}
_BOOTSTRAP = ("person", "role_grant")


def can(state, person, action, entity=None, client=None) -> bool:
    """Role check: super_user all; entity_lead by entity; team_lead by client only."""
    who = next((x for x in state.get("people", []) if x["id"] == person), None)
    if who is None:
        return False
    if client and not entity:
        c = next((x for x in state.get("clients", []) if x["id"] == client), None)
        entity = c["entity"] if c else None
    for g in who["roles"]:
        if g["role"] == "super_user":
            return True
        if g["role"] == "entity_lead" and entity and g.get("entity") == entity:
            return True
        if g["role"] == "team_lead" and client and g.get("client") == client:
            return True
    return False


def missing_media(wo) -> list[str]:
    have = {m["type"] for v in wo.get("visits") or [wo["visit"]] for m in v["media"]}
    return [t for t in wo.get("required_media", []) if t not in have]


def _authz(state, avatar, kind, payload):
    if os.environ.get("PLAN_AUTHZ") != "1":
        return
    if kind in _BOOTSTRAP and not any(g["role"] == "super_user"
                                      for x in state.get("people", []) for g in x["roles"]):
        return
    if not can(state, avatar, kind, entity=payload.get("entity"), client=payload.get("client")):
        raise Refused(f"AUTHZ[{avatar},{kind}]")


def append(avatar: str, kind: str, payload: dict, path=None, now=None) -> dict:
    events = read(path)
    state = reduce(events)
    check(state, kind, payload)
    _authz(state, avatar, kind, payload)
    ev = {"seq": len(events) + 1, "ts": time.time() if now is None else now,
          "avatar": avatar, "kind": kind, "payload": payload}
    p = store_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(ev, sort_keys=True) + "\n")
    return ev


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def minutes(ts: float, base: float) -> int:
    return int(math.floor((ts - base) / 60))


def date_to_ts(d: str) -> float:
    return datetime.combine(date.fromisoformat(d), dtime.min).timestamp()


# ---------------------------------------------------------------- validation
def _names(state) -> set:
    names = set()
    for e in state.get("entities", []):
        names |= {e["id"], e["dba"]} | set(e.get("dbas", []))
        names |= {d["id"] for d in e["docs"]}
    for k in ("clients", "sites", "coordinators", "providers", "work_orders", "people"):
        names |= {x["id"] for x in state.get(k, [])}
    for s in state.get("sites", []):
        names |= set(s["assets"])
    for p in state.get("providers", []):
        names |= {d["id"] for d in p["docs"]}
    for k in ("trades", "sub_trades", "states", "priorities"):
        names |= set(state.get(k, []))
    for w in state.get("work_orders", []):
        names |= {w["proposal"], w["invoice"], w["payout"]}
        for v in w.get("visits") or [w["visit"]]:
            names |= {v["id"]} | {m["id"] for m in v["media"]}
    return names


def _need(payload, *keys):
    for k in keys:
        if payload.get(k) in (None, "", []):
            raise Refused(f"MISSING[{k}]")


def _find(state, coll, ident, what):
    for x in state.get(coll, []):
        if x["id"] == ident:
            return x
    raise Refused(f"UNKNOWN[{what}:{ident}]")


def _fresh(state, name):
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise Refused(f"BAD_NAME[{name!r}] (lowercase letter first, then a-z 0-9 _)")
    if name in _names(state):
        raise Refused(f"DUPLICATE[{name}]")


def _resolve_entity(state, p):
    """Entity a payload refers to: explicit p['entity'], else the sole entity; else MISSING."""
    ents = state.get("entities", [])
    if p.get("entity"):
        return _find(state, "entities", p["entity"], "entity")
    if len(ents) == 1:
        return ents[0]
    raise Refused("MISSING[entity]")


def _entity_of_client(state, cid):
    return next(c for c in state["clients"] if c["id"] == cid)["entity"]


def entity_of(state, wo):
    """Entity id owning a work order (dict or id)."""
    if isinstance(wo, str):
        wo = next(w for w in state["work_orders"] if w["id"] == wo)
    return wo["entity"]


def slice_state(state, wo):
    """State restricted to the one entity owning `wo`, with state['entity'] bound to it."""
    if "entities" not in state:  # hand-written single-entity JSON states (cli examples)
        return state
    eid = entity_of(state, wo)
    ent = next(e for e in state["entities"] if e["id"] == eid)
    sliced = {**state, "entity": ent}
    for k in ("clients", "sites", "providers", "work_orders"):
        sliced[k] = [x for x in state[k] if x["entity"] == eid]
    return sliced


OBSERVATIONS = ("plan_dispatched", "plan_closed", "ledger_settled", "territory_flag",
                "sales_rep_notified")


def check(state, kind, p):
    if kind == "entity":
        _need(p, "name", "dba")
        _fresh(state, p["name"])
        if p["dba"] == p["name"]:
            raise Refused(f"DUPLICATE[{p['dba']}]")
        _fresh(state, p["dba"])
        extras = list(p.get("dbas") or [])
        if len(set(extras)) != len(extras) or {p["name"], p["dba"]} & set(extras):
            raise Refused("DUPLICATE[dbas]")
        for d in extras:
            _fresh(state, d)
        if p.get("parent_entity"):
            _find(state, "entities", p["parent_entity"], "entity")
        return
    if kind not in ("taxonomy", "entity", "person") and not state.get("entities"):
        raise Refused("MISSING[entity]")
    if kind == "entity_dba":
        if _dial("entity_dba_model", "entity_dba_on_one_entity") != "entity_dba_on_one_entity":
            raise Refused("UNKNOWN_KIND[entity_dba]")
        _need(p, "entity", "dba")
        _find(state, "entities", p["entity"], "entity")
        _fresh(state, p["dba"])
        return
    if kind in ("entity_doc", "templates_bound", "client", "provider"):
        _resolve_entity(state, p)
    if kind == "entity_doc":
        _need(p, "doc_type", "name")
        if p["doc_type"] not in subtypes("doc_slot"):
            raise Refused(f"BAD_TYPE[{p['doc_type']}]")
        _fresh(state, p["name"])
    elif kind == "templates_bound":
        pass
    elif kind == "taxonomy":
        _need(p, "type", "name")
        if p["type"] not in subtypes("taxonomy"):
            raise Refused(f"BAD_TYPE[{p['type']}]")
        _fresh(state, p["name"])
    elif kind == "client":
        _need(p, "name", "kind")
        if p["kind"] not in subtypes("client"):
            raise Refused(f"BAD_TYPE[{p['kind']}]")
        secondary = p["kind"] == "secondary_client"
        if secondary and not p.get("parent"):
            raise Refused(f"NO_PARENT[{p['name']}]")
        if p.get("quick_add") and (secondary or p.get("parent")):
            raise Refused(f"QUICK_ADD_SECONDARY[{p['name']}]")
        if p.get("parent"):
            par = _find(state, "clients", p["parent"], "client")
            if par["entity"] != _resolve_entity(state, p)["id"]:
                raise Refused("ENTITY_MISMATCH[client]")
        if p.get("delivery_mode") and p["delivery_mode"] not in domain_constants("delivery_channel"):
            raise Refused(f"BAD_CHANNEL[{p['delivery_mode']}]")
        _fresh(state, p["name"])
    elif kind == "client_rate":
        _need(p, "client", "trade", "cents")
        _find(state, "clients", p["client"], "client")
        if p["trade"] not in state.get("trades", []):
            raise Refused(f"UNKNOWN[trade:{p['trade']}]")
    elif kind == "site":
        _need(p, "name", "client", "state", "territory_client")
        _find(state, "clients", p["client"], "client")
        _find(state, "clients", p["territory_client"], "client")
        if _entity_of_client(state, p["client"]) != _entity_of_client(state, p["territory_client"]):
            raise Refused("ENTITY_MISMATCH[territory_client]")
        if p["state"] not in state.get("states", []):
            raise Refused(f"UNKNOWN[state:{p['state']}]")
        _fresh(state, p["name"])
    elif kind == "asset":
        _need(p, "name", "site")
        _find(state, "sites", p["site"], "site")
        _fresh(state, p["name"])
    elif kind == "coordinator":
        _need(p, "name")
        _fresh(state, p["name"])
    elif kind == "provider":
        _need(p, "name", "kind")
        if p["kind"] not in subtypes("provider"):
            raise Refused(f"BAD_TYPE[{p['kind']}]")
        _fresh(state, p["name"])
    elif kind == "provider_doc":
        _need(p, "provider", "doc_type", "name")
        _find(state, "providers", p["provider"], "provider")
        if p["doc_type"] not in subtypes("doc_slot"):
            raise Refused(f"BAD_TYPE[{p['doc_type']}]")
        if p.get("expiry_date"):
            date.fromisoformat(p["expiry_date"])
        _fresh(state, p["name"])
    elif kind in ("provider_approval", "provider_rate", "provider_rate_approved", "provider_rank"):
        _need(p, "provider", "trade")
        _find(state, "providers", p["provider"], "provider")
        if p["trade"] not in state.get("trades", []):
            raise Refused(f"UNKNOWN[trade:{p['trade']}]")
        if kind == "provider_approval":
            _need(p, "sub_trade")
            if p["sub_trade"] not in state.get("sub_trades", []):
                raise Refused(f"UNKNOWN[sub_trade:{p['sub_trade']}]")
        if kind == "provider_rate":
            _need(p, "cents")
        if kind == "provider_rank":
            _need(p, "rank")
            if not 1 <= int(p["rank"]) <= 20:
                raise Refused("RANGE[rank 1..20]")
    elif kind in ("provider_blacklist", "device_attested"):
        _need(p, "provider")
        _find(state, "providers", p["provider"], "provider")
    elif kind == "provider_filter":
        _need(p, "provider", "dim", "mode", "values")
        _find(state, "providers", p["provider"], "provider")
        if p["mode"] not in ("inc", "exc"):
            raise Refused("BAD_MODE")
        if p["dim"] not in _dims() and \
                _dial("provider_filter_validation", "strict") != "record_then_warn":
            raise Refused(f"BAD_DIM[{p['dim']}]")
    elif kind == "invoice_left_on_site":
        _need(p, "provider", "wo")
        _find(state, "providers", p["provider"], "provider")
        _find(state, "work_orders", p["wo"], "work_order")
    elif kind == "site_manager_clash":
        _need(p, "provider", "site")
        _find(state, "providers", p["provider"], "provider")
        _find(state, "sites", p["site"], "site")
    elif kind == "person":
        _need(p, "name")
        _fresh(state, p["name"])
    elif kind == "role_grant":
        _need(p, "person", "role")
        _find(state, "people", p["person"], "person")
        if p["role"] not in ROLES:
            raise Refused(f"BAD_ROLE[{p['role']}]")
        if p["role"] == "entity_lead":
            _need(p, "entity")
            _find(state, "entities", p["entity"], "entity")
        elif p["role"] == "team_lead":
            _need(p, "client")
            _find(state, "clients", p["client"], "client")
        else:
            if p.get("entity"):
                _find(state, "entities", p["entity"], "entity")
            if p.get("client"):
                _find(state, "clients", p["client"], "client")
    elif kind == "work_order":
        _need(p, "name", "kind", "wo_type", "client", "site", "trade", "sub_trade", "priority",
              "coordinator", "nte_cents", "onsite_sla_min", "complete_sla_min")
        if p["kind"] not in subtypes("work_order"):
            raise Refused(f"BAD_TYPE[{p['kind']}]")
        _find(state, "clients", p["client"], "client")
        site = _find(state, "sites", p["site"], "site")
        if site["entity"] != _entity_of_client(state, p["client"]):
            raise Refused("ENTITY_MISMATCH[site]")
        _find(state, "coordinators", p["coordinator"], "coordinator")
        for k, coll in (("trade", "trades"), ("sub_trade", "sub_trades"), ("priority", "priorities")):
            if p[k] not in state.get(coll, []):
                raise Refused(f"UNKNOWN[{k}:{p[k]}]")
        lk = p.get("link_kind")
        if lk or p.get("parent_wo"):
            if lk not in LINK_KINDS:
                raise Refused(f"BAD_LINK[link_kind]")
            _need(p, "parent_wo")
            par = _find(state, "work_orders", p["parent_wo"], "work_order")
            if par["entity"] != _entity_of_client(state, p["client"]):
                raise Refused("BAD_LINK[entity]")
            if par["client"] != p["client"]:
                raise Refused("BAD_LINK[client]")
            if par["site"] != p["site"]:
                raise Refused("BAD_LINK[site]")
            if lk == "change_order" and (par["id"], "ledger_settled") in state["observed"]:
                raise Refused("BAD_LINK[parent_settled]")
            if p["kind"] != _LINK_WO_KIND[lk]:
                raise Refused("BAD_LINK[kind]")
        if p.get("part_asset") and p["part_asset"] not in site["assets"]:
            raise Refused(f"UNKNOWN[asset:{p['part_asset']}]")
        if int(p["nte_cents"]) <= 0:
            raise Refused("RANGE[nte_cents>0]")
        _fresh(state, p["name"])
        for suffix in ("visit", "proposal", "invoice", "payout"):
            _fresh(state, f"{p['name']}_{suffix}")
    elif kind in ("territory_waiver", "required_media", "visit_open", "change_order_approved",
                  "nte_override_receipt", "dispatch_override"):
        _need(p, "wo")
        wo = _find(state, "work_orders", p["wo"], "work_order")
        if kind == "territory_waiver":
            _need(p, "authority")
        elif kind == "required_media":
            _need(p, "media_type")
            if p["media_type"] not in subtypes("media_artifact"):
                raise Refused(f"BAD_TYPE[{p['media_type']}]")
        elif kind == "visit_open":
            if wo["visit"]["checkout_ts"] is None:
                raise Refused("STAGE[visit open]")
            _fresh(state, f"{wo['id']}_visit{len(wo['visits']) + 1}")
        elif kind == "change_order_approved":
            _need(p, "new_nte_cents", "authority")
            if int(p["new_nte_cents"]) <= wo["nte_limit"]:
                raise Refused("RANGE[new_nte_cents>nte]")
        elif kind == "nte_override_receipt":
            _need(p, "id", "reason")
        else:
            _need(p, "provider", "authority", "reason")
            _find(state, "providers", p["provider"], "provider")
            if wo.get("dispatch_override"):
                raise Refused(f"DUPLICATE[dispatch_override:{wo['id']}]")
    elif kind in ("dispatch", "geofence_attest", "checkin", "checkout", "media",
                  "proposal_quote", "client_attest"):
        _need(p, "wo")
        wo = _find(state, "work_orders", p["wo"], "work_order")
        v = wo["visit"]
        if kind == "dispatch":
            _need(p, "provider")
            prv = _find(state, "providers", p["provider"], "provider")
            if prv["entity"] != wo["entity"]:
                raise Refused("ENTITY_MISMATCH[provider]")
            if wo["stage"] != "intake":
                raise Refused(f"STAGE[{wo['stage']} != intake]")
            if wo.get("parent_wo") and wo.get("link_kind") == "change_order" and \
                    _dial("change_order_parent_wait", "independent") == "wait_for_parent" and \
                    (wo["parent_wo"], "ledger_settled") not in state["observed"]:
                raise Refused("STAGE[parent not settled]")
        elif kind == "geofence_attest":
            if not v.get("provider"):
                raise Refused("MISSING[dispatch]")
        elif kind == "checkin":
            if wo["stage"] != "dispatched":
                raise Refused(f"STAGE[{wo['stage']} != dispatched]")
        elif kind == "checkout":
            if wo["stage"] != "on-site":
                raise Refused(f"STAGE[{wo['stage']} != on-site]")
            if _dial("media_prompt_mode", "soft_only") == "hard_refuse" and missing_media(wo):
                raise Refused(f"MISSING_MEDIA[{','.join(missing_media(wo))}]")
        elif kind == "media":
            _need(p, "media_type", "name", "sha256")
            if p["media_type"] not in subtypes("media_artifact"):
                raise Refused(f"BAD_TYPE[{p['media_type']}]")
            _fresh(state, p["name"])
        else:
            _need(p, "minutes")
            if int(p["minutes"]) <= 0:
                raise Refused("RANGE[minutes>0]")
    elif kind in OBSERVATIONS:
        _need(p, "wo")
        wo = _find(state, "work_orders", p["wo"], "work_order")
        if (p["wo"], kind) in state.get("observed", set()):
            raise Refused(f"DUPLICATE[{kind}:{p['wo']}]")
        if kind in ("territory_flag", "sales_rep_notified"):
            _need(p, "client")
            if kind == "territory_flag":
                _need(p, "site")
            elif (p["wo"], "territory_flag") not in state.get("observed", set()):
                raise Refused("MISSING[territory_flag]")
        elif kind == "ledger_settled":
            _need(p, "ledger_sha256")
            if (p["wo"], "plan_closed") not in state.get("observed", set()):
                raise Refused("MISSING[plan_closed]")
        else:
            _need(p, "goal", "planner_rc", "plan_sha256")
            want = "intake" if kind == "plan_dispatched" else "qa-review"
            if wo["stage"] != want:
                raise Refused(f"STAGE[{wo['stage']} != {want}]")
    else:
        raise Refused(f"UNKNOWN_KIND[{kind}]")


# ---------------------------------------------------------------- reducer
def reduce(events: list[dict]) -> dict:
    """events -> state in the pipeline schema plus per-WO stage and visit events."""
    st = {"clients": [], "sites": [], "coordinators": [], "providers": [], "work_orders": [],
          "trades": [], "sub_trades": [], "states": [], "priorities": [], "clock": 0,
          "observed": set(), "entities": [], "people": [], "warnings": [], "waivers": {}}
    if not events:
        return st
    base = events[0]["ts"]
    st["base_ts"] = base
    st["clock"] = minutes(float(os.environ.get("PLAN_CLOCK_NOW") or time.time()), base)  # env pins the clock for replay
    st["last_event_ts"] = events[-1]["ts"]
    st["clock"] = max(st["clock"], minutes(st["last_event_ts"], base))  # never before last event

    def prov(i):
        return next(x for x in st["providers"] if x["id"] == i)

    def cli(i):
        return next(x for x in st["clients"] if x["id"] == i)

    def wo_(i):
        return next(x for x in st["work_orders"] if x["id"] == i)

    def ent_(p):
        if p.get("entity"):
            return next(x for x in st["entities"] if x["id"] == p["entity"])
        return st["entities"][0]

    for e in events:
        k, p, ts = e["kind"], e["payload"], e["ts"]
        if k == "entity":
            ent = {"id": p["name"], "dba": p["dba"],
                   "dbas": [p["dba"]] + list(p.get("dbas") or []), "docs": [],
                   "templates_bound": False}
            if p.get("parent_entity"):
                ent["parent_entity"] = p["parent_entity"]
            st["entities"].append(ent)
        elif k == "entity_dba":
            next(x for x in st["entities"] if x["id"] == p["entity"])["dbas"].append(p["dba"])
        elif k == "entity_doc":
            ent_(p)["docs"].append({"id": p["name"], "type": p["doc_type"]})
        elif k == "templates_bound":
            ent_(p)["templates_bound"] = True
        elif k == "taxonomy":
            key = {"trade": "trades", "sub_trade": "sub_trades",
                   "state_jurisdiction": "states", "priority_tier": "priorities"}[p["type"]]
            st[key].append(p["name"])
        elif k == "client":
            c = {"id": p["name"], "kind": p["kind"], "labor_rates": {}, "entity": ent_(p)["id"]}
            if p.get("parent"):
                c["contracted_through"] = p["parent"]
            c["quick_add"] = bool(p.get("quick_add"))
            if p.get("delivery_mode"):
                c["delivery_mode"] = p["delivery_mode"]
            if p.get("payment_terms_days") is not None:
                c["payment_terms_days"] = int(p["payment_terms_days"])
            st["clients"].append(c)
        elif k == "client_rate":
            cli(p["client"])["labor_rates"][p["trade"]] = int(p["cents"])
        elif k == "site":
            st["sites"].append({"id": p["name"], "client": p["client"], "state": p["state"],
                                "territory_client": p["territory_client"], "assets": [],
                                "entity": cli(p["client"])["entity"]})
        elif k == "asset":
            next(s for s in st["sites"] if s["id"] == p["site"])["assets"].append(p["name"])
        elif k == "coordinator":
            st["coordinators"].append({"id": p["name"], "active_load": 0})
        elif k == "provider":
            st["providers"].append({
                "id": p["name"], "kind": p["kind"], "device_attested": False, "docs": [],
                "trade_approvals": [], "rate_approved": [], "rates": {}, "dispatch_rank": {},
                "blacklisted": False, "filters": {}, "entity": ent_(p)["id"]})
        elif k == "provider_doc":
            d = {"id": p["name"], "type": p["doc_type"], "valid": bool(p.get("valid"))}
            if p.get("expiry_date"):
                d["expiry"] = minutes(date_to_ts(p["expiry_date"]), base)
            prov(p["provider"])["docs"].append(d)
        elif k == "provider_approval":
            prov(p["provider"])["trade_approvals"].append(
                {"trade": p["trade"], "sub_trade": p["sub_trade"]})
        elif k == "provider_rate":
            prov(p["provider"])["rates"][p["trade"]] = int(p["cents"])
        elif k == "provider_rate_approved":
            prov(p["provider"])["rate_approved"].append(p["trade"])
        elif k == "provider_rank":
            prov(p["provider"])["dispatch_rank"][p["trade"]] = int(p["rank"])
        elif k == "provider_blacklist":
            prov(p["provider"])["blacklisted"] = True
        elif k == "device_attested":
            prov(p["provider"])["device_attested"] = True
        elif k == "provider_filter":
            if p["dim"] in _dims():
                prov(p["provider"])["filters"].setdefault(
                    f"{p['mode']}_{p['dim']}", []).extend(p["values"])
            else:
                st["warnings"].append(f"BAD_DIM[{p['dim']}]")
        elif k == "invoice_left_on_site":
            prov(p["provider"])["blacklisted"] = True
        elif k == "site_manager_clash":
            prov(p["provider"])["filters"].setdefault("exc_site", []).append(p["site"])
        elif k == "person":
            st["people"].append({"id": p["name"], "roles": []})
        elif k == "role_grant":
            g = {"role": p["role"]}
            for f in ("entity", "client"):
                if p.get(f):
                    g[f] = p[f]
            next(x for x in st["people"] if x["id"] == p["person"])["roles"].append(g)
        elif k == "work_order":
            n = p["name"]
            v0 = {"id": f"{n}_visit", "provider": None, "geofence": False, "media": [],
                  "checkin_ts": None, "checkout_ts": None,
                  "quoted_min": None, "external_min": None}
            wo = {
                "id": n, "entity": cli(p["client"])["entity"], "kind": p["kind"], "wo_type": p["wo_type"], "client": p["client"],
                "site": p["site"], "trade": p["trade"], "sub_trade": p["sub_trade"],
                "priority": p["priority"], "coordinator": p["coordinator"],
                "requires_part_replacement": p.get("part_asset"),
                "nte_limit": int(p["nte_cents"]),
                "created_min": minutes(ts, base),
                "onsite_sla_min": int(p["onsite_sla_min"]),
                "complete_sla_min": int(p["complete_sla_min"]),
                "proposal": f"{n}_proposal", "invoice": f"{n}_invoice", "payout": f"{n}_payout",
                "stage": "intake", "required_media": [],
                "visit": v0, "visits": [v0]}
            if p.get("link_kind"):
                wo["link_kind"], wo["parent_wo"] = p["link_kind"], p["parent_wo"]
            st["work_orders"].append(wo)
            next(c for c in st["coordinators"] if c["id"] == p["coordinator"])["active_load"] += 1
        elif k in OBSERVATIONS:
            st["observed"].add((p["wo"], k))  # observation only; never alters stage
        elif k == "territory_waiver":
            st["observed"].add((p["wo"], k))
            st["waivers"][p["wo"]] = p["authority"]
        else:
            w = wo_(p["wo"])
            v = w["visit"]
            if k == "visit_open":
                nv = {"id": f"{w['id']}_visit{len(w['visits']) + 1}", "provider": None,
                      "geofence": False, "media": [], "checkin_ts": None, "checkout_ts": None,
                      "quoted_min": None, "external_min": None}
                w["visits"].append(nv)
                w["visit"] = nv
                w["stage"] = "intake"
            elif k == "required_media":
                w["required_media"].append(p["media_type"])
            elif k == "change_order_approved":
                w["change_order"] = {"approved": True,
                                     "new_nte_limit_cents": int(p["new_nte_cents"])}
            elif k == "nte_override_receipt":
                w["override_receipt"] = {"id": p["id"], "reason": p["reason"]}
            elif k == "dispatch_override":
                w["dispatch_override"] = {"provider": p["provider"], "authority": p["authority"],
                                          "reason": p["reason"]}
            elif k == "dispatch":
                v["provider"] = p["provider"]
                w["stage"] = "dispatched"
            elif k == "geofence_attest":
                v["geofence"] = True
            elif k == "checkin":
                v["checkin_ts"] = ts
                w["stage"] = "on-site"
            elif k == "checkout":
                v["checkout_ts"] = ts
                w["stage"] = "qa-review"
            elif k == "media":
                v["media"].append({"id": p["name"], "type": p["media_type"],
                                   "sha256": p["sha256"], "captured": True})
            elif k == "proposal_quote":
                v["quoted_min"] = int(p["minutes"])
            elif k == "client_attest":
                v["external_min"] = int(p["minutes"])
    if len(st["entities"]) == 1:  # derived single view; absent when 0 or >1 entities
        st["entity"] = st["entities"][0]
    return st
