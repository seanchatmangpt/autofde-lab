# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real FastMCP projection court against the current fabric tool surface."""

from __future__ import annotations

import asyncio

import pytest

fastmcp = pytest.importorskip("fastmcp")

from autofde_lab.fabric.mcp import create_server  # noqa: E402
from autofde_lab.fabric.service import DecisionFabric  # noqa: E402


def test_mcp_projects_one_fabric(fabric: DecisionFabric) -> None:
    server = create_server(fabric)

    async def run():
        async with fastmcp.Client(server) as client:
            tools = await client.list_tools()
            catalog_result = await client.call_tool("decision_catalog", {})
            solve_result = await client.call_tool(
                "decision_solve",
                {"request": {"domain": "Counter", "domain_arguments": {"limit": 1}}},
            )
            issue_catalog = await client.call_tool("issue_reasoning_catalog", {})
            return tools, catalog_result, solve_result, issue_catalog

    tools, catalog_result, solve_result, issue_catalog = asyncio.run(run())

    assert {t.name for t in tools} == {
        "decision_cache_hotset",
        "decision_cache_stats",
        "decision_catalog",
        "decision_match",
        "decision_solve",
        "issue_reason",
        "issue_reasoning_catalog",
    }
    assert catalog_result.structured_content["domains"] == ["Counter"]
    assert solve_result.structured_content["standing"] == "SOLVED"
    assert issue_catalog.structured_content["authority"] == "CANDIDATE_ONLY"
    assert issue_catalog.structured_content["actuation"] == "REFUSED"
