"""M5: K14/K15/K16 repointed repo-relative, K7/K17 local services run."""
import os
import subprocess
import sys
from pathlib import Path

from plankinds import registry, run_kind

LAB = Path(__file__).resolve().parents[3]


def _rows(kind):
    return run_kind(registry()[kind])


def test_k14_uses_in_repo_venv_and_original_cases_green():
    mod = registry()["K14"]
    assert mod.REPO == LAB and mod.PY == str(LAB / ".venv/bin/python")
    src = Path(mod.__file__).read_text()
    assert "uv" + " run" not in src.replace("`", "")
    rows = _rows("K14")
    assert len(rows) >= 5 and all(r["ok"] for r in rows), rows
    by = {r["case"]: r for r in rows}
    assert by["pddl-blocks-3"]["status"] != "SKIP"


def test_k14_exit_classes():
    mod = registry()["K14"]
    assert [mod.classify_pddl_exit(c, "") for c in (0, 1, 2)] == ["PLAN", "NO_PLAN", "REFUSED"]


def test_k15_env_var_and_typed_skip():
    env = dict(os.environ, GYMACT_REPO="/nonexistent/gymact-absent")
    r = subprocess.run([sys.executable, "-c",
                        "from plankinds import registry;m=registry()['K15'];s=m.probe();"
                        "print(m.REPO);print(s.reason if s else None)"],
                       env=env, capture_output=True, text=True, cwd=LAB / "plan",
                       )
    assert r.returncode == 0, r.stderr
    assert "/nonexistent/gymact-absent" in r.stdout and "GYMACT_REPO" in r.stdout, r.stdout


def test_k15_runs_or_typed_skip():
    rows = _rows("K15")
    assert rows and all(r["status"] == "SKIP" or r["ok"] for r in rows), rows


def test_k16_typed_skip_without_key():
    mod = registry()["K16"]
    keys = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")
    if not any(os.environ.get(k) for k in keys):
        assert mod.probe() is not None
    assert str(mod.BLOCKS).startswith(str(LAB)) and mod.BLOCKS.is_dir()


def test_k07_ledger_runs():
    rows = _rows("K7")
    assert len(rows) == 5 and all(r["ok"] for r in rows), rows


def test_k17_hypothesis_importable_and_runs():
    import hypothesis  # noqa: F401
    rows = _rows("K17")
    assert rows and all(r["status"] != "SKIP" and r["ok"] for r in rows), rows


def test_k14_backend_differential_matches_cli():
    mod = registry()["K14"]
    for c in mod.cases():
        if c.id in ("pddl-missing-domain",):
            continue
        cli, be = mod.run(c), mod.run_via_backend(c)
        assert cli.status == c.expect, (c.id, cli)
        assert be.status in (c.expect, "INFEASIBLE" if c.expect == "NO_PLAN" else c.expect), (c.id, be)
