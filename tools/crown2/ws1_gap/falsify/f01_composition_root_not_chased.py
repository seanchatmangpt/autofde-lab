#!/usr/bin/env python3
"""F01: transition reachable only via composition of existing actions; the true root
(NATIVE_ORACLES_BUILT, supplied only by a registered manufacturer) is two `requires`
hops below the planner-reported missing_transition. Classifier trusts the reported
transition and never walks the requires-chain. Correct label: ACTION_GAP."""
from _common import fresh_base, run
fx = fresh_base(); fx["name"] = "f01"
fx["no_plan"]["missing_transition"] = {"provides": "QUALIFICATION_COMPLETE"}
fx["repo_surface_actions"] = []
fx["domain_actions"] = [a for a in fx["domain_actions"]] + [
    {"name": "export RF3_ORACLE_BIN=...", "provides": ["ORACLE_ENV_SET"], "requires": ["NATIVE_ORACLES_BUILT"]},
]
fx["manufacturers"] = [{"name": "ggen-pack:native-oracle-builder", "provides": ["NATIVE_ORACLES_BUILT"]}]
rec = run("f01_composition_root_not_chased", fx, "ACTION_GAP",
          "qualify<-mix test<-export<-NATIVE_ORACLES_BUILT; nothing supplies the root, a manufacturer does")
assert rec["reproduces"], "did not reproduce"
