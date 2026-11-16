#!/usr/bin/env python3
"""Receipt Standing-line law: line 2 = `Standing: <closed vocab>`; H1 on line 1."""
import re, sys, pathlib
VOCAB = {"ALIVE", "PARTIAL_ALIVE", "PASS", "BLOCKED", "UNVERIFIED", "PARTIAL"}
KEY = re.compile(r"^(?:Standing|Status|verdict|Result|Exit code):\s*(.*?)\s*$", re.I)

def lint(p):
    lines = p.read_text().splitlines()
    if len(lines) < 2:
        return "file shorter than 2 lines"
    if not lines[0].startswith("# "):
        return "line 1 is not an H1"
    m = KEY.match(lines[1].replace("**", ""))
    if not m:
        return "line 2 lacks a Standing line"
    val = re.sub(r"\(.*?\)", "", m.group(1)).strip().strip("`").split()
    val = val[0].strip("`.,;") if val else ""
    if val not in VOCAB:
        return f"unsupported standing {val!r}"
    return None

def main(d):
    bad = 0
    files = sorted(pathlib.Path(d).glob("*.md"))
    for p in files:
        e = lint(p)
        print(f"{'FAIL' if e else 'ok  '} {p.name}" + (f": {e}" if e else ""))
        bad += bool(e)
    print(f"{len(files)} receipts, {bad} failing")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "receipts"))
