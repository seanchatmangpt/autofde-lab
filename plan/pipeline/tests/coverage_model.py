"""Pure-Python gate-order oracle over the collapsed factor space.

Gate order: store -> territory -> eligibility(empty set) -> dispatch retries -> stage-2 ->
ledger -> SETTLED. Truncation at stage k yields INCOMPLETE(stage) when nothing refused earlier."""
import itertools
import math
import tomllib
from pathlib import Path

from enterprise_pipeline import store

HERE = Path(__file__).resolve().parent
CFG = tomllib.loads((HERE / "coverage_factors.toml").read_text())
STAGES = CFG["stages"]["order"]
N, R = CFG["names"], CFG["rates"]


def main_levels() -> dict:
    m = CFG["main"]
    return {"wo_kind": store.subtypes(CFG["domain"]["wo_root"]), "part": m["part"], "docs": m["docs"],
            "site_filter": m["site_filter"], "territory": m["territory"], "nte": m["nte"],
            "attest": m["attest"], "provider_count": m["provider_count"],
            "truncation": list(range(len(STAGES)))}


def side_levels() -> dict:
    s = CFG["side"]
    return {"client_kind": s["client_kind"], "provider_kind": s["provider_kind"],
            "blacklist": s["blacklist"], "nte": s["nte"], "provider_count": s["provider_count"]}


def _cells(levels: dict):
    keys = list(levels)
    for combo in itertools.product(*levels.values()):
        yield dict(zip(keys, combo))


def main_cells():
    for c in _cells(main_levels()):
        yield {**CFG["defaults"], **c, "retries": c["provider_count"] - 1}


def main_count() -> int:
    return math.prod(len(v) for v in main_levels().values())


def side_cells():
    """(provider_count, retries 0..count-1) pairs crossed with the other side factors."""
    lv = side_levels()
    pcs = lv.pop("provider_count")
    for c in _cells(lv):
        for pc in pcs:
            for r in range(pc):
                yield {**CFG["defaults"], "wo_kind": store.subtypes(CFG["domain"]["wo_root"])[0],
                       "part": "no_part", "docs": "ok", "site_filter": "none", "territory": "in",
                       "attest": "match", "truncation": len(STAGES) - 1, **c,
                       "provider_count": pc, "retries": r}


# ---------------------------------------------------------------- money
def attest_minutes(c) -> int:
    return R["attest_minutes"]


def quote_minutes(c) -> int:
    return R["attest_minutes"] if c["attest"] == "match" else R["mismatch_quote_minutes"]


def charge_cents(c) -> int:
    return -(-attest_minutes(c) * R["client_cents_per_hour"] // 60)


def provider_cost_cents(c) -> int:
    return -(-attest_minutes(c) * R["provider_cents_per_hour"] // 60)


def nte_cents(c) -> int:
    lvl = c["nte"]
    if lvl == "ample":
        return charge_cents(c) * R["ample_multiplier"]
    if lvl == "between_provider_rate_and_charge":
        return charge_cents(c) - 1
    if lvl == "below_provider_rate":
        return provider_cost_cents(c) - 1
    return 0  # nonpositive (side sweep)


# ---------------------------------------------------------------- store events
def _provider_names(c):
    return [f"{N['provider_prefix']}{i}" for i in range(c["provider_count"])]


def base_events():
    return [("entity", {"name": N["entity"], "dba": N["dba"]}),
            ("taxonomy", {"type": "trade", "name": N["trade"]}),
            ("taxonomy", {"type": "sub_trade", "name": N["sub_trade"]}),
            ("taxonomy", {"type": "state_jurisdiction", "name": N["state"]}),
            ("taxonomy", {"type": "priority_tier", "name": N["priority"]}),
            ("coordinator", {"name": N["coordinator"]})]


def _kind(c, key):
    return N["bad_kind"] if c[key] == "bad_kind" else c[key]


def cell_events(c) -> list:
    ev = [("client", {"name": N["client"], "kind": _kind(c, "client_kind")}),
          ("client", {"name": N["other_client"], "kind": CFG["defaults"]["client_kind"]}),
          ("client_rate", {"client": N["client"], "trade": N["trade"], "cents": R["client_cents_per_hour"]}),
          ("site", {"name": N["site"], "client": N["client"], "state": N["state"],
                    "territory_client": N["client"] if c["territory"] == "in" else N["other_client"]})]
    part = c["part"] != "no_part"
    if part:
        ev.append(("asset", {"name": N["asset"], "site": N["site"]}))
    d = CFG["docs"]
    for p in _provider_names(c):
        ev.append(("provider", {"name": p, "kind": _kind(c, "provider_kind")}))
        for t in d["types"]:
            expired = (c["docs"] == "coi_expired" and t == d["coi_type"]) or \
                      (c["docs"] == "license_expired" and t == d["license_type"])
            ev.append(("provider_doc", {
                "provider": p, "doc_type": t, "name": f"{p}_{t}",
                "valid": not (c["docs"] == "doc_invalid" and t == d["doc_invalid_type"]),
                "expiry_date": d["expired_date"] if expired else d["future_date"]}))
        ev += [("provider_approval", {"provider": p, "trade": N["trade"], "sub_trade": N["sub_trade"]}),
               ("provider_rate_approved", {"provider": p, "trade": N["trade"]}),
               ("provider_rate", {"provider": p, "trade": N["trade"], "cents": R["provider_cents_per_hour"]}),
               ("provider_rank", {"provider": p, "trade": N["trade"], "rank": CFG["events"]["provider_rank"]})]
        f = c.get("site_filter", "none")
        if f != "none":
            mode = "exc" if f.startswith("exc") else "inc"
            val = N["other_site"] if f == "inc_miss" else N["site"]
            ev.append(("provider_filter", {"provider": p, "dim": "site", "mode": mode, "values": [val]}))
        if c.get("blacklist"):
            ev.append(("provider_blacklist", {"provider": p}))
    wo = {"name": N["wo"], "kind": c["wo_kind"], "wo_type": N["wo_type"], "client": N["client"],
          "site": N["site"], "trade": N["trade"], "sub_trade": N["sub_trade"],
          "priority": N["priority"], "coordinator": N["coordinator"], "nte_cents": nte_cents(c),
          "onsite_sla_min": CFG["events"]["onsite_sla_min"],
          "complete_sla_min": CFG["events"]["complete_sla_min"]}
    if part:
        wo["part_asset"] = N["asset"]
    ev.append(("work_order", wo))
    chosen = _provider_names(c)[min(c["retries"], c["provider_count"] - 1)]
    ev += [("dispatch", {"wo": N["wo"], "provider": chosen}),
           ("checkin", {"wo": N["wo"]}), ("checkout", {"wo": N["wo"]}),
           ("proposal_quote", {"wo": N["wo"], "minutes": quote_minutes(c)}),
           ("client_attest", {"wo": N["wo"], "minutes": attest_minutes(c)})]
    return ev


# ---------------------------------------------------------------- oracle gates
def gate_store(c):
    """Code (broken term) the store refuses with, or None. CURRENT behavior, see receipt KD rows."""
    if c["wo_kind"] not in store.subtypes(CFG["domain"]["wo_root"]):
        return "BAD_TYPE"
    if c.get("client_kind") == "bad_kind":
        return "BAD_TYPE"
    if c.get("provider_kind") == "bad_kind":
        return "BAD_TYPE"
    if nte_cents(c) <= 0:
        return "RANGE"
    return None


def gate_territory(c):
    return "OUT_OF_TERRITORY" if c["territory"] == "out" else None


def eligible(c) -> bool:
    return not (c["docs"] != "ok" or c["site_filter"] in ("exc_hit", "inc_miss") or c.get("blacklist"))


def gate_eligibility(c):
    return None if eligible(c) else "EMPTY_ELIGIBLE_SET"


def gate_dispatch(c):
    return "DISPATCH_EXHAUSTED" if c["retries"] >= c["provider_count"] else None


def gate_stage2(c):
    if c["attest"] != "match":
        return "ATTEST_QUOTE_MISMATCH"
    if c["part"] == "part_tag":
        return "PART_TAG_WITHHELD"
    return None


def gate_ledger(c):
    return "NTE_CAP" if nte_cents(c) < charge_cents(c) else None


GATES = {"store": gate_store, "territory": gate_territory, "eligibility": gate_eligibility,
         "dispatch": gate_dispatch, "stage2": gate_stage2, "ledger": gate_ledger}


def outcome(c):
    """-> ('REFUSED', stage, code) | ('INCOMPLETE', stage, None) | ('SETTLED', None, None)."""
    last = c.get("truncation", len(STAGES) - 1)
    for i, s in enumerate(STAGES):
        if i > last:
            break
        code = GATES[s](c)
        if code:
            return ("REFUSED", s, code)
    if last < len(STAGES) - 1:
        return ("INCOMPLETE", STAGES[last], None)
    return ("SETTLED", None, None)
