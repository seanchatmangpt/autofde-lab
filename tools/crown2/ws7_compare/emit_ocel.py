#!/usr/bin/env python3
"""emit_ocel.py — run comparator over a fixture set and emit PredictionCompared via the
real tools/ocel_v2/emitter.py CLI (subprocess), then run validate.py. stdlib only.

usage: python3 emit_ocel.py <out.ocel.json> [<case>]   case in {mixed,confirmed,invariant}; default mixed
"""
from __future__ import annotations
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OCEL = os.path.normpath(os.path.join(HERE, "..", "..", "ocel_v2"))
EMITTER, VALIDATE = os.path.join(OCEL, "emitter.py"), os.path.join(OCEL, "validate.py")
sys.path.insert(0, HERE)
import compare  # noqa: E402

CASES = {
    "mixed": ("predicted_mixed.json", "observed_mixed.json", "prior.json"),
    "confirmed": ("predicted_confirmed.json", "observed_confirmed.json", "prior.json"),
    "invariant": ("predicted_invariant.json", "observed_invariant.json", "prior_invariant.json"),
}

def _j(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return json.load(f)

def _cli(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"emitter/validate failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout

def emit(out, case="mixed"):
    pf, of, prf = CASES[case]
    with open(os.path.join(HERE, "schema.beam4pm.json"), encoding="utf-8") as f:
        schema = json.load(f)
    pred, obs, prior = _j(pf), _j(of), _j(prf)
    res = compare.diff(pred, obs, schema, prior)
    cj = lambda d: json.dumps(d, sort_keys=True, separators=(",", ":"))
    _cli(EMITTER, "init", out)
    _cli(EMITTER, "add-object", out, "WorldState", f"ws7:{case}:prior",
         cj({"label": f"{case}/prior", "observed_at": "2026-09-03T00:00:00+00:00", "state_json": cj(prior)}))
    _cli(EMITTER, "add-object", out, "WorldState", f"ws7:{case}:observed",
         cj({"label": f"{case}/observed", "observed_at": "2026-09-03T00:00:01+00:00", "state_json": cj(obs)}))
    _cli(EMITTER, "add-object", out, "PredictionReceipt", f"ws7:{case}:prediction",
         cj({"prediction_json": cj(pred), "confidence": 0.9, "frozen_at": "2026-09-03T00:00:00+00:00"}))
    _cli(EMITTER, "add-event", out, "PredictionCompared", f"ws7:{case}:compared",
         cj(compare.to_ocel_attrs(res)),
         f"ws7:{case}:prior,ws7:{case}:observed,ws7:{case}:prediction")
    vout = _cli(VALIDATE, out)
    return res, vout

if __name__ == "__main__":
    out = sys.argv[1]; case = sys.argv[2] if len(sys.argv) > 2 else "mixed"
    res, vout = emit(out, case)
    print(json.dumps({"case": case, "verdict": res["verdict"], "digest": res["digest"], "counts": res["counts"]}, indent=1))
    print("validate:", vout.strip())
