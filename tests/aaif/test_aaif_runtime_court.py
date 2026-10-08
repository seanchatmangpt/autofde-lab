"""Real FastMCP client against the autofde AAIF runtime. No mocks."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

fastmcp = pytest.importorskip("fastmcp")

from autofde_lab.aaif import DecisionAgentProtocol, build_mcp_server  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def test_mcp_runtime_serves_decision_tools(fabric) -> None:
    server = build_mcp_server(fabric)

    async def run():
        async with fastmcp.Client(server) as client:
            tools = {t.name for t in await client.list_tools()}
            solve = await client.call_tool(
                "decision_solve",
                {"request": {"domain": "Counter", "domain_arguments": {"limit": 1}}},
            )
            return tools, solve

    tools, solve = asyncio.run(run())
    assert {"decision_catalog", "decision_match", "decision_solve"} <= tools
    assert solve.structured_content["standing"] == "SOLVED"
    assert solve.structured_content["receipt_sha256"]


def test_a2a_handler_solves_and_refuses(fabric) -> None:
    proto = DecisionAgentProtocol(fabric)
    ok = proto.handle_text('{"domain":"Counter","domain_arguments":{"limit":1},"max_steps":2}')
    assert ok["standing"] == "SOLVED"
    assert proto.handle_text("not json")["standing"] == "REFUSED"


def test_rendered_artifacts_point_at_this_runtime() -> None:
    card = json.loads((REPO / ".well-known/agent.json").read_text())
    assert card["url"] == "http://127.0.0.1:8000"
    assert (REPO / ".goosehints").read_text().count("decision_solve") >= 1
    assert (REPO / "docs/aaif/AGENTS.generated.md").exists()
