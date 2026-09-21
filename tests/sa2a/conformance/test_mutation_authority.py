# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Mutation tests for Authority Broker Conformance Court (RFC-SA2A-002 v26.9.16).

Per .claude/rules/level4-completion-law.md "Mutation law":

    For every required relation R, construct an otherwise-complete episode,
    mutate exactly R's identity, and require admission to produce a typed
    non-ALIVE evidence object.

Each test here:

  1. Constructs an otherwise-complete, currently-valid admission episode against
     the REAL ``AuthorityBroker`` (registers a real ``AuthorityGrant``, evaluates a
     real ``ConsequenceRequest`` that the broker actually authorizes) — a positive
     control proving the episode was valid *before* mutation.
  2. Mutates EXACTLY ONE identity/field in that episode — a referenced object
     identity swapped for a different, well-formed one (grant_id or
     target_resource), never a shape/type change.
  3. Re-evaluates the mutated request against the same real broker and asserts a
     typed, non-authorized refusal — never a silent pass, never a broad
     ``except`` swallowing the distinction.

Chicago Zero-Mock Standard:
  - Real ``AuthorityBroker`` / ``AuthorityGrant`` / ``ConsequenceRequest`` instances.
  - No ``unittest.mock``, ``Mock``, ``MagicMock``, ``patch``, or ``monkeypatch``.
  - Assertions are on real, observed ``AuthorityDecision`` state (``authorized``,
    ``refusal_code``), never on "was a method called".

Both mutations below probe grant-identity binding paths in
``AuthorityBroker.evaluate`` (src/autofde_lab/sa2a/authority/broker.py) that are
NOT exercised by the existing tests in ``test_court_authority.py``:

  - ``test_confused_deputy_impersonation_refused`` / ``test_token_rebinding_refused``
    both mutate ``actor_id`` while holding ``grant_id``/``target_resource`` fixed.
  - Neither existing test mutates ``target_resource`` while holding actor+grant_id
    fixed (scope binding, broker.py:226), nor mutates ``grant_id`` itself to a
    wrong-but-well-formed, unregistered identity while holding
    actor/action/resource fixed (reference binding, broker.py:197-205).

This file adds exactly those two identity mutations.
"""

from __future__ import annotations

from autofde_lab.sa2a.authority.broker import (
    REFUSED_NO_GRANT,
    AuthorityBroker,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.conformance.courts.authority_court import (
    AuthorityCourt,
    AuthorityVerdict,
)

# ---------------------------------------------------------------------------
# Mutation 1: target_resource identity swap, actor_id + grant_id unchanged
# ---------------------------------------------------------------------------


def test_grant_scoped_to_one_resource_rejects_mutated_resource_identity() -> None:
    """A grant scoped to resource R1 MUST NOT authorize actuation against R2.

    Otherwise-complete episode: a real grant is registered for
    (actor=urn:agent:resource-bound, action=urn:action:system:restart,
    resource=urn:resource:host:node-1). The court's own
    ``verify_legitimate_grant_authorized`` positive control confirms this exact
    episode IS currently-valid (CONFORMANT, decision.authorized is True) before
    any mutation is applied.

    Mutation: exactly one field — ``target_resource`` — is swapped for a
    different, well-formed resource IRI (``urn:resource:host:node-2``).
    ``actor_id``, ``action_iri``, and ``grant_id`` are held fixed, so this is not
    a confused-deputy (actor-identity) mutation and not a bare-request
    (no-grant) mutation — it isolates resource-scope binding specifically.

    The real ``AuthorityBroker.evaluate`` — the actual admission function every
    ``AuthorityCourt.verify_*`` method wraps — MUST reject the mutated request
    with a typed refusal (``REFUSED_NO_GRANT``, broker.py:226-232: the grant's
    ``target_resource_iri`` no longer matches ``request.target_resource``), never
    silently authorize it because the actor and grant_id still match.
    """
    grant = AuthorityGrant(
        grant_id="grant-resource-mutation-001",
        subject_id="urn:agent:resource-bound",
        action_iri="urn:action:system:restart",
        target_resource_iri="urn:resource:host:node-1",
    )

    # --- Step 1: otherwise-complete, currently-valid episode (positive control) ---
    court = AuthorityCourt()
    baseline_broker = AuthorityBroker()
    baseline_result = court.verify_legitimate_grant_authorized(
        baseline_broker, grant, fail_closed=True
    )
    assert baseline_result.passed is True
    assert baseline_result.verdict == AuthorityVerdict.CONFORMANT
    assert baseline_result.decision is not None
    assert baseline_result.decision.authorized is True, (
        "Baseline episode must be currently-valid (real broker authorizes it) "
        "before the mutation is applied."
    )

    # --- Step 2: mutate EXACTLY ONE identity — target_resource — on a fresh broker
    #     carrying the same registered grant, so the mutation is isolated from the
    #     baseline's own broker state.
    mutation_broker = AuthorityBroker()
    mutation_broker.register_grant(grant)

    mutated_request = ConsequenceRequest(
        actor_id=grant.subject_id,  # unchanged
        action_iri=grant.action_iri,  # unchanged
        target_resource="urn:resource:host:node-2",  # MUTATED: wrong-but-well-formed resource IRI
        grant_id=grant.grant_id,  # unchanged
    )
    mutated_decision = mutation_broker.evaluate(mutated_request)

    # --- Step 3: the real admission function must reject the mutated identity ---
    assert mutated_decision.authorized is False, (
        "SA2A-AUTH-GRANT-SCOPE VIOLATION: grant "
        f"{grant.grant_id!r} scoped to resource {grant.target_resource_iri!r} "
        f"authorized actuation against a different resource "
        f"{mutated_request.target_resource!r} using the same actor_id and grant_id."
    )
    assert mutated_decision.refusal_code == REFUSED_NO_GRANT, (
        "Expected a typed REFUSED_NO_GRANT refusal for resource-scope mismatch, "
        f"got {mutated_decision.refusal_code!r} instead — refusal must be typed, "
        "not a silent pass or an unclassified rejection."
    )


# ---------------------------------------------------------------------------
# Mutation 2: grant_id reference swap, actor_id/action_iri/target_resource unchanged
# ---------------------------------------------------------------------------


def test_grant_id_reference_mutation_to_unregistered_id_rejected() -> None:
    """A request referencing a wrong-but-well-formed, unregistered grant_id MUST be refused.

    Otherwise-complete episode: a real grant ``grant-legit-ref-001`` is registered
    for (actor=urn:agent:ref-bound, action=urn:action:deploy:service,
    resource=urn:resource:cluster:staging). The court's own
    ``verify_legitimate_grant_authorized`` positive control confirms this exact
    episode IS currently-valid before any mutation.

    Mutation: exactly one field — ``grant_id`` — is swapped for a different,
    well-formed-but-never-registered grant identifier
    (``grant-legit-ref-001-FORGED``). ``actor_id``, ``action_iri``, and
    ``target_resource`` are held fixed to the values that WOULD be valid under
    the real registered grant — this isolates the grant-*reference* identity
    itself as the mutated object, distinct from the existing
    ``test_grant_required_bare_request_refused`` test (which supplies no
    grant_id at all, a different code path at broker.py:304-309) and distinct
    from confused-deputy/token-rebinding (which mutate actor_id, not grant_id).

    The real ``AuthorityBroker.evaluate`` MUST reject the forged reference with
    a typed refusal (``REFUSED_NO_GRANT``, broker.py:197-205: grant id not found
    in the authority registry), never authorize it on the strength of a
    matching actor/action/resource triple alone.
    """
    grant = AuthorityGrant(
        grant_id="grant-legit-ref-001",
        subject_id="urn:agent:ref-bound",
        action_iri="urn:action:deploy:service",
        target_resource_iri="urn:resource:cluster:staging",
    )

    # --- Step 1: otherwise-complete, currently-valid episode (positive control) ---
    court = AuthorityCourt()
    baseline_broker = AuthorityBroker()
    baseline_result = court.verify_legitimate_grant_authorized(
        baseline_broker, grant, fail_closed=True
    )
    assert baseline_result.passed is True
    assert baseline_result.verdict == AuthorityVerdict.CONFORMANT
    assert baseline_result.decision is not None
    assert baseline_result.decision.authorized is True, (
        "Baseline episode must be currently-valid (real broker authorizes it) "
        "before the mutation is applied."
    )

    # --- Step 2: mutate EXACTLY ONE identity — grant_id — on a fresh broker
    #     carrying the same registered (unmutated) grant.
    mutation_broker = AuthorityBroker()
    mutation_broker.register_grant(grant)

    forged_grant_id = grant.grant_id + "-FORGED"
    assert forged_grant_id not in mutation_broker._grants, (
        "Test setup invariant violated: the forged grant_id must be genuinely "
        "unregistered, otherwise this is not a reference-identity mutation."
    )

    mutated_request = ConsequenceRequest(
        actor_id=grant.subject_id,  # unchanged — would be valid under the real grant
        action_iri=grant.action_iri,  # unchanged — would be valid under the real grant
        target_resource=grant.target_resource_iri,  # unchanged — would be valid under the real grant
        grant_id=forged_grant_id,  # MUTATED: wrong-but-well-formed, unregistered grant reference
    )
    mutated_decision = mutation_broker.evaluate(mutated_request)

    # --- Step 3: the real admission function must reject the mutated identity ---
    assert mutated_decision.authorized is False, (
        "SA2A-AUTH-GRANT-REFERENCE VIOLATION: broker authorized a request "
        f"referencing forged grant_id {forged_grant_id!r} even though only "
        f"{grant.grant_id!r} is registered — actor/action/resource matching a "
        "real grant must not substitute for referencing that grant's own identity."
    )
    assert mutated_decision.refusal_code == REFUSED_NO_GRANT, (
        "Expected a typed REFUSED_NO_GRANT refusal for the unregistered grant_id "
        f"reference, got {mutated_decision.refusal_code!r} instead — refusal must "
        "be typed, not a silent pass or an unclassified rejection."
    )
