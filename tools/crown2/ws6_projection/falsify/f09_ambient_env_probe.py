"""F09 (expected NOT to reproduce): digest stability across PYTHONHASHSEED, locale, cwd, TZ.
Runs the projection in fresh subprocesses with perturbed environments and compares digests."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
prog = r'''
import sys; sys.path.insert(0, %r)
from _target import *
g,_ = add_qualified(empty_graph(), QualifiedCapabilityReceipt("cap.é", "act", "qr", "sha256:00", ("pü",), (), ("s",)))
print(project_domain(g, {"facts": ["pü", 3.5, 10**20]}, {"scopes": ["s"]})["digest"])
''' % HERE
envs = []
for seed in ("0", "1", "12345", "random"):
    for loc in ("C", "en_US.UTF-8", "tr_TR.UTF-8"):
        e = dict(os.environ, PYTHONHASHSEED=seed, LC_ALL=loc, LANG=loc, TZ="Asia/Kolkata")
        envs.append(e)
outs = set()
for e in envs:
    p = subprocess.run([sys.executable, "-c", prog], env=e, capture_output=True, text=True, cwd=tempfile.gettempdir())
    assert p.returncode == 0, p.stderr
    outs.add(p.stdout.strip())
print("distinct digests over", len(envs), "environments:", len(outs), list(outs))
assert len(outs) == 1, "REPRODUCED: ambient environment changed digest"
print("NOT_REPRODUCED: digest ambient-independent")
