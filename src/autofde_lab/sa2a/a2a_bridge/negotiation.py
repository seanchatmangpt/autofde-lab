"""Profile negotiation for SA2A-PROFILE-v26.9.16 (§9).

RFC-SA2A-001 v26.9.16 profile negotiation between caller and responder agents.
Fails closed with UNSUPPORTED_PROFILE if no compatible profile can be established.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Sequence

from autofde_lab.sa2a.a2a_bridge.agent_card import SA2A_PROFILE_V26_9_16, SemanticAgentCard
from autofde_lab.sa2a.a2a_bridge.downgrade_guard import DowngradeGuard, UnsupportedProfileError


@dataclass(frozen=True, slots=True)
class ProfileNegotiationSession:
    """Established session after profile negotiation (§9)."""

    session_id: str
    initiator_id: str
    responder_id: str
    negotiated_profile: str
    active_capabilities: tuple[str, ...]

    @property
    def session_hash(self) -> str:
        dumped = json.dumps(
            {
                "session_id": self.session_id,
                "initiator": self.initiator_id,
                "responder": self.responder_id,
                "profile": self.negotiated_profile,
                "capabilities": list(self.active_capabilities),
            },
            sort_keys=True,
        )
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class ProfileNegotiator:
    """Negotiates common semantic profile between agents (§9)."""

    def __init__(
        self,
        *,
        guard: DowngradeGuard | None = None,
        preferred_profile: str = SA2A_PROFILE_V26_9_16,
    ) -> None:
        self.guard = guard or DowngradeGuard()
        self.preferred_profile = preferred_profile

    def negotiate(
        self,
        initiator: SemanticAgentCard,
        responder: SemanticAgentCard,
        requested_profile: str | None = None,
    ) -> ProfileNegotiationSession:
        """Negotiate mutually supported profile, enforcing strict downgrade prevention."""
        target_profile = requested_profile or self.preferred_profile

        # Strict downgrade check
        self.guard.assert_supported_profile(target_profile)

        if not initiator.supports_profile(target_profile):
            raise UnsupportedProfileError(
                f"Initiator '{initiator.agent_id}' does not support requested profile '{target_profile}'",
                profile=target_profile,
            )

        if not responder.supports_profile(target_profile):
            raise UnsupportedProfileError(
                f"Responder '{responder.agent_id}' does not support requested profile '{target_profile}'",
                profile=target_profile,
            )

        # Match capabilities
        init_caps = {c.capability_iri for c in initiator.capabilities}
        resp_caps = {c.capability_iri for c in responder.capabilities}
        common_caps = sorted(init_caps.intersection(resp_caps))

        session_id = f"sess_{uuid.uuid4().hex[:12]}"

        return ProfileNegotiationSession(
            session_id=session_id,
            initiator_id=initiator.agent_id,
            responder_id=responder.agent_id,
            negotiated_profile=target_profile,
            active_capabilities=tuple(common_caps),
        )
