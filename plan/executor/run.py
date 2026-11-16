"""Usage: python3 run.py [plan.soln] [out receipts.jsonl]  -- executes plan, asserts expected ledger."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pddl import Executor, parse_plan, write_receipts

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures")


def execute(plan_path, dom=None, prob=None):
    dom = dom or os.path.join(FX, "servengine_ideal_domain.pddl")
    prob = prob or os.path.join(FX, "problem_enterprise_ops.pddl")
    ex = Executor(open(dom).read(), open(prob).read())
    return ex.run(parse_plan(open(plan_path).read()))


if __name__ == "__main__":
    plan = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FX, "plan_expected.soln")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "receipts.jsonl")
    ex = execute(plan)
    write_receipts(out, ex.receipts)
    led = ex.ledger()
    print(f"receipts={len(ex.receipts)} refused={ex.refused} goal={ex.goal_ok()} ledger={led}")
    if ex.refused:
        sys.exit(2)
    ok = ex.goal_ok() and led == {"AR": 58000, "AP": 25500, "margin": 32500}
    sys.exit(0 if ok else 1)
