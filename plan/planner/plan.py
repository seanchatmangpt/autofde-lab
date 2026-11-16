"""L1 temporal planner driver: ground -> aries solve -> validate on ORIGINAL problem (with TIL)."""
import os
import sys, warnings, re
warnings.filterwarnings("ignore")
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import *
from unified_planning.engines import CompilationKind
import unified_planning.plans as plans

dom, prob, out = sys.argv[1:4]
HORIZON = 10000  # TILs beyond this are deferred for search, enforced in validation

# original problem (Real fluents, full TIL) = validation subject
orig = PDDLReader().parse_problem(dom, prob)

# search copy: Int fluents (aries has no Real), TILs past horizon deferred
tm = get_environment().type_manager
tm.RealType = lambda *a, **k: tm.IntType(0, 100_000_000)  # invoice-amount = minutes * cents/h must fit: 1e7 overflowed at $300/h rates (aries then TIMEOUTs); 1e9 gives INTERNAL_ERRORnvoice-amount = minutes * cents/h must fit; 1e7 overflowed at $300/h rates
sp = PDDLReader().parse_problem(dom, prob)
late = [t for t in list(sp.timed_effects) if float(t.delay) > HORIZON]
deferred = {str(t): [str(e) for e in sp.timed_effects[t]] for t in late}
for t in late:
    del sp._timed_effects[t]
with Compiler(name="up_grounder", compilation_kind=CompilationKind.GROUNDING) as c:
    g = c.compile(sp, CompilationKind.GROUNDING)
with OneshotPlanner(name="aries") as pl:
    res = pl.solve(g.problem, timeout=float(os.environ.get("PLAN_SEARCH_TIMEOUT_S", "60")))  # dev profile: 5s
print("search status:", res.status, "| deferred TILs:", deferred)
if res.plan is None:
    print("NO PLAN"); sys.exit(2)
plan = res.plan.replace_action_instances(g.map_back_action_instance)
from unified_planning.plans import ActionInstance
em = orig.environment.expression_manager
plan_o = plans.TimeTriggeredPlan([
    (s, ActionInstance(orig.action(a.action.name),
                       tuple(em.ObjectExp(orig.object(p.object().name)) for p in a.actual_parameters)), d)
    for s, a, d in plan.timed_actions])
end = max(float(s) + float(d) for s, a, d in plan_o.timed_actions)
assert end < HORIZON, "plan reaches deferred TIL horizon"
with PlanValidator(name="up_time_triggered_validator") as v:
    vr = v.validate(orig, plan_o)
print("validator:", vr.status)
if vr.status != up.engines.ValidationResultStatus.VALID:
    print(vr); sys.exit(3)
with open(out, "w") as f:
    for s, a, d in plan_o.timed_actions:
        f.write("%.3f: (%s %s) [%.3f]\n" % (float(s), a.action.name, " ".join(str(p) for p in a.actual_parameters), float(d)))
print("plan end time:", end)
print(open(out).read())
