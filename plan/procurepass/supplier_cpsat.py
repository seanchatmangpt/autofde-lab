#!/usr/bin/env python3
"""ProcurePass supplier/warehouse/delivery-slot chooser (OR-Tools CP-SAT). JSON in -> JSON out.

Times are integer minutes from WO start; money is integer cents.
Input: {sla_minutes, nte_limit, labor_cost, markup_pct, diagnose_minutes, install_minutes,
        order_delay_minutes, travel_minutes, options:[{supplier, warehouse, part_cost,
        ship_cost, lead_minutes, slots:[{start, fee}]}]}
Output: {status: OPTIMAL|INFEASIBLE, reason?, path: in_nte|change_order, ...}
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))

REQUIRED = ["sla_minutes", "nte_limit", "labor_cost", "markup_pct", "diagnose_minutes",
            "install_minutes", "travel_minutes", "options"]


def solve(req: dict) -> dict:
    """Default: coprocessor 'cp' kind. PLAN_ORACLE=1 -> original in-process CP-SAT."""
    if os.environ.get("PLAN_ORACLE") == "1":
        return solve_oracle(req)
    missing = [k for k in REQUIRED if k not in req]
    if missing:
        return {"status": "INVALID", "reason": "MISSING_FIELDS", "fields": missing}
    from enterprise_pipeline.autofde_backend import solve as backend
    ready = req["diagnose_minutes"] + req.get("order_delay_minutes", 0)
    cands = [(o, sl) for o in req["options"] for sl in o["slots"]]
    if not cands:
        return {"status": "INFEASIBLE", "reason": "NO_OPTIONS"}
    H = 10 ** 7
    vs = {"deliver": [0, H], "install_start": [0, H], "install_end": [0, H]}
    terms_d, obj, cost = [], [], []
    for i, (o, sl) in enumerate(cands):
        ok = sl["start"] >= ready + o["lead_minutes"]
        vs[f"b{i}"] = [0, 1 if ok else 0]
        part = o["part_cost"] * (100 + req["markup_pct"]) // 100
        c = part + o["ship_cost"] + sl.get("fee", 0)
        cost.append((c, part))
        terms_d.append([sl["start"], f"b{i}"])
        obj.append([c * 100000, f"b{i}"])
    obj.append([1, "install_end"])
    cons = [
        {"type": "exactly_one", "vars": [f"b{i}" for i in range(len(cands))]},
        {"type": "linear", "terms": [[1, "deliver"]] + [[-c, n] for c, n in terms_d], "op": "==", "rhs": 0},
        {"type": "linear", "terms": [[1, "install_start"], [-1, "deliver"]], "op": ">=", "rhs": 0},
        {"type": "linear", "terms": [[1, "install_start"]], "op": ">=", "rhs": ready + req["travel_minutes"]},
        {"type": "linear", "terms": [[1, "install_end"], [-1, "install_start"]], "op": "==", "rhs": req["install_minutes"]},
        {"type": "linear", "terms": [[1, "install_end"]], "op": "<=", "rhs": req["sla_minutes"]},
    ]
    r = backend("cp", {"model": {"vars": vs, "constraints": cons, "objective": {"sense": "min", "terms": obj}}})
    if r.status != "PLAN":
        earliest_any = min(ready + o["lead_minutes"] for o in req["options"])
        return {"status": "INFEASIBLE", "reason": "LEAD_TIME_EXCEEDS_SLA", "sla_minutes": req["sla_minutes"],
                "earliest_possible_completion": max(earliest_any, ready + req["travel_minutes"]) + req["install_minutes"]}
    val = {a["var"]: a["value"] for a in r.actions}
    i = next(i for i in range(len(cands)) if val[f"b{i}"])
    o, sl = cands[i]; c, part = cost[i]
    total = req["labor_cost"] + part
    over = total > req["nte_limit"]
    return {"status": "OPTIMAL", "supplier": o["supplier"], "warehouse": o["warehouse"],
            "delivery_slot_start": sl["start"], "install_start": val["install_start"],
            "install_end": val["install_end"], "procurement_cost": c, "proposal_total": total,
            "path": "change_order" if over else "in_nte", "change_order_required": over,
            "objective": int(r.cost)}


def solve_oracle(req: dict) -> dict:
    from ortools.sat.python import cp_model
    missing = [k for k in REQUIRED if k not in req]
    if missing:
        return {"status": "INVALID", "reason": "MISSING_FIELDS", "fields": missing}
    order_delay = req.get("order_delay_minutes", 0)
    diag_end = req["diagnose_minutes"]
    ready_to_return = diag_end + order_delay  # order placed after proposal; tech returns later
    m = cp_model.CpModel()
    horizon = 10 ** 7
    cands = []
    for o in req["options"]:
        for sl in o["slots"]:
            b = m.NewBoolVar(f"{o['supplier']}_{o['warehouse']}_{sl['start']}")
            part_total = o["part_cost"] * (100 + req["markup_pct"]) // 100
            cost = part_total + o["ship_cost"] + sl.get("fee", 0)
            earliest = ready_to_return + o["lead_minutes"]  # order, then lead time
            # slot must start no earlier than order+lead
            if sl["start"] < earliest:
                m.Add(b == 0)
            cands.append((b, o, sl, cost, part_total))
    if not cands:
        return {"status": "INFEASIBLE", "reason": "NO_OPTIONS"}
    m.Add(sum(c[0] for c in cands) == 1)
    deliver = m.NewIntVar(0, horizon, "deliver")
    for b, o, sl, _, _ in cands:
        m.Add(deliver == sl["start"]).OnlyEnforceIf(b)
    install_start = m.NewIntVar(0, horizon, "install_start")
    m.Add(install_start >= deliver)
    m.Add(install_start >= ready_to_return + req["travel_minutes"])
    install_end = m.NewIntVar(0, horizon, "install_end")
    m.Add(install_end == install_start + req["install_minutes"])
    m.Add(install_end <= req["sla_minutes"])
    total_cost = m.NewIntVar(0, horizon * 100, "cost")
    m.Add(total_cost == sum(c[3] * c[0] for c in cands))
    # primary objective cost, tie-break earliest completion
    m.Minimize(total_cost * 100000 + install_end)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.random_seed = 0
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        earliest_any = min(ready_to_return + o["lead_minutes"] for o in req["options"])
        return {"status": "INFEASIBLE", "reason": "LEAD_TIME_EXCEEDS_SLA",
                "sla_minutes": req["sla_minutes"],
                "earliest_possible_completion": max(earliest_any, ready_to_return + req["travel_minutes"])
                + req["install_minutes"]}
    for b, o, sl, cost, part_total in cands:
        if s.Value(b):
            proposal_total = req["labor_cost"] + part_total
            over = proposal_total > req["nte_limit"]
            return {"status": "OPTIMAL", "supplier": o["supplier"], "warehouse": o["warehouse"],
                    "delivery_slot_start": sl["start"], "install_start": s.Value(install_start),
                    "install_end": s.Value(install_end), "procurement_cost": cost,
                    "proposal_total": proposal_total,
                    "path": "change_order" if over else "in_nte",
                    "change_order_required": over}
    return {"status": "INVALID", "reason": "NO_SELECTION"}


if __name__ == "__main__":
    src = open(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else sys.stdin
    out = solve(json.load(src))
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["status"] == "OPTIMAL" else 2)
