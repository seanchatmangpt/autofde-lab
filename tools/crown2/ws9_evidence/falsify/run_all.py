#!/usr/bin/env python3
"""Run every f*.py falsifier against the real WS9 target; print each one's real output."""
import glob
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
rc = 0
for f in sorted(glob.glob(os.path.join(here, "f*.py"))):
    p = subprocess.run([sys.executable, f], capture_output=True, text=True)
    print(f"=== {os.path.basename(f)} exit={p.returncode}")
    print(p.stdout.rstrip())
    if p.returncode:
        print(p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "")
        rc = 1
sys.exit(rc)
