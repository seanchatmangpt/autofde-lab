#!/usr/bin/env python3
"""F07 — heartbeat detection is a label-prefix convention, not a structural one.

(a) Heartbeat loop events (LoopStarted/WorldStateObserved/LoopClosed with
    label "heartbeat") related to the PRODUCTION episode ep1 only; the
    heartbeat ProcessEpisode object hb1 has zero events. Passes every rule:
    heartbeat traffic is indistinguishable from production traffic, and an
    orphan heartbeat episode is not a violation.
(b) A ProcessEpisode labelled "Heartbeat-2" (capital H) or "hb-3" emitting
    AuthorityGranted/ActionStarted: R09 does not fire (case-sensitive
    STRSTARTS / str.startswith on the literal "heartbeat").
"""
import sys

from _harness import OBJECTS, build, fired, python_engine, sparql_engine, ts, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
a = build("f07a_heartbeat_events_in_production_episode", [
    (1, "LoopStarted", "e01", {"label": "run"}, ["ep1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
    (17, "LoopStarted", "e17", {"label": "heartbeat"}, ["ep1"]),
    (18, "WorldStateObserved", "e18", {"label": "heartbeat", "state_json": {"alive": True}}, ["ep1"]),
    (19, "LoopClosed", "e19", {"label": "heartbeat"}, ["ep1"]),
])
objs = OBJECTS + [
    ("ProcessEpisode", "hb2", {"label": "Heartbeat-2", "started_at": ts(0), "ended_at": ts(9)}),
    ("ProcessEpisode", "hb3", {"label": "hb-3", "started_at": ts(0), "ended_at": ts(9)}),
]
b = build("f07b_heartbeat_label_case", [
    (1, "LoopStarted", "e01", {"label": "heartbeat"}, ["hb2"]),
    (2, "PredictionFrozen", "e02", {"confidence": 1.0}, ["hb2", "plan1"]),
    (3, "AuthorityEvaluated", "e03", {"rationale": "leak"}, ["hb2", "act1"]),
    (4, "AuthorityGranted", "e04", {"rationale": "leak"}, ["hb2", "act1"]),
    (5, "ActionStarted", "e05", {"name": "apply-patch"}, ["hb2", "act1"]),
    (6, "ActionCompleted", "e06", {"name": "apply-patch", "result_summary": "ok"}, ["hb2", "act1"]),
    (7, "WorldStateObserved", "e07", {"label": "post", "state_json": {}}, ["hb2"]),
    (8, "ReceiptIssued", "e08", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["hb2", "rcpt1"]),
    (9, "LoopClosed", "e09", {"label": "heartbeat"}, ["hb2"]),
    (1, "LoopStarted", "f01", {"label": "hb"}, ["hb3"]),
    (2, "AuthorityGranted", "f02", {"rationale": "leak"}, ["hb3", "act2"]),
    (9, "LoopClosed", "f09", {"label": "hb"}, ["hb3"]),
], objects=objs)
detail, ok = {}, True
for p in (a, b):
    py = fired(python_engine(p, EVR))
    sq = sparql_engine(p, EVR)
    detail[p.rsplit("/", 1)[1]] = {"python": py, "sparql": sq and fired(sq)}
    ok &= not py and (sq is None or not any(sq.values()))
sys.exit(verdict("F07_heartbeat_by_relationship_only", ok, detail))
