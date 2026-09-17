# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test Suite for Authority Broker Conformance Court (RFC-SA2A-002 v26.9.16).

Chicago Zero-Mock Standard:
- Real AuthorityBroker instances; no unittest.mock.
- Adversarial requests use genuine broker evaluation.
- No golden trace fixtures.
"""

from __future__ import annotations

import pytest

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant, ConsequenceRequest
from autofde_lab.sa2a.conformance.courts.authority_court import (
    SA2A_AUTH_AGENT_NOT_AUTHORITY,
    SA2A_AUTH_CAPABILITY_NOT_AUTHORITY,
    SA2A_AUTH_CONFUSED_DEPUTY,
    SA2A_AUTH_GRANT_REQUIRED,
    SA2A_AUTH_PLAN_NOT_AUTHORITY,
    SA2A_AUTH_PROOF_NOT_AUTHORITY,
    CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY,
    CHI_PLAN_AUTH_TOKEN_REBINDING,
    AgentIsAuthorityViolationError,
    AuthorityCourt,
    AuthorityCourtError,
    AuthorityCourtReport,
    AuthorityVerdict,
    ConfusedDeputyViolationError,
    PlanIsAuthorityViolationError,
    TokenRebindingViolationError,
    test_agent_not_authority,
    test_confused_deputy_prevented,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_grant(
    subject_id: str = "urn:agent:authorized",
    action_iri: str = "urn:action:test:execute",
    target_resource_iri: str = "urn:resource:test:node",
    grant_id: str = "grant-test-001",
) -> AuthorityGrant:
    return AuthorityGrant(
        grant_id=grant_id,
        subject_id=subject_id,
        action_iri=action_iri,
        target_resource_iri=target_resource_iri,
    )


# ---------------------------------------------------------------------------
# 1. Agent != Authority (SA2A-AUTH-AGENT-NOT-AUTHORITY)
# ---------------------------------------------------------------------------


def test_agent_not_authority_ambient_refused() -> None:
    """Agent using ambient authority assumption MUST be refused."""
    court = AuthorityCourt()
    broker = AuthorityBroker()
    res = court.verify_agent_not_authority(
        broker,
        actor_id="urn:agent:rogue",
        action_iri="urn:action:system:shutdown",
        target_resource="urn:resource:system:all",
        fail_closed=True,
    )
    assert res.passed is True  # Court passes because the broker correctly refused
    assert res.rule_id == SA2A_AUTH_AGENT_NOT_AUTHORITY
    assert res.decision is not None
    assert not res.decision.authorized


def test_agent_not_authority_in_module_helper() -> None:
    """In-module test helper executes without error."""
    court = AuthorityCourt()
    test_agent_not_authority(court)


# ---------------------------------------------------------------------------
# 2. Plan != Authority (SA2A-AUTH-PLAN-NOT-AUTHORITY)
# ---------------------------------------------------------------------------


def test_plan_not_authority_asserted_plan_refused() -> None:
    """Asserted plan alone MUST NOT authorize actor."""
    court = AuthorityCourt()
    broker = AuthorityBroker()
    res = court.verify_plan_not_authority(
        broker,
        actor_id="urn:agent:planner-output",
        action_iri="urn:action:deploy:service",
        target_resource="urn:resource:cluster:prod",
        fake_plan={"type": "PDDL", "actions": ["move", "grab", "release"]},
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_AUTH_PLAN_NOT_AUTHORITY
    assert not res.decision.authorized


def test_plan_not_authority_court_invariant() -> None:
    """Verify plan non-authority is an invariant across plan shapes."""
    court = AuthorityCourt()
    for plan in [
        {"steps": ["a", "b"]},
        {"goals": ["g1"], "actions": ["op1"]},
        {"pddl": "(:action move :precondition ...)"},
    ]:
        broker = AuthorityBroker()
        res = court.verify_plan_not_authority(
            broker, "urn:agent:any", "urn:action:any", "urn:resource:any",
            fake_plan=plan, fail_closed=True
        )
        assert res.passed is True, f"Plan should not grant authority: {plan}"


# ---------------------------------------------------------------------------
# 3. Proof != Authority (SA2A-AUTH-PROOF-NOT-AUTHORITY)
# ---------------------------------------------------------------------------


def test_proof_not_authority_shacl_validation_refused() -> None:
    """SHACL validation proof MUST NOT authorize execution."""
    court = AuthorityCourt()
    broker = AuthorityBroker()
    res = court.verify_proof_not_authority(
        broker,
        actor_id="urn:agent:validator",
        action_iri="urn:action:publish:graph",
        target_resource="urn:resource:graph:production",
        fake_proof={"type": "shacl_validation", "result": "conformant", "shapes": 42},
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_AUTH_PROOF_NOT_AUTHORITY
    assert not res.decision.authorized


def test_proof_not_authority_receipt_refused() -> None:
    """Receipt evidence MUST NOT authorize execution."""
    court = AuthorityCourt()
    broker = AuthorityBroker()
    res = court.verify_proof_not_authority(
        broker,
        actor_id="urn:agent:receipts-holder",
        action_iri="urn:action:execute:critical",
        target_resource="urn:resource:system:critical",
        fake_proof={"type": "execution_receipt", "receipt_id": "rcpt-001"},
        fail_closed=True,
    )
    assert res.passed is True
    assert not res.decision.authorized


# ---------------------------------------------------------------------------
# 4. Capability != Authority (SA2A-AUTH-CAPABILITY-NOT-AUTHORITY)
# ---------------------------------------------------------------------------


def test_capability_not_authority_admin_cap_refused() -> None:
    """Admin capability MUST NOT grant authority without explicit grant."""
    court = AuthorityCourt()
    broker = AuthorityBroker()
    res = court.verify_capability_not_authority(
        broker,
        actor_id="urn:agent:admin-capable",
        action_iri="urn:action:delete:all",
        target_resource="urn:resource:database:all",
        asserted_capabilities=["urn:cap:admin", "urn:cap:root", "urn:cap:superuser"],
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_AUTH_CAPABILITY_NOT_AUTHORITY
    assert not res.decision.authorized


# ---------------------------------------------------------------------------
# 5. Grant Required (SA2A-AUTH-GRANT-REQUIRED)
# ---------------------------------------------------------------------------


def test_grant_required_bare_request_refused() -> None:
    """Bare request without grant_id or matching grant MUST be refused."""
    court = AuthorityCourt()
    broker = AuthorityBroker()
    res = court.verify_grant_required_for_authorized(
        broker,
        actor_id="urn:agent:unauthorized",
        action_iri="urn:action:system:restart",
        target_resource="urn:resource:host:prod",
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_AUTH_GRANT_REQUIRED
    assert not res.decision.authorized


def test_grant_required_registered_grant_succeeds() -> None:
    """Explicit registered grant IS authorized (positive control)."""
    court = AuthorityCourt()
    grant = _make_grant()
    broker = AuthorityBroker()
    res = court.verify_legitimate_grant_authorized(broker, grant, fail_closed=True)
    assert res.passed is True
    assert res.decision.authorized


# ---------------------------------------------------------------------------
# 6. Confused Deputy Prevention (SA2A-AUTH-CONFUSED-DEPUTY)
# ---------------------------------------------------------------------------


def test_confused_deputy_impersonation_refused() -> None:
    """Impersonating actor using legitimate actor's grant MUST be refused."""
    court = AuthorityCourt()
    grant = _make_grant(subject_id="urn:agent:legitimate")
    broker = AuthorityBroker()
    res = court.verify_confused_deputy_prevented(
        broker=broker,
        legitimate_actor_id="urn:agent:legitimate",
        impersonating_actor_id="urn:agent:adversary",
        action_iri=grant.action_iri,
        target_resource=grant.target_resource_iri,
        grant=grant,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == SA2A_AUTH_CONFUSED_DEPUTY
    assert not res.decision.authorized


def test_confused_deputy_in_module_helper() -> None:
    """In-module confused deputy test helper executes without error."""
    court = AuthorityCourt()
    test_confused_deputy_prevented(court)


def test_confused_deputy_same_actor_is_authorized() -> None:
    """The legitimate actor with registered grant IS authorized."""
    court = AuthorityCourt()
    grant = _make_grant(subject_id="urn:agent:legitimate")
    broker = AuthorityBroker()
    broker.register_grant(grant)
    request = ConsequenceRequest(
        actor_id="urn:agent:legitimate",
        action_iri=grant.action_iri,
        target_resource=grant.target_resource_iri,
        grant_id=grant.grant_id,
    )
    decision = broker.evaluate(request)
    assert decision.authorized


# ---------------------------------------------------------------------------
# 7. Planner Non-Authority (CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY)
# ---------------------------------------------------------------------------


def test_planner_non_authority_dict_output_passes() -> None:
    """Dict planner output has no authority — passes."""
    court = AuthorityCourt()
    planner_output = {
        "type": "PDDL_solution",
        "actions": ["(:action move_arm :parameters ...)"],
        "cost": 12.5,
    }
    res = court.verify_planner_non_authority(planner_output, fail_closed=True)
    assert res.passed is True
    assert res.rule_id == CHI_PLAN_AUTH_PLANNER_NON_AUTHORITY


def test_planner_non_authority_list_passes() -> None:
    """List planner output passes."""
    court = AuthorityCourt()
    res = court.verify_planner_non_authority(["step1", "step2"], fail_closed=True)
    assert res.passed is True


def test_planner_non_authority_callable_refused() -> None:
    """Callable planner output self-authorizes — MUST be refused."""
    court = AuthorityCourt()
    with pytest.raises(PlanIsAuthorityViolationError):
        court.verify_planner_non_authority(lambda: None, fail_closed=True)


def test_planner_non_authority_execute_key_refused() -> None:
    """Dict with 'execute' key self-authorizes — refused."""
    court = AuthorityCourt()
    with pytest.raises(PlanIsAuthorityViolationError):
        court.verify_planner_non_authority(
            {"execute": "urn:action:dangerous:deploy", "target": "prod"},
            fail_closed=True,
        )


def test_planner_non_authority_authorize_key_refused() -> None:
    """Dict with 'authorize' key self-authorizes — refused."""
    court = AuthorityCourt()
    with pytest.raises(PlanIsAuthorityViolationError):
        court.verify_planner_non_authority(
            {"authorize": "urn:agent:self", "grant": "grant-self"},
            fail_closed=True,
        )


# ---------------------------------------------------------------------------
# 8. Token Rebinding (CHI-PLAN-AUTH-TOKEN-REBINDING)
# ---------------------------------------------------------------------------


def test_token_rebinding_refused() -> None:
    """Grant token for legitimate actor MUST NOT be usable by rebinding actor."""
    court = AuthorityCourt()
    grant = _make_grant(subject_id="urn:agent:original-owner", grant_id="grant-rebind-test")
    broker = AuthorityBroker()
    res = court.verify_token_rebinding_detected(
        broker=broker,
        original_actor_id="urn:agent:original-owner",
        rebound_actor_id="urn:agent:rebinder",
        action_iri=grant.action_iri,
        target_resource=grant.target_resource_iri,
        grant=grant,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.rule_id == CHI_PLAN_AUTH_TOKEN_REBINDING
    assert not res.decision.authorized


# ---------------------------------------------------------------------------
# 9. Full Court Sweep
# ---------------------------------------------------------------------------


def test_full_court_sweep_clean_setup() -> None:
    """Full court sweep with compliant setup produces all-pass report."""
    court = AuthorityCourt()
    legitimate_grant = _make_grant(
        subject_id="urn:agent:full-court-actor",
        action_iri="urn:action:test:full",
        target_resource_iri="urn:resource:test:full",
        grant_id="grant-full-court-001",
    )
    report = court.run_full_court(
        actor_id="urn:agent:full-court-actor",
        action_iri="urn:action:test:full",
        target_resource="urn:resource:test:full",
        legitimate_grant=legitimate_grant,
        fail_closed=False,
    )
    assert isinstance(report, AuthorityCourtReport)
    assert report.passed is True, f"Failed: {[r for r in report.gate_results if not r.passed]}"
    assert report.total_checks > 0
    assert report.failed_checks == 0
