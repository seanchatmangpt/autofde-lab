#!/usr/bin/env python3
"""Chicago-style tests for falsifier.py: real OCEL files on disk, real
validate.py, state assertions on the returned closure dicts. No mocks.

Fixtures are derived from the real run log by copying it and applying
minimal, explicit edits (a falsifier that cannot flip must not be trusted).
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import falsifier as F  # noqa: E402


def _load():
    with open(F.DEFAULT_RUN) as fh:
        return json.load(fh)


def _write(tmp, raw, name):
    p = os.path.join(tmp, name)
    with open(p, "w") as fh:
        json.dump(raw, fh)
    return p


class FalsifierOnRealLog(unittest.TestCase):
    def setUp(self):
        self.log = F.Log(F.DEFAULT_RUN)

    def test_real_log_verdicts(self):
        self.assertEqual(F.check_claude_telemetry(self.log)["status"], "ALIVE")
        self.assertEqual(F.check_planner_loop(self.log)["status"], "BLOCKED[NO_TYPED_REFUSAL_PATH]")
        self.assertEqual(F.check_native_bootstrap(self.log, F.DEFAULT_NATIVE)["status"],
                         "BLOCKED[SOLVER_IMPLEMENTATION_ATTR_MISSING]")
        self.assertEqual(F.check_control_invariant(self.log)["status"], "BLOCKED[HEARTBEAT_SPAN_LT_300S]")
        self.assertEqual(len(F.find_full_chains(self.log)), 3)


class FalsifierFlips(unittest.TestCase):
    """Each edit to a real copy must flip exactly the closure it targets."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))
        self.raw = _load()

    def _log(self, raw, name="edited.ocel.json"):
        return F.Log(_write(self.tmp, raw, name))

    def test_adding_typed_refusal_makes_planner_loop_alive(self):
        raw = copy.deepcopy(self.raw)
        base = next(e for e in raw["events"] if e["type"] == "AuthorityGranted")
        ref = copy.deepcopy(base)
        ref["id"], ref["type"] = "ev:authority-refused:test", "AuthorityRefused"
        # refuse a distinct action object that is never started
        act = copy.deepcopy(next(o for o in raw["objects"] if o["type"] == "Action"))
        act["id"] = "action:test:refused"
        raw["objects"].append(act)
        for r in ref["relationships"]:
            if r["qualifier"] == "subject":
                r["objectId"] = act["id"]
        raw["events"].append(ref)
        self.assertEqual(F.check_planner_loop(self._log(raw))["status"], "ALIVE")

    def test_action_started_after_authority_refused_is_blocked(self):
        raw = copy.deepcopy(self.raw)
        ae = next(e for e in raw["events"] if e["type"] == "AuthorityGranted")
        ref = copy.deepcopy(ae)
        ref["id"], ref["type"] = "ev:authority-refused:test", "AuthorityRefused"
        # place refusal 1ms after evaluation, before ActionStarted of same action
        t = F.parse_time(ae["time"]) + timedelta(milliseconds=1)
        ref["time"] = t.isoformat()
        raw["events"].append(ref)
        self.assertEqual(F.check_planner_loop(self._log(raw))["status"],
                         "BLOCKED[ACTION_STARTED_AFTER_AUTHORITY_REFUSED]")

    def test_prediction_frozen_after_action_started_breaks_chain(self):
        raw = copy.deepcopy(self.raw)
        for e in raw["events"]:
            if e["type"] == "PredictionFrozen":
                e["time"] = (F.parse_time(e["time"]) + timedelta(seconds=3600)).isoformat()
        self.assertEqual(F.check_planner_loop(self._log(raw))["status"], "BLOCKED[NO_FULL_LINKED_CHAIN]")

    def test_native_attribute_promotes_bootstrap(self):
        raw = copy.deepcopy(self.raw)
        for ot in raw["objectTypes"]:
            if ot["name"] == "SolverImplementation":
                ot["attributes"].append({"name": "implementation", "type": "string"})
        for o in raw["objects"]:
            if o["type"] == "SolverImplementation":
                o["attributes"].append({"name": "implementation", "value": "native", "time": o["attributes"][0]["time"]})
        p = _write(self.tmp, raw, "native.ocel.json")
        self.assertEqual(F.run_validate(p), {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
        self.assertEqual(F.check_native_bootstrap(F.Log(p), F.DEFAULT_NATIVE)["status"], "ALIVE")

    def test_heartbeat_leak_and_span(self):
        raw = copy.deepcopy(self.raw)
        hbs = [e for e in raw["events"] if e["type"] == "HeartbeatObserved"]
        hbs[-1]["time"] = (F.parse_time(hbs[0]["time"]) + timedelta(seconds=301)).isoformat()
        self.assertEqual(F.check_control_invariant(self._log(raw))["status"], "ALIVE")
        leak = copy.deepcopy(hbs[0])
        leak["id"], leak["type"] = "ev:leak:test", "ActionStarted"
        raw["events"].append(leak)
        self.assertEqual(F.check_control_invariant(self._log(raw))["status"],
                         "BLOCKED[HEARTBEAT_EPISODE_LEAKED_PRODUCTION]")

    def test_telemetry_without_invokes_is_blocked(self):
        raw = copy.deepcopy(self.raw)
        for e in raw["events"]:
            if e["type"].startswith("Claude."):
                e["relationships"] = [r for r in e["relationships"] if r["qualifier"] != "invokes"]
        self.assertEqual(F.check_claude_telemetry(self._log(raw))["status"],
                         "BLOCKED[NO_CLAUDE_TOOL_INVOCATION_LINKED]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
