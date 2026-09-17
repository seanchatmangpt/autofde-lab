"""Unit tests for Semantic A2A Authority Broker & ODRL Mapping (RFC-SA2A-001 v26.9.16).

Verifies:
1. Authority Non-Implications (§29):
   - Agent != Authority
   - Capability != Authority
   - Plan != Authority
   - Proof != Authority
2. Grant Evaluation (§28):
   - Valid explicit authority grant authorizes consequence execution
   - Unknown grant, wrong subject, wrong action/target are refused
   - Grant constraint violations are refused
   - Unfulfilled duties are refused
   - Expired grants are refused
   - ODRL Policy evaluation (Permissions, Prohibitions, Constraints, Duties)
   - Prohibitions override permissions
3. Confused Deputy Prevention Guard (§54):
   - Ambient authority actuation by peers is refused
   - Unauthenticated delegation is refused
   - Broken delegation chain is refused
   - Authorized delegation chain passes inspection
"""

import time
import pytest

from autofde_lab.sa2a.authority import (
    Asset,
    AuthorityBroker,
    AuthorityDecision,
    AuthorityGrant,
    ConsequenceRequest,
    ConfusedDeputyGuard,
    Constraint,
    DelegationHop,
    Duty,
    InvocationContext,
    OdrlAction,
    OdrlOperator,
    Party,
    Permission,
    Policy,
    Prohibition,
    REFUSED_AGENT_IS_NOT_AUTHORITY,
    REFUSED_CAPABILITY_IS_NOT_AUTHORITY,
    REFUSED_CONFUSED_DEPUTY,
    REFUSED_CONSTRAINT_VIOLATION,
    REFUSED_EXPIRED_GRANT,
    REFUSED_NO_GRANT,
    REFUSED_PLAN_IS_NOT_AUTHORITY,
    REFUSED_PROHIBITED,
    REFUSED_PROOF_IS_NOT_AUTHORITY,
    REFUSED_UNAUTHORIZED_DELEGATION,
    REFUSED_UNFULFILLED_DUTY,
)


# ==============================================================================
# Authority Non-Implications Tests (§29)
# ==============================================================================

def test_agent_is_not_authority():
    """Agent != Authority: Possessing an agent identity or asserting ambient authority is refused."""
    broker = AuthorityBroker()
    req = ConsequenceRequest(
        actor_id="agent-alice",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:resource:database:drop",
        ambient_authority_assumed=True,
    )
    decision = broker.evaluate(req)
    assert not decision.authorized
    assert decision.grant_id is None
    assert decision.refusal_code in (REFUSED_AGENT_IS_NOT_AUTHORITY, REFUSED_CONFUSED_DEPUTY)


def test_capability_is_not_authority():
    """Capability != Authority: Possessing tools/capabilities does not imply authority to actuate."""
    broker = AuthorityBroker()
    req = ConsequenceRequest(
        actor_id="agent-bob",
        action_iri=OdrlAction.MODIFY.value,
        target_resource="urn:resource:config:production",
        asserted_capabilities=["can_execute_bash", "has_database_admin_tool"],
    )
    decision = broker.evaluate(req)
    assert not decision.authorized
    assert decision.grant_id is None
    assert decision.refusal_code == REFUSED_CAPABILITY_IS_NOT_AUTHORITY
    assert "Capability does not imply execution authority" in decision.reason


def test_plan_is_not_authority():
    """Plan != Authority: Possessing an admitted or optimal plan does not imply authority to execute."""
    broker = AuthorityBroker()
    req = ConsequenceRequest(
        actor_id="agent-carol",
        action_iri=OdrlAction.TRANSFER.value,
        target_resource="urn:resource:account:funds",
        asserted_plan={"steps": ["step1", "step2"], "score": 0.99, "admitted": True},
    )
    decision = broker.evaluate(req)
    assert not decision.authorized
    assert decision.grant_id is None
    assert decision.refusal_code == REFUSED_PLAN_IS_NOT_AUTHORITY
    assert "Plan does not imply execution authority" in decision.reason


def test_proof_is_not_authority():
    """Proof != Authority: Possessing a verification proof or receipt does not imply execution authority."""
    broker = AuthorityBroker()
    req = ConsequenceRequest(
        actor_id="agent-dave",
        action_iri=OdrlAction.DELETE.value,
        target_resource="urn:resource:cluster:node-1",
        asserted_proof={"formal_check": "VALID", "signature": "0xdeadbeef", "receipt": "rcpt-123"},
    )
    decision = broker.evaluate(req)
    assert not decision.authorized
    assert decision.grant_id is None
    assert decision.refusal_code == REFUSED_PROOF_IS_NOT_AUTHORITY
    assert "Proof does not imply execution authority" in decision.reason


# ==============================================================================
# Grant Evaluation & ODRL Mapping Tests (§28)
# ==============================================================================

def test_explicit_grant_authorization_success():
    """Valid explicit authority grant authorizes consequence execution."""
    grant = AuthorityGrant(
        grant_id="grant-001",
        subject_id="agent-evaluator",
        action_iri=OdrlAction.READ.value,
        target_resource_iri="urn:resource:telemetry",
        constraints={"environment": "production"},
    )
    broker = AuthorityBroker(grants=[grant])

    req = ConsequenceRequest(
        actor_id="agent-evaluator",
        action_iri=OdrlAction.READ.value,
        target_resource="urn:resource:telemetry",
        grant_id="grant-001",
        context={"environment": "production"},
    )
    decision = broker.evaluate(req)
    assert decision.authorized
    assert decision.grant_id == "grant-001"
    assert decision.refusal_code is None
    assert decision.constraints == {"environment": "production"}


def test_explicit_grant_refusals():
    """Test grant mismatch, constraint violation, expiry, and unfulfilled duties."""
    now = time.time()
    grant = AuthorityGrant(
        grant_id="grant-restricted",
        subject_id="agent-alice",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource_iri="urn:service:deploy",
        constraints={"region": "us-west-2"},
        duties=["urn:duty:audit-log"],
        valid_until=now + 100,
    )
    broker = AuthorityBroker(grants=[grant])

    # 1. Wrong actor
    req_wrong_actor = ConsequenceRequest(
        actor_id="agent-mallory",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:service:deploy",
        grant_id="grant-restricted",
        context={"region": "us-west-2", "fulfilled_duties": ["urn:duty:audit-log"]},
    )
    d1 = broker.evaluate(req_wrong_actor)
    assert not d1.authorized
    assert d1.refusal_code == REFUSED_NO_GRANT

    # 2. Constraint violation
    req_constraint_violation = ConsequenceRequest(
        actor_id="agent-alice",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:service:deploy",
        grant_id="grant-restricted",
        context={"region": "eu-central-1", "fulfilled_duties": ["urn:duty:audit-log"]},
    )
    d2 = broker.evaluate(req_constraint_violation)
    assert not d2.authorized
    assert d2.refusal_code == REFUSED_CONSTRAINT_VIOLATION

    # 3. Unfulfilled duty
    req_unfulfilled_duty = ConsequenceRequest(
        actor_id="agent-alice",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:service:deploy",
        grant_id="grant-restricted",
        context={"region": "us-west-2", "fulfilled_duties": []},
    )
    d3 = broker.evaluate(req_unfulfilled_duty)
    assert not d3.authorized
    assert d3.refusal_code == REFUSED_UNFULFILLED_DUTY

    # 4. Expired grant
    expired_grant = AuthorityGrant(
        grant_id="grant-expired",
        subject_id="agent-alice",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource_iri="urn:service:deploy",
        valid_until=now - 10,
    )
    broker.register_grant(expired_grant)
    req_expired = ConsequenceRequest(
        actor_id="agent-alice",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:service:deploy",
        grant_id="grant-expired",
    )
    d4 = broker.evaluate(req_expired)
    assert not d4.authorized
    assert d4.refusal_code == REFUSED_EXPIRED_GRANT


def test_odrl_policy_permission_and_prohibition():
    """Verify ODRL Policy Permission, Constraint, and Prohibition override."""
    # Create permission policy: agent-worker can execute jobs if load < 80
    perm = Permission(
        uid="perm-1",
        action=OdrlAction.EXECUTE,
        target=Asset(uid="urn:job:compute"),
        assignee=Party(uid="agent-worker"),
        constraints=[Constraint(left_operand="load", operator=OdrlOperator.LT, right_operand=80)],
    )
    policy = Policy(uid="policy-compute", permissions=[perm])
    broker = AuthorityBroker(policies=[policy])

    # Allowed when constraint holds
    req_allowed = ConsequenceRequest(
        actor_id="agent-worker",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:job:compute",
        context={"load": 50},
    )
    d1 = broker.evaluate(req_allowed)
    assert d1.authorized
    assert d1.grant_id == "policy-grant-policy-compute-perm-1"

    # Denied when constraint fails
    req_overloaded = ConsequenceRequest(
        actor_id="agent-worker",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:job:compute",
        context={"load": 90},
    )
    d2 = broker.evaluate(req_overloaded)
    assert not d2.authorized
    assert d2.refusal_code == REFUSED_NO_GRANT

    # Add Prohibition: Prohibitions override permissions
    prohib = Prohibition(
        uid="prohib-maintenance",
        action=OdrlAction.EXECUTE,
        target=Asset(uid="urn:job:compute"),
        assignee=Party(uid="agent-worker"),
        constraints=[Constraint(left_operand="maintenance_window", operator=OdrlOperator.EQ, right_operand=True)],
    )
    policy_with_prohib = Policy(uid="policy-compute-2", permissions=[perm], prohibitions=[prohib])
    broker_with_prohib = AuthorityBroker(policies=[policy_with_prohib])

    req_maintenance = ConsequenceRequest(
        actor_id="agent-worker",
        action_iri=OdrlAction.EXECUTE.value,
        target_resource="urn:job:compute",
        context={"load": 50, "maintenance_window": True},
    )
    d3 = broker_with_prohib.evaluate(req_maintenance)
    assert not d3.authorized
    assert d3.refusal_code == REFUSED_PROHIBITED


# ==============================================================================
# Confused Deputy Prevention Guard Tests (§54)
# ==============================================================================

def test_confused_deputy_ambient_authority_refusal():
    """Confused Deputy Guard refuses ambient authority usage when requested by another peer."""
    guard = ConfusedDeputyGuard()
    ctx = InvocationContext(
        actor_id="deputy-agent",
        initiator_id="initiator-agent",
        ambient_authority_asserted=True,
    )
    res = guard.inspect_invocation(ctx, action="delete", target_resource="database")
    assert not res.allowed
    assert res.refusal_code == REFUSED_CONFUSED_DEPUTY
    assert "using ambient authority" in res.reason


def test_confused_deputy_unauthorized_delegation():
    """Confused Deputy Guard refuses delegated invocation without explicit grant."""
    guard = ConfusedDeputyGuard()
    ctx = InvocationContext(
        actor_id="deputy-agent",
        initiator_id="untrusted-peer",
        grant_id=None,  # No explicit delegation grant
    )
    res = guard.inspect_invocation(ctx, action="transfer", target_resource="account")
    assert not res.allowed
    assert res.refusal_code == REFUSED_CONFUSED_DEPUTY
    assert "lacks explicit grant_id" in res.reason


def test_confused_deputy_broken_delegation_chain():
    """Confused Deputy Guard validates continuity of the delegation chain."""
    guard = ConfusedDeputyGuard()

    # Broken chain: first hop does not match initiator
    hop1 = DelegationHop(caller_id="intruder", target_agent_id="deputy-agent", delegated_grant_id="grant-1")
    ctx_broken = InvocationContext(
        actor_id="deputy-agent",
        initiator_id="client-alice",
        grant_id="grant-1",
        delegation_chain=[hop1],
    )
    res_broken = guard.inspect_invocation(ctx_broken, action="read", target_resource="secrets")
    assert not res_broken.allowed
    assert res_broken.refusal_code == REFUSED_CONFUSED_DEPUTY
    assert "does not match initiator" in res_broken.reason


def test_confused_deputy_valid_delegation():
    """Confused Deputy Guard allows valid delegation with explicit authorized grant and chain."""
    guard = ConfusedDeputyGuard(authorized_delegations={"grant-del-42": ["client-alice", "deputy-agent"]})
    hop = DelegationHop(caller_id="client-alice", target_agent_id="deputy-agent", delegated_grant_id="grant-del-42")
    ctx_valid = InvocationContext(
        actor_id="deputy-agent",
        initiator_id="client-alice",
        grant_id="grant-del-42",
        delegation_chain=[hop],
    )
    res = guard.inspect_invocation(ctx_valid, action="read", target_resource="data")
    assert res.allowed
    assert res.refusal_code is None


def test_broker_integration_with_confused_deputy_guard():
    """AuthorityBroker integrates Confused Deputy Guard and halts evaluation on deputy failure."""
    grant = AuthorityGrant(
        grant_id="grant-admin",
        subject_id="deputy-agent",
        action_iri=OdrlAction.DELETE.value,
        target_resource_iri="urn:db:records",
    )
    broker = AuthorityBroker(grants=[grant])

    # Untrusted client asks deputy to delete records without a valid delegation grant
    req = ConsequenceRequest(
        actor_id="deputy-agent",
        action_iri=OdrlAction.DELETE.value,
        target_resource="urn:db:records",
        grant_id="grant-admin",
        invocation_context=InvocationContext(
            actor_id="deputy-agent",
            initiator_id="untrusted-client",
            grant_id=None,  # No grant provided by initiator
        ),
    )
    decision = broker.evaluate(req)
    assert not decision.authorized
    assert decision.refusal_code == REFUSED_CONFUSED_DEPUTY
