#!/usr/bin/env python
"""ROM-clean proof for the coprocessor.

Copies ``src/autofde_lab`` to a temp dir, makes it read-only (chmod -R a-w), runs every
registered coprocessor kind as a subprocess against that copy, and asserts that no file
appeared, vanished or changed under the read-only tree (listing + sha256 before/after).
Also compares ``git status --porcelain`` of the real repo before/after (read-only git).
Kinds reporting BLOCKED are listed, never hidden.

Exit 0 only when the tree is clean and the non-vacuity court (a writing shim kind run
against a writable copy) is caught.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
SRC_PKG = REPO / "src" / "autofde_lab"

DOMAIN = """(define (domain rom) (:requirements :strips)
 (:predicates (a) (b))
 (:action go :parameters () :precondition (a) :effect (and (b) (not (a)))))"""
PROBLEM = """(define (problem rom1) (:domain rom) (:init (a)) (:goal (b)))"""
PDDL_PAYLOAD = {"domain_text": DOMAIN, "problem_text": PROBLEM}

SHIM_NAME = "kinds_rom_shim"
SHIM_SRC = '''"""Court shim: a kind that writes into the package tree."""
import os
from autofde_lab.coprocessor.envelope import PLAN, Result, register_kind


@register_kind("rom_shim_writer", module="kinds_rom_shim")
def _w(env):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "shim_dropping.txt"), "w") as fh:
        fh.write("written")
    return Result(PLAN, solver="shim")
'''


def snapshot(root: Path) -> Dict[str, Tuple[str, str]]:
    snap: Dict[str, Tuple[str, str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for d in dirnames:
            snap[os.path.relpath(os.path.join(dirpath, d), root) + "/"] = ("dir", "")
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                snap[rel] = ("link", os.readlink(p))
                continue
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            snap[rel] = ("file", h.hexdigest())
    return snap


def diff_snapshots(before, after) -> Dict[str, List[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k]),
    }


def is_dirty(d: Dict[str, List[str]]) -> bool:
    return any(d.values())


def make_readonly(root: Path) -> None:
    subprocess.run(["chmod", "-R", "a-w", str(root)], check=True)


def make_writable(root: Path) -> None:
    subprocess.run(["chmod", "-R", "u+w", str(root)], check=False)


def copy_tree(dst_parent: Path) -> Path:
    dst = dst_parent / "autofde_lab"
    shutil.copytree(SRC_PKG, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    overlay_native(dst)
    return dst


def overlay_native(dst: Path) -> int:
    """The compiled hub extension and its binaries live in the installed package, not in
    src/. Overlay every non-python file from there that the copy lacks, so the copy runs
    the same kinds as the real install."""
    installed = Path(sysconfig.get_paths()["purelib"]) / "autofde_lab"
    n = 0
    if not installed.is_dir() or installed.resolve() == SRC_PKG.resolve():
        return n
    for p in installed.rglob("*"):
        if p.is_dir() or p.suffix in (".py", ".pyc") or "__pycache__" in p.parts:
            continue
        target = dst / p.relative_to(installed)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            n += 1
    return n


SITECUSTOMIZE = """import sys
sys.meta_path[:] = [f for f in sys.meta_path
                    if "editable" not in (getattr(type(f), "__module__", "") or "")]
sys.path[:] = [p for p in sys.path if p != %r]
"""


def child_env(pkg_parent: Path, work: Path) -> Dict[str, str]:
    """Child env whose autofde_lab resolves to the copy only: the venv's editable
    finder (which would redirect to the real tree) is stripped by sitecustomize."""
    hook = work / "_hook"
    hook.mkdir(parents=True, exist_ok=True)
    (hook / "sitecustomize.py").write_text(SITECUSTOMIZE % str(REPO / "src"))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(hook), str(pkg_parent)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AUTOFDE_WORK"] = str(work)
    return env


def discover_kinds(pkg_parent: Path, work: Path) -> Dict[str, object]:
    code = (
        "import json,autofde_lab;from autofde_lab.coprocessor import envelope as E;"
        "E.load_kind_modules();print(json.dumps({'kinds':sorted(E.REGISTRY),"
        "'absent':list(E.ABSENT_MODULES),'origin':autofde_lab.__file__}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env=child_env(pkg_parent, work), stdin=subprocess.DEVNULL, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"kind discovery failed: {proc.stderr[-400:]}")
    found = json.loads(proc.stdout.strip().splitlines()[-1])
    expected = str(pkg_parent / "autofde_lab")
    if not os.path.realpath(found["origin"]).startswith(os.path.realpath(expected)):
        raise RuntimeError(f"child imported {found['origin']}, not the copy {expected}")
    return found


def run_kind(kind: str, pkg_parent: Path, work: Path, timeout: float = 300.0) -> Dict[str, object]:
    envelope = {"kind": kind, "payload": dict(PDDL_PAYLOAD), "options": {"timeout": 120}}
    proc = subprocess.run(
        [sys.executable, "-m", "autofde_lab.coprocessor", kind],
        input=json.dumps(envelope), capture_output=True, text=True,
        env=child_env(pkg_parent, work), cwd=str(work), timeout=timeout,
    )
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        out = {"status": "UNPARSEABLE", "stderr": proc.stderr[-300:]}
    return {"kind": kind, "exit": proc.returncode, "status": out.get("status"),
            "blocked_on": (out.get("diagnostics") or {}).get("blocked_on")}


def git_porcelain() -> Optional[List[str]]:
    try:
        p = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=all"],
                           capture_output=True, text=True, timeout=120)
    except Exception:  # noqa: BLE001
        return None
    return p.stdout.splitlines() if p.returncode == 0 else None


def prove_tree(root_parent: Path, readonly: bool, extra_kinds: Tuple[str, ...] = ()) -> Dict[str, object]:
    """Snapshot, run every kind (plus extra_kinds), snapshot, diff."""
    pkg = root_parent / "autofde_lab"
    work = root_parent / "work"
    work.mkdir(exist_ok=True)
    if readonly:
        make_readonly(pkg)
    try:
        before = snapshot(pkg)
        found = discover_kinds(root_parent, work)
        kinds = list(found["kinds"]) + [k for k in extra_kinds if k not in found["kinds"]]
        results = [run_kind(k, root_parent, work) for k in kinds]
        after = snapshot(pkg)
    finally:
        make_writable(pkg)
    return {"diff": diff_snapshots(before, after), "results": results,
            "absent": found["absent"], "kinds": kinds}


def court_shim() -> Dict[str, object]:
    """Non-vacuity: a writing shim kind must be caught in a writable tmp copy, and
    must be unable to write in a read-only copy."""
    out: Dict[str, object] = {}
    for readonly in (False, True):
        with tempfile.TemporaryDirectory(prefix="rom-court-") as td:
            tdp = Path(td)
            pkg = copy_tree(tdp)
            (pkg / "coprocessor" / f"{SHIM_NAME}.py").write_text(SHIM_SRC)
            work = tdp / "work"
            work.mkdir()
            if readonly:
                make_readonly(pkg)
            try:
                before = snapshot(pkg)
                code = (f"import autofde_lab.coprocessor.{SHIM_NAME};"
                        "from autofde_lab.coprocessor.__main__ import main;"
                        "raise SystemExit(main(['rom_shim_writer']))")
                subprocess.run([sys.executable, "-c", code], input=json.dumps({"kind": "rom_shim_writer"}),
                               capture_output=True, text=True, env=child_env(tdp, work), timeout=120)
                after = snapshot(pkg)
            finally:
                make_writable(pkg)
            out["readonly" if readonly else "writable"] = diff_snapshots(before, after)
    out["caught_when_writable"] = "coprocessor/shim_dropping.txt" in out["writable"]["added"]
    out["blocked_when_readonly"] = not is_dirty(out["readonly"])
    return out


def main() -> int:
    git_before = git_porcelain()
    real_before = snapshot(SRC_PKG)
    court = court_shim()
    with tempfile.TemporaryDirectory(prefix="rom-clean-") as td:
        tdp = Path(td)
        copy_tree(tdp)
        try:
            proof = prove_tree(tdp, readonly=True)
        finally:
            make_writable(tdp)
    git_after = git_porcelain()
    real_after = snapshot(SRC_PKG)
    git_new = (sorted(set(git_after) - set(git_before))
               if git_before is not None and git_after is not None else None)
    real_diff = diff_snapshots(real_before, real_after)

    print("kinds run:", ", ".join(proof["kinds"]))
    for r in proof["results"]:
        note = f" blocked_on={r['blocked_on']}" if r["status"] == "BLOCKED" else ""
        print(f"  {r['kind']}: status={r['status']} exit={r['exit']}{note}")
    print("absent modules:", proof["absent"])
    print("read-only tree diff:", json.dumps(proof["diff"]))
    print("court caught_when_writable:", court["caught_when_writable"],
          "blocked_when_readonly:", court["blocked_when_readonly"])
    print("git status new entries:", git_new)
    print("real src diff (informational, concurrent lanes may edit):", json.dumps(
        {k: len(v) for k, v in real_diff.items()}))

    ok = True
    if is_dirty(proof["diff"]):
        print("FAIL: read-only tree changed"); ok = False
    if not court["caught_when_writable"]:
        print("FAIL: vacuous court"); ok = False
    if any(r["status"] == "UNPARSEABLE" for r in proof["results"]):
        print("FAIL: unparseable kind output"); ok = False
    bad_git = [e for e in (git_new or []) if "__pycache__" in e or e.endswith(".pyc")]
    if bad_git:
        print("FAIL: run produced bytecode in repo:", bad_git); ok = False
    print("ROM-CLEAN:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
