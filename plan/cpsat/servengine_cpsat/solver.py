"""Native CP-SAT port of spec/alignment_dispatch.mzn (+ margin veto per lane contract)."""
from __future__ import annotations
from ortools.sat.python import cp_model

# dimension name -> (work-order field, provider inc key, provider exc key)
DIMS = ["brand", "client", "entity", "priority", "coordinator",
        "site", "state", "sub_trade", "trade", "wo_type"]
RANK_SCALE = 100000
NO_SELECTION_SCORE = 99999999


def dim_allowed(val, inc, exc) -> bool:
    return val not in set(exc) and (len(inc) == 0 or val in set(inc))


def _validate(inst: dict) -> None:
    wo = inst["work_order"]
    for d in DIMS:
        if not isinstance(wo[d], str):
            raise ValueError(f"work_order.{d} must be string")
    for k in ("nte_cents", "client_billable_rate_cents"):
        if not isinstance(wo[k], int) or isinstance(wo[k], bool):
            raise ValueError(f"work_order.{k} must be int")
    ids = set()
    for p in inst["providers"]:
        if p["id"] in ids:
            raise ValueError(f"duplicate provider id {p['id']}")
        ids.add(p["id"])
        if not 1 <= p["trade_rank"] <= 20:
            raise ValueError(f"{p['id']}: trade_rank outside 1..20")
        if not isinstance(p["rate_cents"], int) or p["rate_cents"] < 0:
            raise ValueError(f"{p['id']}: rate_cents must be non-negative int")


def vetoes(wo: dict, p: dict) -> dict:
    """Pure-python veto/dim evaluation (shared by oracle; solver feeds it into the model)."""
    inc, exc = p.get("inc", {}), p.get("exc", {})
    v = {
        "blacklist": not p["blacklisted"],
        "entity_alignment": p["entity_aligned"],
        "trade_rate_approval": p["trade_and_rate_approved"],
        "coi_license": p["coi_and_license_unexpired"],
        "nte": p["rate_cents"] <= wo["nte_cents"],
        "margin": p["rate_cents"] < wo["client_billable_rate_cents"],
    }
    for d in DIMS:
        v["dim_" + d] = dim_allowed(wo[d], inc.get(d, []), exc.get(d, []))
    return v


def oracle(inst: dict) -> dict:
    """Brute-force reference: lexicographic (rank, rate, input order)."""
    _validate(inst)
    wo = inst["work_order"]
    best = None
    elig = []
    for i, p in enumerate(inst["providers"]):
        if all(vetoes(wo, p).values()):
            elig.append(p["id"])
            key = (p["trade_rank"], p["rate_cents"], i)
            if best is None or key < best[0]:
                best = (key, p)
    if best is None:
        return {"selected_provider": None, "trigger_reactive_hire": True,
                "eligible": [], "objective_score": NO_SELECTION_SCORE}
    p = best[1]
    return {"selected_provider": p["id"], "trigger_reactive_hire": False, "eligible": elig,
            "objective_score": p["trade_rank"] * RANK_SCALE + p["rate_cents"]}


def solve(inst: dict) -> dict:
    _validate(inst)
    wo, provs = inst["work_order"], inst["providers"]
    n = len(provs)
    m = cp_model.CpModel()
    elig, sel, vetoed_by = [], [], []
    for i, p in enumerate(provs):
        checks = vetoes(wo, p)
        lits = []
        for name, ok in checks.items():
            b = m.NewBoolVar(f"{p['id']}_{name}")
            m.Add(b == int(ok))
            lits.append(b)
        e = m.NewBoolVar(f"elig_{i}")
        m.AddBoolAnd(lits).OnlyEnforceIf(e)
        m.AddBoolOr([l.Not() for l in lits]).OnlyEnforceIf(e.Not())
        elig.append(e)
        s = m.NewBoolVar(f"sel_{i}")
        m.AddImplication(s, e)
        sel.append(s)
        vetoed_by.append([k for k, ok in checks.items() if not ok])
    reactive = m.NewBoolVar("reactive")
    m.Add(sum(sel) + reactive == 1)
    # reactive hire iff nobody eligible
    m.AddBoolOr(elig).OnlyEnforceIf(reactive.Not())
    for e in elig:
        m.AddImplication(reactive, e.Not())
    # lexicographic: rank, rate, then input order (deterministic tiebreak)
    obj = sum(sel[i] * ((p["trade_rank"] * RANK_SCALE + p["rate_cents"]) * (n + 1) + i)
              for i, p in enumerate(provs))
    obj += reactive * NO_SELECTION_SCORE * (n + 1)
    m.Minimize(obj)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    status = solver.Solve(m)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(f"CP-SAT status {solver.StatusName(status)}")
    eligible = [provs[i]["id"] for i in range(n) if solver.Value(elig[i])]
    if solver.Value(reactive):
        chosen, score = None, NO_SELECTION_SCORE
    else:
        i = next(i for i in range(n) if solver.Value(sel[i]))
        chosen = provs[i]["id"]
        score = provs[i]["trade_rank"] * RANK_SCALE + provs[i]["rate_cents"]
    return {"selected_provider": chosen, "trigger_reactive_hire": bool(solver.Value(reactive)),
            "eligible": eligible, "objective_score": score,
            "vetoes": {provs[i]["id"]: vetoed_by[i] for i in range(n) if vetoed_by[i]}}
