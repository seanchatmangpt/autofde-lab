#!/usr/bin/env python3
"""Generates instances/*.dzn and expected.json (deterministic)."""
import json, os
D = [("brand","BRAND","brand","B"),("client","CLIENT","client","C"),("entity","ENTITY","entity","E"),
     ("prio","PRIORITY","priority","PR"),("coord","COORDINATOR","coord","CO"),("site","SITE","site","S"),
     ("state","STATE_JURISDICTION","state","ST"),("sub","SUB_TRADE","sub_trade","SU"),
     ("trade","TRADE","trade","T"),("wotype","WO_TYPE","type","W")]
ENUMS = {e: [f"{p}1", f"{p}2"] for _, e, _, p in D}
def inst(provs, nte=10000, bill=15000):
    names = [p["name"] for p in provs]
    o = ["PROVIDER = {%s};" % ", ".join(names)]
    for _, e, _, _ in D: o.append("%s = {%s};" % (e, ", ".join(ENUMS[e])))
    for _, e, w, p in D: o.append(f"wo_{w} = {p}1;")
    o += [f"wo_nte_cents = {nte};", f"client_billable_rate_cents = {bill};"]
    def arr(k, f): o.append("%s = [%s];" % (k, ", ".join(f(p) for p in provs)))
    for k, d in [("is_blacklisted",False),("is_entity_aligned",True),("trade_and_rate_approved",True),("coi_and_license_unexpired",True)]:
        arr(k, lambda p, k=k, d=d: str(p.get(k, d)).lower())
    arr("provider_trade_rank", lambda p: str(p["rank"]))
    arr("provider_rate_cents", lambda p: str(p.get("rate", 5000)))
    for s, e, _, pf in D:
        for kind in ("inc", "exc"):
            arr(f"{kind}_{s}", lambda p, s=s, kind=kind: "{" + ",".join(p.get(f"{kind}_{s}", [])) + "}")
    return "\n".join(o) + "\n"
cases = {}
def add(n, provs, exp, hire=False, **kw): cases[n] = (inst(provs, **kw), exp, hire)
add("a_canonical", [dict(name="prov_sean_hvac", rank=1, rate=7500, inc_brand=["B1"]),
    dict(name="prov_other_a", rank=2, rate=4000), dict(name="prov_other_b", rank=3, rate=3000)], "prov_sean_hvac")
for s, e, w, p in D:
    add(f"b_dim_{s}", [
      dict(name="p_empty", rank=5, **{}),
      dict(name="p_inc_ok", rank=4, **{f"inc_{s}": [f"{p}1"]}),
      dict(name="p_exc_beats_inc", rank=1, **{f"inc_{s}": [f"{p}1", f"{p}2"], f"exc_{s}": [f"{p}1"]}),
      dict(name="p_inc_miss", rank=2, **{f"inc_{s}": [f"{p}2"]}),
      dict(name="p_exc", rank=3, **{f"exc_{s}": [f"{p}1"]}),
      dict(name="p_exc_other", rank=6, **{f"exc_{s}": [f"{p}2"]})], "p_inc_ok")
add("b_exc_other_wins", [dict(name="p_a", rank=2, exc_brand=["B2"]), dict(name="p_b", rank=3)], "p_a")
add("b_tiebreak_rate", [dict(name="p_x", rank=2, rate=6000), dict(name="p_y", rank=2, rate=5000)], "p_y")
add("b_tiebreak_index", [dict(name="p_m", rank=2, rate=5000), dict(name="p_n", rank=2, rate=5000)], "p_m")
add("c_none_eligible", [dict(name="p1", rank=1, is_blacklisted=True), dict(name="p2", rank=2, exc_brand=["B1"]),
    dict(name="p3", rank=3, inc_site=["S2"]), dict(name="p4", rank=4, is_entity_aligned=False),
    dict(name="p5", rank=5, trade_and_rate_approved=False), dict(name="p6", rank=6, rate=20000)], None, True)
add("d_veto_blacklisted", [dict(name="p_bl", rank=1, is_blacklisted=True), dict(name="p_ok", rank=9)], "p_ok")
add("d_veto_coi", [dict(name="p_coi", rank=1, coi_and_license_unexpired=False), dict(name="p_ok", rank=9)], "p_ok")
add("d_veto_rate_gt_nte", [dict(name="p_hi", rank=1, rate=10001), dict(name="p_ok", rank=9)], "p_ok")
add("d_nte_boundary_equal_ok", [dict(name="p_eq", rank=1, rate=10000), dict(name="p_ok", rank=9)], "p_eq")
add("d_margin_guard", [dict(name="p_nomargin", rank=1, rate=9000), dict(name="p_ok", rank=9, rate=5000)], "p_ok", nte=10000, bill=9000)
add("d_margin_all_fail", [dict(name="p_eqbill", rank=1, rate=9000)], None, True, nte=10000, bill=9000)
os.makedirs("instances", exist_ok=True)
exp = {}
for n, (txt, sel, hire) in cases.items():
    open(f"instances/{n}.dzn", "w").write(txt); exp[n] = {"selected": sel, "trigger_reactive_hire": hire}
json.dump(exp, open("expected.json", "w"), indent=1, sort_keys=True)
print(len(cases), "instances")
