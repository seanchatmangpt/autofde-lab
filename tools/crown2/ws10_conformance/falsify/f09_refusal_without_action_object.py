#!/usr/bin/env python3
"""F09 — AuthorityRefused related only to the episode (no Action object), then
ActionStarted for act1 in the same episode: R05 correlates on the Action
object set, which is empty, so the refusal forbids nothing. Combined with an
AuthorityEvaluated on act1, the log passes every rule although the episode
recorded a refusal and then started the only action it had evaluated."""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
p = build("f09_refusal_no_action", [
    (1, "LoopStarted", "e01", {"label": "run"}, ["ep1"]),
    (5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["ep1", "plan1"]),
    (6, "AuthorityEvaluated", "e06", {"rationale": "eval"}, ["ep1", "act1"]),
    (7, "AuthorityRefused", "e07", {"rationale": "refused"}, ["ep1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
    (10, "WorldStateObserved", "e10", {"label": "post", "state_json": {"x": 1}}, ["ep1", "dom1"]),
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["ep1", "rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
])
py = fired(python_engine(p, EVR))
sq = sparql_engine(p, EVR)
sys.exit(verdict("F09_refusal_without_action_object", not py and (sq is None or not any(sq.values())),
                 {"python": py, "sparql": sq and fired(sq)}))
