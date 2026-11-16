import json, unittest
from gen_problem import gen, to_pddl
from sweep_scheduler import solve

def check(inst, r):
    jobs = {j["id"]: j for j in inst["jobs"]}
    seen = {}
    for s in r["schedule"]:
        j = jobs[s["job"]]; seen[s["job"]] = seen.get(s["job"], 0) + 1
        assert j["open"] <= s["day"] <= j["close"], ("window violated", s)
        p = next(p for p in inst["providers"] if p["id"] == s["provider"])
        assert s["day"] not in p["blackout"] and s["day"] not in inst["global_blackout"], ("blackout", s)
    assert set(seen) == set(jobs) and all(v == 1 for v in seen.values()), "coverage"
    per = {}
    for s in r["schedule"]: per[s["provider"], s["day"]] = per.get((s["provider"], s["day"]), 0) + 1
    for (pid, d), n in per.items():
        assert n <= next(p for p in inst["providers"] if p["id"] == pid)["capacity"], "capacity"

class T(unittest.TestCase):
    def inst(self, **k):
        a = dict(n_assets=6, cadences=["weekly", "monthly", "quarterly", "annual"], horizon=120,
                 n_providers=2, n_sites=3, capacity=4, blackouts={"all": [5, 6, 12, 13], 0: [20, 21]})
        a.update(k); return gen(**a)
    def test_windows_coverage_capacity_blackout(self):
        i = self.inst(); r = solve(i); self.assertIn(r["status"], ("OPTIMAL", "FEASIBLE")); check(i, r)
    def test_all_cadences_present(self):
        self.assertEqual({j["cadence"] for j in self.inst()["jobs"]}, {"weekly", "monthly", "quarterly", "annual"})
    def test_infeasible_capacity_typed(self):
        i = self.inst(capacity=0); self.assertEqual(solve(i)["status"], "INFEASIBLE")
    def test_infeasible_blackout_covers_window(self):
        i = self.inst(blackouts={"all": list(range(0, 7))}); self.assertEqual(solve(i)["status"], "INFEASIBLE")
    def test_pddl_tils(self):
        t = to_pddl(self.inst()); self.assertIn("(at 7 (pm-window-open", t); self.assertIn("(not (pm-window-open", t)
if __name__ == "__main__": unittest.main()
