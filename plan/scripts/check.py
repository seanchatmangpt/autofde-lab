#!/usr/bin/env python3
"""Run each lane's gate recipe if it exists; aggregate table; fail on any red lane/receipt."""
import pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import receipts_lint
ROOT = pathlib.Path(__file__).resolve().parent.parent
LANES = {"L1": "01-l1", "L2": "20-alignment", "L3": "30-l3-cpsat", "L4": "40-pipeline",
         "L5": "50-pm", "L6": "60-procurepass", "L7": "07-executor", "L8": "80-l8",
         "L9": "90-ledger", "L10": "10-root"}
GATES = {"L1": ["l1-plan"], "L2": ["alignment-test"], "L3": ["l3-test"], "L4": ["pipeline-test"],
         "L5": ["pm-test"], "L6": ["procurepass-test"], "L7": ["executor-test"],
         "L8": ["l8-courts"], "L9": ["ledger-test"], "L10": ["gate-root"]}
def jf(lane):
    # lane modules compute ROOT from justfile_directory() == justfile.d, so run them as the justfile
    return str(ROOT / "Justfile") if lane == "L10" else str(ROOT / "justfile.d" / f"{LANES[lane]}.just")
def avail_for(lane):
    return set(subprocess.run(["just", "--justfile", jf(lane), "--summary"],
                              capture_output=True, text=True).stdout.split())
rows, fail = [], False
for lane in LANES:
    rec = ROOT / "receipts" / f"{lane}.md"
    rerr = receipts_lint.lint(rec) if rec.exists() else "receipt missing"
    if rerr:
        fail = True
    av = avail_for(lane)
    gates = [g for g in GATES[lane] if g in av]
    if not gates:
        rows.append((lane, "UNVERIFIED (no gate)", "-", rerr or "ok")); fail = True; continue
    for g in gates:
        r = subprocess.run(["just", "--justfile", jf(lane), g], cwd=ROOT,
                           capture_output=True, text=True)
        rows.append((lane, g, str(r.returncode), rerr or "ok"))
        if r.returncode:
            fail = True
            print(f"--- {lane} {g} output tail ---\n" + (r.stdout + r.stderr)[-1200:])
print(f"{'lane':5} {'gate':28} {'rc':3} receipt")
for r in rows:
    print(f"{r[0]:5} {r[1]:28} {r[2]:3} {r[3]}")
print("RESULT:", "FAIL" if fail else "PASS")
sys.exit(1 if fail else 0)
