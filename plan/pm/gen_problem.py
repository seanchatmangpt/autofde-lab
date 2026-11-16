#!/usr/bin/env python3
"""Problem generator: N assets x cadences -> instance dict, PDDL problem, JSON."""
import argparse, json, random, sys
CAD = {"weekly": 7, "monthly": 30, "quarterly": 90, "annual": 365}

def gen(n_assets, cadences, horizon, n_providers, n_sites, capacity, blackouts, seed=1):
    r = random.Random(seed)
    sites = [f"site{i}" for i in range(n_sites)]
    assets = [{"id": f"asset{i}", "site": sites[i % n_sites]} for i in range(n_assets)]
    provs = [{"id": f"prov{i}", "capacity": capacity,
              "blackout": sorted(blackouts.get(i, []))} for i in range(n_providers)]
    jobs = []
    for a in assets:
        for c in cadences:
            per = CAD[c]; off = r.randrange(0, 1) if c == "weekly" else 0
            k = 0
            while k * per + off < horizon:
                o = k * per + off; cl = min(o + per - 1, horizon - 1)
                jobs.append({"id": f"{a['id']}_{c}_{k}", "asset": a["id"], "site": a["site"],
                             "cadence": c, "open": o, "close": cl})
                k += 1
    return {"horizon": horizon, "sites": sites, "assets": assets, "providers": provs, "jobs": jobs,
            "global_blackout": sorted(blackouts.get("all", []))}

def to_pddl(inst, name="pm-sweep-1"):
    L = [f"(define (problem {name}) (:domain servengine-pm-sweep)", "  (:objects"]
    L.append("    " + " ".join(inst["sites"]) + " - site")
    L.append("    " + " ".join(a["id"] for a in inst["assets"]) + " - asset")
    L.append("    " + " ".join(p["id"] for p in inst["providers"]) + " - provider")
    L.append("    " + " ".join(sorted({j["cadence"] for j in inst["jobs"]})) + " - cadence")
    L.append("    " + " ".join(j["id"] for j in inst["jobs"]) + " - preventive_wo)")
    L.append("  (:init (= (visits-completed) 0)")
    for a in inst["assets"]: L.append(f"    (asset-at-site {a['id']} {a['site']})")
    for p in inst["providers"]:
        L.append(f"    (provider-free {p['id']}) (= (tech-capacity {p['id']}) {p['capacity'] * inst['horizon']})")
        for s in inst["sites"]: L.append(f"    (provider-covers-site {p['id']} {s})")
    for j in inst["jobs"]:
        L.append(f"    (pm-for-asset {j['id']} {j['asset']}) (pm-cadence {j['id']} {j['cadence']})"
                 f" (= (pm-duration {j['id']}) 1) (= (pm-sla-slack {j['id']}) {j['close']-j['open']})")
        if j["open"] > 0: L.append(f"    (at {j['open']} (pm-window-open {j['id']}))")
        else: L.append(f"    (pm-window-open {j['id']})")
        L.append(f"    (at {j['close'] + 1} (not (pm-window-open {j['id']})))")
        L.append(f"    (at {j['close'] + 1} (pm-window-closed {j['id']}))")
    L.append("  )")
    L.append("  (:goal (and " + " ".join(f"(pm-done {j['id']})" for j in inst["jobs"]) + ")))")
    return "\n".join(L) + "\n"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=int, default=6)
    ap.add_argument("--cadences", default="weekly,monthly,quarterly")
    ap.add_argument("--horizon", type=int, default=90)
    ap.add_argument("--providers", type=int, default=2)
    ap.add_argument("--sites", type=int, default=3)
    ap.add_argument("--capacity", type=int, default=4)
    ap.add_argument("--out", default="out/instance")
    a = ap.parse_args()
    inst = gen(a.assets, a.cadences.split(","), a.horizon, a.providers, a.sites, a.capacity,
               {"all": [5, 6, 12, 13]})
    import os; os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(inst, open(a.out + ".json", "w"), indent=1)
    open(a.out + ".pddl", "w").write(to_pddl(inst))
    print(f"jobs={len(inst['jobs'])} -> {a.out}.json {a.out}.pddl")
