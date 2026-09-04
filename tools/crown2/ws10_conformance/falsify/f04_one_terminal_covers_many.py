#!/usr/bin/env python3
"""F04 — cardinality blindness: rules are existential ("some later X sharing an
object"), so ONE terminal event satisfies ANY number of openers.

  * 3 PlannerInvoked, 1 PlanProduced            -> R01 passes for all three
  * 2 PlanProduced (plan1, plan2), 1 PredictionFrozen on plan1 only, but
    both PlanProduced share ep1/dom1 with it -> R02 passes for plan2 too
  * ActionStarted for an action of the never-frozen plan2 -> R03 passes
    (episode-scoped, not plan-scoped)
  * 3 LoopStarted, 1 LoopClosed in the same episode -> R08 passes for all
  * 2 ActionCompleted, 1 WorldStateObserved, 1 ReceiptIssued -> R06/R07 pass
"""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
p = build("f04_one_terminal_many_openers", [
    (1, "LoopStarted", "e01", {"label": "run"}, ["ep1"]),
    (1.1, "LoopStarted", "e01b", {"label": "run-again"}, ["ep1"]),
    (1.2, "LoopStarted", "e01c", {"label": "run-again-again"}, ["ep1"]),
    (3, "PlannerInvoked", "e03", {"solver_name": "astar"}, ["ep1", "dom1"]),
    (3.1, "PlannerInvoked", "e03b", {"solver_name": "bfs"}, ["ep1", "dom1"]),
    (3.2, "PlannerInvoked", "e03c", {"solver_name": "dfs"}, ["ep1", "dom1"]),
    (4, "PlanProduced", "e04", {"summary": "walk", "cost_estimate": 2.0}, ["ep1", "dom1", "plan1"]),
    (4.1, "PlanProduced", "e04b", {"summary": "unfrozen", "cost_estimate": 9.0}, ["ep1", "dom1", "plan2"]),
    (5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["ep1", "plan1"]),
    (6, "AuthorityEvaluated", "e06", {"rationale": "ok"}, ["ep1", "act1", "act2"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1", "plan1"]),
    (8.1, "ActionStarted", "e08b", {"name": "rm-rf"}, ["ep1", "act2", "plan2"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
    (9.1, "ActionCompleted", "e09b", {"name": "rm-rf", "result_summary": "ok"}, ["ep1", "act2"]),
    (10, "WorldStateObserved", "e10", {"label": "post", "state_json": {"x": 1}}, ["ep1", "dom1"]),
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["ep1", "rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
])
py = fired(python_engine(p, EVR))
sq = sparql_engine(p, EVR)
sys.exit(verdict("F04_one_terminal_covers_many", not py and (sq is None or not any(sq.values())),
                 {"python": py, "sparql": sq and fired(sq)}))
