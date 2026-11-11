"""Acceptance: run every ~/plan K14 case through k14_autofde.run and compare to Case.expect.

Run: cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests uv run --quiet python <this file>
Exit 1 on any mismatch, any SKIP, or a Traceback in the unsolvable case's output.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from plankinds import k14_autofde as k14


def main() -> int:
    sk = k14.probe()
    if sk:
        print(f"SKIP: {sk.reason} | {sk.hint}")
        return 1
    bad = 0
    print(f"{'case':28} {'expect':11} {'got':11} ok  detail")
    for c in k14.cases():
        o = k14.run(c)
        ok = o.status == c.expect
        bad += not ok
        print(f"{c.id:28} {c.expect:11} {o.status:11} {'Y' if ok else 'N':3} {o.detail[:80]!r}")
    # Traceback check: run the unsolvable case directly (Outcome.detail truncates output).
    u = next(c for c in k14.cases() if c.id == "pddl-unsolvable")
    with tempfile.TemporaryDirectory() as d:
        prob = Path(d) / "problem.pddl"
        prob.write_text(u.payload["problem_text"])
        r = subprocess.run(["uv", "run", "--quiet", "--project", str(k14.REPO), "python", "-m",
                            "autofde_lab.fabric.pddl_engine", u.payload["domain"], str(prob),
                            str(Path(d) / "plan.txt")], capture_output=True, text=True)
    tb = "Traceback" in r.stdout + r.stderr
    clean = "no plan exists" in (r.stdout + r.stderr)
    print(f"unsolvable: rc={r.returncode} traceback={tb} 'no plan exists'={clean}")
    print(f"  stdout={r.stdout.strip()[-160:]!r}\n  stderr={r.stderr.strip()[-160:]!r}")
    bad += tb
    print("RESULT:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
