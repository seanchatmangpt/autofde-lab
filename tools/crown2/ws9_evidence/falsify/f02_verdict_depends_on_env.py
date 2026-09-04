#!/usr/bin/env python3
"""
F02 — The durability verdict for one fixed file is a function of the CALLER'S
ENVIRONMENT, not of the filesystem. `transient_roots()` derives $TMPDIR from
os.environ at check time; on this machine TMPDIR=~/.cache/tmp, which is under
$HOME. Run the gate CLI with TMPDIR unset (cron / launchd / `env -i`) and the
very same ~/.cache/tmp artifact that the builder's demo REFUSES becomes
RESOLVED.

Expected (correct) answer: same verdict regardless of environment.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import TARGET, evidence, report, write  # noqa: E402

home = os.path.expanduser("~")
cache_tmp = os.path.join(home, ".cache", "tmp")
art = write(os.path.join(cache_tmp, "ws9-f02", "hook.jsonl"), '{"i": 0}\n')
refs = write(os.path.join(cache_tmp, "ws9-f02", "refs.json"), json.dumps({"refs": [
    {"identity": "hook", "durable_path": art, "sha256": evidence.sha256_of(art), "parser": "jsonl"}]}))
gate = os.path.join(TARGET, "evidence_gate.py")

with_env = subprocess.run([sys.executable, gate, refs], capture_output=True, text=True,
                          env={**os.environ, "TMPDIR": cache_tmp})
no_env = subprocess.run([sys.executable, gate, refs], capture_output=True, text=True,
                        env={"HOME": home, "PATH": os.environ["PATH"]})

detail = (
    f"  artifact: {art}\n"
    f"  TMPDIR={cache_tmp}: exit={with_env.returncode}\n    {with_env.stdout.strip()}\n"
    f"  env -i HOME only : exit={no_env.returncode}\n    {no_env.stdout.strip()}\n"
    f"  stderr(no_env)={no_env.stderr.strip()[:200]!r}\n"
)
reproduced = with_env.returncode == 1 and no_env.returncode == 0
report("verdict flips with caller env (TMPDIR unset => ~/.cache/tmp is 'durable')", "BREAKS_CLAIM", reproduced, detail)
os.remove(art); os.remove(refs); os.rmdir(os.path.dirname(art))
assert reproduced, "F02 did not reproduce"
