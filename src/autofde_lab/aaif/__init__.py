# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AAIF runtime for autofde-lab.

Contains NO generated content. All AAIF manifests (agent card, MCP servers,
agentgateway, agent-router, Goose, AGENTS.md) are projections rendered from the
ggen-marketplace ``aaif-vanilla-pack`` (fixtures/autofde_agent.ttl).
This module only exposes the runtime those manifests point at: the shared
DecisionFabric over MCP (FastMCP) and the protocol-neutral A2A handler.
"""

from __future__ import annotations

from autofde_lab.fabric.a2a import DecisionAgentProtocol
from autofde_lab.fabric.mcp import create_server as build_mcp_server
from autofde_lab.fabric.service import DecisionFabric

__all__ = ["DecisionAgentProtocol", "DecisionFabric", "build_mcp_server"]
