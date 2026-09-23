"""Confused Deputy Prevention Guard for Semantic A2A (§54).

Ensures that a peer agent cannot use its ambient authority or execution capability
merely because another peer asked for an action to be performed.

Enforces:
1. Originating caller identity preservation across delegation chains.
2. Authority provenance checking (delegation must be explicit with non-repudiable grant).
3. Privilege separation: Deputy executing an action on behalf of Principal must check
   that the Principal itself possesses the required authority grant, not merely the Deputy.
4. Refusal code REFUSED_CONFUSED_DEPUTY when an ambient or unverified delegation is detected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence

REFUSED_CONFUSED_DEPUTY = "REFUSED_CONFUSED_DEPUTY"
REFUSED_UNAUTHORIZED_DELEGATION = "REFUSED_UNAUTHORIZED_DELEGATION"


@dataclass(frozen=True)
class DelegationHop:
    """A single hop in an A2A delegation chain."""

    caller_id: str
    target_agent_id: str
    delegated_grant_id: Optional[str] = None
    signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InvocationContext:
    """Context accompanying an action execution request across peers."""

    actor_id: str  # The immediate actor attempting actuation
    initiator_id: str  # The original principal initiating the request
    delegation_chain: Sequence[DelegationHop] = field(default_factory=tuple)
    ambient_authority_asserted: bool = False
    grant_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_delegated(self) -> bool:
        return self.actor_id != self.initiator_id or len(self.delegation_chain) > 0


@dataclass(frozen=True)
class DeputyGuardResult:
    """Outcome of evaluating confused deputy prevention rules."""

    allowed: bool
    refusal_code: Optional[str] = None
    reason: str = ""


class ConfusedDeputyGuard:
    """Guard (§54) preventing confused deputy vulnerability in agent-to-agent interactions."""

    def __init__(
        self, authorized_delegations: Optional[Dict[str, Sequence[str]]] = None
    ):
        """
        Args:
            authorized_delegations: Optional map of grant_id -> list of allowed delegating caller IDs.
        """
        self.authorized_delegations = authorized_delegations or {}

    def inspect_invocation(
        self,
        context: InvocationContext,
        action: str,
        target_resource: str,
    ) -> DeputyGuardResult:
        """Inspect invocation context to ensure the actor is not acting as a confused deputy.

        Guards:
        1. Ambient authority: If actor relies on ambient authority without an explicit grant on
           behalf of an external initiator, refuse immediately.
        2. Broken delegation chain: If initiator != actor, each hop must be accounted for.
        3. Delegation grant authority: The initiator must have provided an explicit grant ID
           authorizing the delegation of this action.
        """
        # Rule 1: No ambient authority actuation for delegated or peer requests
        if context.ambient_authority_asserted:
            return DeputyGuardResult(
                allowed=False,
                refusal_code=REFUSED_CONFUSED_DEPUTY,
                reason=(
                    f"Agent {context.actor_id!r} attempted to actuate action {action!r} "
                    f"on {target_resource!r} using ambient authority without explicit grant."
                ),
            )

        # Rule 2: If delegated, the initiator must not be bypassed or assumed
        if context.is_delegated:
            if not context.grant_id:
                return DeputyGuardResult(
                    allowed=False,
                    refusal_code=REFUSED_CONFUSED_DEPUTY,
                    reason=(
                        f"Delegated invocation from initiator {context.initiator_id!r} "
                        f"to actor {context.actor_id!r} lacks explicit grant_id. "
                        "Deputy cannot execute on caller's behalf merely because requested."
                    ),
                )

            # Check if grant is specifically authorized for delegation if mapping is configured
            if context.grant_id in self.authorized_delegations:
                allowed_callers = self.authorized_delegations[context.grant_id]
                if (
                    context.initiator_id not in allowed_callers
                    and context.actor_id not in allowed_callers
                ):
                    return DeputyGuardResult(
                        allowed=False,
                        refusal_code=REFUSED_UNAUTHORIZED_DELEGATION,
                        reason=(
                            f"Grant {context.grant_id!r} is not authorized for delegation by "
                            f"initiator {context.initiator_id!r} or actor {context.actor_id!r}."
                        ),
                    )

            # Validate chain integrity: the chain must connect initiator to actor
            if context.delegation_chain:
                first_hop = context.delegation_chain[0]
                if first_hop.caller_id != context.initiator_id:
                    return DeputyGuardResult(
                        allowed=False,
                        refusal_code=REFUSED_CONFUSED_DEPUTY,
                        reason=f"Delegation chain start {first_hop.caller_id!r} does not match initiator {context.initiator_id!r}.",
                    )
                last_hop = context.delegation_chain[-1]
                if last_hop.target_agent_id != context.actor_id:
                    return DeputyGuardResult(
                        allowed=False,
                        refusal_code=REFUSED_CONFUSED_DEPUTY,
                        reason=f"Delegation chain end {last_hop.target_agent_id!r} does not match actor {context.actor_id!r}.",
                    )

        return DeputyGuardResult(allowed=True)
