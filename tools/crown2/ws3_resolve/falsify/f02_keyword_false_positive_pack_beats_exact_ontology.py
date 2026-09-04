#!/usr/bin/env python3
"""F02 (BREAKS_CLAIM): real data. Gap keywords ['close','finding'] has an exact ontology
individual afl:domain_terragoat_cap_close_finding (capabilityName close_finding, score 1.0).
resolve() selects github-actions-pack (score 0.5) because its prose description contains
'closing ... gap ... found' -> tokens 'close'/'finding' are NOT even both there; only the
description-vs-name mean admits it. Semantics unrelated (GitHub Actions workflow gates).
Expected: an exact-name ontology capability outranks a partial prose keyword hit."""
import os
from _common import R, MARKET, ONTOLOGY, base
gap = {"keywords": ["close", "finding"]}
res = R.resolve(gap, [], marketplace_dir=MARKET, ontology_dir=ONTOLOGY)
print("selected:", res.selected.kind, base(res.selected.ref), res.selected.score, res.selected.matched_keywords)
onto = [c for c in res.candidates if c.kind == "ontology_capability"]
print("ontology candidates:", [(c.ref, c.score, c.evidence["capabilityName"]) for c in onto])
assert onto and onto[0].score == 1.0
assert res.selected.kind == "ontology_capability", (
    f"WRONG: keyword false-positive {base(res.selected.ref)} (score {res.selected.score}) "
    f"selected over exact ontology capability {onto[0].ref} (score 1.0)")
print("F02 did not reproduce")
