#!/usr/bin/env python3
"""crown2_runner.py -- Crown-2 Task H: the real closed-loop runner.

Append-only OCEL 2.0 sink (tools/ocel_v2/emitter.py) created BEFORE anything
else; two concurrent ProcessEpisode objects run for >= 300 monotonic seconds:

  episode:beam4pm-production
     observe (Task A observe(), real probes) -> PlannerInvoked (native hub A*,
     tools/crown2/native/native_plan.py under .venv python; NO fallback) ->
     PlanProduced | PlanRefused -> per action: PredictionFrozen (predicted
     post-state + sha256 written to disk BEFORE acting) -> AuthorityEvaluated
     (+ AuthorityGranted | AuthorityRefused; refused actions are physically
     not executed) -> Claude.PreToolUse (real hook-to-ocel.py build_ocel_event)
     -> ActionStarted -> real command in /Users/sac/crown-2-integration/beam4pm
     -> ActionCompleted | ActionFailed -> Claude.PostToolUse ->
     WorldStateObserved -> QualificationObserved -> PredictionCompared ->
     ReceiptIssued -> LoopClosed | LoopBlocked; then observe-only 'steady'
     cycles until the 300s floor.
  episode:control-heartbeat
     every 10s: validate.py over the growing sink -> HeartbeatObserved.
     Emits no production event type (asserted at the end).

stdlib only. Never mutates prior OCEL artifacts (fresh sink, fresh log copies).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent.parent  # .../autofde-lab/tools
LAB = TOOLS.parent  # .../autofde-lab
INTEGRATION_ROOT = LAB.parent  # /Users/sac/crown-2-integration
BEAM4PM = INTEGRATION_ROOT / "beam4pm"
# Attempt 2 sink (attempt 1 at HERE/crown-run-v3.ocel.json is immutable).
SINK = HERE / "attempt2" / "crown-run-v3-attempt2.ocel.json"
TIMING = SINK.parent / "timing-receipt.json"
RUN_LOGS = SINK.parent / "logs"
PREDICTIONS = SINK.parent / "predictions"
COMPOSITION_RECEIPT = INTEGRATION_ROOT / "CompositionReceipt.json"
VENV_PY = LAB / ".venv" / "bin" / "python"
NATIVE_PLAN = TOOLS / "crown2" / "native" / "native_plan.py"
NATIVE_SOLVE_MIN = TOOLS / "crown2" / "native" / "native_solve_min.py"
HOOK_TO_OCEL = Path(os.path.expanduser("~/.claude/scripts/hook-to-ocel.py"))
FLOOR_SECONDS = float(os.environ.get("CROWN2_FLOOR_SECONDS", "300"))
# Attempt 2: both episodes must also span >= this many seconds of EVENT
# timestamps (first related event -> last related event), not wall-clock alone.
SPAN_SECONDS = float(os.environ.get("CROWN2_SPAN_SECONDS", "320"))
# Attempt 2 (a): a goal predicate no discovered action provides -> PlanRefused.
UNREACHABLE_GOAL_STAGE = "RELEASE_PUBLISHED"
HEARTBEAT_PERIOD = 10.0
STEADY_PERIOD = 15.0
ACTION_TIMEOUT = 1800

sys.path.insert(0, str(TOOLS / "ocel_v2"))
sys.path.insert(0, str(TOOLS / "crown2" / "domain"))
import emitter  # noqa: E402
import validate  # noqa: E402
import beam4pm_domain as dom  # noqa: E402

PRODUCTION_EVENT_TYPES = {
    "WorldStateObserved", "PlannerInvoked", "PlanProduced", "PlanRefused", "PredictionFrozen",
    "AuthorityEvaluated", "AuthorityGranted", "AuthorityRefused", "ActionStarted", "ActionCompleted",
    "ActionFailed", "ActionRefused", "QualificationObserved", "PredictionCompared", "ReceiptIssued",
    "LoopStarted", "LoopClosed", "LoopBlocked", "Claude.PreToolUse", "Claude.PostToolUse",
}

# Runner-level authority policy. Domain actions carry reversible/consequential
# flags discovered from the repo surface; this adds a command denylist that is
# refused regardless of what the domain says.
POLICY = {
    "name": "crown2-reversible-only",
    "grant_if": "action.reversible and not action.consequential and no denylist token in command",
    "denylist_tokens": ["git push", "git merge", "git reset", "git rebase", "rm -rf", "sudo", "ggen sync run"],
    "note": "refused actions are physically not executed; runner emits AuthorityRefused + ActionRefused + LoopBlocked",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def world_snapshot(repo: Path) -> dict:
    """Cheap, real fingerprint of the beam4pm worktree + its remote refs, used to
    prove a refused action was physically not executed (before == after)."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True).stdout
    lock = repo / "ggen.lock"
    return {
        "head": git("rev-parse", "HEAD").strip(),
        "status_porcelain": git("status", "--porcelain"),
        "remote_refs_sha256": sha256_text(git("for-each-ref", "refs/remotes", "--format=%(refname) %(objectname)")),
        "ggen_lock_exists": lock.exists(),
        "ggen_lock_sha256": sha256_text(lock.read_text(encoding="utf-8")) if lock.exists() else None,
        "taken_at": now_iso(),
    }


def load_hook_adapter():
    spec = importlib.util.spec_from_file_location("hook_to_ocel", str(HOOK_TO_OCEL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Sink:
    """Serialized, append-only writes through the shared emitter."""

    def __init__(self, path: Path):
        self.path = str(path)
        self.lock = threading.Lock()
        self.counter = 0
        self.known_objects: set[str] = set()
        with self.lock:
            emitter.init(self.path)

    def next_id(self, prefix: str) -> str:
        with self.lock:
            self.counter += 1
            return f"{prefix}:{self.counter:05d}"

    def obj(self, otype: str, oid: str, attrs: dict) -> str:
        with self.lock:
            if oid in self.known_objects:
                return oid
            emitter.add_object(self.path, otype, oid, attrs)
            self.known_objects.add(oid)
            return oid

    def ev(self, etype: str, eid: str, attrs: dict, rel: list[str], qual: dict[str, str] | None = None) -> str:
        with self.lock:
            emitter.add_event(self.path, etype, eid, attrs, rel, qualifiers=qual)
            return eid

    def read(self) -> dict:
        with self.lock:
            return emitter._read(self.path)


class Runner:
    def __init__(self, out_dir: Path = SINK.parent, floor_seconds: float = FLOOR_SECONDS, span_seconds: float = SPAN_SECONDS) -> None:
        self.t0 = time.monotonic()
        self.started_utc = now_iso()
        self.out_dir = Path(out_dir)
        self.floor = floor_seconds
        self.span = span_seconds
        self.non_execution_proof: dict = {}
        self.sink_path = self.out_dir / SINK.name
        self.timing_path = self.out_dir / TIMING.name
        self.run_logs = self.out_dir / "logs"
        self.predictions = self.out_dir / "predictions"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.run_logs.mkdir(exist_ok=True)
        self.predictions.mkdir(exist_ok=True)
        # Runner-owned copies of the real logs (never mutate the originals).
        for name in ("beam4pm-verify.log", "beam4pm-verify2.log"):
            src = INTEGRATION_ROOT / name
            if src.exists():
                shutil.copyfile(src, self.run_logs / name)
        self.sink = Sink(self.sink_path)  # created before anything else
        self.hook = load_hook_adapter()
        self.run_env = dict(os.environ)
        self.stop = threading.Event()
        self.production_done = threading.Event()
        self.hostname = socket.gethostname()
        self.session_id = f"crown2-runner-{uuid.uuid4().hex[:12]}"
        self.errors: list[str] = []
        self.counts = {
            "world_states_observed": 0, "plans_produced": 0, "plan_refusals": 0, "predictions_frozen": 0,
            "actions": 0, "actions_completed": 0, "actions_failed": 0, "actions_refused": 0,
            "prediction_comparisons": 0, "prediction_matches": 0, "loops_closed": 0, "loops_blocked": 0,
            "claude_hook_events": 0, "heartbeat_events": 0,
        }
        self.clock = threading.Lock()

    def bump(self, k: str, n: int = 1) -> None:
        with self.clock:
            self.counts[k] += n

    def episode_span(self, episode: str) -> float:
        """Seconds between the first and last EVENT timestamp relating `episode`."""
        times = [parse_iso(e["time"]) for e in self.sink.read()["events"]
                 if any(r["objectId"] == episode for r in e["relationships"])]
        return (max(times) - min(times)).total_seconds() if len(times) >= 2 else 0.0

    # ------------------------------------------------------------------ setup
    def emit_composition(self) -> None:
        rc = json.loads(COMPOSITION_RECEIPT.read_text(encoding="utf-8"))
        s = self.sink
        rel = []
        s.obj("Composition", "composition:crown-2", {
            "name": rc["crown_id"], "version": rc["receipt_version"],
            "description": f"CompositionReceipt created_at_utc={rc['created_at_utc']}; "
                           + "; ".join(f"{c['repo']}: base={c['canonical_base_sha']} pr#{c['pr_number']}={c['pr_head_sha']} composed={c['composed_head_sha']}" for c in rc["components"]),
        })
        rel.append("composition:crown-2")
        for c in rc["components"]:
            repo_id = f"repo:{c['repo']}"
            s.obj("Repository", repo_id, {"path": c["canonical_path"], "remote_url": c["remote"], "default_branch": "main"})
            wt_id = f"wt:{c['integration_branch']}"
            s.obj("Worktree", wt_id, {"path": c["integration_path"], "branch": c["integration_branch"], "base_ref": c["canonical_base_sha"]})
            for label, key in (("base", "canonical_base_sha"), ("pr-head", "pr_head_sha"), ("composed", "composed_head_sha")):
                cid = f"commit:{c['repo']}:{c[key][:12]}"
                s.obj("Commit", cid, {"sha": c[key], "message": f"{label} of {c['repo']} (PR #{c['pr_number']}); merge_strategy={c['merge_strategy']}"})
                rel.append(cid)
            rel += [repo_id, wt_id]
        # live SHAs of the worktrees actually used by this run
        for name, path in (("beam4pm", BEAM4PM), ("autofde-lab", LAB)):
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(path), capture_output=True, text=True).stdout.strip()
            cid = f"commit:{name}:live:{sha[:12]}"
            s.obj("Commit", cid, {"sha": sha, "message": f"HEAD of {path} at runner start", "committed_at": self.started_utc})
            rel.append(cid)
        s.obj("Policy", "policy:crown2", {"name": POLICY["name"], "policy_json": POLICY})
        s.obj("Domain", "domain:beam4pm", {"name": "beam4pm", "description": "beam4pm verify chain staged domain (Task A)"})
        s.obj("Machine", f"Machine:{self.hostname}", {"hostname": self.hostname})
        s.obj("ClaudeSession", f"ClaudeSession:{self.session_id}", {
            "session_url": f"runner://{self.session_id}", "model": "crown2_runner.py (synthetic hook payloads, real hook-to-ocel.py mapping)",
            "started_at": self.started_utc})
        s.ev("CompositionCreated", "ev:composition-created", {"name": rc["crown_id"]}, rel,
             {"composition:crown-2": "composition"})

    def check_native(self) -> dict:
        """Task C liveness: the native hub must import and solve, for real, now."""
        if not VENV_PY.exists():
            return {"alive": False, "reason": f"NATIVE_PLANNER_BOOTSTRAP: {VENV_PY} missing"}
        p = subprocess.run([str(VENV_PY), str(NATIVE_SOLVE_MIN)], cwd=str(LAB), capture_output=True, text=True, timeout=300)
        line = next((l for l in p.stdout.splitlines() if l.startswith("{")), "{}")
        try:
            summary = json.loads(line)
        except json.JSONDecodeError:
            summary = {}
        if p.returncode != 0 or not summary.get("ok"):
            return {"alive": False, "reason": f"NATIVE_PLANNER_BOOTSTRAP: native_solve_min exit={p.returncode} {p.stderr[-500:]}"}
        return {"alive": True, "summary": summary}

    # ---------------------------------------------------------- claude hooks
    def claude_hook(self, phase: str, action_id: str, command: str, cwd: str, description: str,
                    tool_use_id: str, response: dict | None = None) -> str:
        payload = {
            "session_id": self.session_id,
            "transcript_path": str(self.out_dir / f"{self.session_id}.jsonl"),
            "cwd": cwd,
            "hook_event_name": phase,
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": command, "description": description},
            "permission_mode": "default",
        }
        if response is not None:
            payload["tool_response"] = response
        ev = self.hook.build_ocel_event(payload)  # the real adapter
        attrs = {a["name"]: a["value"] for a in ev["attributes"]}
        rel, qual = [], {}
        for r in ev["relationships"]:
            oid = r["objectId"]
            if r["objectType"] == "ClaudeToolInvocation":
                self.sink.obj("ClaudeToolInvocation", oid, {
                    "tool_name": "Bash", "args_json": payload["tool_input"],
                    "result_summary": "pending" if response is None else f"exit_code={response.get('exit_code')}"})
            rel.append(oid)
            qual[oid] = r["qualifier"]
        rel.append(action_id)
        qual[action_id] = "invokes"
        e_attrs = {
            "hook_event_id": ev["id"], "hook_event_name": attrs["hook_event_name"], "tool_name": attrs["tool_name"],
            "cwd": attrs["cwd"], "permission_mode": attrs["permission_mode"], "tool_input": attrs["tool_input"],
        }
        if response is not None:
            e_attrs["tool_response"] = attrs["tool_response"]
            e_attrs["is_error"] = bool(attrs.get("is_error", False))
        self.sink.ev(ev["type"], f"ev:hook:{ev['id']}", e_attrs, rel, qual)
        self.bump("claude_hook_events")
        return ev["id"]

    # ------------------------------------------------------------- observe
    def observe(self, label: str, episode: str, cycle: int) -> tuple[dom.WorldState, str]:
        st = dom.observe(BEAM4PM, self.run_logs, self.run_env)
        ws_id = f"ws:{cycle:03d}:{label}"
        self.sink.obj("WorldState", ws_id, {"label": label, "observed_at": now_iso(), "state_json": st.to_json()})
        self.sink.ev("WorldStateObserved", self.sink.next_id("ev:observed"), {"label": label, "state_json": st.stages},
                     [ws_id, episode, "domain:beam4pm"], {ws_id: "observed", episode: "episode"})
        self.bump("world_states_observed")
        return st, ws_id

    def qualification(self, st: dom.WorldState, ws_id: str, episode: str, cycle: int) -> str:
        q_id = f"qual:{cycle:03d}"
        result = "QUALIFICATION_COMPLETE" if st.get("QUALIFICATION_COMPLETE") else "partial:" + ",".join(s for s in dom.STAGES if not st.get(s))
        self.sink.obj("QualificationRun", q_id, {"name": f"staged-qualification-{cycle:03d}", "result": result, "metrics_json": st.stages})
        self.sink.ev("QualificationObserved", self.sink.next_id("ev:qualification"), {"result": result, "metrics_json": st.stages},
                     [q_id, ws_id, episode], {q_id: "qualification", ws_id: "observed", episode: "episode"})
        return q_id

    # ---------------------------------------------------------------- plan
    def native_plan(self, st: dom.WorldState, actions: list[dom.Action], episode: str,
                    goal: dict[str, bool] | None = None) -> tuple[list[dom.Action] | None, str]:
        goal = goal or {"QUALIFICATION_COMPLETE": True}
        stages = dict(st.stages)
        for k in goal:  # a goal predicate outside the observed stages is simply False now
            stages.setdefault(k, False)
        spec = {"stages": stages, "goal": goal,
                "actions": [{"name": a.name, "preconditions": a.preconditions, "postconditions": a.postconditions} for a in actions]}
        self.sink.ev("PlannerInvoked", self.sink.next_id("ev:planner"), {"solver_name": "Astar(native _AStarSolver_) via native_plan.py"},
                     ["solver:astar-native-hub", episode, "domain:beam4pm"], {"solver:astar-native-hub": "solver", episode: "episode"})
        p = subprocess.run([str(VENV_PY), str(NATIVE_PLAN)], input=json.dumps(spec), cwd=str(LAB), capture_output=True, text=True, timeout=300)
        line = next((l for l in p.stdout.splitlines() if l.startswith("{")), "")
        if not line:
            return None, f"native planner produced no JSON (exit={p.returncode}): {p.stderr[-400:]}"
        out = json.loads(line)
        if not out.get("goal_reached"):
            # Typed non-progress: name the goal predicate no discovered action produces.
            producers = {k for a in actions for k, v in a.postconditions.items() if v}
            missing = [k for k, v in goal.items() if v and k not in producers] or [k for k, v in goal.items() if v and not stages.get(k)]
            typed = {"kind": "NO_PLAN_FOUND", "goal": goal, "missing_transition": missing[0] if missing else "?",
                     "unproduced_goal_predicates": missing, "producers": sorted(producers), "native": out}
            return None, f"NO_PLAN_FOUND missing_transition={typed['missing_transition']} " + json.dumps(typed, sort_keys=True)
        by_name = {a.name: a for a in actions}
        return [by_name[n] for n in out["plan"]], json.dumps(out, sort_keys=True)

    # ------------------------------------------------------------- execute
    def authority(self, a: dom.Action, action_id: str, episode: str) -> bool:
        denied = [t for t in POLICY["denylist_tokens"] if t in a.command]
        granted = a.reversible and not a.consequential and not denied
        rationale = (f"reversible={a.reversible} consequential={a.consequential} denylist_hits={denied} "
                     f"-> {'GRANTED' if granted else 'REFUSED'} under {POLICY['name']}")
        d_id = self.sink.next_id("authority")
        self.sink.obj("AuthorityDecision", d_id, {"decision": "GRANTED" if granted else "REFUSED", "rationale": rationale, "decided_at": now_iso()})
        rel = [d_id, action_id, "policy:crown2", episode]
        qual = {d_id: "decision", action_id: "subject", "policy:crown2": "policy", episode: "episode"}
        self.sink.ev("AuthorityEvaluated", self.sink.next_id("ev:authority-evaluated"), {"rationale": rationale}, rel, qual)
        self.sink.ev("AuthorityGranted" if granted else "AuthorityRefused", self.sink.next_id("ev:authority-decided"), {"rationale": rationale}, rel, qual)
        return granted

    def freeze_prediction(self, a: dom.Action, st: dom.WorldState, cycle: int, n: int, action_id: str, episode: str) -> tuple[str, dict, str]:
        predicted = a.apply(st).stages
        record = {"cycle": cycle, "step": n, "action": a.name, "command": a.command, "pre_state": st.stages,
                  "predicted_post_state": predicted, "frozen_at": now_iso()}
        text = json.dumps(record, sort_keys=True, separators=(",", ":"))
        digest = sha256_text(text)
        path = self.predictions / f"{cycle:03d}-{n:02d}-{digest[:12]}.json"
        with open(path, "w", encoding="utf-8") as f:  # on disk + fsync'd BEFORE any action runs
            f.write(text + "\n")
            f.flush()
            os.fsync(f.fileno())
        pr_id = f"prediction:{cycle:03d}:{n:02d}"
        self.sink.obj("PredictionReceipt", pr_id, {"prediction_json": {"path": str(path), "sha256": digest, "predicted_post_state": predicted},
                                                   "confidence": 1.0, "frozen_at": record["frozen_at"]})
        self.sink.ev("PredictionFrozen", self.sink.next_id("ev:prediction-frozen"), {"confidence": 1.0},
                     [pr_id, action_id, episode], {pr_id: "prediction", action_id: "predicts", episode: "episode"})
        self.bump("predictions_frozen")
        return pr_id, predicted, digest

    def execute(self, a: dom.Action, action_id: str, episode: str, cycle: int, n: int) -> tuple[bool, str]:
        tool_use_id = f"toolu_{uuid.uuid4().hex[:16]}"
        self.claude_hook("PreToolUse", action_id, a.command, a.cwd, f"crown2 cycle {cycle} step {n}: {a.name}", tool_use_id)
        self.sink.ev("ActionStarted", self.sink.next_id("ev:action-started"), {"name": a.name}, [action_id, episode], {action_id: "action", episode: "episode"})
        self.bump("actions")
        log_name = "beam4pm-verify2.log" if a.name == "mix test" else f"action-{cycle:03d}-{n:02d}-{a.name.split()[0]}.log"
        log_path = self.run_logs / log_name
        t = time.monotonic()
        try:
            p = subprocess.run(["bash", "-c", a.command], cwd=a.cwd, env=self.run_env, capture_output=True, text=True, timeout=ACTION_TIMEOUT)
            rc, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            rc, out, err = 124, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), f"timeout after {ACTION_TIMEOUT}s"
        elapsed = time.monotonic() - t
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"$ (cd {a.cwd} && {a.command})\n{out}\n{err}\nEXIT:{rc}\n")
        if a.env and rc == 0:
            self.run_env.update(a.env)  # the 'set oracle env' action: exports persist for later subprocesses
        tail = "\n".join((out + "\n" + err).strip().splitlines()[-6:])
        summary = f"exit={rc} in {elapsed:.1f}s; log={log_path.name}; tail: {tail}"[-3000:]
        ok = rc == 0
        if ok:
            self.sink.ev("ActionCompleted", self.sink.next_id("ev:action-completed"), {"name": a.name, "result_summary": summary},
                         [action_id, episode], {action_id: "action", episode: "episode"})
            self.bump("actions_completed")
        else:
            self.sink.ev("ActionFailed", self.sink.next_id("ev:action-failed"), {"name": a.name, "error": summary},
                         [action_id, episode], {action_id: "action", episode: "episode"})
            self.bump("actions_failed")
        self.claude_hook("PostToolUse", action_id, a.command, a.cwd, f"crown2 cycle {cycle} step {n}: {a.name}", tool_use_id,
                         {"stdout": out[-2000:], "stderr": err[-2000:], "exit_code": rc, "is_error": not ok})
        return ok, summary

    def compare_and_receipt(self, pr_id: str, predicted: dict, observed: dom.WorldState, ws_id: str, action_id: str, episode: str, cycle: int, n: int, digest: str) -> bool:
        delta = {k: {"predicted": predicted[k], "observed": observed.stages[k]} for k in dom.STAGES if predicted[k] != observed.stages[k]}
        match = not delta
        self.sink.ev("PredictionCompared", self.sink.next_id("ev:prediction-compared"), {"delta_json": {"match": match, "delta": delta}},
                     [pr_id, ws_id, action_id, episode], {pr_id: "prediction", ws_id: "observed", action_id: "action", episode: "episode"})
        self.bump("prediction_comparisons")
        if match:
            self.bump("prediction_matches")
        rec = {"cycle": cycle, "step": n, "prediction_sha256": digest, "observed": observed.stages, "match": match}
        rdigest = sha256_text(json.dumps(rec, sort_keys=True, separators=(",", ":")))
        r_id = f"receipt:{cycle:03d}:{n:02d}"
        self.sink.obj("Receipt", r_id, {"kind": "prediction-comparison", "digest": rdigest, "issued_at": now_iso()})
        self.sink.ev("ReceiptIssued", self.sink.next_id("ev:receipt-issued"), {"digest": rdigest}, [r_id, pr_id, episode],
                     {r_id: "receipt", pr_id: "prediction", episode: "episode"})
        return match

    # ------------------------------------------------------------ episodes
    def production(self, native: dict) -> None:
        ep = "episode:beam4pm-production"
        self.sink.obj("ProcessEpisode", ep, {"label": "beam4pm-production", "started_at": now_iso()})
        cycle = 0
        try:
            if not native["alive"]:
                cycle += 1
                self.sink.ev("LoopStarted", self.sink.next_id("ev:loop-started"), {"label": f"cycle-{cycle:03d}"}, [ep], {ep: "episode"})
                st, ws_id = self.observe("initial", ep, cycle)
                self.qualification(st, ws_id, ep, cycle)
                self.sink.ev("LoopBlocked", self.sink.next_id("ev:loop-blocked"), {"reason": native["reason"]}, [ep, ws_id], {ep: "episode", ws_id: "observed"})
                self.bump("loops_blocked")
            else:
                self.sink.obj("SolverImplementation", "solver:astar-native-hub", {
                    "name": "Astar", "kind": "cpp:_AStarSolver_", "version": native["summary"]["extension_path"],
                    "implementation": native["summary"].get("implementation", "native")})
                terminal = False
                while not terminal:
                    cycle += 1
                    self.sink.ev("LoopStarted", self.sink.next_id("ev:loop-started"), {"label": f"cycle-{cycle:03d}"}, [ep], {ep: "episode"})
                    st, ws_id = self.observe("pre-plan", ep, cycle)
                    self.qualification(st, ws_id, ep, cycle)
                    if st.get("QUALIFICATION_COMPLETE"):
                        self.sink.ev("LoopClosed", self.sink.next_id("ev:loop-closed"), {"label": "goal"}, [ep, ws_id], {ep: "episode", ws_id: "observed"})
                        self.bump("loops_closed")
                        break
                    actions = dom.discover_actions(BEAM4PM)
                    plan, detail = self.native_plan(st, actions, ep)
                    if plan is None:
                        self.sink.ev("PlanRefused", self.sink.next_id("ev:plan-refused"), {"reason": detail[-1000:]}, [ep, ws_id], {ep: "episode", ws_id: "observed"})
                        self.bump("plan_refusals")
                        self.sink.ev("LoopBlocked", self.sink.next_id("ev:loop-blocked"), {"reason": "PLAN_REFUSED: " + detail[-800:]}, [ep, ws_id], {ep: "episode"})
                        self.bump("loops_blocked")
                        break
                    plan_id = f"plan:{cycle:03d}"
                    summary = " -> ".join(a.name for a in plan)
                    self.sink.obj("Plan", plan_id, {"summary": summary, "steps_json": {"native": json.loads(detail), "steps": [asdict(a) for a in plan]}, "cost_estimate": float(len(plan))})
                    self.sink.ev("PlanProduced", self.sink.next_id("ev:plan-produced"), {"summary": summary, "cost_estimate": float(len(plan))},
                                 [plan_id, "solver:astar-native-hub", ep, ws_id], {plan_id: "plan", "solver:astar-native-hub": "solver", ep: "episode", ws_id: "from"})
                    self.bump("plans_produced")
                    cur = st
                    blocked = None
                    for n, a in enumerate(plan, 1):
                        action_id = f"action:{cycle:03d}:{n:02d}"
                        self.sink.obj("Action", action_id, {"name": a.name, "kind": "consequential" if a.consequential else "reversible",
                                                             "args_json": {"command": a.command, "cwd": a.cwd, "source": a.source, "env": a.env}})
                        pr_id, predicted, digest = self.freeze_prediction(a, cur, cycle, n, action_id, ep)
                        if not self.authority(a, action_id, ep):
                            self.sink.ev("ActionRefused", self.sink.next_id("ev:action-refused"), {"name": a.name, "reason": "AuthorityRefused: consequential or denylisted"},
                                         [action_id, ep], {action_id: "action", ep: "episode"})
                            self.bump("actions_refused")
                            blocked = f"AUTHORITY_REFUSED: {a.name}"
                            break
                        ok, _ = self.execute(a, action_id, ep, cycle, n)
                        cur, ws_id = self.observe(f"post-{a.name.split()[0]}", ep, cycle)
                        self.qualification(cur, ws_id, ep, cycle)
                        match = self.compare_and_receipt(pr_id, predicted, cur, ws_id, action_id, ep, cycle, n, digest)
                        if not ok or not match:
                            blocked = f"{'ACTION_FAILED' if not ok else 'PREDICTION_MISMATCH'}: {a.name}"
                            break
                    if blocked:
                        self.sink.ev("LoopBlocked", self.sink.next_id("ev:loop-blocked"), {"reason": blocked}, [ep, ws_id], {ep: "episode", ws_id: "observed"})
                        self.bump("loops_blocked")
                        terminal = True
                    else:
                        self.sink.ev("LoopClosed", self.sink.next_id("ev:loop-closed"), {"label": "goal" if cur.get("QUALIFICATION_COMPLETE") else "plan-executed"},
                                     [ep, ws_id], {ep: "episode", ws_id: "observed"})
                        self.bump("loops_closed")
                        terminal = cur.get("QUALIFICATION_COMPLETE") or cycle >= 3
                cycle = self.lawful_non_progress(ep, cycle)
            # steady observe-only cycles until the floor AND the event-timestamp span
            while time.monotonic() - self.t0 < self.floor or self.episode_span(ep) < self.span:
                cycle += 1
                st, ws_id = self.observe("steady", ep, cycle)
                self.sink.ev("LoopClosed", self.sink.next_id("ev:loop-closed"), {"label": "steady"}, [ep, ws_id], {ep: "episode", ws_id: "observed"})
                self.bump("loops_closed")
                remaining = max(self.floor - (time.monotonic() - self.t0), self.span - self.episode_span(ep))
                if remaining <= 0:
                    break
                time.sleep(min(STEADY_PERIOD, remaining))
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"production: {type(e).__name__}: {e}")
            try:
                self.sink.ev("LoopBlocked", self.sink.next_id("ev:loop-blocked"), {"reason": f"RUNNER_EXCEPTION: {type(e).__name__}: {e}"[-1000:]}, [ep], {ep: "episode"})
                self.bump("loops_blocked")
            except Exception as e2:  # noqa: BLE001
                self.errors.append(f"production-emit: {e2}")
        finally:
            self.production_done.set()

    def lawful_non_progress(self, ep: str, cycle: int) -> int:
        """Attempt 2 (3a/3b): one real cycle whose only lawful outcome is typed refusal.

        (a) the native planner is asked for a goal no discovered action provides
            -> PlanRefused carrying the typed missing transition;
        (b) the discovered action the policy classifies CONSEQUENTIAL (denylist
            or consequential flag) goes through PredictionFrozen ->
            AuthorityEvaluated -> AuthorityRefused -> ActionRefused and is
            physically NOT executed (world fingerprint before == after).
        Both refusal events relate to the production episode and an Action.
        """
        cycle += 1
        self.sink.ev("LoopStarted", self.sink.next_id("ev:loop-started"), {"label": f"cycle-{cycle:03d}-lawful-non-progress"}, [ep], {ep: "episode"})
        st, ws_id = self.observe("pre-refusal", ep, cycle)
        self.qualification(st, ws_id, ep, cycle)
        actions = dom.discover_actions(BEAM4PM)
        # (a) unreachable goal -> PlanRefused (typed)
        goal = {"QUALIFICATION_COMPLETE": True, UNREACHABLE_GOAL_STAGE: True}
        probe_id = f"action:{cycle:03d}:01"
        self.sink.obj("Action", probe_id, {"name": f"plan for goal {UNREACHABLE_GOAL_STAGE}", "kind": "planning-probe",
                                           "args_json": {"goal": goal, "cwd": str(BEAM4PM), "source": "runner: goal predicate no discovered action provides"}})
        plan, detail = self.native_plan(st, actions, ep, goal=goal)
        if plan is not None:
            raise RuntimeError(f"unreachable goal {goal} was planned: {detail}")
        self.sink.ev("PlanRefused", self.sink.next_id("ev:plan-refused"), {"reason": detail[-1500:]},
                     [ep, ws_id, "solver:astar-native-hub", probe_id], {ep: "episode", ws_id: "observed", "solver:astar-native-hub": "solver", probe_id: "subject"})
        self.bump("plan_refusals")
        # (b) consequential discovered action -> AuthorityRefused, physically not executed
        cons = next((a for a in actions if a.consequential or any(t in a.command for t in POLICY["denylist_tokens"])), None)
        if cons is None:
            raise RuntimeError("no CONSEQUENTIAL action discovered from the beam4pm surface")
        action_id = f"action:{cycle:03d}:02"
        self.sink.obj("Action", action_id, {"name": cons.name, "kind": "consequential",
                                            "args_json": {"command": cons.command, "cwd": cons.cwd, "source": cons.source, "env": cons.env}})
        before = world_snapshot(BEAM4PM)
        self.freeze_prediction(cons, st, cycle, 2, action_id, ep)
        granted = self.authority(cons, action_id, ep)
        if granted:
            raise RuntimeError(f"policy granted consequential action {cons.name}: {cons.command}")
        self.sink.ev("ActionRefused", self.sink.next_id("ev:action-refused"), {"name": cons.name, "reason": "AuthorityRefused: consequential or denylisted"},
                     [action_id, ep], {action_id: "action", ep: "episode"})
        self.bump("actions_refused")
        after = world_snapshot(BEAM4PM)
        unchanged = {k: before[k] == after[k] for k in before if k != "taken_at"}
        self.non_execution_proof = {"action": action_id, "name": cons.name, "command": cons.command, "before": before, "after": after,
                                    "world_unchanged": all(unchanged.values()), "per_field": unchanged}
        self.sink.ev("LoopBlocked", self.sink.next_id("ev:loop-blocked"),
                     {"reason": f"LAWFUL_NON_PROGRESS: PLAN_REFUSED[{UNREACHABLE_GOAL_STAGE}]; AUTHORITY_REFUSED[{cons.name}]; world_unchanged={all(unchanged.values())}"},
                     [ep, ws_id, probe_id, action_id], {ep: "episode", ws_id: "observed", probe_id: "subject", action_id: "subject"})
        self.bump("loops_blocked")
        return cycle

    def heartbeat(self) -> None:
        ep = "episode:control-heartbeat"
        self.sink.obj("ProcessEpisode", ep, {"label": "control-heartbeat", "started_at": now_iso()})
        seq = 0
        while True:
            seq += 1
            log = self.sink.read()
            summary = validate.validate(log)
            self.sink.ev("HeartbeatObserved", f"ev:heartbeat:{seq:04d}",
                         {"seq": seq, "monotonic_seconds": time.monotonic() - self.t0, "events_so_far": len(log["events"]), "validate_json": summary},
                         [ep], {ep: "episode"})
            self.bump("heartbeat_events")
            if self.stop.is_set():
                return
            self.stop.wait(HEARTBEAT_PERIOD)

    # ---------------------------------------------------------------- main
    def run(self) -> dict:
        self.emit_composition()
        native = self.check_native()
        hb = threading.Thread(target=self.heartbeat, name="control-heartbeat", daemon=True)
        prod = threading.Thread(target=self.production, args=(native,), name="beam4pm-production", daemon=True)
        hb.start()
        prod.start()
        prod.join()
        hb_ep = "episode:control-heartbeat"
        while time.monotonic() - self.t0 < self.floor or self.episode_span(hb_ep) < self.span:
            time.sleep(0.5)
        self.stop.set()  # heartbeat emits one final beat after stop, then exits
        hb.join(timeout=60)
        t1 = time.monotonic()
        log = self.sink.read()
        spans = {ep: self.episode_span(ep) for ep in ("episode:beam4pm-production", hb_ep)}
        summary = validate.validate(log)
        hb_types = {e["type"] for e in log["events"] if any(r["objectId"] == "episode:control-heartbeat" for r in e["relationships"])}
        leak = sorted(hb_types & PRODUCTION_EVENT_TYPES)
        by_type: dict[str, int] = {}
        for e in log["events"]:
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        receipt = {
            "sink": str(self.sink_path),
            "monotonic_start": self.t0, "monotonic_end": t1, "elapsed_monotonic_seconds": t1 - self.t0,
            "started_utc": self.started_utc, "ended_utc": now_iso(), "floor_seconds": self.floor,
            "span_seconds_required": self.span, "episode_event_spans_seconds": spans,
            "non_execution_proof": self.non_execution_proof,
            "native_planner": {"alive": native["alive"], "detail": native.get("summary") or native.get("reason")},
            "counts": dict(self.counts),
            "events_by_type": by_type, "objects": len(log["objects"]), "events": len(log["events"]),
            "validate": summary, "heartbeat_production_event_leak": leak, "errors": self.errors,
            "final_env_oracle_vars": {k: self.run_env.get(k) for k in sorted(self.run_env) if k.startswith(("RF2_", "RF3_"))},
        }
        self.timing_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt


def main() -> int:
    print(f"pwd={os.getcwd()} runner={__file__} sink={SINK}", flush=True)
    r = Runner().run()
    print(json.dumps(r, indent=2, sort_keys=True))
    ok = (all(v == 0 for v in r["validate"].values()) and not r["heartbeat_production_event_leak"]
          and r["elapsed_monotonic_seconds"] >= r["floor_seconds"] and not r["errors"]
          and all(v >= r["span_seconds_required"] for v in r["episode_event_spans_seconds"].values())
          and r["non_execution_proof"].get("world_unchanged") is True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
