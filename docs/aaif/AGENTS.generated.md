# AGENTS.md

> Standard Repository Guidance for autofde-lab Decision Agent (Conforming to AAIF AGENTS.md Specification)

## Purpose
Formal decision planning agent: scikit-decide solver matching, bounded rollouts, typed refusals, OCEL audit.

## Dev Environment
Python 3.13, uv, scikit-decide, fastmcp, a2a-sdk.

## Testing Instructions
Run uv run pytest tests/fabric tests/aaif with real collaborators; no mocks.

## Coding Conventions
Generated AAIF artifacts come from ggen-marketplace aaif-vanilla-pack; do not hand-edit.

## Useful Commands
uv run pytest tests/aaif, python -m autofde_lab.aaif

## Operating Boundaries
Fail-closed admission, typed refusals, zero ambient execution authority.

## Open Protocol Conformances (AAIF 6-Project Suite)
- **Agent2Agent (A2A)**: Discovery at `.well-known/agent.json`.
- **Model Context Protocol (MCP)**: Server configurations in `mcp/mcp_servers.json`.
- **Agentgateway**: L7 reverse proxy configuration in `agentgateway/config.json`.
- **Agent Router**: Envoy AI Gateway CRD manifests in `k8s/agent-router.yaml`.
- **Goose**: Local autonomous agent runtime configured in `.config/goose/config.yaml`.
- **AGENTS.md**: Standardized repository instruction format.
