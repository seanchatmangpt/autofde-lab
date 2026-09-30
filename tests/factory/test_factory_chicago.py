"""Chicago-style: real loop, real ledger on disk, fresh verifier subprocess.

No mocks. Mutation tests edit the durable ledger and require a typed non-ALIVE
verdict: a verifier that cannot go red is not checking anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autofde_lab.factory.loop import run_factory
from autofde_lab.factory.verify import verify_ledger


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("factory")
    return {"out": out, "report": run_factory(out, sony=False)}


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()]


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def test_compounding_and_honest_unknown(run):
    v = run["report"]["verdict"]
    rows = _rows(run["out"] / "ledger.jsonl")
    assert v["technical_standing"] == "ALIVE"
    assert v["experience_routes"] == 18 and v["replay_cost"] == 0
    assert v["investigation_cost"] > 0
    unobs = [r for r in rows if r["class_key"][0] == 999]
    assert [r["standing"] for r in unobs] == ["UNKNOWN"]
    assert unobs[0]["admitted_mode"] is None and unobs[0]["receipt"] is None


def test_organizational_standing_is_never_computed(run):
    v = run["report"]["verdict"]
    assert v["organizational_standing"] == "UNKNOWN"
    assert v["enterprise_standing"] == "UNKNOWN"


def test_fresh_verifier_without_runtime(run):
    code = (
        "import sys,json;"
        "from autofde_lab.factory.verify import verify_ledger;"
        f"v=verify_ledger(__import__('pathlib').Path({str(run['out'] / 'ledger.jsonl')!r}));"
        "bad=[m for m in ('autofde_lab.factory.loop','autofde_lab.factory.world') if m in sys.modules];"
        "print(json.dumps([v.technical_standing,bad]))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert json.loads(out.stdout) == ["ALIVE", []]


def _mutated(run, tmp_path, fn):
    rows = _rows(run["out"] / "ledger.jsonl")
    fn(rows)
    p = tmp_path / "m.jsonl"
    _write(p, rows)
    return verify_ledger(p)


def _first(rows, route):
    return next(r for r in rows if r["route"] == route)


def test_mutation_tampered_receipt(run, tmp_path):
    def f(rows):
        _first(rows, "investigation")["receipt"]["receipt_digest"] = "0" * 64

    v = _mutated(run, tmp_path, f)
    assert v.technical_standing == "BUILD_BROKEN"
    assert any(x.startswith("INVALID_RECEIPT") for x in v.findings)


def test_mutation_experience_joined_to_wrong_investigation(run, tmp_path):
    def f(rows):
        invs = [r for r in rows if r["route"] == "investigation"]
        exp = _first(rows, "experience")
        other = next(i for i in invs if i["class_key"] != exp["class_key"])
        exp["derived_from_case"] = other["case_id"]

    v = _mutated(run, tmp_path, f)
    assert any(x.startswith("UNDERIVED_EXPERIENCE") for x in v.findings)


def test_mutation_experience_without_its_investigation(run, tmp_path):
    def f(rows):
        exp = _first(rows, "experience")
        rows[:] = [r for r in rows if r["case_id"] != exp["derived_from_case"]]
        for i, r in enumerate(rows):
            r["seq"] = i

    v = _mutated(run, tmp_path, f)
    assert v.technical_standing == "BUILD_BROKEN"


def test_mutation_solved_class_reinvestigated_is_regression(run, tmp_path):
    def f(rows):
        _first(rows, "experience")["cost"] = 3

    v = _mutated(run, tmp_path, f)
    assert any(x.startswith("ARCHITECTURE_REGRESSION") for x in v.findings)


def test_mutation_self_certified_receipt(run, tmp_path):
    def f(rows):
        rc = _first(rows, "investigation")["receipt"]
        rc["verifier_id"] = rc["producer_id"]

    v = _mutated(run, tmp_path, f)
    assert any(x.startswith("INVALID_RECEIPT") for x in v.findings)


def test_zero_budget_yields_unknown_not_alive(tmp_path):
    r = run_factory(tmp_path, budget=0, sony=False)
    assert r["verdict"]["technical_standing"] == "UNKNOWN"
    assert r["verdict"]["experience_routes"] == 0


def test_empty_ledger_is_unknown(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_text("")
    assert verify_ledger(p).technical_standing == "UNKNOWN"


def test_cli_end_to_end_no_llm_modules(tmp_path):
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "autofde_lab.factory",
            "--out",
            str(tmp_path / "o"),
            "--no-sony",
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr[-800:]
    assert json.loads(p.stdout)["llm_modules_loaded"] == []
