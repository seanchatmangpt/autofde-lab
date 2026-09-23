"""Semantic Agent Card capability declarations (§10).

RFC-SA2A-001 v26.9.16 capability declarations, security boundaries,
and supported profiles.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

SA2A_PROFILE_V26_9_16 = "SA2A-PROFILE-v26.9.16"


@dataclass(frozen=True, slots=True)
class SemanticCapability:
    """A declared semantic capability of an agent (§10)."""

    capability_iri: str
    description: str
    shacl_shape_iri: str | None = None
    cost_per_invocation: float = 1.0
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticAgentCard:
    """Agent Card declaring identity, capabilities, and supported profiles (§10)."""

    agent_id: str
    name: str
    version: str
    supported_profiles: tuple[str, ...]
    capabilities: tuple[SemanticCapability, ...]
    security_level: str = "RESTRICTED"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def card_hash(self) -> str:
        dumped = json.dumps(
            {
                "agent_id": self.agent_id,
                "name": self.name,
                "version": self.version,
                "supported_profiles": list(self.supported_profiles),
                "capabilities": [
                    {
                        "iri": c.capability_iri,
                        "cost": c.cost_per_invocation,
                    }
                    for c in self.capabilities
                ],
                "security_level": self.security_level,
            },
            sort_keys=True,
        )
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    def supports_profile(self, profile: str) -> bool:
        return profile in self.supported_profiles


def create_default_sa2a_agent_card(
    agent_id: str = "autofde-agent-10",
    name: str = "AutoFDE SA2A Default Agent",
    version: str = "v26.9.16",
    capabilities: Sequence[SemanticCapability] | None = None,
) -> SemanticAgentCard:
    """Create standard RFC-SA2A-001 v26.9.16 agent card."""
    caps = tuple(
        capabilities
        or (
            SemanticCapability(
                capability_iri="urn:autofde:sa2a:capability:unknown-allocation",
                description="CMCA resource allocation for UNKNOWN candidate frontier",
            ),
            SemanticCapability(
                capability_iri="urn:autofde:sa2a:capability:experience-compilation",
                description="Deterministic machine experience rule compilation",
            ),
        )
    )
    return SemanticAgentCard(
        agent_id=agent_id,
        name=name,
        version=version,
        supported_profiles=(SA2A_PROFILE_V26_9_16,),
        capabilities=caps,
        security_level="RESTRICTED",
    )
