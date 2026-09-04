#!/usr/bin/env python3
"""F09: planner rejected_actions reason 'Authority: policy denies' (capitalised, as an
A* rejection log would write it). startswith('authority') misses it -> NOVEL_INFORMATION_GAP.
Correct: AUTHORITY_GAP. COSMETIC unless the planner contract fixes casing."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f09"
fx["no_plan"]["missing_transition"] = {"provides": "MIX_TEST_GREEN"}
fx["no_plan"]["rejected_actions"] = [{"name": "mix test", "reason": "Authority: policy denies network"}]
rec = run("f09_rejected_reason_case", fx, "AUTHORITY_GAP", "reason casing")
assert rec["reproduces"], "did not reproduce"
