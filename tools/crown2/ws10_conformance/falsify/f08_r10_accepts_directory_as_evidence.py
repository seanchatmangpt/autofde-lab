#!/usr/bin/env python3
"""F08 — R10 checks os.path.exists only: evidence_path "." (the evidence root
itself), "/" and "../.." all count as present evidence. Also an event-level
evidence_path overrides a Receipt object's path even when they disagree, and
the Receipt's own path is never checked when the event carries one."""
import sys

from _harness import build, fired, python_engine, sparql_engine, verdict

EVR = "/Users/sac/crown-2-orthogonal/tools/crown2/ws10_conformance/fixtures"
detail, ok = {}, True
for tag, path in (("dot", "."), ("root", "/"), ("dotdot", "../.."), ("dir", "evidence")):
    p = build(f"f08_r10_{tag}", [
        (1, "ReceiptIssued", "e15", {"digest": "sha256:abc", "evidence_path": path}, ["ep1", "rcpt1"]),
    ])
    py = fired(python_engine(p, EVR))
    sq = sparql_engine(p, EVR)
    detail[tag] = {"evidence_path": path, "python": py, "sparql": sq and fired(sq)}
    ok &= not py and (sq is None or not any(sq.values()))
sys.exit(verdict("F08_r10_accepts_directory_as_evidence", ok, detail))
