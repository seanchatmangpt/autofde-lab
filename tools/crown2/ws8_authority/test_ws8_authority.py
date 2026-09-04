#!/usr/bin/env python3
"""Chicago-style tests: real filesystem, real subprocess, real emitter, real validator."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authority as A  # noqa: E402
import check_ocel_authority as C  # noqa: E402

OCEL_V2 = os.path.normpath(os.path.join(HERE, "..", "..", "ocel_v2"))
EMITTER = os.path.join(OCEL_V2, "emitter.py")
VALIDATE = os.path.join(OCEL_V2, "validate.py")
CHECKER = os.path.join(HERE, "check_ocel_authority.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def touch_action(marker: str, name: str = "touch-marker") -> dict:
    return {"name": name, "argv": ["/usr/bin/touch", marker]}


class PolicyTable(unittest.TestCase):
    def d(self, **kw):
        base = dict(action={"name": "x", "argv": ["true"]}, reversibility="REVERSIBLE", blast_radius="NONE",
                    authority_requirement="NONE", subject_identity="sac", standing=1.0,
                    evidence_confidence=0.9, world={"min_confidence": 0.5})
        base.update(kw)
        return A.decide(**base)

    def test_reversible_non_consequential_granted(self):
        self.assertEqual(self.d().verdict, "GRANTED")

    def test_network_fetch_only_if_reversible(self):
        self.assertEqual(self.d(blast_radius="NETWORK_FETCH").verdict, "GRANTED")
        self.assertEqual(self.d(blast_radius="NETWORK_FETCH", reversibility="IRREVERSIBLE").verdict,
                         "REFUSED:IRREVERSIBLE_NETWORK_FETCH")

    def test_consequential_escalates(self):
        self.assertEqual(self.d(blast_radius="CONSEQUENTIAL").verdict, "ESCALATE:HUMAN_CONFIRMATION")

    def test_destructive_refused_or_escalates(self):
        self.assertEqual(self.d(blast_radius="DESTRUCTIVE").verdict, "REFUSED:DESTRUCTIVE")
        self.assertEqual(self.d(blast_radius="DESTRUCTIVE", authority_requirement="ESCALATABLE").verdict,
                         "ESCALATE:HUMAN_CONFIRMATION")

    def test_unknown_subject_refused_before_anything_else(self):
        for ident in (None, "", "   "):
            self.assertEqual(self.d(subject_identity=ident, blast_radius="DESTRUCTIVE").verdict,
                             "REFUSED:SUBJECT_UNBOUND")

    def test_standing_below_threshold(self):
        self.assertEqual(self.d(authority_requirement="OWNER", standing=0.79).verdict,
                         "REFUSED:INSUFFICIENT_STANDING")
        self.assertEqual(self.d(authority_requirement="OWNER", standing=0.8).verdict, "GRANTED")

    def test_low_evidence_escalates(self):
        self.assertEqual(self.d(evidence_confidence=0.1).verdict, "ESCALATE:EVIDENCE_INSUFFICIENT")

    def test_granted_carries_token_refused_does_not(self):
        self.assertIsNotNone(self.d().grant_token)
        self.assertIsNone(self.d(blast_radius="DESTRUCTIVE").grant_token)


class PhysicalGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ws8_")
        self.marker = os.path.join(self.tmp, "MARKER")

    def test_refused_destructive_leaves_filesystem_unchanged(self):
        action = touch_action(self.marker)
        dec = A.decide(action, "IRREVERSIBLE", "DESTRUCTIVE", "OWNER", "sac", 1.0, 0.9)
        self.assertEqual(dec.verdict, "REFUSED:DESTRUCTIVE")
        before = sorted(os.listdir(self.tmp))
        res = A.execute(action, dec)
        self.assertFalse(res.ran)
        self.assertEqual(res.reason, "REFUSED:DESTRUCTIVE")
        self.assertEqual(sorted(os.listdir(self.tmp)), before)
        self.assertFalse(os.path.exists(self.marker))

    def test_granted_actually_runs_subprocess(self):
        action = touch_action(self.marker)
        dec = A.decide(action, "REVERSIBLE", "LOCAL", "NONE", "sac", 1.0, 0.9)
        res = A.execute(action, dec)
        self.assertTrue(res.ran)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(self.marker))

    def test_forged_granted_decision_cannot_run(self):
        action = touch_action(self.marker)
        forged = A.Decision(verdict="GRANTED", rule="forged", action_digest=A.action_digest(action),
                            rationale="", grant_token="deadbeef" * 8)
        res = A.execute(action, forged)
        self.assertFalse(res.ran)
        self.assertEqual(res.reason, "REFUSED:FORGED_GRANT")
        self.assertFalse(os.path.exists(self.marker))

    def test_grant_for_other_action_cannot_be_reused(self):
        benign = {"name": "true", "argv": ["/usr/bin/true"]}
        dec = A.decide(benign, "REVERSIBLE", "NONE", "NONE", "sac", 1.0, 0.9)
        self.assertTrue(dec.granted)
        res = A.execute(touch_action(self.marker), dec)
        self.assertFalse(res.ran)
        self.assertIn("ACTION_MISMATCH", res.reason)
        self.assertFalse(os.path.exists(self.marker))

    def test_non_decision_raises(self):
        with self.assertRaises(A.AuthorityViolation):
            A.execute(touch_action(self.marker), "GRANTED")  # type: ignore[arg-type]
        self.assertFalse(os.path.exists(self.marker))


class OcelEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ws8_ocel_")
        self.ocel = os.path.join(self.tmp, "ws8.ocel.json")
        r = subprocess.run([sys.executable, EMITTER, "init", self.ocel], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _validate(self):
        r = subprocess.run([sys.executable, VALIDATE, self.ocel], capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def _check(self):
        r = subprocess.run([sys.executable, CHECKER, self.ocel], capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def test_honest_run_emits_and_validates_and_checker_green(self):
        marker = os.path.join(self.tmp, "M")
        refused_action = touch_action(marker, "rm-ish")
        d1 = A.decide(refused_action, "IRREVERSIBLE", "DESTRUCTIVE", "OWNER", "sac", 1.0, 0.9)
        r1 = A.run_with_authority(self.ocel, "act-destructive", refused_action, d1, 1)
        self.assertFalse(r1.ran)
        self.assertFalse(os.path.exists(marker))
        ok_action = touch_action(marker, "touch-ok")
        d2 = A.decide(ok_action, "REVERSIBLE", "LOCAL", "NONE", "sac", 1.0, 0.9)
        r2 = A.run_with_authority(self.ocel, "act-ok", ok_action, d2, 1)
        self.assertTrue(r2.ran)
        self.assertTrue(os.path.exists(marker))
        code, summary = self._validate()
        self.assertEqual((code, summary), (0, {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0}))
        with open(self.ocel, encoding="utf-8") as f:
            types = [e["type"] for e in json.load(f)["events"]]
        self.assertEqual(types, ["AuthorityEvaluated", "AuthorityRefused", "AuthorityEvaluated",
                                 "AuthorityGranted", "ActionStarted"])
        code, res = self._check()
        self.assertEqual(code, 0)
        self.assertEqual(res, {"violations": [], "actions_checked": 2})

    def test_refused_then_started_is_detected_as_violation(self):
        em = _load(EMITTER, "em")
        action = touch_action(os.path.join(self.tmp, "M"), "bad")
        d = A.decide(action, "IRREVERSIBLE", "DESTRUCTIVE", "OWNER", "sac", 1.0, 0.9)
        A.emit_decision(self.ocel, "act-lying", action, d, 1)
        # Simulate a lying log: a REFUSED line followed by the action having started anyway.
        em.add_event(self.ocel, "ActionStarted", "act-lying:started:1", {"name": "bad"}, ["act-lying"])
        code, summary = self._validate()
        self.assertEqual(code, 0, summary)  # structurally valid OCEL ...
        code, res = self._check()          # ... but semantically a failed gate
        self.assertEqual(code, 1)
        self.assertEqual(res["violations"], [{"action": "act-lying", "refused_event": "act-lying:refused:1",
                                              "started_event": "act-lying:started:1"}])

    def test_refused_then_granted_then_started_is_not_violation(self):
        action = {"name": "later-ok", "argv": ["/usr/bin/true"]}
        d1 = A.decide(action, "IRREVERSIBLE", "DESTRUCTIVE", "OWNER", "sac", 1.0, 0.9)
        A.emit_decision(self.ocel, "act-later", action, d1, 1)
        d2 = A.decide(action, "REVERSIBLE", "NONE", "NONE", "sac", 1.0, 0.9)
        r = A.run_with_authority(self.ocel, "act-later", action, d2, 2)
        self.assertTrue(r.ran)
        self.assertEqual(self._check(), (0, {"violations": [], "actions_checked": 1}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
