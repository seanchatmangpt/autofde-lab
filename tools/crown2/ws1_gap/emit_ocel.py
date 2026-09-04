#!/usr/bin/env python3
"""
emit_ocel.py — classify every fixture and emit it as an OCEL 2.0 GapDiagnosed
event (plus a GapDiagnosis object) via tools/ocel_v2/emitter.py, then run
tools/ocel_v2/validate.py on the result.

Run: python3 emit_ocel.py [out.ocel.json]
Default output: out/ws1_gap.ocel.json (sibling of this file).
Exit code: validate.py's exit code (0 only when all three counts are zero).
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OCEL_V2 = os.path.abspath(os.path.join(HERE, "..", "..", "ocel_v2"))
sys.path.insert(0, OCEL_V2)
sys.path.insert(0, HERE)

import emitter  # noqa: E402  (tools/ocel_v2/emitter.py)
from gap import classify_fixture  # noqa: E402


def emit_all(out_path: str) -> list[dict]:
    emitter.init(out_path)
    emitter.add_object(out_path, "Repository", "repo:beam4pm",
                       {"path": "/Users/sac/beam4pm", "remote_url": "", "default_branch": "main"})
    emitter.add_object(out_path, "SolverImplementation", "solver:astar-staged",
                       {"name": "astar/staged-qualification", "kind": "astar", "version": "ws1"})
    rows = []
    for path in sorted(glob.glob(os.path.join(HERE, "fixtures", "*.json"))):
        with open(path, encoding="utf-8") as f:
            fx = json.load(f)
        d = classify_fixture(fx)
        oid = f"gap:{fx['name']}"
        emitter.add_object(out_path, "GapDiagnosis", oid, {
            "gap_type": d.gap_type.value, "planner": d.planner,
            "unavailable_transition": d.unavailable_transition,
            "standing": d.standing, "receipt_digest": d.receipt_digest,
        })
        emitter.add_event(out_path, "GapDiagnosed", f"ev:gapdiagnosed:{fx['name']}", {
            "gap_type": d.gap_type.value,
            "unavailable_transition": d.unavailable_transition,
            "missing_preconditions": ",".join(d.missing_preconditions),
            "receipt_digest": d.receipt_digest,
            "diagnosis_json": d.to_json(),
        }, [oid, "repo:beam4pm", "solver:astar-staged"])
        rows.append({"fixture": fx["name"], "expected": fx["expected_gap_type"], "got": d.gap_type.value})
    return rows


def main(argv: list[str]) -> int:
    out_path = argv[1] if len(argv) > 1 else os.path.join(HERE, "out", "ws1_gap.ocel.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rows = emit_all(out_path)
    for r in rows:
        print(json.dumps(r))
    proc = subprocess.run([sys.executable, os.path.join(OCEL_V2, "validate.py"), out_path],
                          capture_output=True, text=True)
    print(f"validate.py {out_path}: {proc.stdout.strip()} EXIT:{proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
