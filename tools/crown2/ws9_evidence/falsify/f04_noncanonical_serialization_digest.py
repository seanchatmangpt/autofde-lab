#!/usr/bin/env python3
"""
F04 — DigestCheck hashes raw bytes, not canonical content. The SAME OCEL log
re-serialized (indent / key order / trailing newline) is REFUSED, while the
ReplayCheck (the real validator) accepts both identically. Conversely nothing
canonicalizes before hashing, so a ref cannot be matched against a regenerated
but semantically identical artifact.

This is a false REFUSAL (soundness preserved, completeness lost):
severity WEAKENS_CLAIM.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import TARGET, cleanup, evidence, fresh_scratch, report, write  # noqa: E402

d = fresh_scratch("f04")
src = os.path.join(TARGET, "fixtures", "crown-run-v2.ocel.json")
with open(src, encoding="utf-8") as f:
    doc = json.load(f)
a = write(os.path.join(d, "a.ocel.json"), json.dumps(doc, indent=2, sort_keys=True) + "\n")
b = write(os.path.join(d, "b.ocel.json"), json.dumps(doc, separators=(",", ":")))

ref_a = evidence.make_ref("crown", a, "ocel")
same_content_other_bytes = evidence.EvidenceRef("crown", b, ref_a.sha256, "ocel")
res_b = evidence.resolve(same_content_other_bytes)
replay_a = evidence.replay_check(a, "ocel"); replay_b = evidence.replay_check(b, "ocel")

detail = (
    f"  a sha={ref_a.sha256[:16]}  b sha={evidence.sha256_of(b)[:16]}\n"
    f"  replay(a)={replay_a.ok} {replay_a.detail}\n  replay(b)={replay_b.ok} {replay_b.detail}\n"
    f"  resolve(b with a's sha) -> {res_b.status}\n"
)
reproduced = res_b.status == evidence.refusal("DigestCheck") and replay_a.ok and replay_b.ok \
    and replay_a.detail == replay_b.detail
report("byte-digest refuses semantically identical re-serialization", "WEAKENS_CLAIM", reproduced, detail)
cleanup("f04")
assert reproduced, "F04 did not reproduce"
