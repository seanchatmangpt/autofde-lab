#!/usr/bin/env python3
"""F01 (BREAKS_CLAIM): a composition covers the transition, but resolve() selects a
local action that neither is applicable from current_facts nor achieves needed_facts.
Cause: local_action keyword-only hits are halved to exactly MIN_SCORE (0.5) and stay
admitted; rank-1 sort_key then outranks the rank-3 chain with score 1.0 (no domination
either way). Correct answer: selected must cover needed_facts when any candidate does."""
from _common import R, base
acts = [
    {"name": "release_tag_note", "preconditions": ["never_true"], "postconditions": ["note_written"]},
    {"name": "run_tests", "preconditions": ["on_branch"], "postconditions": ["tests_green"]},
    {"name": "tag_release", "preconditions": ["tests_green"], "postconditions": ["release_tagged"]},
]
gap = {"keywords": ["release", "tag"], "current_facts": ["on_branch"], "needed_facts": ["release_tagged"]}
res = R.resolve(gap, acts, marketplace_dir="/nonexistent", ontology_dir="/nonexistent")
print("selected:", res.selected.kind, res.selected.ref, "score", res.selected.score, "evidence", res.selected.evidence)
print("candidates:", [(c.kind, c.ref, c.score, c.depth) for c in res.candidates])
covering = [c for c in res.candidates if c.kind == "composable_chain" and c.score == 1.0]
assert covering, "expected a covering chain run_tests>tag_release among candidates"
assert res.selected.evidence.get("covers_needed_facts") is True or res.selected.kind == "composable_chain", (
    f"WRONG: selected {res.selected.ref!r} does not achieve needed_facts while {covering[0].ref!r} does")
print("F01 did not reproduce")
