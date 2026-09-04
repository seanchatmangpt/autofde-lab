#!/usr/bin/env python3
"""F06 (BREAKS_CLAIM): a marketplace pack whose name exactly covers the gap (ocel-drift-pack,
score 1.0) loses to a local action whose preconditions are NOT satisfied from current_facts
and which does not produce needed_facts (score halved to 0.5). Neither dominates, rank wins."""
from _common import R, MARKET, base
acts = [{"name": "ocel_drift_summary", "preconditions": ["never_true"], "postconditions": ["summary_md"]}]
gap = {"keywords": ["ocel", "drift"], "current_facts": ["ocel_log_present"], "needed_facts": ["drift_report"]}
res = R.resolve(gap, acts, marketplace_dir=MARKET, ontology_dir="/nonexistent")
print("selected:", res.selected.kind, base(res.selected.ref), res.selected.score, res.selected.evidence)
packs = [c for c in res.candidates if c.kind == "marketplace_pack" and c.score == 1.0]
print("full-cover packs retained:", [base(c.ref) for c in packs])
assert res.selected.evidence.get("applicable_from_current_facts", True), (
    f"WRONG: non-applicable local action {res.selected.ref!r} selected over full-cover pack(s) {[base(c.ref) for c in packs]}")
print("F06 did not reproduce")
