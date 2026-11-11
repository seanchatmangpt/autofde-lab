"""Chicago-style tests for scripts/stub_register.py: real files, real subprocesses."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "stub_register.py"


def run(src: Path, disp: Path, repo: Path, *flags: str, doc: Path | None = None):
    cmd = [sys.executable, str(SCRIPT), "--src-root", str(src), "--dispositions", str(disp),
           "--repo", str(repo), *flags]
    if doc:
        cmd += ["--doc", str(doc)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def mirror(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    src = tmp_path / "src" / "autofde_lab"
    for rel, body in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    disp = tmp_path / "disp.toml"
    disp.write_text("")
    return src, disp


def test_abstract_sites_are_not_open(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": (
        "import abc\nfrom typing import Protocol\n"
        "class A(abc.ABC):\n    @abc.abstractmethod\n    def f(self):\n"
        "        raise NotImplementedError\n"
        "class P(Protocol):\n    def g(self) -> int: ...\n")})
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 0, r.stdout
    assert "ABSTRACT_BY_DESIGN" in r.stdout


def test_open_kinds_detected(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": (
        "def a():\n    raise NotImplementedError\n"
        "def b():\n    raise NotImplementedError('x')\n"
        "def c():\n    pass\n"
        "def d():  # TODO later\n    return 1\n"
        "x = 1  # PLACEHOLDER\n")})
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1
    for kind in ("NIE_BARE", "NIE_CALL", "EMPTY_BODY", "TODO", "STUB_WORD"):
        assert kind in r.stdout, r.stdout


def test_closed_requires_existing_test_and_blocked_requires_evidence(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": "def c():\n    pass\n"})
    key = "autofde_lab/a/m.py::c::EMPTY_BODY"
    disp.write_text(f'["{key}"]\ndisposition = "CLOSED"\n'
                    'evidence = "tests/nope/test_missing.py::t"\nlane = "L"\n')
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1 and "CLOSED_TEST_MISSING" in r.stdout
    (tmp_path / "tests" / "nope").mkdir(parents=True)
    (tmp_path / "tests" / "nope" / "test_missing.py").write_text("")
    assert run(src, disp, tmp_path, "--check").returncode == 0
    disp.write_text(f'["{key}"]\ndisposition = "BLOCKED"\nevidence = ""\nlane = "L"\n')
    r = run(src, disp, tmp_path, "--check")
    assert r.returncode == 1 and "BLOCKED_NO_EVIDENCE" in r.stdout
    disp.write_text(f'["{key}"]\ndisposition = "BLOCKED"\nevidence = "cmd: x"\nlane = "L"\n')
    assert run(src, disp, tmp_path, "--check").returncode == 0


def test_write_is_deterministic(tmp_path):
    src, disp = mirror(tmp_path, {"a/m.py": "def c():\n    pass\n"})
    d1, d2 = tmp_path / "1.md", tmp_path / "2.md"
    run(src, disp, tmp_path, "--write", doc=d1)
    run(src, disp, tmp_path, "--write", doc=d2)
    assert d1.read_bytes() == d2.read_bytes()
    text = d1.read_text()
    assert text.startswith("# STUB-REGISTER") and "By directory" in text
    assert all(len(line) <= 100 for line in text.splitlines()[:12])


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_shim_court_gate_refuses_unregistered_nie(tmp_path):
    """Copy a real src file, insert an unregistered NIE, gate must REFUSE; restore is exact."""
    real = next(p for p in sorted((REPO / "src" / "autofde_lab").rglob("*.py"))
                if p.stat().st_size > 0 and "NotImplementedError" not in p.read_text(
                    errors="replace"))
    rel = real.relative_to(REPO / "src" / "autofde_lab").as_posix()
    src, disp = mirror(tmp_path, {})
    copy = src / rel
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(real.read_bytes())
    base_sha = _sha(copy)
    before = run(src, disp, tmp_path, "--check")

    shim = copy.read_bytes() + b"\n\ndef _shim_court():  # SHIM-COURT\n    raise NotImplementedError\n"
    copy.write_bytes(shim)
    during = run(src, disp, tmp_path, "--check")
    assert during.returncode == 1, during.stdout
    assert "NIE_BARE" in during.stdout and "_shim_court" in during.stdout

    copy.write_bytes(real.read_bytes())
    after = run(src, disp, tmp_path, "--check")
    assert _sha(copy) == base_sha
    assert (after.returncode, after.stdout) == (before.returncode, before.stdout)
    assert "_shim_court" not in after.stdout
