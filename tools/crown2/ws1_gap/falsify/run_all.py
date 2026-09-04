#!/usr/bin/env python3
"""Run every f*.py falsifier as a real subprocess; print per-file verdict."""
import glob, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
rc = 0
for p in sorted(glob.glob(os.path.join(HERE, "f*.py"))):
    r = subprocess.run([sys.executable, p], capture_output=True, text=True, cwd=HERE)
    tag = "REPRODUCES" if r.returncode == 0 else "NO_REPRO"
    print(f"{tag} {os.path.basename(p)}\n  {r.stdout.strip()}\n  {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
    rc |= 0
