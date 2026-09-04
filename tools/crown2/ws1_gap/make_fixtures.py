#!/usr/bin/env python3
"""
make_fixtures.py — deterministic generator for fixtures/*.json.

Every fixture is a real-shaped NO_PLAN_FOUND situation taken from the
beam4pm staged-qualification runs observed under Crown-2 (run1 verify:
Rust 1548 tests pass, mix test EXIT:1 'Unchecked dependencies ... run
"mix deps.get"'; recovery: mix deps.get EXIT:0; run2: 2393 tests, 18
failures = RF3_ORACLE_BIN unset + rf1-dfg-oracle binary not built).

Run: python3 make_fixtures.py   (idempotent; rewrites fixtures/)
"""
from __future__ import annotations

import json
import os
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

GOAL_GREEN = {"MIX_TEST_GREEN": True, "QUALIFICATION_COMPLETE": True}

RUN1_STATE = {  # after run1: rust green, mix deps unchecked
    "SUBMODULES_READY": True, "SYNC_READY": True, "LINT_TRUTH_READY": True,
    "RUST_TESTS_READY": True, "ELIXIR_DEPS_READY": False, "MIX_TEST_RUNNABLE": False,
    "NATIVE_ORACLES_BUILT": False, "ORACLE_ENV_SET": False, "MIX_TEST_GREEN": False,
    "QUALIFICATION_COMPLETE": False,
    "observed": {"rust_tests_passed": 1548, "mix_test_exit": 1,
                 "mix_test_stderr": 'Unchecked dependencies ... run "mix deps.get"'},
}
RUN2_STATE = {  # after mix deps.get: 2393 tests, 18 failures, 92 skipped
    **{k: v for k, v in RUN1_STATE.items() if k != "observed"},
    "ELIXIR_DEPS_READY": True, "MIX_TEST_RUNNABLE": True,
    "observed": {"mix_tests": 2393, "failures": 18, "skipped": 92, "mix_test_exit": 2,
                 "failure_classes": ["System.EnvError RF3_ORACLE_BIN not set",
                                     "RuntimeError rf1-dfg-oracle binary not found"]},
}

DOMAIN_BASE = [
    {"name": "git submodule update --init --recursive", "provides": ["SUBMODULES_READY"], "requires": []},
    {"name": "make sync", "provides": ["SYNC_READY"], "requires": ["SUBMODULES_READY"]},
    {"name": "make lint_truth", "provides": ["LINT_TRUTH_READY"], "requires": ["SYNC_READY"]},
    {"name": "cargo test --workspace", "provides": ["RUST_TESTS_READY"], "requires": ["LINT_TRUTH_READY"]},
    {"name": "mix test", "provides": ["MIX_TEST_GREEN"], "requires": ["MIX_TEST_RUNNABLE", "NATIVE_ORACLES_BUILT", "ORACLE_ENV_SET"]},
    {"name": "qualify", "provides": ["QUALIFICATION_COMPLETE"], "requires": ["MIX_TEST_GREEN"]},
]
EXPLORED_BASE = [a["name"] for a in DOMAIN_BASE]
FRESH = [{"precondition": s, "status": "fresh"} for s in RUN1_STATE if s != "observed"]
POLICY = {"forbidden_actions": ["git push --force"], "forbid_destructive": True, "credential_grants": []}
QUAL_OK = {"available": True}


def fx(name: str, expected: str, note: str, *, state=RUN2_STATE, goal=GOAL_GREEN, transition: str,
       domain=None, repo=None, policy=POLICY, sensors=FRESH, manufacturers=None, qual=QUAL_OK,
       rejected=None, invariants=None, explored=None, missing_pre=None, tags=()) -> dict[str, Any]:
    mt: dict[str, Any] = {"provides": transition}
    if missing_pre:
        mt["missing_preconditions"] = missing_pre
    return {
        "name": name, "expected_gap_type": expected, "note": note, "tags": list(tags),
        "no_plan": {"status": "NO_PLAN_FOUND", "goal": goal, "initial_world_state": state,
                    "planner": "astar/staged-qualification", "explored_actions": explored or EXPLORED_BASE,
                    "rejected_actions": rejected or [], "missing_transition": mt, "invariants": invariants or []},
        "domain_actions": domain if domain is not None else DOMAIN_BASE,
        "repo_surface_actions": repo or [],
        "authority_policy": policy, "sensors": sensors, "manufacturers": manufacturers or [],
        "qualification_env": qual,
    }


def repo(name, provides, source="docs", documented=True, credential=False, destructive=False, dominated_by=None):
    return {"name": name, "provides": provides, "source": source, "documented": documented,
            "requires_credential": credential, "destructive": destructive, "dominated_by": dominated_by}


MIX_DEPS_GET = repo("mix deps.get", ["ELIXIR_DEPS_READY"], source="mix.exs+README")
CARGO_ORACLE = repo("cargo build --release (native/rf1-dfg-oracle)", ["NATIVE_ORACLES_BUILT"], source="error-message")

FIXTURES: list[dict[str, Any]] = [
    # --- the four canonical dead ends ----------------------------------------
    fx("canonical_impossible_goal", "GOAL_IMPOSSIBLE",
       "goal wants MIX_TEST_GREEN while an invariant pins MIX_TEST_GREEN=False (skipped-92 policy)",
       transition="MIX_TEST_GREEN", invariants=[{"stage": "MIX_TEST_GREEN", "value": False}],
       tags=("canonical", "goal-contradictory")),
    fx("canonical_hidden_repo_action_mix_deps_get", "ACTION_DISCOVERY_GAP",
       "run1: mix test EXIT:1 'Unchecked dependencies ... run mix deps.get'; deps.get is in the repo surface, not the domain",
       state=RUN1_STATE, transition="ELIXIR_DEPS_READY", repo=[MIX_DEPS_GET],
       tags=("canonical", "dependency-declared-but-absent")),
    fx("canonical_genuinely_absent_action", "MANUFACTURING_GAP",
       "RF3 oracle binary: no action, no source tree, no manufacturer supplies RF3_ORACLE_BIN",
       transition="ORACLE_ENV_SET", missing_pre=["ORACLE_ENV_SET"], tags=("canonical",)),
    fx("canonical_disallowed_consequential", "AUTHORITY_GAP",
       "only repo action supplying a clean rebuild is destructive (rm -rf _build deps) and policy forbids destructive",
       transition="ELIXIR_DEPS_READY", state=RUN1_STATE,
       repo=[repo("rm -rf _build deps && mix deps.get", ["ELIXIR_DEPS_READY"], destructive=True)],
       tags=("canonical", "command-destructive")),
    # --- one per remaining class -----------------------------------------------
    fx("class_observation_gap_sensor_missing", "OBSERVATION_GAP",
       "no sensor for NATIVE_ORACLES_BUILT at all, though cargo build could supply it",
       transition="NATIVE_ORACLES_BUILT", repo=[CARGO_ORACLE],
       sensors=[s for s in FRESH if s["precondition"] != "NATIVE_ORACLES_BUILT"], tags=("sensor-missing",)),
    fx("class_observation_gap_sensor_stale", "OBSERVATION_GAP",
       "sensor for NATIVE_ORACLES_BUILT last read before run2; stale",
       transition="NATIVE_ORACLES_BUILT", repo=[CARGO_ORACLE],
       sensors=[({**s, "status": "stale"} if s["precondition"] == "NATIVE_ORACLES_BUILT" else s) for s in FRESH],
       tags=("sensor-stale",)),
    fx("class_action_gap_manufacturer_registered", "ACTION_GAP",
       "nothing sets RF3_ORACLE_BIN; an env-wiring manufacturer (ggen envrc pack generator) is registered",
       transition="ORACLE_ENV_SET",
       manufacturers=[{"name": "ggen:envrc-generator", "provides": ["ORACLE_ENV_SET"]}]),
    fx("class_qualification_gap_env_absent", "QUALIFICATION_GAP",
       "mix test is in the domain and admissible, but no qualification environment (no act runner / no BEAM) available",
       transition="MIX_TEST_GREEN", qual={"available": False}, tags=("qualification-env-absent",)),
    fx("class_authority_gap_domain_rejected", "AUTHORITY_GAP",
       "domain action 'qualify' exists but planner rejected it: authority grant missing for consequential merge",
       transition="QUALIFICATION_COMPLETE",
       rejected=[{"name": "qualify", "reason": "authority: no AuthorityDecision for consequential step"}],
       tags=("authority-missing",)),
    fx("class_knowledge_gap_marketplace_only", "KNOWLEDGE_GAP",
       "ORACLE_ENV_SET only supplied by a ggen-marketplace pack; not in repo, not in domain",
       transition="ORACLE_ENV_SET",
       repo=[repo("ggen pack apply oracle-env", ["ORACLE_ENV_SET"], source="marketplace-pack")],
       tags=("command-only-in-marketplace-pack",)),
    fx("class_novel_information_gap_two_actions", "NOVEL_INFORMATION_GAP",
       "two admissible undominated ways to build the oracle (cargo build vs make oracles); nothing observed distinguishes them",
       transition="NATIVE_ORACLES_BUILT",
       repo=[CARGO_ORACLE, repo("make oracles", ["NATIVE_ORACLES_BUILT"], source="Makefile")],
       tags=("two-possible-actions",)),
    # --- remaining real-shaped states -----------------------------------------
    fx("state_command_exists_but_undocumented", "ACTION_DISCOVERY_GAP",
       "cargo build for the oracle appears only in shell history / an error string, never in docs",
       transition="NATIVE_ORACLES_BUILT",
       repo=[repo("cargo build --release", ["NATIVE_ORACLES_BUILT"], source="shell-history", documented=False)],
       tags=("command-undocumented",)),
    fx("state_command_only_in_ci", "ACTION_DISCOVERY_GAP",
       "RF3_ORACLE_BIN export lives only in .github/workflows/ci.yml env block",
       transition="ORACLE_ENV_SET",
       repo=[repo("export RF3_ORACLE_BIN=native/rf3/target/release/rf3", ["ORACLE_ENV_SET"], source="ci")],
       tags=("command-only-in-ci",)),
    fx("state_command_only_in_generated_code", "ACTION_DISCOVERY_GAP",
       "oracle build step exists only in ggen-generated build.rs output",
       transition="NATIVE_ORACLES_BUILT",
       repo=[repo("generated build.rs: build_oracle()", ["NATIVE_ORACLES_BUILT"], source="generated")],
       tags=("command-only-in-generated-code",)),
    fx("state_command_requires_credential", "AUTHORITY_GAP",
       "fetching the prebuilt RF3 oracle needs GH_TOKEN; no credential grant in policy",
       transition="ORACLE_ENV_SET",
       repo=[{**repo("gh release download rf3-oracle", ["ORACLE_ENV_SET"], credential=True), "credential": "GH_TOKEN"}],
       tags=("command-requires-credential",)),
    fx("state_command_requires_credential_granted", "ACTION_DISCOVERY_GAP",
       "falsifier: same credentialed command with the grant present is merely undiscovered, not an authority gap",
       transition="ORACLE_ENV_SET",
       policy={**POLICY, "credential_grants": ["GH_TOKEN"]},
       repo=[{**repo("gh release download rf3-oracle", ["ORACLE_ENV_SET"], credential=True), "credential": "GH_TOKEN"}],
       tags=("falsifier",)),
    fx("state_goal_self_contradictory", "GOAL_IMPOSSIBLE",
       "goal asserts MIX_TEST_GREEN and NOT_MIX_TEST_GREEN",
       goal={"MIX_TEST_GREEN": True, "NOT_MIX_TEST_GREEN": True}, transition="MIX_TEST_GREEN",
       tags=("goal-contradictory",)),
    fx("state_absent_action_no_manufacturer_no_sensor", "MANUFACTURING_GAP",
       "falsifier: a missing sensor does NOT become OBSERVATION_GAP when nothing could supply the transition anyway",
       transition="ORACLE_ENV_SET", sensors=[s for s in FRESH if s["precondition"] != "ORACLE_ENV_SET"],
       tags=("falsifier",)),
]


def main() -> None:
    os.makedirs(FIX, exist_ok=True)
    for f in FIXTURES:
        path = os.path.join(FIX, f["name"] + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(f, fh, indent=2, sort_keys=True)
            fh.write("\n")
    print(f"wrote {len(FIXTURES)} fixtures to {FIX}")


if __name__ == "__main__":
    main()
