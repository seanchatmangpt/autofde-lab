#!/usr/bin/env python3
"""
F01 — A file that physically lives in $TMPDIR (~/.cache/tmp) RESOLVES when
referenced through a case-variant spelling of the path.

macOS APFS (default) is case-insensitive; os.path.realpath preserves the
caller's casing, so `/Users/sac/.CACHE/tmp/x` never string-matches the
transient root `/Users/sac/.cache/tmp` in `_under`, but IS under $HOME.
The target then says RESOLVED for a transient-only artifact.

Expected (correct) answer: REFUSED[...:DurabilityCheck]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import evidence, report, write  # noqa: E402

tmpdir = os.environ.get("TMPDIR")
if not tmpdir or os.path.realpath(tmpdir) == os.path.realpath(tmpdir).lower():
    pass

real_dir = os.path.join(os.path.realpath(tmpdir), "ws9-f01")
real_file = write(os.path.join(real_dir, "hook.jsonl"), '{"i": 0}\n')

# Build a case-variant spelling of the same path (flip one directory component).
parts = real_file.split(os.sep)
# find a lowercase alpha component below /Users/<user>/ to upper-case
idx = next(i for i in range(3, len(parts) - 1) if parts[i] and parts[i] != parts[i].upper())
parts[idx] = parts[idx].upper()
variant = os.sep.join(parts)

assert os.path.exists(variant), "filesystem is case-sensitive; F01 not applicable here"
assert os.path.realpath(variant) != real_file, "realpath normalized case; F01 not applicable"

sha = evidence.sha256_of(real_file)
honest = evidence.resolve(evidence.EvidenceRef("hook", real_file, sha, "jsonl"))
sneaky = evidence.resolve(evidence.EvidenceRef("hook", variant, sha, "jsonl"))

detail = (
    f"  real file : {real_file}\n"
    f"  honest ref: {honest.status}\n"
    f"  variant   : {variant}\n"
    f"  variant ref: {sneaky.status}  checks[0]={honest.checks[0].reason!r} / {sneaky.checks[0].detail}\n"
)
reproduced = honest.status.startswith(evidence.REFUSAL_PREFIX) and sneaky.status == evidence.RESOLVED
report("case-variant path into $TMPDIR resolves", "BREAKS_CLAIM", reproduced, detail)
os.remove(real_file)
os.rmdir(real_dir)
assert reproduced, "F01 did not reproduce"
