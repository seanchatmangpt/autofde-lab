#!/usr/bin/env python3
"""F05 — events with NO ProcessEpisode form one implicit case (episode None).

ActionCompleted related only to act1 (no episode), and an unrelated
WorldStateObserved + ReceiptIssued related only to dom1/rcpt1 (no episode):
`_episode()` returns None for all three, None == None, so R06/R07 are
satisfied across what are actually unscoped, unrelated events. The SPARQL
engine never binds ocel:episode for these events so it cannot even evaluate
R06/R07/R08 on them — it passes them for a different reason.
"""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
p = build("f05_episodeless", [
    (1, "LoopStarted", "e01", {"label": "orphan-loop"}, ["dom1"]),
    (5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["plan1"]),
    (6, "AuthorityEvaluated", "e06", {"rationale": "ok"}, ["act1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["act1"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["act1"]),
    (10, "WorldStateObserved", "e10", {"label": "unrelated", "state_json": {"y": 1}}, ["dom1"]),
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "other-loop"}, ["dom1"]),
])
py = fired(python_engine(p, EVR))
sq = sparql_engine(p, EVR)
sys.exit(verdict("F05_episodeless_events_share_none_case",
                 not py and (sq is None or not any(sq.values())),
                 {"python": py, "sparql": sq and fired(sq)}))
