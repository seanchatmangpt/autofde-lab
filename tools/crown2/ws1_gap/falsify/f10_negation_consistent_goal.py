#!/usr/bin/env python3
"""F10 (hypothesis expected NOT to reproduce): goal {X:true, NOT_X:false} is consistent;
check _goal_contradiction does not flag it as GOAL_IMPOSSIBLE."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f10"
fx["no_plan"]["goal"]["NOT_MIX_TEST_GREEN"] = False
rec = run("f10_negation_consistent_goal", fx, "ACTION_DISCOVERY_GAP", "consistent negation must not be GOAL_IMPOSSIBLE")
assert rec["reproduces"], "did not reproduce"
