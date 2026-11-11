#!/usr/bin/env python3
"""Deterministic stub register generator and closure gate.

Scans src/autofde_lab with ``ast`` (code stubs) and ``tokenize`` (comment markers).
Every site is classified ABSTRACT_BY_DESIGN, CLOSED, BLOCKED or OPEN.

  python scripts/stub_register.py --check   # exit 1 on OPEN / bad rows
  python scripts/stub_register.py --write   # regenerate docs/STUB-REGISTER.md
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
import tomllib
import warnings
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = REPO / "src" / "autofde_lab"
DEFAULT_DISP = REPO / "docs" / "jira" / "v26.11.11" / "stub-dispositions.toml"
DEFAULT_DOC = REPO / "docs" / "STUB-REGISTER.md"

DISPOSITIONS = {"CLOSED", "ABSTRACT_BY_DESIGN", "BLOCKED"}
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX)\b")
STUB_RE = re.compile(r"\b(STUB|PLACEHOLDER)\b")


def _deco_names(node) -> set[str]:
    out = set()
    for d in getattr(node, "decorator_list", []):
        t = d.func if isinstance(d, ast.Call) else d
        if isinstance(t, ast.Attribute):
            out.add(t.attr)
        elif isinstance(t, ast.Name):
            out.add(t.id)
    return out


def _base_names(cls: ast.ClassDef) -> set[str]:
    out = set()
    for b in cls.bases:
        t = b.value if isinstance(b, ast.Subscript) else b
        if isinstance(t, ast.Attribute):
            out.add(t.attr)
        elif isinstance(t, ast.Name):
            out.add(t.id)
    return out


def _is_empty_body(body: list[ast.stmt]) -> bool:
    for s in body:
        if isinstance(s, ast.Pass):
            continue
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            continue  # docstring or Ellipsis
        return False
    return True


def _nie_kind(node: ast.Raise) -> str | None:
    e = node.exc
    if isinstance(e, ast.Name) and e.id == "NotImplementedError":
        return "NIE_BARE"
    if (isinstance(e, ast.Call) and isinstance(e.func, ast.Name)
            and e.func.id == "NotImplementedError"):
        return "NIE_CALL"
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self):
        self.stack: list[str] = []
        self.classes: list[ast.ClassDef] = []
        self.funcs: list[ast.AST] = []
        self.sites: list[tuple[str, str, int, bool]] = []  # qual, kind, line, abstract

    def _qual(self) -> str:
        return ".".join(self.stack) or "<module>"

    def _abstract_ctx(self) -> bool:
        """Innermost enclosing function is abstract/overload or in a Protocol."""
        for f in reversed(self.funcs):
            if _deco_names(f) & {"abstractmethod", "overload"}:
                return True
        if self.classes and "Protocol" in _base_names(self.classes[-1]) and self.funcs:
            return True
        return False

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.classes.append(node)
        self.generic_visit(node)
        self.classes.pop()
        self.stack.pop()

    def _func(self, node):
        self.stack.append(node.name)
        if _is_empty_body(node.body):
            abstract = bool(_deco_names(node) & {"abstractmethod", "overload"}) or (
                bool(self.classes) and "Protocol" in _base_names(self.classes[-1])
                and len(self.stack) >= 2 and self.stack[-2] == self.classes[-1].name)
            self.sites.append((self._qual(), "EMPTY_BODY", node.lineno, abstract))
        self.funcs.append(node)
        self.generic_visit(node)
        self.funcs.pop()
        self.stack.pop()

    visit_FunctionDef = _func
    visit_AsyncFunctionDef = _func

    def visit_Raise(self, node):
        k = _nie_kind(node)
        if k:
            self.sites.append((self._qual(), k, node.lineno, self._abstract_ctx()))
        self.generic_visit(node)


def _enclosing(tree: ast.AST, line: int) -> str:
    best, best_span = "<module>", None

    def walk(node, stack):
        nonlocal best, best_span
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                st = stack + [ch.name]
                end = getattr(ch, "end_lineno", ch.lineno)
                if ch.lineno <= line <= end:
                    span = end - ch.lineno
                    if best_span is None or span <= best_span:
                        best, best_span = ".".join(st), span
                walk(ch, st)

    walk(tree, [])
    return best


def scan_file(path: Path, rel: str) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except SyntaxError:
        return [dict(path=rel, qual="<module>", kind="PARSE_ERROR", line=1, abstract=False)]
    v = _Visitor()
    v.visit(tree)
    sites = [dict(path=rel, qual=q, kind=k, line=ln, abstract=a) for q, k, ln, a in v.sites]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.COMMENT:
                continue
            ln = tok.start[0]
            for rx, kind in ((TODO_RE, "TODO"), (STUB_RE, "STUB_WORD")):
                if rx.search(tok.string):
                    sites.append(dict(path=rel, qual=_enclosing(tree, ln), kind=kind,
                                      line=ln, abstract=False))
    except (tokenize.TokenError, IndentationError):
        pass
    return sites


def scan(src_root: Path) -> list[dict]:
    base = src_root.parent  # keys are relative to src/
    sites: list[dict] = []
    for p in sorted(src_root.rglob("*.py")):
        sites.extend(scan_file(p, p.relative_to(base).as_posix()))
    sites.sort(key=lambda s: (s["path"], s["qual"], s["kind"], s["line"]))
    seen: Counter = Counter()
    for s in sites:
        k = f"{s['path']}::{s['qual']}::{s['kind']}"
        seen[k] += 1
        s["key"] = k if seen[k] == 1 else f"{k}#{seen[k]}"
    return sites


def load_dispositions(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _evidence_file(evidence: str) -> str | None:
    m = re.search(r"([\w./\-]+\.py)", evidence or "")
    return m.group(1) if m else None


def classify(sites: list[dict], disp: dict[str, dict]) -> None:
    for s in sites:
        row = disp.get(s["key"])
        if s["abstract"]:
            s["status"] = "ABSTRACT_BY_DESIGN"
        elif row and row.get("disposition") in DISPOSITIONS:
            s["status"] = row["disposition"]
        else:
            s["status"] = "OPEN"
        s["row"] = row


def problems(sites: list[dict], disp: dict[str, dict], repo: Path) -> list[str]:
    out = []
    keys = {s["key"] for s in sites}
    for k, row in sorted(disp.items()):
        d = row.get("disposition")
        if d not in DISPOSITIONS:
            out.append(f"BAD_DISPOSITION {k}: {d!r}")
            continue
        ev = (row.get("evidence") or "").strip()
        if d == "BLOCKED" and not ev:
            out.append(f"BLOCKED_NO_EVIDENCE {k}")
        if d == "CLOSED":
            ref = _evidence_file(ev)
            if ref and ref.startswith("tests/") and not (repo / ref).exists():
                out.append(f"CLOSED_TEST_MISSING {k}: {ref}")
            if not ev:
                out.append(f"CLOSED_NO_EVIDENCE {k}")
        if k not in keys and d != "CLOSED":
            # a CLOSED site that no longer scans as a stub is the point of closing it
            out.append(f"STALE_ROW {k}")
    for s in sites:
        if s["status"] == "OPEN":
            out.append(f"OPEN {s['key']} (line {s['line']})")
    return out


def _topdir(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 2 else "(root)"


def render(sites: list[dict]) -> str:
    kinds = sorted({s["kind"] for s in sites})
    statuses = ["OPEN", "BLOCKED", "CLOSED", "ABSTRACT_BY_DESIGN"]
    by_kind = Counter((s["kind"], s["status"]) for s in sites)
    by_dir = Counter((_topdir(s["path"]), s["status"]) for s in sites)
    dirs = sorted({_topdir(s["path"]) for s in sites})
    L = ["# STUB-REGISTER", "",
         "Written by `scripts/stub_register.py`; do not hand-edit. Every count below is",
         "produced by the script from `src/autofde_lab` and",
         "`docs/jira/v26.11.11/stub-dispositions.toml`.", "",
         "Regenerate: `.venv/bin/python scripts/stub_register.py --write`", "",
         "Gate: `.venv/bin/python scripts/stub_register.py --check` (exit 1 if any OPEN site,",
         "BLOCKED row without evidence, or CLOSED row whose test file is missing).", "",
         "## Totals", ""]
    tot = Counter(s["status"] for s in sites)
    L += ["| status | count |", "|---|---|"]
    L += [f"| {st} | {tot[st]} |" for st in statuses]
    L += [f"| TOTAL | {len(sites)} |", "", "## By category", "",
          "| kind | " + " | ".join(statuses) + " |", "|---|" + "---|" * len(statuses)]
    for k in kinds:
        L.append(f"| {k} | " + " | ".join(str(by_kind[(k, st)]) for st in statuses) + " |")
    L += ["", "## By directory (first level under src/autofde_lab)", "",
          "| directory | " + " | ".join(statuses) + " |", "|---|" + "---|" * len(statuses)]
    for d in dirs:
        L.append(f"| {d} | " + " | ".join(str(by_dir[(d, st)]) for st in statuses) + " |")
    L += ["", "## Non-trivial rows (every site not ABSTRACT_BY_DESIGN)", ""]
    for s in sites:
        if s["status"] == "ABSTRACT_BY_DESIGN":
            continue
        ev = (s.get("row") or {}).get("evidence") or ""
        L.append(f"- {s['status']} {s['kind']} line {s['line']}")
        L.append(f"  `{s['key']}`" + (f" evidence: {ev}" if ev else ""))
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--src-root", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--dispositions", type=Path, default=DEFAULT_DISP)
    ap.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    ap.add_argument("--repo", type=Path, default=REPO)
    a = ap.parse_args(argv)
    sites = scan(a.src_root)
    disp = load_dispositions(a.dispositions)
    classify(sites, disp)
    if a.write:
        a.doc.write_text(render(sites), encoding="utf-8")
        print(f"wrote {a.doc}")
    probs = problems(sites, disp, a.repo)
    tot = Counter(s["status"] for s in sites)
    od = Counter(_topdir(s["path"]) for s in sites if s["status"] == "OPEN")
    print("totals:", dict(sorted(tot.items())))
    print("OPEN by directory:", dict(sorted(od.items())))
    if a.check:
        for p in probs:
            print(p)
        print("REFUSED" if probs else "PASS", f"({len(probs)} problems)")
        return 1 if probs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
