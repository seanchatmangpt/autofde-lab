#!/usr/bin/env python3
"""F03 (BREAKS_CLAIM): rules.json min_keyword_score=0.5, yet resolve() admits AND selects a
marketplace pack with score 0.25. search_marketplace tests full_score >= MIN_SCORE, then
averages with name_score (0) -> 0.25, never re-checked. Real data: ['deliver','notification']
-> beam4pm-mcp-contracts-pack 0.25 selected over ontology deliver_notification 1.0."""
from _common import R, MARKET, ONTOLOGY, base
gap = {"keywords": ["deliver", "notification"]}
res = R.resolve(gap, [], marketplace_dir=MARKET, ontology_dir=ONTOLOGY)
print("selected:", res.selected.kind, base(res.selected.ref), res.selected.score)
low = [c for c in res.candidates + res.dominated if c.score < R.MIN_SCORE and c.kind != "MANUFACTURING_GAP"]
print("admitted below MIN_SCORE:", len(low), [(base(c.ref), c.score) for c in low[:5]])
assert not low, f"WRONG: {len(low)} candidates below min_keyword_score={R.MIN_SCORE} admitted; selected score={res.selected.score}"
print("F03 did not reproduce")
