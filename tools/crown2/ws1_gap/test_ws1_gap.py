#!/usr/bin/env python3
"""
test_ws1_gap.py — Chicago-style tests for the WS1 NO_PLAN_FOUND interceptor.

Real collaborators only: real fixture JSON on disk, the real classify(),
the real tools/ocel_v2/emitter.py writing a real OCEL file, and the real
validate.py run as a subprocess. No mocks.

Run: python3 -m unittest -v tools/crown2/ws1_gap/test_ws1_gap.py
  or: cd tools/crown2/ws1_gap && python3 -m unittest -v test_ws1_gap
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "ocel_v2")))

from gap import BEAM4PM_STAGES, GapDiagnosis, GapType, NoPlanFound, classify, classify_fixture  # noqa: E402
import emit_ocel  # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(HERE, "fixtures", "*.json")))
REQUIRED_STAGES = (
    "SUBMODULES_READY", "SYNC_READY", "LINT_TRUTH_READY", "RUST_TESTS_READY",
    "ELIXIR_DEPS_READY", "MIX_TEST_RUNNABLE", "NATIVE_ORACLES_BUILT",
    "ORACLE_ENV_SET", "MIX_TEST_GREEN", "QUALIFICATION_COMPLETE",
)
REQUIRED_STATE_TAGS = (
    "dependency-declared-but-absent", "command-undocumented", "command-only-in-ci",
    "command-only-in-generated-code", "command-requires-credential", "command-destructive",
    "command-only-in-marketplace-pack", "two-possible-actions", "goal-contradictory",
    "sensor-missing", "sensor-stale", "authority-missing", "qualification-env-absent",
)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestGapTypeEnum(unittest.TestCase):
    def test_exact_membership(self):
        self.assertEqual(
            {g.value for g in GapType},
            {"GOAL_IMPOSSIBLE", "OBSERVATION_GAP", "ACTION_DISCOVERY_GAP", "ACTION_GAP",
             "MANUFACTURING_GAP", "QUALIFICATION_GAP", "AUTHORITY_GAP", "KNOWLEDGE_GAP",
             "NOVEL_INFORMATION_GAP"},
        )

    def test_stages_present(self):
        for s in REQUIRED_STAGES:
            self.assertIn(s, BEAM4PM_STAGES)


class TestFixturesClassify(unittest.TestCase):
    def test_fixtures_exist(self):
        self.assertGreaterEqual(len(FIXTURES), 18)

    def test_every_class_has_a_fixture(self):
        covered = {_load(p)["expected_gap_type"] for p in FIXTURES}
        self.assertEqual(covered, {g.value for g in GapType})

    def test_every_required_real_shaped_state_has_a_fixture(self):
        tags = set()
        for p in FIXTURES:
            tags.update(_load(p).get("tags", []))
        self.assertTrue(set(REQUIRED_STATE_TAGS) <= tags, set(REQUIRED_STATE_TAGS) - tags)

    def test_each_fixture_classifies_as_expected(self):
        for p in FIXTURES:
            fx = _load(p)
            with self.subTest(fixture=fx["name"]):
                d = classify_fixture(fx)
                self.assertIsInstance(d, GapDiagnosis)
                self.assertEqual(d.gap_type.value, fx["expected_gap_type"])
                self.assertTrue(d.receipt_digest.startswith("sha256:"))
                self.assertEqual(d.receipt_digest, d.compute_digest())
                self.assertTrue(d.supporting_observations)

    def test_four_canonical_dead_ends_classify_differently(self):
        got = {}
        for p in FIXTURES:
            fx = _load(p)
            if "canonical" in fx.get("tags", []):
                got[fx["name"]] = classify_fixture(fx).gap_type
        self.assertEqual(len(got), 4, got)
        self.assertEqual(len(set(got.values())), 4, got)
        self.assertEqual(got["canonical_impossible_goal"], GapType.GOAL_IMPOSSIBLE)
        self.assertEqual(got["canonical_hidden_repo_action_mix_deps_get"], GapType.ACTION_DISCOVERY_GAP)
        self.assertEqual(got["canonical_genuinely_absent_action"], GapType.MANUFACTURING_GAP)
        self.assertEqual(got["canonical_disallowed_consequential"], GapType.AUTHORITY_GAP)

    def test_digest_is_deterministic_and_content_bound(self):
        fx = _load(os.path.join(HERE, "fixtures", "canonical_hidden_repo_action_mix_deps_get.json"))
        a, b = classify_fixture(fx), classify_fixture(fx)
        self.assertEqual(a.receipt_digest, b.receipt_digest)
        fx2 = json.loads(json.dumps(fx))
        fx2["no_plan"]["planner"] = "other"
        self.assertNotEqual(classify_fixture(fx2).receipt_digest, a.receipt_digest)

    def test_rejects_non_no_plan_status(self):
        np_ = NoPlanFound(goal={}, initial_world_state={}, planner="x", status="PLAN_FOUND")
        with self.assertRaises(ValueError):
            classify(np_, [], [], {}, [], [])


class TestOcelEmission(unittest.TestCase):
    def test_emit_and_validate_green(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "ws1.ocel.json")
            rows = emit_ocel.emit_all(out)
            self.assertEqual(len(rows), len(FIXTURES))
            log = _load(out)
            evs = [e for e in log["events"] if e["type"] == "GapDiagnosed"]
            self.assertEqual(len(evs), len(FIXTURES))
            for e in evs:
                attrs = {a["name"]: a["value"] for a in e["attributes"]}
                self.assertIn(attrs["gap_type"], {g.value for g in GapType})
                self.assertEqual(json.loads(attrs["diagnosis_json"])["receipt_digest"], attrs["receipt_digest"])
            validate = os.path.abspath(os.path.join(HERE, "..", "..", "ocel_v2", "validate.py"))
            proc = subprocess.run([sys.executable, validate, out], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(proc.stdout),
                             {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})

    def test_bootstrap_still_validates(self):
        ocel = os.path.abspath(os.path.join(HERE, "..", "..", "ocel_v2"))
        proc = subprocess.run([sys.executable, os.path.join(ocel, "validate.py"),
                               os.path.join(ocel, "bootstrap.ocel.json")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
