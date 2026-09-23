"""Explicit Authority Broker & Non-Implication Enforcement for Semantic A2A (§28, §29).

Enforces Authority Non-Implications (§29):
  1. Agent != Authority      (Possessing an agent identity or role does not imply authority)
  2. Capability != Authority (Having the technical capability/tooling to do X does not imply authority)
  3. Plan != Authority       (Generating or possessing an admitted plan does not imply authority)
  4. Proof != Authority      (Having a formal proof or validation receipt does not imply authority)

Authority must be granted explicitly via formal policy/grants (ODRL-compatible).
Evaluates whether actor may execute consequence c under context.
Returns AuthorityDecision(authorized: bool, grant_id: str | None, refusal_code: str | None, constraints: dict).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from autofde_lab.sa2a.authority.confused_deputy import (
    REFUSED_CONFUSED_DEPUTY,
    ConfusedDeputyGuard,
    InvocationContext,
)
from autofde_lab.sa2a.authority.odrl import (
    Constraint,
    OdrlAction,
    Permission,
    Policy,
    Prohibition,
)

# Standard SA2A Refusal Codes (§29, §54)
REFUSED_NO_GRANT = "REFUSED_NO_GRANT"
REFUSED_PROHIBITED = "REFUSED_PROHIBITED"
REFUSED_CONSTRAINT_VIOLATION = "REFUSED_CONSTRAINT_VIOLATION"
REFUSED_UNFULFILLED_DUTY = "REFUSED_UNFULFILLED_DUTY"
REFUSED_AGENT_IS_NOT_AUTHORITY = "REFUSED_AGENT_IS_NOT_AUTHORITY"
REFUSED_CAPABILITY_IS_NOT_AUTHORITY = "REFUSED_CAPABILITY_IS_NOT_AUTHORITY"
REFUSED_PLAN_IS_NOT_AUTHORITY = "REFUSED_PLAN_IS_NOT_AUTHORITY"
REFUSED_PROOF_IS_NOT_AUTHORITY = "REFUSED_PROOF_IS_NOT_AUTHORITY"
REFUSED_EXPIRED_GRANT = "REFUSED_EXPIRED_GRANT"


@dataclass(frozen=True)
class AuthorityDecision:
    """Decision returned by the Authority Broker."""

    authorized: bool
    grant_id: Optional[str] = None
    refusal_code: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class AuthorityGrant:
    """Explicit grant of authority issued to an actor or policy."""

    grant_id: str
    subject_id: str  # The authorized party or actor UID
    action_iri: str  # Action IRI (e.g., OdrlAction.EXECUTE)
    target_resource_iri: str  # Target Asset IRI
    constraints: Dict[str, Any] = field(default_factory=dict)
    duties: Sequence[str] = field(
        default_factory=tuple
    )  # Required duty IDs or action IRIs
    valid_until: Optional[float] = None
    issuer_id: str = "authority-root"


@dataclass(frozen=True)
class ConsequenceRequest:
    """Request to actuate consequence c under an evaluation context."""

    actor_id: str
    action_iri: str
    target_resource: str
    context: Dict[str, Any] = field(default_factory=dict)
    grant_id: Optional[str] = None
    invocation_context: Optional[InvocationContext] = None

    # Explicit claims provided in the request (to test Non-Implications)
    asserted_capabilities: Sequence[str] = field(default_factory=tuple)
    asserted_plan: Optional[Dict[str, Any]] = None
    asserted_proof: Optional[Dict[str, Any]] = None
    ambient_authority_assumed: bool = False


class AuthorityBroker:
    """Explicit Authority Broker (§28, §29) evaluating consequence actuation."""

    def __init__(
        self,
        policies: Optional[Sequence[Policy]] = None,
        grants: Optional[Sequence[AuthorityGrant]] = None,
        deputy_guard: Optional[ConfusedDeputyGuard] = None,
    ):
        self._policies: List[Policy] = list(policies or [])
        self._grants: Dict[str, AuthorityGrant] = {
            g.grant_id: g for g in (grants or [])
        }
        self._deputy_guard: ConfusedDeputyGuard = deputy_guard or ConfusedDeputyGuard()

    def register_grant(self, grant: AuthorityGrant) -> None:
        """Register an explicit authority grant."""
        self._grants[grant.grant_id] = grant

    def register_policy(self, policy: Policy) -> None:
        """Register an ODRL policy."""
        self._policies.append(policy)

    def evaluate(self, request: ConsequenceRequest) -> AuthorityDecision:
        """Evaluate whether actor may execute consequence c under request.context.

        Enforces:
        - Confused Deputy Prevention (§54)
        - Authority Non-Implications (§29)
        - ODRL Policy prohibitions, permissions, constraints, duties
        - Explicit grant validity
        """
        # 1. Confused Deputy Check (§54)
        inv_ctx = request.invocation_context
        if inv_ctx is None:
            # Construct default invocation context from request
            inv_ctx = InvocationContext(
                actor_id=request.actor_id,
                initiator_id=request.actor_id,
                ambient_authority_asserted=request.ambient_authority_assumed,
                grant_id=request.grant_id,
                parameters=request.context,
            )

        guard_res = self._deputy_guard.inspect_invocation(
            context=inv_ctx,
            action=request.action_iri,
            target_resource=request.target_resource,
        )
        if not guard_res.allowed:
            return AuthorityDecision(
                authorized=False,
                grant_id=None,
                refusal_code=guard_res.refusal_code or REFUSED_CONFUSED_DEPUTY,
                reason=guard_res.reason,
            )

        # 2. Authority Non-Implications (§29)
        # 2a. Ambient authority / Agent != Authority: an agent cannot assume authority merely by existing
        if request.ambient_authority_assumed:
            return AuthorityDecision(
                authorized=False,
                grant_id=None,
                refusal_code=REFUSED_AGENT_IS_NOT_AUTHORITY,
                reason="Agent identity does not imply execution authority (Agent != Authority §29).",
            )

        # 2b. Capability != Authority: Having capabilities or tools does not authorize execution
        if request.grant_id is None and request.asserted_capabilities:
            # If the actor presents capabilities without a grant
            return AuthorityDecision(
                authorized=False,
                grant_id=None,
                refusal_code=REFUSED_CAPABILITY_IS_NOT_AUTHORITY,
                reason="Capability does not imply execution authority (Capability != Authority §29).",
            )

        # 2c. Plan != Authority: Having a plan does not authorize execution
        if request.grant_id is None and request.asserted_plan is not None:
            return AuthorityDecision(
                authorized=False,
                grant_id=None,
                refusal_code=REFUSED_PLAN_IS_NOT_AUTHORITY,
                reason="Plan does not imply execution authority (Plan != Authority §29).",
            )

        # 2d. Proof != Authority: Having a proof or validation receipt does not authorize execution
        if request.grant_id is None and request.asserted_proof is not None:
            return AuthorityDecision(
                authorized=False,
                grant_id=None,
                refusal_code=REFUSED_PROOF_IS_NOT_AUTHORITY,
                reason="Proof does not imply execution authority (Proof != Authority §29).",
            )

        # 3. Check ODRL Prohibitions first (Prohibitions override permissions)
        for pol in self._policies:
            for prohib in pol.prohibitions:
                if self._matches_rule(
                    prohib,
                    request.actor_id,
                    request.action_iri,
                    request.target_resource,
                ):
                    # Check if all constraints on prohibition match
                    if self._check_constraints(prohib.constraints, request.context):
                        return AuthorityDecision(
                            authorized=False,
                            grant_id=None,
                            refusal_code=REFUSED_PROHIBITED,
                            reason=f"Action explicitly prohibited by policy {pol.uid} rule {prohib.uid}.",
                        )

        # 4. Check Explicit Grant or ODRL Policy Permission
        # First: If explicit grant_id was supplied or matching registered grant exists
        grant: AuthorityGrant | None = None
        if request.grant_id is not None:
            grant = self._grants.get(request.grant_id)
            if not grant:
                return AuthorityDecision(
                    authorized=False,
                    grant_id=None,
                    refusal_code=REFUSED_NO_GRANT,
                    reason=f"Grant ID {request.grant_id!r} not found in authority registry.",
                )
        else:
            for g in self._grants.values():
                if (
                    g.subject_id == request.actor_id
                    and g.action_iri == request.action_iri
                    and g.target_resource_iri == request.target_resource
                ):
                    grant = g
                    break

        if grant is not None:
            # Validate grant matches actor, action, resource
            if grant.subject_id != request.actor_id:
                return AuthorityDecision(
                    authorized=False,
                    grant_id=grant.grant_id,
                    refusal_code=REFUSED_NO_GRANT,
                    reason=f"Grant {grant.grant_id!r} is issued to {grant.subject_id!r}, not {request.actor_id!r}.",
                )

            if (
                grant.action_iri != request.action_iri
                or grant.target_resource_iri != request.target_resource
            ):
                return AuthorityDecision(
                    authorized=False,
                    grant_id=grant.grant_id,
                    refusal_code=REFUSED_NO_GRANT,
                    reason=f"Grant {grant.grant_id!r} does not cover action/resource ({grant.action_iri}, {grant.target_resource_iri}).",
                )

            if grant.valid_until is not None and time.time() > grant.valid_until:
                return AuthorityDecision(
                    authorized=False,
                    grant_id=grant.grant_id,
                    refusal_code=REFUSED_EXPIRED_GRANT,
                    reason=f"Grant {grant.grant_id!r} has expired.",
                )

            # Evaluate grant constraints
            for ck, cv in grant.constraints.items():
                if request.context.get(ck) != cv:
                    return AuthorityDecision(
                        authorized=False,
                        grant_id=grant.grant_id,
                        refusal_code=REFUSED_CONSTRAINT_VIOLATION,
                        constraints=grant.constraints,
                        reason=f"Grant constraint failed: context[{ck!r}]={request.context.get(ck)!r} != {cv!r}.",
                    )

            # Evaluate required duties fulfilled
            fulfilled_duties = set(request.context.get("fulfilled_duties", []))
            for required_duty in grant.duties:
                if required_duty not in fulfilled_duties:
                    return AuthorityDecision(
                        authorized=False,
                        grant_id=grant.grant_id,
                        refusal_code=REFUSED_UNFULFILLED_DUTY,
                        reason=f"Required duty {required_duty!r} is unfulfilled.",
                    )

            return AuthorityDecision(
                authorized=True,
                grant_id=grant.grant_id,
                refusal_code=None,
                constraints=grant.constraints,
            )

        # Second: If no explicit grant_id was given, see if an ODRL policy grants permission
        for pol in self._policies:
            for perm in pol.permissions:
                if self._matches_rule(
                    perm, request.actor_id, request.action_iri, request.target_resource
                ):
                    if not self._check_constraints(perm.constraints, request.context):
                        continue

                    # Check duties on permission
                    fulfilled_duties = set(request.context.get("fulfilled_duties", []))
                    all_duties_satisfied = True
                    for duty in perm.duties:
                        duty_action = (
                            duty.action.value
                            if isinstance(duty.action, OdrlAction)
                            else str(duty.action)
                        )
                        if (
                            duty.uid not in fulfilled_duties
                            and duty_action not in fulfilled_duties
                        ):
                            all_duties_satisfied = False
                            break

                    if not all_duties_satisfied:
                        return AuthorityDecision(
                            authorized=False,
                            grant_id=None,
                            refusal_code=REFUSED_UNFULFILLED_DUTY,
                            reason=f"Duty under permission {perm.uid} is unfulfilled.",
                        )

                    # Mint / associate synthetic grant for policy permission
                    return AuthorityDecision(
                        authorized=True,
                        grant_id=f"policy-grant-{pol.uid}-{perm.uid}",
                        refusal_code=None,
                        constraints={
                            c.left_operand: c.right_operand for c in perm.constraints
                        },
                    )

        # No grant and no permission found
        return AuthorityDecision(
            authorized=False,
            grant_id=None,
            refusal_code=REFUSED_NO_GRANT,
            reason=f"No authority grant or policy permits actor {request.actor_id!r} to perform {request.action_iri!r} on {request.target_resource!r}.",
        )

    def _matches_rule(
        self, rule: Permission | Prohibition, actor_id: str, action: str, target: str
    ) -> bool:
        assignee_id = (
            rule.assignee.uid if hasattr(rule.assignee, "uid") else str(rule.assignee)
        )
        target_id = rule.target.uid if hasattr(rule.target, "uid") else str(rule.target)
        rule_action = (
            rule.action.value
            if isinstance(rule.action, OdrlAction)
            else str(rule.action)
        )

        if assignee_id != "*" and assignee_id != actor_id:
            return False
        if target_id != "*" and target_id != target:
            return False
        if rule_action != "*" and rule_action != action:
            return False
        return True

    def _check_constraints(
        self, constraints: Sequence[Constraint], context: Dict[str, Any]
    ) -> bool:
        for c in constraints:
            if not c.evaluate(context):
                return False
        return True
