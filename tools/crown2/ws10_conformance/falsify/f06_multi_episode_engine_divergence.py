#!/usr/bin/env python3
"""F06 — an event related to TWO ProcessEpisodes: Python `_episode()` takes the
FIRST ProcessEpisode in relationship order; the RDF projection emits
ocel:episode for EVERY related episode. The two engines therefore disagree
on the same log, refuting "equivalent SPARQL".

Log: ActionCompleted e09 in ep1; the only later observation e10 is related to
[hb1, ep1] (hb1 first). Python: episode(e10)=hb1 != ep1 -> R06 fires on e09.
SPARQL: e10 ocel:episode ep1 holds -> R06 does not fire. Also e10 is a
WorldStateObserved in a heartbeat episode, which R09 does not consider
production, so the heartbeat quietly satisfies a production obligation.
"""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
p = build("f06_two_episodes", [
    (1, "LoopStarted", "e01", {"label": "run"}, ["ep1"]),
    (5, "PredictionFrozen", "e05", {"confidence": 0.9}, ["ep1", "plan1"]),
    (6, "AuthorityEvaluated", "e06", {"rationale": "ok"}, ["ep1", "act1"]),
    (8, "ActionStarted", "e08", {"name": "apply-patch"}, ["ep1", "act1"]),
    (9, "ActionCompleted", "e09", {"name": "apply-patch", "result_summary": "ok"}, ["ep1", "act1"]),
    (10, "WorldStateObserved", "e10", {"label": "hb-and-prod", "state_json": {"x": 1}}, ["hb1", "ep1"]),
    (15, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": "evidence/receipt-001.txt"},
     ["hb1", "ep1", "rcpt1"]),
    (16, "LoopClosed", "e16", {"label": "run"}, ["ep1"]),
    (17, "LoopStarted", "e17", {"label": "heartbeat"}, ["hb1"]),
    (19, "LoopClosed", "e19", {"label": "heartbeat"}, ["hb1"]),
])
py = fired(python_engine(p, EVR))
sq = sparql_engine(p, EVR)
diverge = sq is not None and py != fired(sq)
sys.exit(verdict("F06_multi_episode_engine_divergence", diverge,
                 {"python": py, "sparql": sq and fired(sq), "engines_disagree": diverge}))
