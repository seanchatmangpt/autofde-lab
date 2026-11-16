#!/usr/bin/env python3
"""L8 mutation courts. Shim-court style: sha256 BASELINE -> baseline solve -> MUTATE (copy) ->
mutant outcome -> RESTORE byte-exact (sha256 verified). Never writes spec/.
Usage: court.py pddl | mzn | selfcheck | all
Env: COURT_PLANNER_WAIT_S (default 900) deadline for planner/run.sh to appear.
"""
import hashlib, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "courts"); WORK = os.path.join(HERE, "work")
DOM = os.path.join(ROOT, "spec/servengine_ideal_domain.pddl")
PROB = os.path.join(ROOT, "spec/problem_enterprise_ops.pddl")
RUN = os.path.join(HERE, "plan_arg.sh")  # arg-honouring shim over planner/plan.py
PLANNER_RUN = os.path.join(ROOT, "planner/run.sh")
REACH = os.path.join(HERE, "reach.py")

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def pick_backend():
    wait = float(os.environ.get("COURT_PLANNER_WAIT_S", "900"))
    dl = time.monotonic() + wait
    while True:
        if os.path.isfile(PLANNER_RUN) and os.access(os.path.join(ROOT, "planner/.venv/bin/python"), os.X_OK): return "planner"
        if time.monotonic() >= dl: break
        time.sleep(min(5, max(0.0, dl - time.monotonic())))  # SLEEP-CLASS: POLL-STEP
    print(f"[SKIP] planner/run.sh absent after {wait:.0f}s deadline; using STRIPS-RELAXATION "
          f"fallback courts/reach.py (UNSOLVABLE sound, SOLVABLE only relaxed-reachable)")
    return "reach"

def solve(backend, prob):
    """-> SOLVED | UNSOLVABLE | ERROR(detail)"""
    cmd = ["sh", RUN, DOM, prob] if backend == "planner" else ["python3", REACH, DOM, prob]
    try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired: return "ERROR(timeout)"
    full = (r.stdout + r.stderr).strip()
    st = re.search(r"search status: (\S+)", full)
    out = (f"[{st.group(1)}] " if st else "") + full.replace("\n", " | ")[-160:]
    if backend == "reach":
        return {0: "SOLVED", 2: "UNSOLVABLE"}.get(r.returncode, f"ERROR(rc={r.returncode} {out})")
    if r.returncode == 0 and not re.search(r"UNSOLVABLE|REFUSED|NO[ _-]PLAN", out, re.I): return "SOLVED"
    if r.returncode == 2 or re.search(r"UNSOLVABLE|REFUSED|NO[ _-]PLAN", out, re.I): return "UNSOLVABLE"
    return f"ERROR(rc={r.returncode} {out})"

# (id, invariant, [(regex-exact-line-substring, replacement)]) ; replacement None = delete line,
# "+after" adds a line after the matched line.
M = [
 (1, "provider-not-blacklisted", "(provider-onboarded prov_sean_hvac ent_national_hvac)", ("add", "    (provider-blacklisted prov_sean_hvac)")),
 (2, "coi-unexpired-at-clock", "(= (doc-expiry-time prov_sean_hvac doc_prov_coi) 525600)", ("sub", "(= (doc-expiry-time prov_sean_hvac doc_prov_coi) 5)")),
 (3, "model-tag-photo-if-part-replacement", "(media-captured vis_9001_01 pic_compressor_tag)", ("del", None)),
 (4, "device-integrity-attested", "(device-integrity-attested prov_sean_hvac)", ("del", None)),
 (5, "geofence-attested", "(geofence-attested vis_9001_01 prov_sean_hvac site_sbux_0094)", ("del", None)),
 (6, "wo-nte-limit-positive", "(= (wo-nte-limit wo_reactive_9001) 150000)", ("sub", "(= (wo-nte-limit wo_reactive_9001) 0)")),
 (7, "onsite-sla-not-before-dispatch-finish", "(= (wo-onsite-sla wo_reactive_9001) 1440)", ("sub", "(= (wo-onsite-sla wo_reactive_9001) 5)")),
 (8, "client-delivery-mode-bound", "(client-delivery-mode cli_facility_broker ch_portal_api)", ("del", None)),
 (9, "entity-templates-bound", "(entity-templates-bound ent_national_hvac)", ("del", None)),
 (10, "site-in-client-territory", "(site-in-territory site_sbux_0094 cli_facility_broker)", ("del", None)),
 (11, "external-duration-equals-quoted", "(= (external-client-duration vis_9001_01) 4)", ("sub", "(= (external-client-duration vis_9001_01) 5)")),
 (12, "eligible-for-wo", "(eligible-for-wo prov_sean_hvac wo_reactive_9001)", ("del", None)),
]

CLOCK = "(= (current-clock) 0)"  # M02/M07 also advance the clock to 10 (expiry 5 < clock; sla 5 < clock)

def mutate(text, needle, op, mid=0):
    if mid in (2, 7):
        text, err = mutate(text, CLOCK, ("sub", "(= (current-clock) 10)"))
        if err: return None, err
    lines = text.split("\n")
    idx = [i for i, l in enumerate(lines) if needle in l]
    if len(idx) != 1: return None, f"needle matched {len(idx)} lines: {needle}"
    i = idx[0]; kind, arg = op
    if kind == "del": del lines[i]
    elif kind == "add": lines.insert(i + 1, arg)
    else: lines[i] = lines[i].replace(needle, arg)
    return "\n".join(lines), None

def court_pddl():
    be = pick_backend(); fails = 0
    os.makedirs(WORK, exist_ok=True)
    spec_sha = sha(PROB); work = os.path.join(WORK, "problem.pddl")
    shutil.copyfile(PROB, work)
    print(f"BASELINE sha256={spec_sha[:16]} backend={be}")
    b = solve(be, work)
    print(f"BASELINE solve={b}")
    if b != "SOLVED":
        print("FAIL baseline does not solve: all courts invalid"); return len(M) + 1
    base_text = open(PROB).read()
    for mid, inv, needle, op in M:
        new, err = mutate(base_text, needle, op, mid)
        if err: print(f"FAIL M{mid:02d} [{inv}] mutation inapplicable: {err}"); fails += 1; continue
        open(work, "w").write(new)
        assert sha(work) != spec_sha
        out = solve(be, work)
        shutil.copyfile(PROB, work)  # RESTORE
        ok_restore = sha(work) == spec_sha
        verdict = "PASS" if (out == "UNSOLVABLE" and ok_restore) else "FAIL"
        if verdict == "FAIL": fails += 1
        print(f"{verdict} M{mid:02d} [{inv}] mutant={out} restore_sha_ok={ok_restore}")
    if sha(PROB) != spec_sha: print("FAIL spec problem changed during run"); fails += 1
    print(f"PDDL courts: {len(M)} mutants, fails={fails}, backend={be}")
    return fails

# ---- MiniZinc courts ----
import json
MODELS = [os.path.join(HERE, "mzn/alignment_dispatch.mzn"), os.path.join(HERE, "mzn/alignment_repaired.mzn")]
MZN = MODELS[0]; BASE = os.path.join(HERE, "mzn/baseline.dzn")

def mz(dzn):
    r = subprocess.run(["minizinc", "--solver", "gecode", MZN, dzn], capture_output=True, text=True, timeout=120)
    o = r.stdout
    j = [l for l in o.splitlines() if l.startswith("{")]
    if j and not r.returncode:
        d = json.loads(j[-1]); return (d["selected"] or "<>", d["trigger_reactive_hire"], "json")
    sp = re.search(r"selected_provider = (\w+|<>);", o); th = re.search(r"trigger_reactive_hire = (\w+);", o)
    el = re.search(r"eligible = \[(.*?)\];", o)
    if r.returncode or not (sp and th and el): return None
    return sp.group(1), th.group(1) == "true", el.group(1)

def arr_set(text, name, idx, val):
    m = re.search(rf"^{name} = \[(.*)\];$", text, re.M)
    if not m: return None
    items = re.findall(r"\{[^}]*\}|[^,\s\[\]]+", m.group(1)); items[idx] = val
    return text[:m.start()] + f"{name} = [{', '.join(items)}];" + text[m.end():]

def court_mzn():
    fails = 0; t = open(BASE).read(); bs = sha(BASE)
    base = mz(BASE); print(f"MZN BASELINE sha256={bs[:16]} result={base}")
    if not base or base[0] != "prov_sean_hvac" or base[1]:
        print("FAIL mzn baseline must select prov_sean_hvac"); return 99
    scal = lambda tx, n, v: re.sub(rf"^{n} = .*;$", f"{n} = {v};", tx, flags=re.M)
    cases = [
     ("V01 blacklisted", lambda x: arr_set(x, "is_blacklisted", 0, "true")),
     ("V02 coi/license expired", lambda x: arr_set(x, "coi_and_license_unexpired", 0, "false")),
     ("V03 rate>nte", lambda x: scal(x, "wo_nte_cents", 7000)),
     ("V04 not entity aligned", lambda x: arr_set(x, "is_entity_aligned", 0, "false")),
     ("V05 trade/rate unapproved", lambda x: arr_set(x, "trade_and_rate_approved", 0, "false")),
     ("V06 exc_brand excludes wo brand (exclusion beats inclusion)", lambda x: arr_set(x, "exc_brand", 0, "{B1}")),
     ("V07 inc_client excludes wo client", lambda x: arr_set(x, "inc_client", 0, "{C2}")),
    ]
    for name, f in cases:
        mt = f(t)
        if mt is None or mt == t: print(f"FAIL {name} mutation inapplicable"); fails += 1; continue
        p = os.path.join(WORK, "mut.dzn"); open(p, "w").write(mt); r = mz(p); os.remove(p)
        ok = r is not None and r[0] != "prov_sean_hvac" and not r[1] and (r[2] == "json" or r[2].split(",")[0].strip().endswith("false"))
        fails += 0 if ok else 1; print(f"{'PASS' if ok else 'FAIL'} {name} -> {r}")
    # all-veto: blacklist everyone -> reactive hire, no selection
    mt = re.sub(r"^is_blacklisted = .*;$", "is_blacklisted = [true, true, true];", t, flags=re.M)
    p = os.path.join(WORK, "mut.dzn"); open(p, "w").write(mt); r = mz(p); os.remove(p)
    ok = r is not None and r[0] == "<>" and r[1]
    fails += 0 if ok else 1; print(f"{'PASS' if ok else 'FAIL'} V08 all providers vetoed -> reactive hire {r}")
    if sha(BASE) != bs: print("FAIL baseline dzn changed"); fails += 1
    print(f"MZN courts: 8 mutants, fails={fails}"); return fails

def selfcheck():
    """non-vacuity: (a) identity mutant must SOLVE, (b) a corrupted restore must be detected,
    (c) a mutant that removes a NON-load-bearing fact must NOT flip (court can distinguish)."""
    be = pick_backend(); os.makedirs(WORK, exist_ok=True); f = 0
    w = os.path.join(WORK, "self.pddl"); shutil.copyfile(PROB, w)
    r = solve(be, w); ok = r == "SOLVED"; f += not ok; print(f"{'PASS' if ok else 'FAIL'} selfcheck identity -> {r}")
    open(w, "a").write("\n;corrupt\n"); ok = sha(w) != sha(PROB); f += not ok
    print(f"{'PASS' if ok else 'FAIL'} selfcheck corrupted-restore detected={ok}")
    new, e = mutate(open(PROB).read(), "(wo-priority wo_reactive_9001 prio_24h_urgent)", ("del", None))
    open(w, "w").write(new); r = solve(be, w)
    ok = r == "SOLVED"; f += not ok
    print(f"{'PASS' if ok else 'FAIL'} selfcheck non-load-bearing mutant still solves -> {r} (court is discriminating)")
    os.remove(w); return f

def court_mzn_all():
    global MZN
    tot = 0
    for m in MODELS:
        if not os.path.isfile(m): print(f"[SKIP] {m} missing"); continue
        MZN = m; print(f"== MZN model {os.path.basename(m)} sha256={sha(m)[:16]}"); tot += court_mzn()
    return tot

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    f = {"pddl": court_pddl, "mzn": court_mzn_all, "selfcheck": selfcheck}.get(m)
    tot = f() if f else court_pddl() + court_mzn_all() + selfcheck()
    print(f"TOTAL fails={tot}"); sys.exit(1 if tot else 0)
