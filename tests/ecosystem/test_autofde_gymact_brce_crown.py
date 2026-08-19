"""Chicago crown: autonomous AutoFDE POWL -> GymAct BRCE -> real consequence."""

from __future__ import annotations

import pytest
from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.models import MaterializationIntent, Standing
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

from autofde_lab.gymact.brce_plan import AdmittedActuationSession

BASE = "urn:autofde-lab:test:brce-plan"
AUTHORITY = f"{BASE}:authority"
CHICAGO_SCOPE = f"{BASE}:scope:chicago"
SET_ACTION = f"{BASE}/set"
INCREMENT_ACTION = f"{BASE}/increment"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"


def _request(
    *,
    episode_id: str,
    action_ref: str,
    capability_ref: str,
    payload: dict[str, object],
    expected: dict[str, object],
    key: str,
    scope_refs: tuple[str, ...] = (CHICAGO_SCOPE,),
) -> BrokerRequest:
    effect = ExpectedEffect(predicate="state", parameters=expected)
    action = ActionDefinition(
        semantic_id=action_ref,
        provider_ref="urn:gymact:provider:memory",
        capability_ref=capability_ref,
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:gymact:observer:memory",
            expected=expected,
        ),
    )
    subject = SubjectRef(
        semantic_id=f"urn:gymact:episode:{episode_id}",
        provider_ref="memory",
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode_id,
        subject=subject,
        payload=payload,
        admission_digest=f"admitted:{key}",
        idempotency_key=key,
    )
    grant = ExecutionGrant(
        principal="urn:autofde-lab:test:principal",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=capability_ref,
        authority_ref=AUTHORITY,
        policy_revision="autofde-test-policy-v1",
        admitted_observation_ref=f"urn:autofde-lab:test:observation:{key}",
        intended_effects=action.expected_effects,
        scope_refs=scope_refs,
        nonce=f"nonce:{key}",
    )
    return BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        expected=expected,
    )


async def _runtime_and_episode() -> tuple[ProductionGymAct, str]:
    runtime = ProductionGymAct(
        validate_profile=False,
        authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"requires_authority": True},
            idempotency_key="autofde-brce-materialize",
        )
    )
    assert materialized.episode is not None
    return runtime, materialized.episode.episode_id


def _authorized_bundle(episode_id: str) -> dict[str, BrokerRequest]:
    return {
        SET_ACTION: _request(
            episode_id=episode_id,
            action_ref=SET_ACTION,
            capability_ref=SET_CAPABILITY,
            payload={"key": "counter", "value": 10},
            expected={"counter": 10},
            key="autofde-brce-set",
        ),
        INCREMENT_ACTION: _request(
            episode_id=episode_id,
            action_ref=INCREMENT_ACTION,
            capability_ref=INCREMENT_CAPABILITY,
            payload={"key": "counter", "amount": 5},
            expected={"counter": 15},
            key="autofde-brce-increment",
        ),
    }


@pytest.mark.asyncio
async def test_chicago_session_autonomously_actuates_complete_plan_only_via_brce() -> None:
    runtime, episode_id = await _runtime_and_episode()
    session = AdmittedActuationSession(
        broker=BRCEBroker(runtime),
        request_binding=_authorized_bundle(episode_id),
        scope_ref=CHICAGO_SCOPE,
    )

    execution = session.run(
        ["(set counter ten)", "(increment counter five)"],
        base_iri=BASE,
    )

    assert execution.alive is True
    assert [transition.standing for transition in execution.transitions] == [
        Standing.ALIVE,
        Standing.ALIVE,
    ]
    assert all(
        transition.receipt.principal == "urn:autofde-lab:test:principal"
        for transition in execution.transitions
    )
    assert all(
        CHICAGO_SCOPE in request.grant.scope_refs
        for request in session.request_binding.values()
    )
    assert not hasattr(session, "act")
    assert (
        "mfwp:implementsAction <urn:autofde-lab:test:brce-plan/set>"
        in execution.powl_turtle
    )
    assert (
        "mfwp:implementsAction <urn:autofde-lab:test:brce-plan/increment>"
        in execution.powl_turtle
    )
    assert len(execution.ocel_log.events) == 2
    assert (await runtime.observe(episode_id)).state == {"counter": 15}
    assert runtime.verify_evidence_chain()


@pytest.mark.asyncio
async def test_chicago_preflight_refuses_identity_drift_before_first_do() -> None:
    runtime, episode_id = await _runtime_and_episode()
    bundle = _authorized_bundle(episode_id)
    bundle[INCREMENT_ACTION] = _request(
        episode_id=episode_id,
        action_ref=f"{BASE}/wrong-increment",
        capability_ref=INCREMENT_CAPABILITY,
        payload={"key": "counter", "amount": 5},
        expected={"counter": 15},
        key="autofde-brce-wrong-increment",
    )
    session = AdmittedActuationSession(
        broker=BRCEBroker(runtime),
        request_binding=bundle,
        scope_ref=CHICAGO_SCOPE,
    )

    with pytest.raises(ValueError, match="REFUSED:BROKER_REQUEST_ACTION_IDENTITY_DRIFT"):
        session.run(
            ["(set counter ten)", "(increment counter five)"],
            base_iri=BASE,
        )

    assert (await runtime.observe(episode_id)).state == {}


@pytest.mark.asyncio
async def test_chicago_preflight_refuses_out_of_scope_bundle_before_first_do() -> None:
    runtime, episode_id = await _runtime_and_episode()
    bundle = _authorized_bundle(episode_id)
    bundle[INCREMENT_ACTION] = _request(
        episode_id=episode_id,
        action_ref=INCREMENT_ACTION,
        capability_ref=INCREMENT_CAPABILITY,
        payload={"key": "counter", "amount": 5},
        expected={"counter": 15},
        key="autofde-brce-out-of-scope",
        scope_refs=(f"{BASE}:scope:not-chicago",),
    )
    session = AdmittedActuationSession(
        broker=BRCEBroker(runtime),
        request_binding=bundle,
        scope_ref=CHICAGO_SCOPE,
    )

    with pytest.raises(PermissionError, match="REFUSED:ACTUATION_SCOPE_MISMATCH"):
        session.run(
            ["(set counter ten)", "(increment counter five)"],
            base_iri=BASE,
        )

    assert (await runtime.observe(episode_id)).state == {}
