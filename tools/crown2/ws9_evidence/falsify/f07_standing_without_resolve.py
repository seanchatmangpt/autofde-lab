#!/usr/bin/env python3
"""
F07 — "standing is issued only if every ref resolves" is enforced only inside
the `standing()` function. The `Standing` / `Resolution` types carry no
invariant, no digest of the resolutions, no timestamp: a Standing with
issued=True can be constructed with zero resolutions, a refused Resolution can
be mutated to RESOLVED after the fact, and `Standing.to_dict()` output is
indistinguishable from a real one. The gate CLI's --json output is therefore
unverifiable by any consumer.

severity WEAKENS_CLAIM (invariant is procedural, not structural).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import cleanup, evidence, fresh_scratch, report  # noqa: E402

d = fresh_scratch("f07")
ghost = evidence.EvidenceRef("ghost", os.path.join(d, "never-written.jsonl"), "00" * 32, "jsonl")

# 1. Standing issued with no resolve() ever run
forged = evidence.Standing("crown-run-v2-happened", True, "STANDING", [])
# 2. Real refusal, mutated into RESOLVED
real = evidence.standing(evidence.Claim("c", "", (ghost,)))
real.resolutions[0].status = evidence.RESOLVED
real.issued = True; real.status = "STANDING"
# 3. Neither is distinguishable from an honest Standing by shape
honest_keys = set(json.loads(json.dumps(evidence.standing(evidence.Claim("c", "", (ghost,))).to_dict())).keys())

detail = (
    f"  forged.to_dict()   = {forged.to_dict()}\n"
    f"  mutated.issued     = {real.issued}, resolutions[0].resolved={real.resolutions[0].resolved}, "
    f"checks[0].ok={real.resolutions[0].checks[0].ok}\n"
    f"  keys(honest)={sorted(honest_keys)}  keys(forged)={sorted(forged.to_dict())}\n"
)
reproduced = forged.issued and not forged.resolutions and real.issued and real.resolutions[0].resolved \
    and not real.resolutions[0].checks[0].ok and honest_keys == set(forged.to_dict())
report("Standing constructible/mutable without resolve(); no integrity binding", "WEAKENS_CLAIM", reproduced, detail)
cleanup("f07")
assert reproduced, "F07 did not reproduce"
