#!/usr/bin/env python3
"""Build WS10 conformance fixtures through the REAL emitter (tools/ocel_v2/emitter.py).

Outputs (in this directory):
  clean.ocel.json                      — passes all 10 rules
  violates_R01..R10.ocel.json          — each violates exactly one rule
  evidence/receipt-001.txt             — the evidence file the clean ReceiptIssued points at

Each fixture is a mutation of the same clean scenario; MUTATIONS documents the
exact edit so the fixture is itself the falsifier spec for that rule.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
EMITTER = os.path.join(REPO, "tools", "ocel_v2", "emitter.py")

spec = importlib.util.spec_from_file_location("emitter", EMITTER)
emitter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emitter)

T0 = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)


def ts(step: float) -> str:
    return (T0 + timedelta(seconds=step)).isoformat()


OBJECTS = [
    ("ProcessEpisode", "ep1", {"label": "production-run-1", "started_at": ts(0), "ended_at": ts(20)}),
    ("ProcessEpisode", "hb1", {"label": "heartbeat-1", "started_at": ts(17), "ended_at": ts(19)}),
    ("Domain", "dom1", {"name": "maze", "description": "fixture domain"}),
    ("Plan", "plan1", {"summary": "walk", "steps_json": ["a", "b"], "cost_estimate": 2.0}),
    ("Action", "act1", {"name": "apply-patch", "kind": "edit", "args_json": {"file": "x.py"}}),
    ("Action", "act2", {"name": "rm-rf", "kind": "destructive", "args_json": {"path": "/"}}),
    ("Receipt", "rcpt1", {"kind": "standing", "digest": "sha256:abc", "issued_at": ts(15),
                          "evidence_path": "evidence/receipt-001.txt"}),
]

# (step, type, id, attrs, related objects)
CLEAN = [
    (1, "LoopStarted", "e01", {"label": "run"}, ["ep1"]),
    (2, "WorldStateObserved", "e02", {"label": "pre", "state_json": {"x": 0}}, ["ep1", "dom1"]),
    (3, "PlannerInvoked", "e03", {"solver_name": "astar"}, ["ep1", "dom1"]),
    (4, "PlanProduced", "e04", {"summary": "walk", "cost_estimate": 2.0}, ["ep1", "dom1", "plan1"]),
    (5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["ep1", "plan1"]),
    (6, "AuthorityEvaluated", "e06", {"rationale": "policy ok"}, ["ep1", "act1"]),
    (7, "AuthorityGranted", "e07", {"rationale": "policy ok"}, ["ep1", "act1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
    (10, "WorldStateObserved", "e10", {"label": "post", "state_json": {"x": 1}}, ["ep1", "dom1"]),
    (11, "QualificationObserved", "e11", {"result": "pass", "metrics_json": {"t": 1}}, ["ep1", "act1"]),
    (12, "AuthorityEvaluated", "e12", {"rationale": "destructive"}, ["ep1", "act2"]),
    (13, "AuthorityRefused", "e13", {"rationale": "destructive"}, ["ep1", "act2"]),
    (14, "ActionRefused", "e14", {"name": "rm-rf", "reason": "refused"}, ["ep1", "act2"]),
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["ep1", "rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
    (17, "LoopStarted", "e17", {"label": "heartbeat"}, ["hb1"]),
    (18, "WorldStateObserved", "e18", {"label": "hb", "state_json": {"alive": True}}, ["hb1"]),
    (19, "LoopClosed", "e19", {"label": "heartbeat"}, ["hb1"]),
]


def drop(*ids):
    return lambda evs: [e for e in evs if e[2] not in ids]


def retime(eid, step):
    return lambda evs: [(step if e[2] == eid else e[0], *e[1:]) for e in evs]


def add(*new):
    return lambda evs: evs + list(new)


def set_attr(eid, key, val):
    return lambda evs: [(e[0], e[1], e[2], {**e[3], key: val}, e[4]) if e[2] == eid else e for e in evs]


MUTATIONS = {
    "R01": drop("e04"),                       # PlannerInvoked e03 has no terminal planner event
    "R02": retime("e04", 5.5),                # PlanProduced now AFTER PredictionFrozen -> no frozen after it
    "R03": retime("e05", 8.5),                # PredictionFrozen after ActionStarted e08
    "R04": drop("e06"),                       # ActionStarted e08 has no AuthorityEvaluated for act1
    "R05": add((7.5, "AuthorityRefused", "e07b", {"rationale": "late veto"}, ["ep1", "act1"])),
    "R06": drop("e10", "e11"),                # ActionCompleted e09 has no following observation
    "R07": drop("e15"),                       # consequences e09,e11 have no ReceiptIssued
    "R08": drop("e16"),                       # LoopStarted e01 never closed/blocked
    "R09": add((18.5, "AuthorityGranted", "e18b", {"rationale": "leak"}, ["hb1", "act1"])),
    "R10": set_attr("e15", "evidence_path", "evidence/does-not-exist.txt"),
}


def build(path: str, events) -> None:
    emitter.init(path)
    for otype, oid, attrs in OBJECTS:
        emitter.add_object(path, otype, oid, attrs)
    for step, etype, eid, attrs, objs in sorted(events, key=lambda e: e[0]):
        emitter.add_event(path, etype, eid, attrs, objs, time=ts(step))


def main() -> int:
    os.makedirs(os.path.join(HERE, "evidence"), exist_ok=True)
    with open(os.path.join(HERE, "evidence", "receipt-001.txt"), "w") as f:
        f.write("standing receipt evidence for fixture rcpt1\n")
    build(os.path.join(HERE, "clean.ocel.json"), CLEAN)
    print("built clean.ocel.json")
    for rid, mut in MUTATIONS.items():
        p = os.path.join(HERE, f"violates_{rid}.ocel.json")
        build(p, mut(list(CLEAN)))
        print(f"built {os.path.basename(p)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
