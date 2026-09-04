#!/usr/bin/env python3
"""
F03 — "durable" == "realpath under $HOME and not under a transient root".
Two directories under $HOME that are conventionally disposable are therefore
durable to the target:
  * ~/.Trash/<file>     — the user already deleted it; Finder "Empty Trash" wipes it
  * ~/.cache/<not tmp>  — XDG cache, purgeable by convention
A ref into either RESOLVES.

Expected (correct) answer: REFUSED[...:DurabilityCheck] (or at least a
distinguishable status).
"""
from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import evidence, report, write  # noqa: E402

home = os.path.expanduser("~")
paths = {
    "trash": os.path.join(home, ".Trash", "ws9-f03", "crown-run.jsonl"),
    "cache": os.path.join(home, ".cache", "ws9-f03", "crown-run.jsonl"),
}
results = {}
for name, p in paths.items():
    write(p, '{"i": 0}\n')
    results[name] = evidence.resolve(evidence.EvidenceRef("hook", p, evidence.sha256_of(p), "jsonl"))
    shutil.rmtree(os.path.dirname(p), ignore_errors=True)

detail = "".join(f"  {n}: {p} -> {results[n].status}\n" for n, p in paths.items())
reproduced = all(r.status == evidence.RESOLVED for r in results.values())
report("~/.Trash and ~/.cache artifacts resolve as durable", "WEAKENS_CLAIM", reproduced, detail)
assert reproduced, "F03 did not reproduce"
