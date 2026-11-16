"""replay.py verify receipts.jsonl -- recompute hash chain, identity digests, and (sequential) state replay."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pddl import GENESIS, Problem, State, apply_delta, canon, sha

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def verify(path, problem_path=None):
    raw = open(path, "rb").read().decode()
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    prob_text = open(problem_path or os.path.join(FX, "problem_enterprise_ops.pddl")).read()
    st0 = Problem(prob_text)
    st = State(st0.facts, st0.fluents)
    prev = GENESIS
    for i, ln in enumerate(lines):
        try:
            r = json.loads(ln)
        except Exception as e:
            return False, f"receipt {i}: unparseable ({e})"
        if canon(r) != ln:
            return False, f"receipt {i}: non-canonical bytes"
        rep = r.get("replay", {})
        if rep.get("prev") != prev:
            return False, f"receipt {i}: chain break (prev mismatch)"
        body = {k: v for k, v in r.items() if k != "replay"}
        if sha(prev + canon(body)) != rep.get("this"):
            return False, f"receipt {i}: hash mismatch"
        idn = r["identity"]
        if idn["digest"] != sha(idn["domain_sha256"] + idn["problem_sha256"] + idn["action"] + idn["state_before"]):
            return False, f"receipt {i}: identity digest mismatch"
        if idn["problem_sha256"] != sha(prob_text):
            return False, f"receipt {i}: problem sha mismatch"
        if idn["state_before"] != st.hash():
            return False, f"receipt {i}: state_before != replayed state"
        apply_delta(st, r["consequence"]["delta"])
        if r["consequence"]["state_after"] != st.hash():
            return False, f"receipt {i}: state_after != replayed state"
        prev = rep["this"]
    return True, f"{len(lines)} receipts verified, head={prev[:16]}"


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "verify":
        print("usage: replay.py verify receipts.jsonl"); sys.exit(64)
    ok, msg = verify(sys.argv[2])
    print(("VERIFIED: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)
