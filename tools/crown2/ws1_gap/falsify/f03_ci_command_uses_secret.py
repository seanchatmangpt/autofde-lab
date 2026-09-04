#!/usr/bin/env python3
"""F03: CI-only command references ${{ secrets.HEX_API_KEY }}; extractor did not set
requires_credential (it only knows the command text). Classifier says ACTION_DISCOVERY_GAP,
but locally the command cannot run without a grant. Correct: AUTHORITY_GAP."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f03"
fx["no_plan"]["missing_transition"] = {"provides": "ELIXIR_DEPS_READY"}
fx["repo_surface_actions"] = [{"name": "HEX_API_KEY=${{ secrets.HEX_API_KEY }} mix hex.organization auth acme && mix deps.get",
    "provides": ["ELIXIR_DEPS_READY"], "source": "ci", "documented": False,
    "requires_credential": False, "destructive": False, "dominated_by": None}]
rec = run("f03_ci_command_uses_secret", fx, "AUTHORITY_GAP",
          "command text carries a GitHub secrets reference; no credential_grants")
assert rec["reproduces"], "did not reproduce"
