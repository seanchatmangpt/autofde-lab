#!/usr/bin/env python3
"""F02 — temporal semantics.

(a) COLLAPSE: every event of the clean scenario stamped with the SAME instant,
    written to the file in REVERSED order (LoopClosed first ... LoopStarted
    last, ActionStarted before PredictionFrozen before PlanProduced). All
    rules use >= / <= so simultaneity satisfies "before" and "after" at once;
    document order is discarded by the parser. Expected: passes all 10 rules.

(b) HYPOTHESIS FROM THE BRIEF: PredictionFrozen with a LATER timestamp than
    ActionStarted but EARLIER in file order. Expected by the brief to slip
    through; checked honestly here.
"""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

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
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["ep1", "rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
]
EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"

# (a) all at T0, reversed document order
collapsed = [(0, *e[1:]) for e in reversed(CLEAN)]
pa = build("f02a_collapsed_reversed", collapsed, sort_by_step=False)
py_a = fired(python_engine(pa, EVR))
sq_a = sparql_engine(pa, EVR)
repro_a = not py_a and (sq_a is None or not any(sq_a.values()))

# (b) PredictionFrozen later timestamp (8.5) but earlier in file order than ActionStarted(8)
later_frozen = [e for e in CLEAN if e[2] != "e05"]
idx = next(i for i, e in enumerate(later_frozen) if e[2] == "e08")
later_frozen.insert(idx, (8.5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["ep1", "plan1"]))
pb = build("f02b_frozen_later_ts_earlier_file", later_frozen, sort_by_step=False)
py_b = fired(python_engine(pb, EVR))
sq_b = sparql_engine(pb, EVR)
repro_b = "R03_action_started_before_prediction_frozen" not in py_b

sys.exit(verdict("F02_timestamp_collapse_and_file_order", repro_a or repro_b, {
    "a_collapsed_same_instant_reversed_order": {"python": py_a, "sparql": sq_a and fired(sq_a),
                                                "reproduced": repro_a},
    "b_frozen_later_ts_earlier_file_order": {"python": py_b, "sparql": sq_b and fired(sq_b),
                                             "reproduced": repro_b},
}))
