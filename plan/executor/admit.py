"""Plan admission on autofde-lab: GraphLaw admits the plan (receipt chain), pm4pytest gates the
executed trace, the POWL oracle (PyPI powl) cross-checks conformance.

    python3 admit.py [plan.soln] [domain.pddl] [problem.pddl]   -> exit 0 ADMITTED, 2 REFUSED

The numeric replay executor (pddl.py / run.py under PLAN_ORACLE=1) stays as the differential oracle.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures")
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _lab(name, args):
    return "(" + " ".join([name] + list(args)) + ")"


def default_texts(dom=None, prob=None):
    dom = dom or os.path.join(FX, "servengine_ideal_domain.pddl")
    prob = prob or os.path.join(FX, "problem_enterprise_ops.pddl")
    return open(dom).read(), open(prob).read()


def trace_of(plan_text):
    """Executed activity sequence: one activity per plan line (name + args), start-time order."""
    from autofde_lab.law_bridge.pddl_encoding import parse_plan
    steps = sorted(enumerate(parse_plan(plan_text)), key=lambda p: (p[1][0], p[0]))
    return [_lab(n, a) for _i, (_t, n, a, _d) in steps]


def admit_plan(plan_text, dom_text=None, prob_text=None):
    """-> dict(status, plan_index, step, action, unmet, receipts, skipped). The admission goes
    through law_bridge.graphlaw_admitter (real WASM module)."""
    from autofde_lab.law_bridge import GraphLawAdmitter
    from autofde_lab.law_bridge.pddl_encoding import encode_pddl_plan
    if dom_text is None or prob_text is None:
        dom_text, prob_text = default_texts()
    enc = encode_pddl_plan(dom_text, prob_text, plan_text)
    v = GraphLawAdmitter().admit(enc.initial, enc.actions, goal=enc.goal)
    out = {"status": v.status, "skipped": enc.skipped, "steps": len(enc.actions),
           "plan_index": None, "step": None, "action": None, "unmet": (), "receipts": 0,
           "chain": []}
    if v.status == "ADMITTED":
        out["receipts"] = len(v.receipts)
        out["chain"] = v.chain
    else:
        out["step"] = v.index
        out["plan_index"] = enc.plan_index(v.index)
        out["action"] = v.action
        out["unmet"] = tuple(v.unmet)
        out["error"] = v.error
    return out


def pm4_fitness(reference, trace, min_fitness=1.0):
    """pm4pytest FSM conformance of `trace` against `reference` through the real PM4PySession."""
    from pm4pytest.conformance import ConformanceSpec
    from pm4pytest.plugin import PM4PySession
    s = PM4PySession(test_name="m4_trace")
    try:
        s.register_object("obj1", "plan")
        for i, a in enumerate(trace):
            s.emit_event(f"ev{i}", a, timestamp=BASE + timedelta(seconds=i),
                         relationships=[{"objectId": "obj1", "qualifier": "of"}])
        s.set_conformance(ConformanceSpec.from_fsm([list(reference)], min_fitness=min_fitness))
        ok, violations, metrics = s.evaluate_all()
    finally:
        s.cleanup()
    return ok, float(metrics["conformance"]["fitness"]), violations


def powl_fitness(reference, trace):
    from autofde_lab.coprocessor.kinds_rl import powl_fitness as f
    return f(reference, trace)


def main(argv):
    plan = argv[1] if len(argv) > 1 else os.path.join(FX, "plan_expected.soln")
    dom, prob = default_texts(*(argv[2:4] if len(argv) > 3 else (None, None)))
    r = admit_plan(open(plan).read(), dom, prob)
    print(f"graphlaw={r['status']} steps={r['steps']} receipts={r['receipts']} "
          f"refused_at={r['action']} unmet={list(r['unmet'])[:1]} skipped={list(r['skipped'])}")
    return 0 if r["status"] == "ADMITTED" else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
