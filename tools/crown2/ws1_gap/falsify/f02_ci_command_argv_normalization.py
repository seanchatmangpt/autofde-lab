#!/usr/bin/env python3
"""F02: command present only in CI yaml, whose argv differs cosmetically from the
policy's forbidden_actions entry (`mix deps.get --only prod` vs forbidden `mix deps.get`).
_forbidden() does exact string match, so the CI variant slips policy. Correct: AUTHORITY_GAP."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f02"
fx["no_plan"]["missing_transition"] = {"provides": "ELIXIR_DEPS_READY"}
fx["no_plan"]["initial_world_state"]["ELIXIR_DEPS_READY"] = False
fx["authority_policy"]["forbidden_actions"] = ["mix deps.get"]
fx["repo_surface_actions"] = [{"name": "mix deps.get --only prod", "provides": ["ELIXIR_DEPS_READY"],
    "source": "ci", "documented": False, "requires_credential": False, "destructive": False, "dominated_by": None}]
rec = run("f02_ci_command_argv_normalization", fx, "AUTHORITY_GAP",
          "policy forbids `mix deps.get`; CI yaml runs the same binary with extra flags")
assert rec["reproduces"], "did not reproduce"
