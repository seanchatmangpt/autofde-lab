#!/usr/bin/env python3
"""Poll for L1 planner/run.sh until deadline (Instant-style), then run it or typed [SKIP]."""
import os, subprocess, sys, time
from pathlib import Path
PLAN_ROOT = Path(__file__).resolve().parents[1]
run = str(PLAN_ROOT / "planner" / "run.sh")
dl = time.monotonic() + float(os.environ.get("PM_PLANNER_WAIT", "600"))
while not os.path.exists(run) and time.monotonic() < dl:
    time.sleep(5)  # POLL-STEP
if not os.path.exists(run):
    print("[SKIP] planner/run.sh absent at deadline"); sys.exit(0)
dom, prob = sys.argv[1], sys.argv[2]
p = subprocess.run([os.path.dirname(run)+"/.venv/bin/python","-u",os.path.dirname(run)+"/plan.py",dom,prob,"out/small.soln"], capture_output=True, text=True, timeout=300)
print(p.stdout[-1500:], p.stderr[-500:]); print("planner rc=", p.returncode); sys.exit(p.returncode)
