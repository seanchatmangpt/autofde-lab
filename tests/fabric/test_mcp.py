from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

from autofde_lab.fabric.mcp import create_server
from autofde_lab.fabric.service import DecisionFabric


class FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, Any] = {}

    def tool(self, function: Any) -> Any:
        self.tools[function.__name__] = function
        return function


def test_mcp_projects_one_fabric(
    fabric: DecisionFabric,
    monkeypatch: Any,
) -> None:
    monkeypatch.setitem(sys.modules, "fastmcp", SimpleNamespace(FastMCP=FakeFastMCP))

    server = create_server(fabric)

    assert set(server.tools) == {
        "decision_cache_hotset",
        "decision_cache_stats",
        "decision_catalog",
        "decision_match",
        "decision_solve",
    }
    assert server.tools["decision_catalog"]()["domains"] == ("Counter",)
    result = server.tools["decision_solve"](
        {"domain": "Counter", "domain_arguments": {"limit": 1}}
    )
    assert result["standing"] == "SOLVED"
