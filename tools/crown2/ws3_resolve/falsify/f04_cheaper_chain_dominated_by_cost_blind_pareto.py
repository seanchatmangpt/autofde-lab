#!/usr/bin/env python3
"""F04 (WEAKENS_CLAIM): domination ignores chain cost. A depth-2 chain of total_cost 200
dominates a depth-3 chain of total_cost 3; the cheap alternative is moved to dominated[]
although it is non-dominated on the (depth, cost) trade-off. rules.json names only
(rank, score, depth) so this is a documented-but-lossy objective, hence WEAKENS."""
from _common import R
acts = [
    {"name": "big_jump", "preconditions": ["s0"], "postconditions": ["s2"], "cost": 100},
    {"name": "finish", "preconditions": ["s2"], "postconditions": ["goal"], "cost": 100},
    {"name": "a", "preconditions": ["s0"], "postconditions": ["s1"], "cost": 1},
    {"name": "b", "preconditions": ["s1"], "postconditions": ["s2b"], "cost": 1},
    {"name": "c", "preconditions": ["s2b"], "postconditions": ["goal"], "cost": 1},
]
gap = {"keywords": ["zz"], "current_facts": ["s0"], "needed_facts": ["goal"]}
res = R.resolve(gap, acts, marketplace_dir="/nonexistent", ontology_dir="/nonexistent")
print("candidates:", [(c.ref, c.depth, c.evidence["total_cost"]) for c in res.candidates])
print("dominated :", [(c.ref, c.depth, c.evidence["total_cost"]) for c in res.dominated])
cheap = [c for c in res.candidates if c.ref == "a>b>c"]
assert cheap, "WRONG: cheapest chain a>b>c (cost 3) dropped to dominated[] by big_jump>finish (cost 200)"
print("F04 did not reproduce")
