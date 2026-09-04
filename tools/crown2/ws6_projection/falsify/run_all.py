#!/usr/bin/env python3
"""Run every f*.py falsifier as a real subprocess; print per-file verdict lines."""
import glob, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
rc = 0
for f in sorted(glob.glob(os.path.join(HERE, "f*.py"))):
    p = subprocess.run([sys.executable, f], capture_output=True, text=True)
    last = (p.stdout.strip().splitlines() or [""])[-1]
    print(f"{os.path.basename(f)}: exit={p.returncode} :: {last}")
    if p.returncode != 0:
        print(p.stderr.strip()[-400:]); rc = 1
sys.exit(rc)
