#!/usr/bin/env python3
"""F08: no_plan carries no missing_transition (planner exhausted search without naming
one). Classifier silently classifies transition='' as MANUFACTURING_GAP instead of
refusing. Correct: ValueError / UNVERIFIED."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f08"
fx["no_plan"]["missing_transition"] = {}
rec = run("f08_empty_missing_transition", fx, "<refuse>", "empty transition should be rejected, not classified")
assert rec["reproduces"], "did not reproduce"
