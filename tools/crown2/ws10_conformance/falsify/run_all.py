#!/usr/bin/env python3
"""Run every f*.py falsifier; print one JSON summary line per falsifier.
Exit 0 always (this is a report, each falsifier's own exit code is recorded)."""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
summary = {}
for f in sorted(glob.glob(os.path.join(HERE, "f*.py"))):
    p = subprocess.run([sys.executable, f], capture_output=True, text=True, cwd=HERE)
    name = os.path.basename(f)
    try:
        summary[name] = json.loads(p.stdout)["result"]
    except Exception:
        summary[name] = f"ERROR rc={p.returncode}: {p.stderr.strip()[-300:]}"
print(json.dumps(summary, indent=1))
