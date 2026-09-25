"""Passive corpus runner and CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

from autofde_lab.iec.cli import main
from autofde_lab.iec.inventory import RepositoryInventoryScanner
from autofde_lab.iec.model import RepositorySubject
from autofde_lab.iec.runner import PassiveCorpusRunner, RepositoryInput
from autofde_lab.iec.structural import ParseStanding


def subject() -> RepositorySubject:
    return RepositorySubject(
        repository="seanchatmangpt/local-fixture",
        revision="f" * 40,
        default_branch="main",
    )


def test_inventory_is_deterministic_and_excludes_build_cache(tmp_path: Path) -> None:
    (tmp_path / "b.py").write_text("b = 2\n")
    (tmp_path / "a.py").write_text("a = 1\n")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "ignored.pyc").write_bytes(b"ignored")

    first = RepositoryInventoryScanner(tmp_path).scan()
    second = RepositoryInventoryScanner(tmp_path).scan()
    assert first == second
    assert tuple(entry.path for entry in first.entries) == ("a.py", "b.py")


def test_inventory_records_symlink_as_refusal(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("target")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    inventory = RepositoryInventoryScanner(tmp_path).scan()
    assert ("link.txt", "REFUSED_SYMLINK") in inventory.skipped
    link_entry = next(entry for entry in inventory.entries if entry.path == "link.txt")
    assert link_entry.symlink


def test_passive_runner_observes_parses_projects_and_receipts(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.1"\n'
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "api.py").write_text("def public(x: int) -> int:\n    return x + 1\n")

    result = PassiveCorpusRunner().run(
        (
            RepositoryInput(
                subject=subject(),
                root=str(tmp_path),
            ),
        )
    )
    assert len(result.repositories) == 1
    repository = result.repositories[0]
    assert repository.subject == subject()
    assert "RepositorySubject" in repository.rdf_projection
    assert len(repository.structural_documents) == 2
    standings = {
        path: document.standing for path, document in repository.structural_documents
    }
    assert standings["pyproject.toml"] is ParseStanding.OBSERVED
    assert standings["src/api.py"] is ParseStanding.OBSERVED
    assert len(result.receipts) == 2
    assert result.receipts[0].previous_receipt is None
    assert result.receipts[1].previous_receipt == result.receipts[0].receipt_id
    assert all(receipt.authority == "NONE" for receipt in result.receipts)


def test_cli_scan_prints_machine_readable_zero_authority_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    exit_code = main(
        [
            "scan",
            str(tmp_path),
            "--repository",
            "seanchatmangpt/local-fixture",
            "--revision",
            "a" * 40,
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["authority"] == "NONE"
    assert payload["files"] == 1
    assert payload["receipt_ids"]


def test_cli_parse_returns_two_for_unsupported_language(
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "main.rs"
    path.write_text("fn main() {}")
    exit_code = main(["parse", str(path)])
    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["standing"] == "UNSUPPORTED"


def test_cli_anti_unify_reconstructs_inputs(tmp_path: Path, capsys) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text('{"name":"alpha","port":1}')
    right.write_text('{"name":"beta","port":2}')
    exit_code = main(["anti-unify", str(left), str(right)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["reconstructed"] == [
        {"name": "alpha", "port": 1},
        {"name": "beta", "port": 2},
    ]


def test_cli_ggen_create_plan_is_intent_only(capsys) -> None:
    exit_code = main(
        [
            "ggen-create-plan",
            "--repository",
            "seanchatmangpt/example",
            "--revision",
            "e" * 40,
            "--ggen-create-revision",
            "ggen-create-sha",
            "--generator",
            "example",
            "--include",
            "src/a.py",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["intents"]
    assert all(intent["authority"] == "NONE" for intent in payload["intents"])
