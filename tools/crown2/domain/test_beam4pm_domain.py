#!/usr/bin/env python3
"""Chicago-style tests for beam4pm_domain: real repo, real probes, real logs.
No mocks. Run: python3 -m unittest tools/crown2/domain/test_beam4pm_domain.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import beam4pm_domain as d  # noqa: E402

REPO = d.DEFAULT_REPO
GOAL = {"QUALIFICATION_COMPLETE": True}


def _names(plan):
    return [a.name for a in plan]


class ObserveRealState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = d.observe(REPO)

    def test_repo_exists_and_all_stages_present(self):
        self.assertTrue(REPO.is_dir(), REPO)
        self.assertEqual(tuple(self.state.stages), d.STAGES)
        self.assertEqual(set(self.state.evidence), set(d.STAGES))

    def test_current_real_state_matches_logs(self):
        s = self.state.stages
        # Observed in beam4pm-verify.log / verify2.log + live probes.
        self.assertTrue(s["SUBMODULES_READY"], self.state.evidence["SUBMODULES_READY"])
        self.assertTrue(s["SYNC_READY"], self.state.evidence["SYNC_READY"])
        self.assertTrue(s["LINT_TRUTH_READY"], self.state.evidence["LINT_TRUTH_READY"])
        self.assertTrue(s["RUST_TESTS_READY"], self.state.evidence["RUST_TESTS_READY"])
        self.assertTrue(s["ELIXIR_DEPS_READY"], self.state.evidence["ELIXIR_DEPS_READY"])
        self.assertTrue(s["MIX_TEST_RUNNABLE"], self.state.evidence["MIX_TEST_RUNNABLE"])
        # The two typed gaps behind the 18 failures.
        rf1 = REPO / "native/rf1-dfg-oracle/target/release/rf1-dfg-oracle"
        self.assertEqual(s["NATIVE_ORACLES_BUILT"], rf1.exists() and "absent=[]" in self.state.evidence["NATIVE_ORACLES_BUILT"].detail)
        self.assertEqual(s["ORACLE_ENV_SET"], bool(os.environ.get("RF3_ORACLE_BIN")) and bool(os.environ.get("RF2_ORACLE_BIN")))
        self.assertFalse(s["MIX_TEST_GREEN"])
        self.assertIn("18 failures", self.state.evidence["MIX_TEST_GREEN"].detail)
        self.assertFalse(s["QUALIFICATION_COMPLETE"])

    def test_evidence_cites_real_sources(self):
        ev = self.state.evidence
        self.assertEqual(ev["RUST_TESTS_READY"].source, "beam4pm-verify.log:2457")
        self.assertIn("All 1548 tests passed.", ev["RUST_TESTS_READY"].detail)
        self.assertEqual(ev["LINT_TRUTH_READY"].kind, "probe")
        self.assertIn("GATE LINT-TRUTH: PASS", ev["LINT_TRUTH_READY"].detail)
        self.assertIn("RF3_ORACLE_BIN", ev["ORACLE_ENV_SET"].detail)


class DiscoverActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actions = d.discover_actions(REPO)
        cls.by_name = {a.name: a for a in cls.actions}

    def test_every_action_carries_discovery_source(self):
        for a in self.actions:
            self.assertRegex(a.source, r"[\w./-]+:\d+", a)

    def test_recipes_from_justfile(self):
        self.assertEqual(self.by_name["mix test"].source, "justfile:18")
        self.assertEqual(self.by_name["submodules"].command, "git submodule update --init --recursive")
        self.assertEqual(self.by_name["lint_truth"].command, "bash scripts/gate_lint_truth.sh")

    def test_mix_deps_from_mix_exs(self):
        a = self.by_name["mix deps.get"]
        self.assertTrue(a.source.startswith("mix.exs:"))
        self.assertEqual(a.postconditions, {"ELIXIR_DEPS_READY": True})

    def test_cargo_build_from_native_cargo_toml(self):
        a = self.by_name["cargo build --release (oracles)"]
        self.assertIn("cd native/rf1-dfg-oracle && cargo build --release", a.command)
        self.assertIn("native/rf1-dfg-oracle/Cargo.toml:2", a.source)
        self.assertIn("native/rf3-ocel-oracle/Cargo.toml:2", a.source)

    def test_env_action_from_fetch_env_reads(self):
        a = self.by_name["set oracle env"]
        self.assertEqual(a.env["RF3_ORACLE_BIN"], str(REPO / "native/rf3-ocel-oracle/target/release/rf3-ocel-oracle"))
        self.assertIn("test/beam4pm_rf3_ocel_test.exs:19 -> scripts/env/rust4pm_reactor_env.sh:21", a.source)
        self.assertIn("RF2_ORACLE_BIN", a.env)


class Plan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = d.observe(REPO)
        cls.actions = d.discover_actions(REPO)

    def test_from_deps_missing_mix_deps_get_precedes_mix_test(self):
        s = self.state.with_(ELIXIR_DEPS_READY=False, MIX_TEST_RUNNABLE=False)
        p = d.plan(s, GOAL, self.actions)
        self.assertNotIsInstance(p, d.NoPlanFound, p)
        n = _names(p)
        self.assertIn("mix deps.get", n)
        self.assertLess(n.index("mix deps.get"), n.index("mix test"))

    def test_from_current_real_state_oracle_build_and_env_precede_mix_test(self):
        p = d.plan(self.state, GOAL, self.actions)
        self.assertNotIsInstance(p, d.NoPlanFound, p)
        n = _names(p)
        self.assertEqual(n[-1], "mix test")
        if not self.state.get("NATIVE_ORACLES_BUILT"):
            self.assertLess(n.index("cargo build --release (oracles)"), n.index("mix test"))
        if not self.state.get("ORACLE_ENV_SET"):
            self.assertLess(n.index("set oracle env"), n.index("mix test"))
        self.assertNotIn("mix deps.get", n)  # deps already real on disk

    def test_from_empty_state_full_chain_is_ordered(self):
        s = d.WorldState({k: False for k in d.STAGES}, {}, str(REPO))
        p = d.plan(s, GOAL, self.actions)
        n = _names(p)
        self.assertEqual(n[0], "submodules")
        self.assertEqual(n[-1], "mix test")
        self.assertLess(n.index("mix deps.get"), n.index("cargo build --release (oracles)"))

    def test_no_plan_found_is_typed_and_names_missing_transition(self):
        s = self.state.with_(NATIVE_ORACLES_BUILT=False)
        acts = [a for a in self.actions if a.name != "cargo build --release (oracles)"]
        p = d.plan(s, GOAL, acts)
        self.assertIsInstance(p, d.NoPlanFound)
        self.assertEqual(p.missing_transition, "NATIVE_ORACLES_BUILT")

    def test_plan_receipt_through_shared_ocel_emitter(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "beam4pm.ocel.json"
            rep = d.emit_receipt(self.state, d.plan(self.state, GOAL, self.actions), out)
            log = json.loads(out.read_text())
            self.assertEqual(rep["duplicate_ids"], 0)
            self.assertEqual(rep["dangling_refs"], 0)
            self.assertEqual([e["type"] for e in log["events"]], ["WorldStateObserved", "PlanProduced"])


if __name__ == "__main__":
    unittest.main()
