#!/usr/bin/env python3
"""CP-SAT PM sweep scheduler. Exit 0 = FEASIBLE/OPTIMAL, 3 = typed INFEASIBLE."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))


def build_model(inst):
    """Declarative cp payload for the PM sweep (visit vars, window/blackout domains, capacity, cluster min)."""
    gb = set(inst.get("global_blackout", []))
    P = inst["providers"]; vars_ = {}; cons = []; byk = {}; infeasible = False
    for j in inst["jobs"]:
        names = []
        for pi, p in enumerate(P):
            bl = gb | set(p["blackout"])
            for d in range(j["open"], j["close"] + 1):
                if d in bl: continue
                n = f"x|{j['id']}|{pi}|{d}"; vars_[n] = [0, 1]; names.append(n)
                byk.setdefault((pi, d), []).append((j["id"], n))
        if names: cons.append({"type": "exactly_one", "vars": names})
        else: infeasible = True
    if infeasible: cons.append({"type": "infeasible"})
    jsite = {j["id"]: j["site"] for j in inst["jobs"]}; ys = []
    for (pi, d), items in byk.items():
        cons.append({"type": "linear", "terms": [[1, n] for _, n in items], "op": "<=", "rhs": P[pi]["capacity"]})
        for s in inst["sites"]:
            sv = [n for jid, n in items if jsite[jid] == s]
            if sv:
                y = f"y|{pi}|{d}|{s}"; vars_[y] = [0, 1]; ys.append(y)
                for n in sv: cons.append({"type": "implies", "a": n, "b": y})
    return {"vars": vars_, "constraints": cons, "objective": {"sense": "min", "terms": [[1, y] for y in ys]}}


def solve(inst, time_limit=30.0):
    """Default: coprocessor 'cp' kind. PLAN_ORACLE=1 -> original in-process CP-SAT (differential oracle)."""
    if os.environ.get("PLAN_ORACLE") == "1":
        return solve_oracle(inst, time_limit)
    from enterprise_pipeline.autofde_backend import solve as backend
    r = backend("cp", {"model": build_model(inst)}, options={"time_limit": time_limit}, timeout=time_limit + 120)
    if r.status == "INFEASIBLE":
        return {"status": "INFEASIBLE", "reason": "capacity/window/blackout constraints unsatisfiable"}
    if r.status != "PLAN":
        return {"status": "UNKNOWN", "reason": f"{r.status} {r.diagnostics}"}
    P = inst["providers"]; sched = []
    for a in r.actions:
        if a["value"] and a["var"].startswith("x|"):
            _, jid, pi, d = a["var"].split("|"); sched.append({"job": jid, "provider": P[int(pi)]["id"], "day": int(d)})
    return {"status": "OPTIMAL" if r.diagnostics.get("optimal") else "FEASIBLE", "clusters": int(r.cost),
            "schedule": sorted(sched, key=lambda s: (s["day"], s["provider"], s["job"]))}


def solve_oracle(inst, time_limit=30.0):
    from ortools.sat.python import cp_model
    m = cp_model.CpModel(); H = inst["horizon"]
    gb = set(inst.get("global_blackout", []))
    P = inst["providers"]; x = {}; cl = {}
    for j in inst["jobs"]:
        lits = []
        for pi, p in enumerate(P):
            bl = gb | set(p["blackout"])
            for d in range(j["open"], j["close"] + 1):
                if d in bl: continue
                x[j["id"], pi, d] = m.NewBoolVar(f"x_{j['id']}_{pi}_{d}"); lits.append(x[j["id"], pi, d])
        m.Add(sum(lits) == 1) if lits else m.AddBoolOr([])  # empty -> infeasible
    byk = {}
    for (jid, pi, d), v in x.items(): byk.setdefault((pi, d), []).append((jid, v))
    jsite = {j["id"]: j["site"] for j in inst["jobs"]}
    for (pi, d), items in byk.items():
        m.Add(sum(v for _, v in items) <= P[pi]["capacity"])
        for s in inst["sites"]:
            sv = [v for jid, v in items if jsite[jid] == s]
            if sv:
                y = m.NewBoolVar(f"y_{pi}_{d}_{s}"); cl[pi, d, s] = y
                for v in sv: m.AddImplication(v, y)
    m.Minimize(sum(cl.values()))
    sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = time_limit; sv.parameters.num_workers = 8
    st = sv.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "INFEASIBLE" if st == cp_model.INFEASIBLE else "UNKNOWN",
                "reason": "capacity/window/blackout constraints unsatisfiable"}
    sched = []
    for (jid, pi, d), v in x.items():
        if sv.Value(v): sched.append({"job": jid, "provider": P[pi]["id"], "day": d})
    return {"status": "OPTIMAL" if st == cp_model.OPTIMAL else "FEASIBLE",
            "clusters": int(sv.ObjectiveValue()), "schedule": sorted(sched, key=lambda s: (s["day"], s["provider"], s["job"]))}

if __name__ == "__main__":
    inst = json.load(open(sys.argv[1])); r = solve(inst)
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out: json.dump(r, open(out, "w"), indent=1)
    print(r["status"], r.get("clusters", ""), f"visits={len(r.get('schedule', []))}")
    sys.exit(0 if r["status"] in ("OPTIMAL", "FEASIBLE") else 3)
