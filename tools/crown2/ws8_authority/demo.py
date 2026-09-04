#!/usr/bin/env python3
"""Produce evidence/ws8_honest.ocel.json (gate held) and evidence/ws8_lying.ocel.json (gate faked)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authority as A  # noqa: E402

OCEL_V2 = os.path.normpath(os.path.join(HERE, "..", "..", "ocel_v2"))
EVID = os.path.join(HERE, "evidence")


def sh(*argv):
    r = subprocess.run([sys.executable, *argv], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def main() -> int:
    os.makedirs(EVID, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="ws8demo_")
    marker = os.path.join(tmp, "MARKER")
    honest = os.path.join(EVID, "ws8_honest.ocel.json")
    lying = os.path.join(EVID, "ws8_lying.ocel.json")
    report = {}

    sh(os.path.join(OCEL_V2, "emitter.py"), "init", honest)
    act = {"name": "touch-marker", "argv": ["/usr/bin/touch", "<tmp>/MARKER"]}
    real_act = dict(act, argv=["/usr/bin/touch", marker])
    d1 = A.decide(real_act, "IRREVERSIBLE", "DESTRUCTIVE", "OWNER", "sac", 1.0, 0.9)
    r1 = A.run_with_authority(honest, "act-destructive", real_act, d1, 1)
    report["refused"] = {"verdict": d1.verdict, "ran": r1.ran, "marker_exists": os.path.exists(marker)}
    d2 = A.decide(real_act, "REVERSIBLE", "LOCAL", "NONE", "sac", 1.0, 0.9)
    r2 = A.run_with_authority(honest, "act-granted", real_act, d2, 1)
    report["granted"] = {"verdict": d2.verdict, "ran": r2.ran, "rc": r2.returncode,
                         "marker_exists": os.path.exists(marker)}
    report["honest_validate"] = sh(os.path.join(OCEL_V2, "validate.py"), honest)
    report["honest_check"] = sh(os.path.join(HERE, "check_ocel_authority.py"), honest)

    spec = importlib.util.spec_from_file_location("em", os.path.join(OCEL_V2, "emitter.py"))
    em = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(em)
    em.init(lying)
    A.emit_decision(lying, "act-lying", real_act, d1, 1)
    em.add_event(lying, "ActionStarted", "act-lying:started:1", {"name": "touch-marker"}, ["act-lying"])
    report["lying_validate"] = sh(os.path.join(OCEL_V2, "validate.py"), lying)
    report["lying_check"] = sh(os.path.join(HERE, "check_ocel_authority.py"), lying)

    # Scrub the tmp path so committed evidence is machine-independent.
    for p in (honest, lying):
        with open(p, encoding="utf-8") as f:
            s = f.read().replace(tmp, "<tmp>")
        with open(p, "w", encoding="utf-8") as f:
            f.write(s)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
