#!/usr/bin/env python3
"""check_run_invariants.py -- falsifier for a Crown-2 runner sink.

Executable knowledge of what a closed-loop run MUST look like, so the next
audit is a command, not a reasoning session. Every rule is a real check over
the OCEL file; any violation is listed and exit code is 1.

  R1  the very first event is CompositionCreated (sink existed before work)
  R2  for every Action object that has ActionStarted: a PredictionFrozen
      event referencing it precedes ActionStarted, and its PredictionReceipt
      names a file on disk whose sha256 matches the record it carries
  R3  AuthorityGranted precedes ActionStarted for every started action;
      an action with AuthorityRefused has NO ActionStarted/Completed/Failed
  R4  every started action has a Claude.PreToolUse before ActionStarted and
      a Claude.PostToolUse after ActionCompleted|ActionFailed, both relating
      the Action object with qualifier 'invokes'
  R5  every ActionCompleted|ActionFailed is followed by WorldStateObserved,
      QualificationObserved, PredictionCompared and ReceiptIssued (same cycle)
  R6  episode:control-heartbeat relates ONLY HeartbeatObserved events, and
      no production event relates to it
  R7  heartbeat spacing: consecutive HeartbeatObserved monotonic_seconds
      differ by <= 2x the period (default 10s) -> liveness was continuous
  R8  timing-receipt elapsed_monotonic_seconds >= floor_seconds
  R9  validate.py: strict/dup/dangling all zero
  R10 if a SolverImplementation object exists, every PlanProduced relates to it
      (native plan, not a fallback); if none exists, a LoopBlocked with reason
      NATIVE_PLANNER_BOOTSTRAP must exist and no PlanProduced may exist
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ocel_v2"))
import validate  # noqa: E402


def _attr(e: dict, name: str):
    for a in e.get("attributes", []):
        if a["name"] == name:
            return a["value"]
    return None


def _rels(e: dict) -> dict[str, str]:
    return {r["objectId"]: r.get("qualifier", "") for r in e.get("relationships", [])}


def check(sink_path: Path, timing_path: Path | None = None, heartbeat_period: float = 10.0) -> list[str]:
    log = json.loads(sink_path.read_text(encoding="utf-8"))
    events = log["events"]
    objects = {o["id"]: o for o in log["objects"]}
    v: list[str] = []
    idx = {e["id"]: i for i, e in enumerate(events)}

    # R1
    if not events or events[0]["type"] != "CompositionCreated":
        v.append("R1: first event is not CompositionCreated")

    def first(etype: str, oid: str, after: int = -1) -> int | None:
        for i, e in enumerate(events):
            if i > after and e["type"] == etype and oid in _rels(e):
                return i
        return None

    action_ids = [oid for oid, o in objects.items() if o["type"] == "Action"]
    for aid in action_ids:
        started = first("ActionStarted", aid)
        refused = first("AuthorityRefused", aid)
        if refused is not None:
            for t in ("ActionStarted", "ActionCompleted", "ActionFailed"):
                if first(t, aid) is not None:
                    v.append(f"R3: {aid} was AuthorityRefused but has {t}")
            if first("ActionRefused", aid) is None:
                v.append(f"R3: {aid} AuthorityRefused without ActionRefused")
            continue
        if started is None:
            continue
        # R2
        frozen = first("PredictionFrozen", aid)
        if frozen is None or frozen > started:
            v.append(f"R2: {aid} has no PredictionFrozen before ActionStarted")
        else:
            pr_ids = [o for o, q in _rels(events[frozen]).items() if objects.get(o, {}).get("type") == "PredictionReceipt"]
            for pr in pr_ids:
                pj = json.loads(next(a["value"] for a in objects[pr]["attributes"] if a["name"] == "prediction_json"))
                p = Path(pj["path"])
                if not p.exists():
                    v.append(f"R2: {pr} prediction file missing on disk: {p}")
                else:
                    digest = hashlib.sha256(p.read_text(encoding="utf-8").rstrip("\n").encode()).hexdigest()
                    if digest != pj["sha256"]:
                        v.append(f"R2: {pr} sha256 mismatch on disk")
        # R3
        granted = first("AuthorityGranted", aid)
        if granted is None or granted > started:
            v.append(f"R3: {aid} started without prior AuthorityGranted")
        # R4
        pre = first("Claude.PreToolUse", aid)
        if pre is None or pre > started or _rels(events[pre]).get(aid) != "invokes":
            v.append(f"R4: {aid} lacks Claude.PreToolUse[invokes] before ActionStarted")
        done = first("ActionCompleted", aid)
        if done is None:
            done = first("ActionFailed", aid)
        if done is None:
            v.append(f"R5: {aid} started but never Completed/Failed")
            continue
        post = first("Claude.PostToolUse", aid, after=done)
        if post is None or _rels(events[post]).get(aid) != "invokes":
            v.append(f"R4: {aid} lacks Claude.PostToolUse[invokes] after completion")
        # R5
        cmp_i = first("PredictionCompared", aid, after=done)
        if cmp_i is None:
            v.append(f"R5: {aid} no PredictionCompared after completion")
        else:
            between = {e["type"] for e in events[done + 1: cmp_i + 1]}
            for t in ("WorldStateObserved", "QualificationObserved"):
                if t not in between:
                    v.append(f"R5: {aid} missing {t} between completion and PredictionCompared")
            if not any(e["type"] == "ReceiptIssued" for e in events[cmp_i + 1: cmp_i + 4]):
                v.append(f"R5: {aid} no ReceiptIssued right after PredictionCompared")

    # R6 / R7
    hb = [e for e in events if "episode:control-heartbeat" in _rels(e)]
    bad = sorted({e["type"] for e in hb if e["type"] != "HeartbeatObserved"})
    if bad:
        v.append(f"R6: heartbeat episode carries non-heartbeat events {bad}")
    times = [_attr(e, "monotonic_seconds") for e in hb if e["type"] == "HeartbeatObserved"]
    for a, b in zip(times, times[1:]):
        if b - a > 2 * heartbeat_period:
            v.append(f"R7: heartbeat gap {b - a:.1f}s > {2 * heartbeat_period}s")
    if len(times) < 2:
        v.append("R7: fewer than 2 heartbeats")

    # R8
    if timing_path and timing_path.exists():
        t = json.loads(timing_path.read_text(encoding="utf-8"))
        if t["elapsed_monotonic_seconds"] < t["floor_seconds"]:
            v.append(f"R8: elapsed {t['elapsed_monotonic_seconds']:.1f} < floor {t['floor_seconds']}")

    # R9
    summary = validate.validate(log)
    if any(summary.values()):
        v.append(f"R9: validate {summary}")

    # R10
    solvers = [oid for oid, o in objects.items() if o["type"] == "SolverImplementation"]
    plans = [e for e in events if e["type"] == "PlanProduced"]
    if solvers:
        for e in plans:
            if not any(s in _rels(e) for s in solvers):
                v.append(f"R10: {e['id']} PlanProduced without SolverImplementation relation")
    else:
        if plans:
            v.append("R10: PlanProduced without any SolverImplementation (fallback planner?)")
        if not any(e["type"] == "LoopBlocked" and "NATIVE_PLANNER_BOOTSTRAP" in str(_attr(e, "reason")) for e in events):
            v.append("R10: no SolverImplementation and no LoopBlocked NATIVE_PLANNER_BOOTSTRAP")
    return v


def main(argv: list[str]) -> int:
    sink = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("crown-run-v3.ocel.json")
    timing = Path(argv[2]) if len(argv) > 2 else sink.with_name("timing-receipt.json")
    violations = check(sink, timing)
    print(json.dumps({"sink": str(sink), "violations": violations, "ok": not violations}, indent=2))
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
