"""python3 -m enterprise_pipeline.cli STATE.json [--out problem.pddl] [--backend minizinc|cpsat]"""
import argparse
import json
import sys
from pathlib import Path

from . import align, pddl, planner


def compile_state(state, backend="minizinc"):
    elig = align.eligibility(state, backend)
    return pddl.emit(state, elig), elig


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("state")
    ap.add_argument("--out", default="problem.pddl")
    ap.add_argument("--backend", default="minizinc")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--deadline", type=float, default=5.0)
    a = ap.parse_args(argv)
    state = json.loads(Path(a.state).read_text())
    try:
        text, elig = compile_state(state, a.backend)
    except align.Skip as e:
        print(e)
        return 0
    Path(a.out).write_text(text)
    for w, (m, trig) in elig.items():
        print(f"{w}: eligible={[p for p, ok in m.items() if ok]} reactive_hire={trig}")
    print(f"wrote {a.out}")
    if a.plan:
        try:
            rc, out, steps = planner.run_planner(a.out, a.deadline)
        except align.Skip as e:
            print(e)
            return 0
        print(f"planner rc={rc}; {len(steps)} steps")
        for s in steps:
            print(s)
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
