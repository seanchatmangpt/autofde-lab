#!/usr/bin/env python3
"""F06: goal impossible ONLY under the current authority policy: the invariant
MIX_TEST_GREEN=false is sourced from authority_policy (no-network sandbox forbids the
only oracle download). Classifier reports GOAL_IMPOSSIBLE (unfixable) instead of
AUTHORITY_GAP (fixable by changing policy)."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f06"
fx["no_plan"]["invariants"] = [{"stage": "MIX_TEST_GREEN", "value": False, "source": "authority_policy:no-network"}]
fx["authority_policy"]["invariants"] = [{"stage": "MIX_TEST_GREEN", "value": False}]
rec = run("f06_policy_invariant_is_goal_impossible", fx, "AUTHORITY_GAP",
          "invariant is policy-conditional, not physical")
assert rec["reproduces"], "did not reproduce"
