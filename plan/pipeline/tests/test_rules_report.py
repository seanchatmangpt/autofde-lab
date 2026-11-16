"""Chicago tests: real store.py / PDDL / roster / pytest collection; LAWS text built per test."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import laws_ledger as ll  # noqa: E402
import rules_report as rr  # noqa: E402

SELF = "pipeline/tests/test_rules_report.py"


def laws_text(rows):
    head = "| " + " | ".join(ll.LAWS_COLS) + " |\n|" + "---|" * len(ll.LAWS_COLS) + "\n"
    return ll.LAWS_MARK + "\n\n" + head + "".join(
        "| " + " | ".join(r) + " |\n" for r in rows)


def open_text():
    head = "| " + " | ".join(ll.OPEN_COLS) + " |\n|" + "---|" * len(ll.OPEN_COLS) + "\n"
    row = ["Q1", "q?", "a", "b", "a", "Tony", "sw", "12"]
    return ll.OPEN_MARK + "\n\n" + head + "| " + " | ".join(row) + " |\n"


def law_row(i, check="-", pddl="-", test="-", status="LOCKED"):
    return [i, "law text", "quote", "7", check, pddl, test, "-", "-", status]


@pytest.fixture
def repo(tmp_path):
    prefix = next(iter(rr.refused_prefixes()))
    action = rr.pddl_names()[0][0]
    p = tmp_path
    (p / "LAWS.md").write_text(laws_text([
        law_row("L1", check=prefix, pddl=action, test=f"{SELF}::test_extraction_real")]))
    (p / "OPEN.md").write_text(open_text())
    return p


def run(p, *extra):
    return rr.main(["--laws", str(p / "LAWS.md"), "--open", str(p / "OPEN.md"),
                    "--out-dir", str(p / "out"), "--collect", SELF, *extra])


def test_extraction_real():
    pre = rr.refused_prefixes()
    assert "SINGLE_ENTITY_STORE" not in pre  # L6 multi-entity landed
    assert "ENTITY_MISMATCH" in pre
    actions, preds = rr.pddl_names()
    assert actions and preds and rr.mzn_constraints()
    assert len(rr.roster_unsupported()) == 16


def test_generates_and_check_passes(repo):
    assert run(repo) == 0
    md = (repo / "out/RULES-REPORT.md").read_text()
    assert md.splitlines()[0] == rr.HEADER
    for role in rr.roster_unsupported():
        assert role in md
    assert "| Q1 | q? | a | b | a | Tony | sw | 12 |" in md
    assert json.loads((repo / "out/rules.json").read_text())["unresolved"] == []
    assert run(repo, "--check") == 0


def test_unresolved_reference_exits_1(repo, capsys):
    (repo / "LAWS.md").write_text(laws_text([law_row("L9", check="NO_SUCH_PREFIX")]))
    assert run(repo) == 1
    assert "L9" in capsys.readouterr().err
    assert not (repo / "out").exists()


def test_open_status_exempt_but_rendered(repo):
    (repo / "LAWS.md").write_text(laws_text([
        law_row("L2", check="NO_SUCH_PREFIX", status="UNSUPPORTED")]))
    assert run(repo) == 0
    assert "UNSUPPORTED" in (repo / "out/RULES-REPORT.md").read_text()


def test_check_detects_one_cell_edit(repo):
    assert run(repo) == 0
    f = repo / "out/RULES-REPORT.md"
    f.write_text(f.read_text().replace("| 7 |", "| 8 |", 1))
    assert run(repo, "--check") == 1


def test_schema_mismatch_fails_loudly(repo):
    (repo / "LAWS.md").write_text(laws_text([law_row("L1")]).replace("| status |", "| stat |"))
    with pytest.raises(ll.SchemaError):
        run(repo)
