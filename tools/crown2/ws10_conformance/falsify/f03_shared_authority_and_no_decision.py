#!/usr/bin/env python3
"""F03 — authority gate.

(a) ONE AuthorityEvaluated related to BOTH act1 and act2 (destructive), then
    ActionStarted for each: both pass R04. One evaluation licenses N actions.
(b) AuthorityEvaluated for act1 with NO AuthorityGranted/AuthorityRefused ever,
    then ActionStarted: passes R04/R05 — an evaluation with no decision is
    accepted as a grant.
(c) AuthorityRefused for act1 whose ActionStarted is stamped 1s EARLIER than
    the refusal but AFTER the same Action's Evaluated: passes R05 (refusal
    only forbids later starts; a refused action that was already running is
    never flagged — no ActionFailed/ActionRefused required).
"""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
PRE = [
    (1, "LoopStarted", "e01", {"label": "run"}, ["ep1"]),
    (3, "PlannerInvoked", "e03", {"solver_name": "astar"}, ["ep1", "dom1"]),
    (4, "PlanProduced", "e04", {"summary": "walk", "cost_estimate": 2.0}, ["ep1", "dom1", "plan1"]),
    (5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["ep1", "plan1"]),
]
POST = [
    (10, "WorldStateObserved", "e10", {"label": "post", "state_json": {"x": 1}}, ["ep1", "dom1"]),
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["ep1", "rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
]

a = build("f03a_shared_authority_evaluated", PRE + [
    (6, "AuthorityEvaluated", "e06", {"rationale": "one eval two actions"}, ["ep1", "act1", "act2"]),
    (7, "AuthorityGranted", "e07", {"rationale": "ok"}, ["ep1", "act1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1"]),
    (8.1, "ActionStarted", "e08b", {"name": "rm-rf"}, ["ep1", "act2"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
    (9.1, "ActionCompleted", "e09b", {"name": "rm-rf", "result_summary": "gone"}, ["ep1", "act2"]),
] + POST)
b = build("f03b_evaluated_without_decision", PRE + [
    (6, "AuthorityEvaluated", "e06", {"rationale": "pending"}, ["ep1", "act1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
] + POST)
c = build("f03c_refused_while_running", PRE + [
    (6, "AuthorityEvaluated", "e06", {"rationale": "pending"}, ["ep1", "act1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1"]),
    (8.5, "AuthorityRefused", "e08r", {"rationale": "veto"}, ["ep1", "act1"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
] + POST)

detail, ok = {}, True
for p in (a, b, c):
    py = fired(python_engine(p, EVR))
    sq = sparql_engine(p, EVR)
    detail[p.rsplit("/", 1)[1]] = {"python": py, "sparql": sq and fired(sq)}
    ok &= not py and (sq is None or not any(sq.values()))
sys.exit(verdict("F03_shared_authority_and_no_decision", ok, detail))
