#!/usr/bin/env python3
"""Differential harness: CP-SAT vs MiniZinc over alignment/instances/*.dzn.
Waits (monotonic deadline) for instances; absent -> typed [SKIP], exit 3.
Per-instance subprocess timeout; verdict printed as each instance finishes.
Exit 0 all agree, 1 any disagree/error."""
import glob, json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PLAN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from servengine_cpsat import solve, DIMS  # noqa: E402

DEADLINE_S = float(os.environ.get("DIFF_WAIT_S", 600))
INST_TIMEOUT_S = float(os.environ.get("DIFF_INSTANCE_TIMEOUT_S", 60))
MZN = os.path.join(PLAN, "alignment", "alignment_dispatch.mzn")
PATTERNS = [os.path.join(PLAN, "alignment", "instances", "*.dzn"),
            os.path.join(PLAN, "alignment", "*.dzn")]
SETS = {"brand": "brand", "client": "client", "entity": "entity", "prio": "priority",
        "coord": "coordinator", "site": "site", "state": "state", "sub": "sub_trade",
        "trade": "trade", "wotype": "wo_type"}
WO = {"brand": "wo_brand", "client": "wo_client", "entity": "wo_entity", "priority": "wo_priority",
      "coordinator": "wo_coord", "site": "wo_site", "state": "wo_state",
      "sub_trade": "wo_sub_trade", "trade": "wo_trade", "wo_type": "wo_type"}

def parse_dzn(txt):
    txt = re.sub(r"%[^\n]*", "", txt)
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(\w+)\s*=\s*(.*?);", txt, re.S)}

def split_top(s):
    s = s.strip()
    if s.startswith("["): s = s[1:-1]
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "{[": depth += 1
        if ch in "}]": depth -= 1
        if ch == "," and depth == 0: out.append(cur.strip()); cur = ""
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out

def members(tok):
    return [x.strip() for x in tok.strip().strip("{}").split(",") if x.strip()]

def dzn_to_inst(v):
    provs = members(v["PROVIDER"])
    arr = lambda k: split_top(v[k])
    b = lambda k: [x == "true" for x in arr(k)]
    wo = {d: v[WO[d]].strip() for d in DIMS}
    wo["nte_cents"] = int(v["wo_nte_cents"]); wo["client_billable_rate_cents"] = int(v["client_billable_rate_cents"])
    bl, ea, ap, co = b("is_blacklisted"), b("is_entity_aligned"), b("trade_and_rate_approved"), b("coi_and_license_unexpired")
    rk = [int(x) for x in arr("provider_trade_rank")]; rt = [int(x) for x in arr("provider_rate_cents")]
    inc = {s: arr("inc_" + s) for s in SETS}; exc = {s: arr("exc_" + s) for s in SETS}
    return {"work_order": wo, "providers": [
        {"id": provs[i], "blacklisted": bl[i], "entity_aligned": ea[i], "trade_and_rate_approved": ap[i],
         "coi_and_license_unexpired": co[i], "trade_rank": rk[i], "rate_cents": rt[i],
         "inc": {SETS[s]: members(inc[s][i]) for s in SETS},
         "exc": {SETS[s]: members(exc[s][i]) for s in SETS}} for i in range(len(provs))]}

def run_mzn(f):
    r = subprocess.run(["minizinc", "--solver", "gecode", MZN, f],
                       capture_output=True, text=True, timeout=INST_TIMEOUT_S)
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise RuntimeError(f"no JSON line from minizinc rc={r.returncode} err={r.stderr.strip()[:200]!r}")

def main():
    if not shutil.which("minizinc"):
        print("[SKIP] minizinc binary not on PATH", flush=True); return 3
    if not os.path.exists(MZN):
        print(f"[SKIP] {MZN} missing", flush=True); return 3
    end = time.monotonic() + DEADLINE_S
    while not (files := sorted(f for p in PATTERNS for f in glob.glob(p))):
        if time.monotonic() >= end:
            print(f"[SKIP] no .dzn under {PLAN}/alignment within {DEADLINE_S:.0f}s", flush=True); return 3
        time.sleep(min(5, max(0.0, end - time.monotonic())))  # SLEEP-CLASS: POLL-STEP
    agree = bad = 0
    for f in files:
        name = os.path.basename(f)
        try:
            ours = solve(dzn_to_inst(parse_dzn(open(f).read())))
            mz = run_mzn(f)
            a = (ours["selected_provider"], ours["trigger_reactive_hire"])
            t = (mz["selected"], mz["trigger_reactive_hire"])
            if a == t: agree += 1; print(f"[AGREE] {name}: {a[0]} reactive={a[1]}", flush=True)
            else: bad += 1; print(f"[DISAGREE] {name}: cpsat={a} minizinc={t}", flush=True)
        except subprocess.TimeoutExpired:
            bad += 1; print(f"[ERROR] {name}: minizinc timeout {INST_TIMEOUT_S:.0f}s", flush=True)
        except Exception as e:
            bad += 1; print(f"[ERROR] {name}: {type(e).__name__}: {e}", flush=True)
    print(f"SUMMARY agree={agree} bad={bad} total={len(files)}", flush=True)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
