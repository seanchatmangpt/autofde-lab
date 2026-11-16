#!/usr/bin/env python3
"""Fail-closed Diataxis verifier (skeleton).

Checks: (1) VERIFIED-BY marker parse + pytest, (2) runnable blocks, (3) reference drift,
(4) jargon/TODO/literal/sleep lint, (5) non-vacuity self-check with sha256 restore.
Exit 0 only if every check passes. Missing docs/inputs are failures, never skips.
Usage: verify_diataxis.py [--root DIR] [--only N,N] [--self-check] [--no-pytest]
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUADS = ["01-TUTORIAL.md", "02-HOW-TO-GUIDES.md", "03-REFERENCE.md", "04-EXPLANATION.md"]
JARGON_DOCS = ["01-TUTORIAL.md", "02-HOW-TO-GUIDES.md", "04-EXPLANATION.md"]
JARGON = ["PDDL", "MiniZinc", "CP-SAT", "satisficing", "timed initial literals", "TIL",
          "delete-relaxation", "token-based replay", "inductive miner", "Petri", "OCEL",
          "SHACL", "aries"]
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX|lorem ipsum)\b|<placeholder>|\?\?\?", re.I)
MARKER = re.compile(r"<!--\s*VERIFIED-BY:\s*(.*?)\s*-->")
DIALS = re.compile(r"<!--\s*DIALS:\s*(.*?)\s*-->")
UNSUP = re.compile(r"<!--\s*UNSUPPORTED:\s*(.*?)\s*-->")
BLOCK = re.compile(r"```bash runnable[^\n]*\n(.*?)```", re.S)
HEAD = re.compile(r"^(#{2,3})\s+(.*)$", re.M)


class Fail(Exception):
    pass


def read(p: Path) -> str:
    if not p.is_file():
        raise Fail(f"MISSING[{p}]")
    return p.read_text()


def sections(text):
    hs = list(HEAD.finditer(text))
    for i, h in enumerate(hs):
        end = hs[i + 1].start() if i + 1 < len(hs) else len(text)
        yield h.group(2).strip(), text[h.end():end]


def pytest_cmd(root, nodes):
    cmd = ["uv", "run", "--quiet", "--with", "pytest", "--with", "factory-boy",
           "--with", "faker", "--with", "hypothesis", "--with", "allpairspy",
           "--with", "/Users/sac/pm4pytest", "--with", "playwright",
           "pytest", "-q", *nodes]
    env = dict(os.environ, PYTHONPATH=f"{root}/pipeline:{root}/pipeline/tests")
    return cmd, env


def check1(root, docs, run_pytest=True):
    errs, nodes = [], []
    for name in ("01-TUTORIAL.md", "02-HOW-TO-GUIDES.md"):
        try:
            text = read(docs / name)
        except Fail as e:
            errs.append(str(e)); continue
        n_sec = 0
        for title, body in sections(text):
            n_sec += 1
            ids = [n.strip() for m in MARKER.finditer(body) for n in m.group(1).split(",") if n.strip()]
            if UNSUP.search(body) and not ids:
                continue
            if not ids:
                errs.append(f"NO_MARKER[{name}:{title}]"); continue
            if len(ids) < 2 or not any("twin" in i.lower() for i in ids):
                errs.append(f"NO_TWIN[{name}:{title}] need positive + node id containing 'twin'")
            nodes += ids
        if n_sec == 0:
            errs.append(f"NO_SECTIONS[{name}]")
    for name in ("03-REFERENCE.md", "04-EXPLANATION.md"):
        try:
            text = read(docs / name)
        except Fail as e:
            errs.append(str(e)); continue
        for title, body in sections(text):
            if not MARKER.search(body) and not UNSUP.search(body):
                errs.append(f"NO_MARKER[{name}:{title}]")
            nodes += [n.strip() for m in MARKER.finditer(body) for n in m.group(1).split(",") if n.strip()]
    for n in dict.fromkeys(nodes):
        if not (root / n.split("::")[0]).is_file():
            errs.append(f"NODE_FILE_MISSING[{n}]")
    if run_pytest and not errs and nodes:
        cmd, env = pytest_cmd(root, list(dict.fromkeys(nodes)))
        r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            errs.append(f"PYTEST_RC[{r.returncode}] {r.stdout[-400:]}")
    return errs


def check2(root, docs):
    errs, total = [], 0
    for name in QUADS:
        p = docs / name
        if not p.is_file():
            errs.append(f"MISSING[{p}]"); continue
        for i, m in enumerate(BLOCK.finditer(p.read_text())):
            total += 1
            body = m.group(1)
            want_rc = int(next(iter(re.findall(r"^#\s*expect-rc:\s*(\d+)", body, re.M)), "0"))
            wants = re.findall(r"^#\s*expect:\s*(.+)$", body, re.M)
            with tempfile.TemporaryDirectory() as store:
                env = dict(os.environ, PLAN_STORE=store)
                r = subprocess.run(["bash", "-c", "set -o pipefail\n" + body], cwd=root,
                                   env=env, capture_output=True, text=True, timeout=300)
            out = r.stdout + r.stderr
            if r.returncode != want_rc:
                errs.append(f"BLOCK_RC[{name}#{i}] got {r.returncode} want {want_rc}")
            errs += [f"BLOCK_OUT[{name}#{i}] missing {w!r}" for w in wants if w not in out]
    return errs


def extract_reference_sets(root):
    store = (root / "pipeline/enterprise_pipeline/store.py").read_text()
    align = (root / "pipeline/enterprise_pipeline/align.py").read_text()
    kinds = set()
    for line in store.splitlines():
        if re.search(r"\bkind\s*(==|in\b)", line) or "OBSERVATIONS" in line:
            kinds |= set(re.findall(r'"([a-z_]+)"', line))
    refused = set(re.findall(r'Refused\(f?"([A-Z_]+)', store))
    m = re.search(r"^DIMS\s*=\s*\[(.*?)\]", align, re.M)
    dims = set(re.findall(r'"(\w+)"', m.group(1))) if m else set()
    dials = set()
    d = root / "pipeline/policy_dials.toml"
    if d.is_file():
        def walk(o, pre=""):
            for k, v in o.items():
                (walk(v, pre + k + ".") if isinstance(v, dict) else dials.add(pre + k))
        walk(tomllib.loads(d.read_text()))
    return {"event kinds": kinds, "refusal codes": refused, "dimensions": dims, "dials": dials}


def check3(root, docs):
    text = read(docs / "03-REFERENCE.md")
    sets = extract_reference_sets(root)
    errs = []
    for key, want in sets.items():
        body = next((b for t, b in sections(text) if key in t.lower()), None)
        if body is None:
            errs.append(f"REF_SECTION_MISSING[{key}]"); continue
        got = set()
        for line in body.splitlines():
            m = re.match(r"\s*(?:\||[-*])\s*`([^`]+)`", line)
            if m:
                got.add(re.match(r"[A-Za-z0-9_.]+", m.group(1)).group(0) if key != "dials" else m.group(1))
        errs += [f"UNDOCUMENTED[{key}:{x}]" for x in sorted(want - got)]
        errs += [f"PHANTOM[{key}:{x}]" for x in sorted(got - want)]
    return errs


LITERAL = re.compile(r'(?:"(?:Acme|Barrel|Contoso)[^"]*"|\b\d+(?:_\d{3})+\b|"\$\d+|rate_cents\s*=\s*\d+)')
SLEEP = re.compile(r"\btime\.sleep\(")


def check4(root, docs):
    errs = []
    for name in QUADS:
        p = docs / name
        if not p.is_file():
            errs.append(f"MISSING[{p}]"); continue
        t = p.read_text()
        if PLACEHOLDER.search(t):
            errs.append(f"PLACEHOLDER[{name}] {PLACEHOLDER.search(t).group(0)}")
        if name in JARGON_DOCS:
            for j in JARGON:
                if re.search(rf"(?<!\w){re.escape(j)}(?!\w)", t):
                    errs.append(f"JARGON[{name}:{j}]")
    td = root / "pipeline/tests/diataxis"
    if not td.is_dir():
        errs.append(f"MISSING[{td}]")
    else:
        files = sorted(td.rglob("*.py"))
        if not files:
            errs.append(f"EMPTY[{td}]")
        for f in files:
            for n, line in enumerate(f.read_text().splitlines(), 1):
                if LITERAL.search(line):
                    errs.append(f"LITERAL[{f.relative_to(root)}:{n}]")
                if SLEEP.search(line) and "SLEEP-CLASS: POLL-STEP" not in line:
                    errs.append(f"SLEEP[{f.relative_to(root)}:{n}]")
    return errs


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_checks(root, docs, only, run_pytest):
    fns = {1: lambda: check1(root, docs, run_pytest), 2: lambda: check2(root, docs),
           3: lambda: check3(root, docs), 4: lambda: check4(root, docs)}
    bad = 0
    for n in only:
        try:
            errs = fns[n]()
        except Fail as e:
            errs = [str(e)]
        except Exception as e:  # fail closed on any verifier error
            errs = [f"VERIFIER_ERROR[{type(e).__name__}: {e}]"]
        print(f"[check{n}] {'PASS' if not errs else 'FAIL'}")
        for e in errs:
            print(f"  {e}")
        bad += bool(errs)
    return bad


def build_fixture(scratch):
    for sub in ("pipeline/enterprise_pipeline", "pipeline/tests/diataxis", "docs/diataxis"):
        (scratch / sub).mkdir(parents=True)
    (scratch / "pipeline/enterprise_pipeline/store.py").write_text(
        'if kind == "alpha":\n    raise Refused("BAD_ONE")\n')
    (scratch / "pipeline/enterprise_pipeline/align.py").write_text('DIMS = ["d1"]\n')
    (scratch / "pipeline/policy_dials.toml").write_text("dial_one = 1\n")
    (scratch / "pipeline/tests/diataxis/test_x.py").write_text(
        "def test_ok(): pass\ndef test_twin(): pass\n")
    d = scratch / "docs/diataxis"
    m = ("<!-- VERIFIED-BY: pipeline/tests/diataxis/test_x.py::test_ok, "
         "pipeline/tests/diataxis/test_x.py::test_twin -->\n")
    (d / "01-TUTORIAL.md").write_text(f"# T\n\n## Step\n{m}text\n")
    (d / "02-HOW-TO-GUIDES.md").write_text(f"# H\n\n## Recipe\n{m}text\n")
    (d / "03-REFERENCE.md").write_text(
        "# R\n\n## Event kinds\n<!-- UNSUPPORTED: fx -->\n- `alpha`\n"
        "## Refusal codes\n<!-- UNSUPPORTED: fx -->\n- `BAD_ONE`\n"
        "## Dimensions\n<!-- UNSUPPORTED: fx -->\n- `d1`\n"
        "## Dials\n<!-- UNSUPPORTED: fx -->\n- `dial_one`\n")
    (d / "04-EXPLANATION.md").write_text("# E\n\n## Why\n<!-- UNSUPPORTED: x -->\ntext\n")
    return d


def self_check():
    """Check 5: mutate scratch copies; verifier must flip to FAIL; restore is sha256-exact."""
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        d = build_fixture(scratch)
        if run_checks(scratch, d, [1, 3, 4], False):
            print("[self-check] FAIL baseline fixture does not pass"); return 1
        mutations = [
            (scratch / "pipeline/policy_dials.toml", "dial_one", "dial_renamed", 3),
            (d / "01-TUTORIAL.md", "VERIFIED-BY", "VERIFIED_BY", 1),
            (d / "04-EXPLANATION.md", "text", "TODO text", 4),
        ]
        for f, a, b, chk in mutations:
            orig, h0 = f.read_bytes(), sha(f)
            f.write_text(orig.decode().replace(a, b, 1))
            print(f"[self-check] SHIM-COURT mutate {f.name}: {a}->{b} (check{chk})")
            bad = run_checks(scratch, d, [chk], False)
            f.write_bytes(orig)
            if not bad:
                print(f"[self-check] FAIL VACUOUS GATE: check{chk} accepted mutation"); return 1
            if sha(f) != h0:
                print("[self-check] FAIL restore not byte-exact"); return 1
            print(f"[self-check] restored {f.name} sha256={h0[:12]} flip=OK")
        # restore-detection non-vacuity: a corrupted restore must be caught
        f = d / "03-REFERENCE.md"
        h0 = sha(f)
        f.write_bytes(f.read_bytes() + b" ")
        if sha(f) == h0:
            print("[self-check] FAIL restore-detection vacuous"); return 1
        print("[self-check] restore-detection non-vacuous")
    print("[check5] PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--only", default="1,2,3,4")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--no-pytest", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    root = Path(a.root).resolve()
    only = [int(x) for x in a.only.split(",") if x]
    bad = run_checks(root, root / "docs/diataxis", only, not a.no_pytest)
    if bad == 0 and set(only) >= {1, 2, 3, 4}:
        bad = self_check()
    print("diataxis-check:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        print(f"VERIFIER_ERROR[{type(e).__name__}: {e}]")
        sys.exit(2)
