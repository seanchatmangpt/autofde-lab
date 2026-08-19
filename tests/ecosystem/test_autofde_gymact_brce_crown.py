"""Cross-repo crown: AutoFDE POWL -> GymAct BRCE -> verified world consequence."""

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

from autofde_lab.gymact.brce_plan import execute_plan_lines_via_gymact_brce

BASE = "urn:autofde-lab:test:brce-plan"
AUTHORITY = f"{BASE}:authority"
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
        nonce=f"nonce:{key}",
    )
    return BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        expected=expected,
    )


@pytest.mark.asyncio
async def test_candidate_plan_executes_only_via_gymact_brce_and_returns_verified_alive() -> (
    None
):
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
    episode_id = materialized.episode.episode_id

    execution = execute_plan_lines_via_gymact_brce(
        ["(set counter ten)", "(increment counter five)"],
        base_iri=BASE,
        broker=BRCEBroker(runtime),
        request_binding={
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
        },
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
