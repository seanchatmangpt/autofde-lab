"""Eligibility per (provider, work order) via the real MiniZinc alignment model."""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from . import store

HERE = Path(__file__).resolve().parent
MZN = HERE / "alignment_dispatch.mzn"
CPSAT_DIR = HERE.parents[1] / "cpsat"
CPSAT_RUN = CPSAT_DIR / "run.sh"
DIMS = ["brand", "client", "entity", "prio", "coord", "site", "state", "sub", "trade", "wotype"]
BIG = 2**30


class Skip(Exception):
    """Typed skip: a required external tool is absent."""

    def __init__(self, reason):
        super().__init__(f"[SKIP] {reason}")
        self.reason = reason


OPEN_DEFAULTS = {"document_expiry_enforcement": "veto_dispatch_when_expired"}


def dial(switch):
    """Policy switch via dials.py (never a literal); OPEN.md default if dials is not yet present."""
    try:
        from . import dials
    except ImportError:
        return OPEN_DEFAULTS[switch]
    return dials.get(switch)


def _doc_ok(p, dtype, clock):
    docs = [d for d in p["docs"] if d["type"] == dtype]
    # coi/license expiry always enforced; w9/contract per document_expiry_enforcement
    enforce = dtype in ("coi_doc", "license_doc") or dial("document_expiry_enforcement") == "veto_dispatch_when_expired"
    return bool(docs) and all(
        d.get("valid") and (not enforce or d.get("expiry") is None or d["expiry"] > clock) for d in docs)


def apply_override(state, wo, pmap, trigger):
    """dispatch_override permits a provider the court rejected (never a blacklisted one: howto playbook law)
    unless it has no valid W-9. -> (pmap, trigger)."""
    ov = wo.get("dispatch_override")
    if not ov:
        return pmap, trigger
    p = next((x for x in state["providers"] if x["id"] == ov.get("provider")), None)
    if p is None or p["id"] not in pmap:
        return pmap, trigger
    if p.get("blacklisted") or not any(d["type"] == "w9_doc" and d.get("valid") for d in p["docs"]):
        return pmap, trigger
    return {**pmap, p["id"]: True}, False


def desolate_market_count(state, wo):
    """Providers in this wo's market (approved for its trade/sub-trade, not blacklisted)."""
    _, provs = derive(state, wo)
    return sum(1 for p in provs if p["approved"] and not p["blacklisted"])


def is_desolate(state, wo):
    """Market desolate iff provider count < threshold (TOML switch clock_policy_auto)."""
    try:
        from . import dials
        thr = int(dials.param("clock_policy_auto", "desolate_market_provider_threshold"))
    except ImportError:
        return False
    return desolate_market_count(state, wo) < thr


def derive(state, wo):
    """Return (wo_vars, provider_vars) for one work order."""
    state = store.slice_state(state, wo)
    clock = state.get("clock", 0)
    site = next(s for s in state["sites"] if s["id"] == wo["site"])
    provs = []
    for p in state["providers"]:
        trade = wo["trade"]
        approved = ({"trade": trade, "sub_trade": wo["sub_trade"]} in p["trade_approvals"]
                    and trade in p.get("rate_approved", []))
        provs.append({
            "id": p["id"],
            "blacklisted": bool(p.get("blacklisted")),
            "aligned": _doc_ok(p, "w9_doc", clock) and _doc_ok(p, "contract_doc", clock),
            "approved": approved,
            "unexpired": _doc_ok(p, "coi_doc", clock) and _doc_ok(p, "license_doc", clock),
            "rank": p.get("dispatch_rank", {}).get(trade, 20),
            "rate": p.get("rates", {}).get(trade, BIG),
            "filters": p.get("filters", {}),
        })
    wov = {
        "brand": state["entity"]["dba"], "client": wo["client"], "entity": state["entity"]["id"],
        "prio": wo["priority"], "coord": wo["coordinator"], "site": wo["site"],
        "state": site["state"], "sub": wo["sub_trade"], "trade": wo["trade"],
        "wotype": wo["wo_type"], "nte": wo["nte_limit"],
    }
    return wov, provs


def _enum(name, values):
    return f"{name} = {{{', '.join(values)}}};\n"


def build_dzn(state, wo):
    state = store.slice_state(state, wo)
    wov, provs = derive(state, wo)
    ent = state["entity"]
    universe = {
        "PROVIDER": [p["id"] for p in provs],
        "BRAND": [ent["dba"]],
        "CLIENT": [c["id"] for c in state["clients"]],
        "ENTITY": [ent["id"]],
        "PRIORITY": state["priorities"],
        "COORDINATOR": [c["id"] for c in state["coordinators"]],
        "SITE": [s["id"] for s in state["sites"]],
        "STATE_JURISDICTION": state["states"],
        "SUB_TRADE": state["sub_trades"],
        "TRADE": state["trades"],
        "WO_TYPE": sorted({w["wo_type"] for w in state["work_orders"]}),
    }
    out = "".join(_enum(k, v) for k, v in universe.items())
    for key, name in [("brand", "wo_brand"), ("client", "wo_client"), ("entity", "wo_entity"),
                      ("prio", "wo_priority"), ("coord", "wo_coord"), ("site", "wo_site"),
                      ("state", "wo_state"), ("sub", "wo_sub_trade"), ("trade", "wo_trade"),
                      ("wotype", "wo_type")]:
        out += f"{name} = {wov[key]};\n"
    client = next(c for c in state["clients"] if c["id"] == wov["client"])
    billable = client.get("labor_rates", {}).get(wov["trade"], 0)
    out += f"wo_nte_cents = {wov['nte']};\nclient_billable_rate_cents = {billable};\n"
    b = lambda v: "true" if v else "false"
    out += "is_blacklisted = [%s];\n" % ", ".join(b(p["blacklisted"]) for p in provs)
    out += "is_entity_aligned = [%s];\n" % ", ".join(b(p["aligned"]) for p in provs)
    out += "trade_and_rate_approved = [%s];\n" % ", ".join(b(p["approved"]) for p in provs)
    out += "coi_and_license_unexpired = [%s];\n" % ", ".join(b(p["unexpired"]) for p in provs)
    out += "provider_trade_rank = [%s];\n" % ", ".join(str(p["rank"]) for p in provs)
    out += "provider_rate_cents = [%s];\n" % ", ".join(str(p["rate"]) for p in provs)
    for d in DIMS:
        for pre in ("inc", "exc"):
            sets = ["{%s}" % ", ".join(p["filters"].get(f"{pre}_{d}", [])) for p in provs]
            out += f"{pre}_{d} = [{', '.join(sets)}];\n"
    return out, [p["id"] for p in provs]


def run_minizinc(state, wo, timeout=60):
    dzn, ids = build_dzn(state, wo)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "wo.dzn"
        f.write_text(dzn)
        r = subprocess.run(["minizinc", "--output-mode", "json", str(MZN), str(f)],
                           capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "TMPDIR": tempfile.gettempdir()})
    if r.returncode != 0 or "eligible" not in r.stdout:
        raise RuntimeError(f"minizinc failed rc={r.returncode}: {r.stderr or r.stdout}")
    sol = json.loads(r.stdout.split("----------")[0])
    state = store.slice_state(state, wo)
    return apply_override(state, wo, dict(zip(ids, sol["eligible"])), bool(sol["trigger_reactive_hire"]))


CPSAT_KEY = {"prio": "priority", "coord": "coordinator", "sub": "sub_trade", "wotype": "wo_type"}


def cpsat_input(state, wo):
    state = store.slice_state(state, wo)
    wov, provs = derive(state, wo)
    client = next(c for c in state["clients"] if c["id"] == wo["client"])
    site = next(s for s in state["sites"] if s["id"] == wo["site"])
    plist = []
    for p in provs:
        inc, exc = {}, {}
        for d in DIMS:
            k = CPSAT_KEY.get(d, d)
            for pre, tgt in (("inc", inc), ("exc", exc)):
                if p["filters"].get(f"{pre}_{d}"):
                    tgt[k] = p["filters"][f"{pre}_{d}"]
        plist.append({"id": p["id"], "blacklisted": p["blacklisted"], "entity_aligned": p["aligned"],
                      "trade_and_rate_approved": p["approved"],
                      "coi_and_license_unexpired": p["unexpired"], "trade_rank": p["rank"],
                      "rate_cents": min(p["rate"], BIG), "inc": inc, "exc": exc})
    return {"work_order": {
        "brand": wov["brand"], "client": wov["client"], "entity": wov["entity"],
        "priority": wov["prio"], "coordinator": wov["coord"], "site": wov["site"],
        "state": site["state"], "sub_trade": wov["sub"], "trade": wov["trade"],
        "wo_type": wov["wotype"], "nte_cents": wov["nte"],
        "client_billable_rate_cents": client.get("labor_rates", {}).get(wo["trade"], BIG)},
        "providers": plist}


def _veto_matrix(inp):
    """Eligibility row per provider (declarative input to the cp kind): every veto must pass."""
    wo = inp["work_order"]
    def allowed(val, inc, exc):
        return val not in exc and (not inc or val in inc)
    rows = []
    for p in inp["providers"]:
        ok = (not p["blacklisted"] and p["entity_aligned"] and p["trade_and_rate_approved"]
              and p["coi_and_license_unexpired"] and p["rate_cents"] <= wo["nte_cents"]
              and p["rate_cents"] < wo["client_billable_rate_cents"])
        ok = ok and all(allowed(wo[d], p["inc"].get(d, []), p["exc"].get(d, []))
                        for d in ("brand", "client", "entity", "priority", "coordinator",
                                  "site", "state", "sub_trade", "trade", "wo_type"))
        rows.append(int(ok))
    return rows


def run_cpsat(state, wo, deadline_s=5.0):
    """K3 default: coprocessor 'cp' kind (assignment eligibility matrix + min-cost choice).
    PLAN_ORACLE=1 keeps the original servengine_cpsat subprocess as differential oracle."""
    if os.environ.get("PLAN_ORACLE") == "1":
        return run_cpsat_oracle(state, wo, deadline_s)
    from . import autofde_backend
    inp = cpsat_input(state, wo)
    elig = _veto_matrix(inp)
    n = len(elig)
    vs = {f"sel{i}": [0, elig[i]] for i in range(n)}
    vs["reactive"] = [0, 1]
    cons = [{"type": "linear", "terms": [[1, f"sel{i}"] for i in range(n)] + [[1, "reactive"]],
             "op": "==", "rhs": 1}]
    # reactive hire only when nobody is eligible
    cons.append({"type": "linear", "terms": [[1, "reactive"]], "op": "<=", "rhs": 1 - max(elig, default=0)})
    obj = [[(p["trade_rank"] * 100000 + p["rate_cents"]) * (n + 1) + i, f"sel{i}"]
           for i, p in enumerate(inp["providers"])] + [[99999999 * (n + 1), "reactive"]]
    r = autofde_backend.solve("cp", {"model": {"vars": vs, "constraints": cons,
                                               "objective": {"sense": "min", "terms": obj}}})
    if r.status != "PLAN" or not r.diagnostics.get("optimal"):
        raise RuntimeError(f"cp kind failed: {r.status} {r.diagnostics}")
    val = {a["var"]: a["value"] for a in r.actions}
    el = {p["id"] for p, e in zip(inp["providers"], elig) if e}
    state = store.slice_state(state, wo)
    return apply_override(state, wo, {p["id"]: p["id"] in el for p in inp["providers"]},
                          bool(val["reactive"]))


def run_cpsat_oracle(state, wo, deadline_s=5.0):
    """Bounded deadline poll for the cpsat venv; typed Skip if absent.

    Contract: `cd cpsat && .venv/bin/python -m servengine_cpsat < in.json` -> JSON with
    "eligible" (list of provider ids) and "trigger_reactive_hire".
    """
    py = CPSAT_DIR / ".venv/bin/python"
    end = time.monotonic() + deadline_s
    while not py.exists():
        if time.monotonic() >= end:
            raise Skip(f"cpsat CLI absent at {py} after {deadline_s}s deadline")
        time.sleep(0.1)  # SLEEP-CLASS: POLL-STEP (bounded by monotonic deadline)
    inp = cpsat_input(state, wo)
    r = subprocess.run([str(py), "-m", "servengine_cpsat"], input=json.dumps(inp), cwd=CPSAT_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"cpsat failed rc={r.returncode}: {r.stdout}{r.stderr}")
    out = json.loads(r.stdout)
    el = set(out["eligible"])
    state = store.slice_state(state, wo)
    return apply_override(state, wo, {p["id"]: p["id"] in el for p in inp["providers"]},
                          bool(out["trigger_reactive_hire"]))


def eligibility(state, backend="minizinc"):
    """-> {wo_id: ({provider: bool}, trigger_reactive_hire)}"""
    fn = run_minizinc if backend == "minizinc" else run_cpsat
    return {wo["id"]: fn(state, wo) for wo in state["work_orders"]}
