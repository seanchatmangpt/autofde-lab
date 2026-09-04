#!/usr/bin/env python3
"""F01 — vacuity: an empty log, an objects-only log, and a log consisting of a
lone LoopClosed / ActionFailed all pass every rule. No rule asserts that any
process happened at all, and ActionFailed has no observation/receipt guard
beyond R07."""
import sys

from _harness import build, fired, python_engine, sparql_engine, validate, verdict

empty = build("f01_empty", [], objects=[])
objects_only = build("f01_objects_only", [])
only_closed = build("f01_only_loopclosed", [(1, "LoopClosed", "e1", {"label": "run"}, ["ep1"])])
# ActionFailed with no observation: R06 only guards ActionCompleted.
failed_no_obs = build("f01_failed_no_observation", [
    (1, "LoopStarted", "e1", {"label": "run"}, ["ep1"]),
    (2, "PredictionFrozen", "e2", {"confidence": 0.1}, ["ep1", "plan1"]),
    (3, "AuthorityEvaluated", "e3", {"rationale": "ok"}, ["ep1", "act1"]),
    (4, "ActionStarted", "e4", {"name": "apply-patch"}, ["ep1", "act1"]),
    (5, "ActionFailed", "e5", {"name": "apply-patch", "error": "boom"}, ["ep1", "act1"]),
    (6, "ReceiptIssued", "e6", {"digest": "sha256:abc", "evidence_path": "."}, ["ep1", "rcpt1"]),
    (7, "LoopClosed", "e7", {"label": "run"}, ["ep1"]),
])

detail = {}
all_clean = True
for p in (empty, objects_only, only_closed, failed_no_obs):
    py = fired(python_engine(p))
    sq = sparql_engine(p)
    detail[p.rsplit("/", 1)[1]] = {"validate": validate(p), "python": py,
                                   "sparql": fired(sq) if sq is not None else "rdflib-absent"}
    all_clean &= not py and (sq is None or not any(sq.values()))
sys.exit(verdict("F01_empty_log_is_conformant", all_clean, detail))
