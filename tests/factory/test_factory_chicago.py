"""Chicago-style: real loop, real ledger on disk, fresh verifier subprocess.

No mocks. Mutation tests edit the durable ledger and re-seal the hash chain, so
it is the verifier's semantic checks (not chain breakage) that must catch them;
a verifier that cannot go red is not checking anything. Forgery tests build a
ledger from scratch with the repo's own issuer, which is the attack that an
edit-a-real-ledger test cannot express.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from autofde_lab.factory.chain import seal
from autofde_lab.factory.loop import run_factory
from autofde_lab.factory.verify import SCHEMA, verify_ledger
from autofde_lab.wd_fa.receipts import issue_receipt
from autofde_lab.wd_fa.synthetic import RULES, make_case
from autofde_lab.wd_fa.triage import triage


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("factory")
    return {"out": out, "report": run_factory(out, sony=False)}


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()]


def _store(path: Path, rows: list[dict], *, reseal: bool = True) -> Path:
    if reseal:
        rows = seal(rows)
        path.with_suffix(".head").write_text(rows[-1]["digest"] + "\n")
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    return path


def _mutated(run, tmp_path, fn):
    rows = _rows(run["out"] / "ledger.jsonl")
    fn(rows)
    return verify_ledger(_store(tmp_path / "m.jsonl", rows))


def _first(rows, route):
    return next(r for r in rows if r.get("route") == route)


def test_compounding_and_honest_unknown(run):
    v = run["report"]["verdict"]
    rows = _rows(run["out"] / "ledger.jsonl")
    assert v["technical_standing"] == "ALIVE"
    assert v["experience_routes"] == 18 and v["replay_cost"] == 0
    assert v["investigation_cost"] > 0 and v["unresolved"] == 1
    unobs = [r for r in rows if r.get("class_key", [0])[0] == 999]
    assert [r["standing"] for r in unobs] == ["UNKNOWN"]
    assert unobs[0]["admitted_mode"] is None and unobs[0]["receipt"] is None
    assert unobs[0]["reason"] == "NO_OBSERVATION_WITHIN_BUDGET"


def test_human_gate_is_carried_not_claimed(run):
    for r in _rows(run["out"] / "ledger.jsonl")[1:]:
        assert r["human_gate"] == "NOT_AWAITED_DISPOSITION_UNCLAIMED"
        assert r["authority"] == "SELECT_ONLY"


def test_organizational_standing_is_never_computed(run):
    v = run["report"]["verdict"]
    assert v["organizational_standing"] == "UNKNOWN"
    assert v["enterprise_standing"] == "UNKNOWN"


def test_fresh_verifier_without_runtime_or_llm(run):
    code = (
        "import sys,json;"
        "from pathlib import Path;"
        "from autofde_lab.factory.verify import verify_ledger;"
        f"v=verify_ledger(Path({str(run['out'] / 'ledger.jsonl')!r}));"
        "bad=[m for m in sys.modules if m=='autofde_lab.factory.loop' "
        "or m.split('.')[0] in ('dspy','openai','anthropic','litellm') "
        "or m in ('autofde_lab.fabric.dspy','autofde_lab.fabric.mcp')];"
        "print(json.dumps([v.technical_standing,bad]))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert json.loads(out.stdout) == ["ALIVE", []]


def test_import_closure_denylist_with_sony():
    code = (
        "import sys,json;"
        "import autofde_lab.factory.loop, autofde_lab.sony.crown;"
        "deny=('dspy','openai','anthropic','litellm');"
        "bad=[m for m in sys.modules if m.split('.')[0] in deny "
        "or m in ('autofde_lab.fabric.dspy','autofde_lab.fabric.dspy_ensemble',"
        "'autofde_lab.fabric.mcp','autofde_lab.fabric.a2a','autofde_lab.fabric.cli',"
        "'autofde_lab.wd_fa.demo','autofde_lab.wd_fa.automl')];"
        "print(json.dumps(bad))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert json.loads(out.stdout) == []


def test_two_runs_same_seed_are_byte_identical(tmp_path):
    run_factory(tmp_path / "a", sony=False)
    run_factory(tmp_path / "b", sony=False)
    for name in ("ledger.jsonl", "ledger.head"):
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name
        ).read_bytes()


# --- mutations of a genuine ledger (re-sealed: the semantic check must fire) --


def test_mutation_tampered_receipt(run, tmp_path):
    def f(rows):
        _first(rows, "investigation")["receipt"]["receipt_digest"] = "0" * 64

    v = _mutated(run, tmp_path, f)
    assert v.technical_standing == "BUILD_BROKEN"
    assert any(x.startswith("INVALID_RECEIPT") for x in v.findings)


def test_mutation_experience_joined_to_wrong_investigation(run, tmp_path):
    def f(rows):
        invs = [r for r in rows if r.get("route") == "investigation"]
        exp = _first(rows, "experience")
        other = next(i for i in invs if i["class_key"] != exp["class_key"])
        exp["derived_from_case"] = other["case_id"]

    v = _mutated(run, tmp_path, f)
    assert any(x.startswith("UNDERIVED_EXPERIENCE") for x in v.findings)


def test_mutation_experience_without_its_investigation(run, tmp_path):
    def f(rows):
        exp = _first(rows, "experience")
        rows[:] = [
            r
            for r in rows
            if r.get("type") == "header" or r["case_id"] != exp["derived_from_case"]
        ]
        for i, r in enumerate(rows[1:]):
            r["seq"] = i

    v = _mutated(run, tmp_path, f)
    assert v.technical_standing == "BUILD_BROKEN"
    assert any(x.startswith("UNDERIVED_EXPERIENCE") for x in v.findings)


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


def test_mutation_wrong_mode_fails_world_replay(run, tmp_path):
    def f(rows):
        inv = _first(rows, "investigation")
        inv["admitted_mode"] = "MODE-LIE-000000"
        inv["receipt"]["observed_disposition"] = "MODE-LIE-000000"

    v = _mutated(run, tmp_path, f)
    assert any(
        x.startswith(("WORLD_REPLAY_MISMATCH", "INVALID_RECEIPT")) for x in v.findings
    )


def test_mutation_unobservable_class_claimed_resolved(run, tmp_path):
    def f(rows):
        row = next(r for r in rows if r.get("class_key", [0])[0] == 999)
        inv = dict(_first(rows, "investigation"))
        row.update(
            route="investigation",
            standing="ALIVE",
            admitted_mode=inv["admitted_mode"],
            receipt=inv["receipt"],
            cost=inv["cost"],
            reason=None,
        )

    v = _mutated(run, tmp_path, f)
    assert v.technical_standing == "BUILD_BROKEN"


def test_mutation_unresolved_but_observable(run, tmp_path):
    def f(rows):
        inv = _first(rows, "investigation")
        inv.update(
            route="unresolved",
            standing="UNKNOWN",
            admitted_mode=None,
            receipt=None,
            reason="NO_OBSERVATION_WITHIN_BUDGET",
            cost=6,
        )

    v = _mutated(run, tmp_path, f)
    assert any(x.startswith("UNRESOLVED_BUT_OBSERVABLE") for x in v.findings)


def test_mutation_fabricated_seed_rule_claim(run, tmp_path):
    def f(rows):
        row = _first(rows, "investigation")
        row.update(
            route="seed_rule", receipt=None, cost=0, admitted_mode="MODE-NOT-SEEDED"
        )

    v = _mutated(run, tmp_path, f)
    assert any(x.startswith("SEED_RULE_CLAIM") for x in v.findings)


# --- forgery from scratch: the attack a mutate-a-real-ledger test cannot express


def _forged_rows(with_header: bool, spec: dict) -> list[dict]:
    case = make_case(
        "FORGED-0",
        symptom_code=555,
        firmware=5,
        supplier=5,
        station=55,
        lot_risk=0.1,
        rework_count=0,
        vibration=0.2,
        kinds=("test", "waveform"),
        process=("drive_built",),
    )
    receipt = issue_receipt(
        case,
        triage(case, RULES),
        producer_id="forger",
        verifier_id="anyone-i-like",
        observed_disposition="MODE-FAKE",
    )
    common = dict(
        class_key=[555, 5, 5, 55],
        evidence_kinds=["test", "waveform"],
        human_gate="x",
        authority="SELECT_ONLY",
        admitted_mode="MODE-FAKE",
        standing="ALIVE",
    )
    rows = [
        dict(
            seq=0,
            case_id="FORGED-0",
            route="investigation",
            cost=1,
            receipt=asdict(receipt),
            experience_id="MX-FORGED-0",
            derived_from_case=None,
            **common,
        ),
        dict(
            seq=1,
            case_id="FORGED-1",
            route="experience",
            cost=0,
            receipt=None,
            experience_id="MX-FORGED-0",
            derived_from_case="FORGED-0",
            **common,
        ),
    ]
    if with_header:
        rows.insert(0, {"type": "header", "schema": SCHEMA, "budget": 6, "world": spec})
    return rows


def test_forged_ledger_without_header_is_refused(tmp_path):
    v = verify_ledger(_store(tmp_path / "f.jsonl", _forged_rows(False, {})))
    assert v.technical_standing == "BUILD_BROKEN" and "HEADER_MISSING" in v.findings


def test_forged_ledger_with_own_header_and_valid_chain_fails_world_replay(tmp_path):
    rows = _forged_rows(True, {"seed": 7, "unobservable": []})
    v = verify_ledger(_store(tmp_path / "f.jsonl", rows))
    assert v.technical_standing == "BUILD_BROKEN"
    assert any(
        x.startswith(("WORLD_REPLAY_MISMATCH", "RECEIPT_BINDING")) for x in v.findings
    )


# --- ledger integrity ----------------------------------------------------------


def test_edit_without_reseal_breaks_chain(run, tmp_path):
    rows = _rows(run["out"] / "ledger.jsonl")
    rows[3]["cost"] = 99
    p = _store(tmp_path / "c.jsonl", rows, reseal=False)
    p.with_suffix(".head").write_text(rows[-1]["digest"] + "\n")
    v = verify_ledger(p)
    assert any(x.startswith("CHAIN_") for x in v.findings)


def test_tail_truncation_is_detected_via_head(run, tmp_path):
    rows = _rows(run["out"] / "ledger.jsonl")
    p = _store(tmp_path / "t.jsonl", rows, reseal=False)
    p.with_suffix(".head").write_text(rows[-1]["digest"] + "\n")
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows[:-2]))
    assert "HEAD_MISMATCH" in verify_ledger(p).findings


def test_missing_head_is_a_finding(run, tmp_path):
    rows = _rows(run["out"] / "ledger.jsonl")
    p = tmp_path / "h.jsonl"
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    assert "HEAD_MISSING" in verify_ledger(p).findings


def test_malformed_row_fails_typed_not_crash(run, tmp_path):
    def f(rows):
        del rows[2]["route"]
        rows[3]["standing"] = "ALIVE-ish"

    v = _mutated(run, tmp_path, f)
    assert v.technical_standing == "BUILD_BROKEN"
    assert any(x.startswith(("ROW_SCHEMA", "ROW_ENUM")) for x in v.findings)


# --- absence and degenerate inputs ----------------------------------------------


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
