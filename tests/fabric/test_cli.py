from __future__ import annotations

from typing import Any

from typer.testing import CliRunner

from skdecide.fabric.cli import app
from skdecide.fabric.service import DecisionFabric

runner = CliRunner()


def test_catalog_and_match_project_shared_fabric(
    fabric: DecisionFabric,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr("skdecide.fabric.cli.get_fabric", lambda _path=None: fabric)

    catalog = runner.invoke(app, ["catalog"])
    match = runner.invoke(app, ["match", "Counter"])

    assert catalog.exit_code == 0
    assert '"Counter"' in catalog.stdout
    assert match.exit_code == 0
    assert '"CounterSolver"' in match.stdout


def test_solve_emits_receipt(fabric: DecisionFabric, monkeypatch: Any) -> None:
    monkeypatch.setattr("skdecide.fabric.cli.get_fabric", lambda _path=None: fabric)

    result = runner.invoke(
        app,
        [
            "solve",
            "Counter",
            "--domain-arguments",
            '{"limit":1}',
            "--max-steps",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert '"receipt_sha256"' in result.stdout
    assert '"SOLVED"' in result.stdout


def test_cli_rejects_non_object_json(
    fabric: DecisionFabric,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr("skdecide.fabric.cli.get_fabric", lambda _path=None: fabric)

    result = runner.invoke(
        app,
        ["match", "Counter", "--domain-arguments", "[]"],
    )

    assert result.exit_code == 2
    assert "must decode to a JSON object" in result.output
