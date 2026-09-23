from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

typer_testing = pytest.importorskip("typer.testing")
app = importlib.import_module("autofde_lab.fabric.cli").app
CliRunner = typer_testing.CliRunner
# The JSON payload assertions below need stdout kept pure: the
# catalog/match/solve commands legitimately log diagnostics (missing
# optional-dependency warnings from the live entry-point probe) to stderr
# while the full registry is installed. Click <8.2 mixes stderr into
# .stdout by default, so the runner is built with mix_stderr=False there;
# click >=8.2 removed the argument and always keeps the streams separate.
# The gate itself (exit 0 + valid JSON payload) is unchanged on either.
try:
    runner = CliRunner(mix_stderr=False)  # click < 8.2
except TypeError:  # click >= 8.2: streams separate by default
    runner = CliRunner()

# Chicago-style: these exercise the real Typer app against the real
# ScikitDecideBackend entry-point registry and a real SQLite ERRC cache file
# on disk (via the CLI's own --cache-path option). No factory is patched.
# `Maze` / `Astar` are genuinely registered domain/solver entry points of this
# package, so the CLI's production `get_fabric` path is what runs.
_DOMAIN = "Maze"
_SOLVER = "Astar"


def _cache_option(tmp_path: Path) -> list[str]:
    return ["--cache-path", str(tmp_path / "errc-cache.sqlite3")]


def test_catalog_and_match_use_the_real_registry(tmp_path: Path) -> None:
    catalog = runner.invoke(app, ["catalog", *_cache_option(tmp_path)])
    match = runner.invoke(app, ["match", _DOMAIN, *_cache_option(tmp_path)])

    assert catalog.exit_code == 0, catalog.output
    catalog_payload = json.loads(catalog.stdout)
    assert _DOMAIN in catalog_payload["domains"]
    assert _SOLVER in catalog_payload["solvers"]

    assert match.exit_code == 0, match.output
    match_payload = json.loads(match.stdout)
    assert match_payload["domain"] == _DOMAIN
    assert _SOLVER in match_payload["compatible_solvers"]

    # The real cache file was created and written by the real CLI run.
    assert (tmp_path / "errc-cache.sqlite3").exists()


def test_solve_emits_receipt(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "solve",
            _DOMAIN,
            "--solver",
            _SOLVER,
            "--max-steps",
            "100",
            *_cache_option(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["standing"] == "SOLVED"
    assert payload["solver"] == _SOLVER
    assert len(payload["receipt_sha256"]) == 64
    assert payload["steps"], "a solved rollout must record real transitions"


def test_cli_rejects_non_object_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["match", _DOMAIN, "--domain-arguments", "[]", *_cache_option(tmp_path)],
    )

    assert result.exit_code == 2
    assert "must decode to a JSON object" in result.output
