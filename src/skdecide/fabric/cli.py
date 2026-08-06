# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Typer projection of the shared scikit-decide decision fabric."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from skdecide.fabric.cache import SQLiteERRCCache
from skdecide.fabric.models import DecisionRefusal, DecisionRequest
from skdecide.fabric.service import DecisionFabric

app = typer.Typer(
    name="skdecide-fabric",
    help="CLI, MCP, A2A, DSPy, and ERRC cache for scikit-decide.",
    no_args_is_help=True,
)


def get_fabric(cache_path: Path | None = None) -> DecisionFabric:
    """Construct the shared service; isolated for tests and embedding."""
    cache = SQLiteERRCCache(cache_path) if cache_path is not None else None
    return DecisionFabric(cache=cache)


def _object(value: str, name: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise typer.BadParameter(f"{name} must be valid JSON: {error.msg}") from error
    if not isinstance(decoded, dict):
        raise typer.BadParameter(f"{name} must decode to a JSON object")
    return decoded


def _emit(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def _refuse(error: DecisionRefusal) -> None:
    _emit(error.as_dict())
    raise typer.Exit(code=3)


@app.command()
def catalog(
    cache_path: Path | None = typer.Option(None, help="SQLite ERRC cache path"),
) -> None:
    """List registered domains and solvers."""
    try:
        _emit(get_fabric(cache_path).catalog().as_dict())
    except DecisionRefusal as error:
        _refuse(error)


@app.command()
def match(
    domain: str = typer.Argument(..., help="Registered domain name"),
    domain_arguments: str = typer.Option("{}", help="Domain arguments as JSON"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache"),
    cache_path: Path | None = typer.Option(None, help="SQLite ERRC cache path"),
) -> None:
    """Match compatible solvers for a domain."""
    try:
        result = get_fabric(cache_path).match(
            domain,
            domain_arguments=_object(domain_arguments, "domain_arguments"),
            use_cache=use_cache,
        )
        _emit(result.as_dict())
    except DecisionRefusal as error:
        _refuse(error)


@app.command()
def solve(
    domain: str = typer.Argument(..., help="Registered domain name"),
    solver: str | None = typer.Option(None, help="Solver; defaults to first match"),
    domain_arguments: str = typer.Option("{}", help="Domain arguments as JSON"),
    solver_arguments: str = typer.Option("{}", help="Solver arguments as JSON"),
    max_steps: int = typer.Option(100, min=1, help="Bounded rollout transitions"),
    subject_digest: str = typer.Option("UNBOUND_SUBJECT"),
    policy_digest: str = typer.Option("UNBOUND_POLICY"),
    environment_digest: str = typer.Option("UNBOUND_ENVIRONMENT"),
    randomness_digest: str = typer.Option("UNBOUND_RANDOMNESS"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache"),
    cache_path: Path | None = typer.Option(None, help="SQLite ERRC cache path"),
) -> None:
    """Solve and emit a receipt-bearing trajectory."""
    try:
        request = DecisionRequest(
            domain=domain,
            solver=solver,
            domain_arguments=_object(domain_arguments, "domain_arguments"),
            solver_arguments=_object(solver_arguments, "solver_arguments"),
            max_steps=max_steps,
            subject_digest=subject_digest,
            policy_digest=policy_digest,
            environment_digest=environment_digest,
            randomness_digest=randomness_digest,
            use_cache=use_cache,
        )
        _emit(get_fabric(cache_path).solve(request).as_dict())
    except DecisionRefusal as error:
        _refuse(error)


@app.command("cache-stats")
def cache_stats(
    cache_path: Path | None = typer.Option(None, help="SQLite ERRC cache path"),
) -> None:
    """Show cache hits, misses, writes, and namespaces."""
    _emit(get_fabric(cache_path).cache_stats())


@app.command("cache-hotset")
def cache_hotset(
    cache_path: Path | None = typer.Option(None, help="SQLite ERRC cache path"),
) -> None:
    """Measure whether 20% of artifacts account for 80% of reuse."""
    _emit(get_fabric(cache_path).cache_hotset())


@app.command("serve-mcp")
def serve_mcp() -> None:
    """Run the FastMCP server over stdio."""
    from skdecide.fabric.mcp import create_server

    create_server().run()


@app.command("serve-a2a")
def serve_a2a(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(9999, min=1, max=65535),
) -> None:
    """Run the A2A JSON-RPC server."""
    from skdecide.fabric.a2a import run

    run(host=host, port=port)
