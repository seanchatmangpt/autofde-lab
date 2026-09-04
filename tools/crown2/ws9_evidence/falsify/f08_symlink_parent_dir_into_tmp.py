#!/usr/bin/env python3
"""
F08 — Hypothesis: a durable-looking path whose PARENT DIRECTORY (not the leaf)
is a symlink into $TMPDIR/ /tmp slips past DurabilityCheck (the builder only
tested a leaf symlink). Also: a hardlink from /tmp.

Result recorded honestly below (realpath resolves intermediate components,
so the directory-symlink variant is expected NOT to reproduce; the hardlink
variant is genuinely durable — the inode survives /tmp cleanup — so a
RESOLVED there is correct, not a counterexample).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import cleanup, evidence, fresh_scratch, report, write  # noqa: E402

d = fresh_scratch("f08")
tmp_dir = os.path.join(os.environ.get("TMPDIR", "/tmp"), "ws9-f08"); os.makedirs(tmp_dir, exist_ok=True)
target = write(os.path.join(tmp_dir, "hook.jsonl"), '{"i": 0}\n')
os.symlink(tmp_dir, os.path.join(d, "runs"))              # directory symlink
via_dir_link = os.path.join(d, "runs", "hook.jsonl")
hard = os.path.join(d, "hard.jsonl"); os.link(target, hard)  # hardlink

r_dir = evidence.resolve(evidence.EvidenceRef("h", via_dir_link, evidence.sha256_of(target), "jsonl"))
r_hard = evidence.resolve(evidence.EvidenceRef("h", hard, evidence.sha256_of(target), "jsonl"))
os.remove(target); os.rmdir(tmp_dir)
r_hard_after_tmp_gone = evidence.resolve(evidence.EvidenceRef("h", hard, evidence.sha256_of(hard), "jsonl"))

detail = (
    f"  dir-symlink -> tmp : {r_dir.status} ({r_dir.checks[0].reason})\n"
    f"  hardlink from tmp  : {r_hard.status}; after tmp file removed: {r_hard_after_tmp_gone.status}\n"
)
reproduced = r_dir.resolved
report("parent-directory symlink into tmp evades DurabilityCheck", "BREAKS_CLAIM", reproduced, detail)
cleanup("f08")
