#!/usr/bin/env python3
"""Chicago-style tests for crown2_runner.py: real emitter, real hook adapter,
real subprocesses, real files -- assertions on resulting state only.

    cd /Users/sac/crown-2-integration/autofde-lab
    python3 -m unittest tools/crown2/run/test_crown2_runner.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "ocel_v2"))
import crown2_runner as cr  # noqa: E402
import check_run_invariants as inv  # noqa: E402
import emitter  # noqa: E402

dom = cr.dom


def _events(runner: cr.Runner, etype: str | None = None) -> list[dict]:
    log = runner.sink.read()
    return [e for e in log["events"] if etype is None or e["type"] == etype]


class RunnerParts(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("CROWN2_TEST_TMP") or None)
        self.out = Path(self.tmp.name) / "run"
        self.r = cr.Runner(out_dir=self.out, floor_seconds=1.0)
        self.r.emit_composition()
        self.ep = "episode:test"
        self.r.sink.obj("ProcessEpisode", self.ep, {"label": "test", "started_at": cr.now_iso()})
        self.state = dom.WorldState(stages={s: False for s in dom.STAGES}, evidence={}, repo=str(self.out))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _action(self, name: str, command: str, reversible=True, consequential=False, env=None) -> dom.Action:
        return dom.Action(name, command, str(self.out), {}, {"SUBMODULES_READY": True}, reversible, consequential, "test:1", env or {})

    def test_sink_created_first_and_composition_carries_real_shas(self) -> None:
        log = self.r.sink.read()
        self.assertEqual(log["events"][0]["type"], "CompositionCreated")
        rc = json.loads(cr.COMPOSITION_RECEIPT.read_text())
        shas = {a["value"] for o in log["objects"] if o["type"] == "Commit" for a in o["attributes"] if a["name"] == "sha"}
        for c in rc["components"]:
            self.assertIn(c["composed_head_sha"], shas)
            self.assertIn(c["pr_head_sha"], shas)

    def test_refused_consequential_action_is_physically_not_executed(self) -> None:
        marker = self.out / "SHOULD_NOT_EXIST"
        a = self._action("dangerous", f"touch {marker}", reversible=False, consequential=True)
        self.r.sink.obj("Action", "action:t:01", {"name": a.name, "kind": "consequential", "args_json": {}})
        granted = self.r.authority(a, "action:t:01", self.ep)
        self.assertFalse(granted)
        self.assertFalse(marker.exists())
        self.assertEqual(len(_events(self.r, "AuthorityRefused")), 1)
        self.assertEqual(len(_events(self.r, "AuthorityGranted")), 0)

    def test_denylist_refuses_even_reversible_action(self) -> None:
        a = self._action("push", "echo ok && git push origin main")
        self.r.sink.obj("Action", "action:t:02", {"name": a.name, "kind": "reversible", "args_json": {}})
        self.assertFalse(self.r.authority(a, "action:t:02", self.ep))
        rationale = _events(self.r, "AuthorityRefused")[0]["attributes"][0]["value"]
        self.assertIn("git push", rationale)

    def test_prediction_is_on_disk_with_matching_sha_before_any_action(self) -> None:
        a = self._action("noop", "true")
        self.r.sink.obj("Action", "action:t:03", {"name": a.name, "kind": "reversible", "args_json": {}})
        pr_id, predicted, digest = self.r.freeze_prediction(a, self.state, 1, 1, "action:t:03", self.ep)
        files = list((self.out / "predictions").glob("001-01-*.json"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text().rstrip("\n")
        self.assertEqual(cr.sha256_text(text), digest)
        self.assertEqual(json.loads(text)["predicted_post_state"]["SUBMODULES_READY"], True)
        self.assertEqual(predicted["SUBMODULES_READY"], True)
        self.assertEqual(len(_events(self.r, "PredictionFrozen")), 1)

    def test_execute_runs_real_command_and_hooks_carry_invokes_qualifier(self) -> None:
        marker = self.out / "RAN"
        a = self._action("touch", f"touch {marker} && echo done")
        self.r.sink.obj("Action", "action:t:04", {"name": a.name, "kind": "reversible", "args_json": {}})
        ok, summary = self.r.execute(a, "action:t:04", self.ep, 1, 1)
        self.assertTrue(ok)
        self.assertTrue(marker.exists())
        self.assertIn("exit=0", summary)
        pre = _events(self.r, "Claude.PreToolUse")
        post = _events(self.r, "Claude.PostToolUse")
        self.assertEqual((len(pre), len(post)), (1, 1))
        for e in pre + post:
            rels = {r["objectId"]: r["qualifier"] for r in e["relationships"]}
            self.assertEqual(rels["action:t:04"], "invokes")
            self.assertIn(f"ClaudeSession:{self.r.session_id}", rels)
        post_attrs = {x["name"]: x["value"] for x in post[0]["attributes"]}
        self.assertFalse(post_attrs["is_error"])
        self.assertEqual(json.loads(post_attrs["tool_response"])["exit_code"], 0)
        self.assertEqual(len(_events(self.r, "ActionCompleted")), 1)
        # the action log is a real file with the real exit line
        logs = list((self.out / "logs").glob("action-001-01-*.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn("EXIT:0", logs[0].read_text())

    def test_execute_failing_command_emits_action_failed_and_error_hook(self) -> None:
        a = self._action("fail", "echo boom >&2; exit 3")
        self.r.sink.obj("Action", "action:t:05", {"name": a.name, "kind": "reversible", "args_json": {}})
        ok, summary = self.r.execute(a, "action:t:05", self.ep, 1, 2)
        self.assertFalse(ok)
        self.assertIn("exit=3", summary)
        self.assertEqual(len(_events(self.r, "ActionFailed")), 1)
        post_attrs = {x["name"]: x["value"] for x in _events(self.r, "Claude.PostToolUse")[0]["attributes"]}
        self.assertTrue(post_attrs["is_error"])

    def test_env_action_persists_into_runner_env_for_later_subprocesses(self) -> None:
        a = self._action("set env", 'export CROWN2_TEST_VAR="yes"', env={"CROWN2_TEST_VAR": "yes"})
        self.r.sink.obj("Action", "action:t:06", {"name": a.name, "kind": "reversible", "args_json": {}})
        ok, _ = self.r.execute(a, "action:t:06", self.ep, 1, 3)
        self.assertTrue(ok)
        p = subprocess.run(["bash", "-c", "echo $CROWN2_TEST_VAR"], env=self.r.run_env, capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), "yes")

    def test_heartbeat_episode_emits_only_heartbeats_with_validate_summary(self) -> None:
        t = threading.Thread(target=self.r.heartbeat)
        self.r.stop.set()  # one beat then exit
        t.start()
        t.join(30)
        hb = [e for e in self.r.sink.read()["events"] if any(r["objectId"] == "episode:control-heartbeat" for r in e["relationships"])]
        self.assertEqual({e["type"] for e in hb}, {"HeartbeatObserved"})
        attrs = {x["name"]: x["value"] for x in hb[0]["attributes"]}
        self.assertEqual(json.loads(attrs["validate_json"]), {"strict_type_mismatches": 0, "duplicate_ids": 0, "dangling_refs": 0})
        self.assertGreater(attrs["events_so_far"], 0)

    def test_native_plan_is_real_astar_over_observed_actions(self) -> None:
        if not cr.VENV_PY.exists():
            self.skipTest(f"{cr.VENV_PY} missing: Task C native bootstrap not present on this machine")
        self.r.sink.obj("SolverImplementation", "solver:astar-native-hub", {"name": "Astar", "kind": "cpp", "version": "test"})
        actions = dom.discover_actions(cr.BEAM4PM)
        st = dom.WorldState(stages={s: s in ("SUBMODULES_READY", "SYNC_READY", "LINT_TRUTH_READY", "RUST_TESTS_READY") for s in dom.STAGES}, evidence={}, repo=str(cr.BEAM4PM))
        plan, detail = self.r.native_plan(st, actions, self.ep)
        self.assertIsNotNone(plan, detail)
        names = [a.name for a in plan]
        self.assertEqual(names[-1], "mix test")
        self.assertLess(names.index("mix deps.get"), names.index("mix compile (test)"))
        self.assertLess(names.index("cargo build --release (oracles)"), names.index("set oracle env"))
        self.assertEqual(json.loads(detail)["implementation"], "native")
        self.assertEqual(len(_events(self.r, "PlannerInvoked")), 1)


class InvariantsChecker(unittest.TestCase):
    def test_catches_action_started_without_prediction_or_authority(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sink = Path(d) / "x.ocel.json"
            emitter.init(str(sink))
            emitter.add_object(str(sink), "Composition", "c", {"name": "x"})
            emitter.add_event(str(sink), "CompositionCreated", "e0", {"name": "x"}, ["c"])
            emitter.add_object(str(sink), "Action", "action:1", {"name": "a", "kind": "k", "args_json": {}})
            emitter.add_event(str(sink), "ActionStarted", "e1", {"name": "a"}, ["action:1"])
            emitter.add_object(str(sink), "ProcessEpisode", "episode:control-heartbeat", {"label": "hb"})
            emitter.add_event(str(sink), "LoopClosed", "e2", {"label": "leak"}, ["episode:control-heartbeat"])
            emitter.add_event(str(sink), "PlanProduced", "e3", {"summary": "s", "cost_estimate": 1.0}, ["action:1"])
            v = inv.check(sink, None)
        codes = {x.split(":")[0] for x in v}
        self.assertEqual(codes, {"R2", "R3", "R4", "R5", "R6", "R7", "R10"})


class EmitterQualifiers(unittest.TestCase):
    def test_default_qualifier_unchanged_and_explicit_qualifier_lands(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sink = Path(d) / "q.ocel.json"
            emitter.init(str(sink))
            emitter.add_object(str(sink), "Action", "a", {"name": "n", "kind": "k", "args_json": {}})
            emitter.add_event(str(sink), "ActionStarted", "e1", {"name": "n"}, ["a"])
            emitter.add_event(str(sink), "ActionStarted", "e2", {"name": "n"}, ["a"], qualifiers={"a": "invokes"})
            ev = {e["id"]: e for e in json.loads(sink.read_text())["events"]}
        self.assertEqual(ev["e1"]["relationships"][0]["qualifier"], "")
        self.assertEqual(ev["e2"]["relationships"][0]["qualifier"], "invokes")


if __name__ == "__main__":
    unittest.main()
