# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Authority Broker Conformance Court (RFC-SA2A-002 v26.9.16).

Gate families:
  SA2A-AUTH-*      — Non-implications: Agent≠Authority, Plan≠Authority, Proof≠Authority
  CHI-PLAN-AUTH-*  — Planner output non-authority, confused deputy prevention

Chicago Zero-Mock Standard:
  - Real AuthorityBroker instances; no unittest.mock.
  - Real grant registration; adversarial requests use spoofed identities.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityDecision,
    AuthorityGrant,
    ConsequenceRequest,
)

# Refusal code imports
try:
    from autofde_lab.sa2a.authority.broker import (
        REFUSED_AGENT_IS_NOT_AUTHORITY,
        REFUSED_CAPABILITY_IS_NOT_AUTHORITY,
        REFUSED_CONFUSED_DEPUTY,
        REFUSED_NO_GRANT,
        REFUSED_PLAN_IS_NOT_AUTHORITY,
        REFUSED_PROOF_IS_NOT_AUTHORITY,
    )
except ImportError:
    REFUSED_AGENT_IS_NOT_AUTHORITY = "REFUSED_AGENT_IS_NOT_AUTHORITY"
    REFUSED_CAPABILITY_IS_NOT_AUTHORITY = "REFUSED_CAPABILITY_IS_NOT_AUTHORITY"
    REFUSED_CONFUSED_DEPUTY = "REFUSED_CONFUSED_DEPUTY"
    REFUSED_NO_GRANT = "REFUSED_NO_GRANT"
    REFUSED_PLAN_IS_NOT_AUTHORITY = "REFUSED_PLAN_IS_NOT_AUTHORITY"
    REFUSED_PROOF_IS_NOT_AUTHORITY = "REFUSED_PROOF_IS_NOT_AUTHORITY"

# ---------------------------------------------------------------------------
# Rule IDs
# ---------------------------------------------------------------------------
SA2A_AUTH_AGENT_NOT_AUTHORITY = "SA2A-AUTH-AGENT-NOT-AUTHORITY"
SA2A_AUTH_PLAN_NOT_AUTHORITY = "SA2A-AUTH-PLAN-NOT-AUTHORITY"
SA2A_AUTH_PROOF_NOT_AUTHORITY = "SA2A-AUTH-PROOF-NOT-AUTHORITY"
SA2A_AUTH_CAPABILITY_NOT_AUTHORITY = "SA2A-AUTH-CAPABILITY-NOT-AUTHORITY"
SA2A_AUTH_GRANT_REQUIRED = "SA2A-AUTH-GRANT-REQUIRED"
SA2A_AUTH_CONFUSED_DEPUTY = "SA2A-AUTH-CONFUSED-DEPUTY"
CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY = "CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY"
CHI_PLAN_AUTH_TOKEN_REBINDING = "CHI-PLAN-AUTH-TOKEN-REBINDING"

# ---------------------------------------------------------------------------
# Verdicts and errors
# ---------------------------------------------------------------------------


class AuthorityCourtError(Exception):
    """Base error for Authority Court violations."""

    def __init__(
        self, message: str, details: Optional[Dict[str, Any]] = None, rule_id: str = ""
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.rule_id = rule_id


class AgentIsAuthorityViolationError(AuthorityCourtError):
    """Raised when broker grants authority purely based on agent identity."""


class PlanIsAuthorityViolationError(AuthorityCourtError):
    """Raised when broker grants authority based on planner output."""


class ConfusedDeputyViolationError(AuthorityCourtError):
    """Raised when confused deputy attack succeeds against broker."""


class TokenRebindingViolationError(AuthorityCourtError):
    """Raised when authority token rebinding is not detected."""


class AuthorityVerdict(str):
    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"
    REFUSED = "REFUSED"


@dataclass
class AuthorityCheckResult:
    rule_id: str
    passed: bool
    verdict: str
    decision: Optional[AuthorityDecision] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorityCourtReport:
    """Aggregated report from all Authority court checks."""

    gate_results: List[AuthorityCheckResult] = field(default_factory=list)
    passed: bool = True
    total_checks: int = 0
    failed_checks: int = 0
    report_digest: str = ""

    def __post_init__(self) -> None:
        self.total_checks = len(self.gate_results)
        self.failed_checks = sum(1 for r in self.gate_results if not r.passed)
        self.passed = self.failed_checks == 0
        payload = str([(r.rule_id, r.passed) for r in self.gate_results]).encode()
        self.report_digest = hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Court implementation
# ---------------------------------------------------------------------------


class AuthorityCourt:
    """Conformance court for SA2A-AUTH-* and CHI-PLAN-AUTH-* gate families.

    Verifies all RFC-SA2A-002 authority non-implication invariants:
    1. Agent identity alone does NOT grant execution authority.
    2. Plan possession does NOT grant execution authority.
    3. Proof/validation receipt does NOT grant execution authority.
    4. Capability ownership does NOT grant execution authority.
    5. All actuation requires an explicit registered grant.
    6. Confused deputy attacks are detected and refused.
    7. Planner output does not self-authorize.
    8. Authority token rebinding is detected.
    """

    # ------------------------------------------------------------------
    # SA2A-AUTH-AGENT-NOT-AUTHORITY
    # ------------------------------------------------------------------

    def verify_agent_not_authority(
        self,
        broker: AuthorityBroker,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify that agent identity alone does not grant execution authority.

        RFC §29: Agent existence/identity MUST NOT imply authority.
        A request using ambient_authority_assumed=True MUST be refused.
        """
        request = ConsequenceRequest(
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            ambient_authority_assumed=True,  # The forbidden assumption
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"SA2A-AUTH-AGENT-NOT-AUTHORITY VIOLATION: broker authorized actor "
                f"'{actor_id}' based on ambient authority (Agent != Authority §29)"
            )
            if fail_closed:
                raise AgentIsAuthorityViolationError(
                    err_msg,
                    {"actor_id": actor_id, "action_iri": action_iri},
                    rule_id=SA2A_AUTH_AGENT_NOT_AUTHORITY,
                )
            return AuthorityCheckResult(
                rule_id=SA2A_AUTH_AGENT_NOT_AUTHORITY,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=SA2A_AUTH_AGENT_NOT_AUTHORITY,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={"refusal_code": decision.refusal_code},
        )

    # ------------------------------------------------------------------
    # SA2A-AUTH-PLAN-NOT-AUTHORITY
    # ------------------------------------------------------------------

    def verify_plan_not_authority(
        self,
        broker: AuthorityBroker,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        fake_plan: Optional[Dict[str, Any]] = None,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify that possessing a plan does not grant execution authority.

        RFC §29: Plan != Authority. Presenting an asserted_plan MUST NOT authorize.
        """
        request = ConsequenceRequest(
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            asserted_plan=fake_plan
            or {"steps": ["initialize", "execute", "terminate"]},
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"SA2A-AUTH-PLAN-NOT-AUTHORITY VIOLATION: broker authorized actor "
                f"'{actor_id}' based on asserted plan (Plan != Authority §29)"
            )
            if fail_closed:
                raise PlanIsAuthorityViolationError(
                    err_msg,
                    {"actor_id": actor_id, "action_iri": action_iri},
                    rule_id=SA2A_AUTH_PLAN_NOT_AUTHORITY,
                )
            return AuthorityCheckResult(
                rule_id=SA2A_AUTH_PLAN_NOT_AUTHORITY,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=SA2A_AUTH_PLAN_NOT_AUTHORITY,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={"refusal_code": decision.refusal_code},
        )

    # ------------------------------------------------------------------
    # SA2A-AUTH-PROOF-NOT-AUTHORITY
    # ------------------------------------------------------------------

    def verify_proof_not_authority(
        self,
        broker: AuthorityBroker,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        fake_proof: Optional[Dict[str, Any]] = None,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify that possessing a proof/validation receipt does not grant authority.

        RFC §29: Proof != Authority. Presenting an asserted_proof MUST NOT authorize.
        """
        request = ConsequenceRequest(
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            asserted_proof=fake_proof
            or {"type": "shacl_validation", "result": "conformant"},
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"SA2A-AUTH-PROOF-NOT-AUTHORITY VIOLATION: broker authorized actor "
                f"'{actor_id}' based on asserted proof (Proof != Authority §29)"
            )
            if fail_closed:
                raise AuthorityCourtError(
                    err_msg,
                    {"actor_id": actor_id, "action_iri": action_iri},
                    rule_id=SA2A_AUTH_PROOF_NOT_AUTHORITY,
                )
            return AuthorityCheckResult(
                rule_id=SA2A_AUTH_PROOF_NOT_AUTHORITY,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=SA2A_AUTH_PROOF_NOT_AUTHORITY,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={"refusal_code": decision.refusal_code},
        )

    # ------------------------------------------------------------------
    # SA2A-AUTH-CAPABILITY-NOT-AUTHORITY
    # ------------------------------------------------------------------

    def verify_capability_not_authority(
        self,
        broker: AuthorityBroker,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        asserted_capabilities: Optional[Sequence[str]] = None,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify that owning capabilities does not grant execution authority.

        RFC §29: Capability != Authority. Presenting asserted_capabilities MUST NOT authorize.
        """
        caps = list(asserted_capabilities or ["urn:cap:admin", "urn:cap:root"])
        request = ConsequenceRequest(
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            asserted_capabilities=caps,
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"SA2A-AUTH-CAPABILITY-NOT-AUTHORITY VIOLATION: broker authorized actor "
                f"'{actor_id}' based on capabilities (Capability != Authority §29)"
            )
            if fail_closed:
                raise AuthorityCourtError(
                    err_msg,
                    {"actor_id": actor_id, "capabilities": caps},
                    rule_id=SA2A_AUTH_CAPABILITY_NOT_AUTHORITY,
                )
            return AuthorityCheckResult(
                rule_id=SA2A_AUTH_CAPABILITY_NOT_AUTHORITY,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=SA2A_AUTH_CAPABILITY_NOT_AUTHORITY,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={"refusal_code": decision.refusal_code},
        )

    # ------------------------------------------------------------------
    # SA2A-AUTH-GRANT-REQUIRED
    # ------------------------------------------------------------------

    def verify_grant_required_for_authorized(
        self,
        broker: AuthorityBroker,
        actor_id: str,
        action_iri: str,
        target_resource: str,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify explicit registered grant is required for authorization.

        A bare request without a grant_id or matching registered grant MUST be refused.
        """
        request = ConsequenceRequest(
            actor_id=actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            # No grant_id, no ambient authority, no asserted capabilities/plan/proof
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"SA2A-AUTH-GRANT-REQUIRED VIOLATION: broker authorized actor '{actor_id}' "
                f"without a registered grant (explicit grant required §28)"
            )
            if fail_closed:
                raise AuthorityCourtError(
                    err_msg,
                    {"actor_id": actor_id, "action_iri": action_iri},
                    rule_id=SA2A_AUTH_GRANT_REQUIRED,
                )
            return AuthorityCheckResult(
                rule_id=SA2A_AUTH_GRANT_REQUIRED,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=SA2A_AUTH_GRANT_REQUIRED,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={"refusal_code": decision.refusal_code},
        )

    # ------------------------------------------------------------------
    # SA2A-AUTH-CONFUSED-DEPUTY
    # ------------------------------------------------------------------

    def verify_confused_deputy_prevented(
        self,
        broker: AuthorityBroker,
        legitimate_actor_id: str,
        impersonating_actor_id: str,
        action_iri: str,
        target_resource: str,
        grant: AuthorityGrant,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify confused deputy attack is detected and refused.

        Register a grant for legitimate_actor, then attempt to use it as impersonating_actor.
        The broker MUST refuse the impersonator.
        """
        broker.register_grant(grant)

        # Attempt to use the grant as a different actor (confused deputy)
        request = ConsequenceRequest(
            actor_id=impersonating_actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            grant_id=grant.grant_id,
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"SA2A-AUTH-CONFUSED-DEPUTY VIOLATION: broker authorized impersonating actor "
                f"'{impersonating_actor_id}' using grant '{grant.grant_id}' issued to "
                f"'{legitimate_actor_id}' — confused deputy attack succeeded!"
            )
            if fail_closed:
                raise ConfusedDeputyViolationError(
                    err_msg,
                    {
                        "impersonator": impersonating_actor_id,
                        "grant_id": grant.grant_id,
                    },
                    rule_id=SA2A_AUTH_CONFUSED_DEPUTY,
                )
            return AuthorityCheckResult(
                rule_id=SA2A_AUTH_CONFUSED_DEPUTY,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=SA2A_AUTH_CONFUSED_DEPUTY,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={
                "legitimate_actor": legitimate_actor_id,
                "impersonator": impersonating_actor_id,
                "refusal_code": decision.refusal_code,
            },
        )

    # ------------------------------------------------------------------
    # CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY
    # ------------------------------------------------------------------

    def verify_planner_non_authority(
        self,
        planner_output: Any,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify planner output does not self-authorize execution.

        RFC §35/§36: Planner output is CANDIDATE — not admitted actuation authority.
        The planner output must be a data structure, not a callable consequence.
        """
        if callable(planner_output):
            err_msg = (
                "CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY: planner output is callable — "
                "planning result MUST NOT have execution authority (Plan != Authority §29, §35)"
            )
            if fail_closed:
                raise PlanIsAuthorityViolationError(
                    err_msg,
                    rule_id=CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY,
                )
            return AuthorityCheckResult(
                rule_id=CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                error_message=err_msg,
            )

        # Check if the planner output attempts to claim authority
        if isinstance(planner_output, dict):
            authority_keys = {"grant", "authorize", "execute", "actuate", "do"}
            found = authority_keys.intersection(str(k).lower() for k in planner_output)
            if found:
                err_msg = (
                    f"CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY: planner output asserts authority "
                    f"via keys {sorted(found)} — planner MUST NOT self-authorize"
                )
                if fail_closed:
                    raise PlanIsAuthorityViolationError(
                        err_msg,
                        {"authority_keys": sorted(found)},
                        rule_id=CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY,
                    )
                return AuthorityCheckResult(
                    rule_id=CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY,
                    passed=False,
                    verdict=AuthorityVerdict.REFUSED,
                    error_message=err_msg,
                    details={"authority_keys": sorted(found)},
                )

        return AuthorityCheckResult(
            rule_id=CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            details={"output_type": type(planner_output).__name__},
        )

    # ------------------------------------------------------------------
    # CHI-PLAN-AUTH-TOKEN-REBINDING
    # ------------------------------------------------------------------

    def verify_token_rebinding_detected(
        self,
        broker: AuthorityBroker,
        original_actor_id: str,
        rebound_actor_id: str,
        action_iri: str,
        target_resource: str,
        grant: AuthorityGrant,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify authority token rebinding (grant reassignment) is detected.

        A grant issued to original_actor MUST NOT be rebindable to a different actor
        without explicit re-registration with the new subject_id.
        """
        broker.register_grant(grant)

        # Attempt to use grant with a different actor_id (token rebinding)
        request = ConsequenceRequest(
            actor_id=rebound_actor_id,
            action_iri=action_iri,
            target_resource=target_resource,
            grant_id=grant.grant_id,
        )
        decision = broker.evaluate(request)

        if decision.authorized:
            err_msg = (
                f"CHI-PLAN-AUTH-TOKEN-REBINDING: broker allowed token rebinding — "
                f"grant '{grant.grant_id}' for '{original_actor_id}' was accepted "
                f"by '{rebound_actor_id}'"
            )
            if fail_closed:
                raise TokenRebindingViolationError(
                    err_msg,
                    {"original": original_actor_id, "rebound": rebound_actor_id},
                    rule_id=CHI_PLAN_AUTH_TOKEN_REBINDING,
                )
            return AuthorityCheckResult(
                rule_id=CHI_PLAN_AUTH_TOKEN_REBINDING,
                passed=False,
                verdict=AuthorityVerdict.REFUSED,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id=CHI_PLAN_AUTH_TOKEN_REBINDING,
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={
                "original_actor": original_actor_id,
                "rebound_actor": rebound_actor_id,
                "refusal_code": decision.refusal_code,
            },
        )

    # ------------------------------------------------------------------
    # Convenience: verify a legitimate grant is authorized
    # ------------------------------------------------------------------

    def verify_legitimate_grant_authorized(
        self,
        broker: AuthorityBroker,
        grant: AuthorityGrant,
        fail_closed: bool = True,
    ) -> AuthorityCheckResult:
        """Verify that a properly registered grant IS authorized (positive control)."""
        broker.register_grant(grant)
        request = ConsequenceRequest(
            actor_id=grant.subject_id,
            action_iri=grant.action_iri,
            target_resource=grant.target_resource_iri,
            grant_id=grant.grant_id,
        )
        decision = broker.evaluate(request)

        if not decision.authorized:
            err_msg = (
                f"Legitimate grant '{grant.grant_id}' for actor '{grant.subject_id}' "
                f"was NOT authorized — broker is over-refusing (positive control failed)"
            )
            if fail_closed:
                raise AuthorityCourtError(
                    err_msg,
                    {"grant_id": grant.grant_id, "refusal_code": decision.refusal_code},
                    rule_id="SA2A-AUTH-LEGITIMATE-GRANT",
                )
            return AuthorityCheckResult(
                rule_id="SA2A-AUTH-LEGITIMATE-GRANT",
                passed=False,
                verdict=AuthorityVerdict.NON_CONFORMANT,
                decision=decision,
                error_message=err_msg,
            )

        return AuthorityCheckResult(
            rule_id="SA2A-AUTH-LEGITIMATE-GRANT",
            passed=True,
            verdict=AuthorityVerdict.CONFORMANT,
            decision=decision,
            details={"grant_id": decision.grant_id},
        )

    # ------------------------------------------------------------------
    # Full court sweep
    # ------------------------------------------------------------------

    def run_full_court(
        self,
        *,
        broker: Optional[AuthorityBroker] = None,
        actor_id: str = "urn:agent:test-actor",
        action_iri: str = "urn:action:test:execute",
        target_resource: str = "urn:resource:test:file",
        legitimate_grant: Optional[AuthorityGrant] = None,
        fail_closed: bool = False,
    ) -> AuthorityCourtReport:
        """Run all Authority court checks and return aggregated report."""
        if broker is None:
            broker = AuthorityBroker()

        results: List[AuthorityCheckResult] = []

        # Non-implication checks (all with empty broker)
        empty_broker = AuthorityBroker()
        results.append(
            self.verify_agent_not_authority(
                empty_broker,
                actor_id,
                action_iri,
                target_resource,
                fail_closed=fail_closed,
            )
        )
        results.append(
            self.verify_plan_not_authority(
                AuthorityBroker(),
                actor_id,
                action_iri,
                target_resource,
                fail_closed=fail_closed,
            )
        )
        results.append(
            self.verify_proof_not_authority(
                AuthorityBroker(),
                actor_id,
                action_iri,
                target_resource,
                fail_closed=fail_closed,
            )
        )
        results.append(
            self.verify_capability_not_authority(
                AuthorityBroker(),
                actor_id,
                action_iri,
                target_resource,
                fail_closed=fail_closed,
            )
        )
        results.append(
            self.verify_grant_required_for_authorized(
                AuthorityBroker(),
                actor_id,
                action_iri,
                target_resource,
                fail_closed=fail_closed,
            )
        )

        # Confused deputy and token rebinding (need real grants)
        if legitimate_grant is not None:
            cd_broker = AuthorityBroker()
            results.append(
                self.verify_confused_deputy_prevented(
                    broker=cd_broker,
                    legitimate_actor_id=legitimate_grant.subject_id,
                    impersonating_actor_id="urn:agent:impersonator",
                    action_iri=legitimate_grant.action_iri,
                    target_resource=legitimate_grant.target_resource_iri,
                    grant=legitimate_grant,
                    fail_closed=fail_closed,
                )
            )
            tb_broker = AuthorityBroker()
            results.append(
                self.verify_token_rebinding_detected(
                    broker=tb_broker,
                    original_actor_id=legitimate_grant.subject_id,
                    rebound_actor_id="urn:agent:rebinder",
                    action_iri=legitimate_grant.action_iri,
                    target_resource=legitimate_grant.target_resource_iri,
                    grant=legitimate_grant,
                    fail_closed=fail_closed,
                )
            )
            # Positive control
            pos_broker = AuthorityBroker()
            results.append(
                self.verify_legitimate_grant_authorized(
                    pos_broker, legitimate_grant, fail_closed=fail_closed
                )
            )

        # Planner non-authority
        results.append(
            self.verify_planner_non_authority(
                {"steps": ["plan_step_1"], "goal": "urn:goal:test"},
                fail_closed=fail_closed,
            )
        )

        return AuthorityCourtReport(gate_results=results)


# ---------------------------------------------------------------------------
# In-module test helpers
# ---------------------------------------------------------------------------


def test_agent_not_authority(court: Optional[AuthorityCourt] = None) -> None:
    """Verify agent identity does not imply authority."""
    c = court or AuthorityCourt()
    broker = AuthorityBroker()
    res = c.verify_agent_not_authority(
        broker,
        "urn:agent:test",
        "urn:action:test",
        "urn:resource:test",
        fail_closed=True,
    )
    assert not res.passed or res.decision is not None  # Refusal expected
    # More precisely: ambient authority must be refused
    broker2 = AuthorityBroker()
    request = ConsequenceRequest(
        actor_id="urn:agent:test",
        action_iri="urn:action:test",
        target_resource="urn:resource:test",
        ambient_authority_assumed=True,
    )
    decision = broker2.evaluate(request)
    assert not decision.authorized, "Ambient authority MUST be refused"


def test_confused_deputy_prevented(court: Optional[AuthorityCourt] = None) -> None:
    """Verify confused deputy attack is refused."""
    c = court or AuthorityCourt()
    grant = AuthorityGrant(
        grant_id="grant-test-001",
        subject_id="urn:agent:legitimate",
        action_iri="urn:action:system:restart",
        target_resource_iri="urn:resource:system:node-1",
    )
    broker = AuthorityBroker()
    res = c.verify_confused_deputy_prevented(
        broker=broker,
        legitimate_actor_id="urn:agent:legitimate",
        impersonating_actor_id="urn:agent:adversary",
        action_iri="urn:action:system:restart",
        target_resource="urn:resource:system:node-1",
        grant=grant,
        fail_closed=True,
    )
    assert res.passed, f"Confused deputy should be refused: {res.error_message}"
