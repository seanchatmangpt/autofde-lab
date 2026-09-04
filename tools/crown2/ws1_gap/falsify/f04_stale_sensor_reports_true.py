#!/usr/bin/env python3
"""F04: stale sensor whose last reading (and initial_world_state) say the precondition
ALREADY HOLDS; the real blocker is a second precondition supplied only by a forbidden
action. Step 2 fires on the first stale precondition regardless of its value.
Correct: AUTHORITY_GAP."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f04"
fx["no_plan"]["missing_transition"] = {"provides": "MIX_TEST_GREEN",
    "missing_preconditions": ["ELIXIR_DEPS_READY", "NATIVE_ORACLES_BUILT"]}
fx["no_plan"]["initial_world_state"]["ELIXIR_DEPS_READY"] = True
for s in fx["sensors"]:
    if s["precondition"] == "ELIXIR_DEPS_READY": s.update(status="stale", last_value=True)
fx["repo_surface_actions"] = [{"name": "rm -rf native/*/target && cargo build --release", "provides": ["NATIVE_ORACLES_BUILT"],
    "source": "docs", "documented": True, "requires_credential": False, "destructive": True, "dominated_by": None}]
rec = run("f04_stale_sensor_reports_true", fx, "AUTHORITY_GAP",
          "stale sensor already reports true; refreshing it changes nothing; only supplier is destructive")
assert rec["reproduces"], "did not reproduce"
