# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fresh adversarial falsifiers against `_admission_covers_action_target()`
(`src/autofde_lab/sa2a/brce/boundary.py`), written under the "identity-binding bypass"
lens per `.claude/rules/level4-completion-law.md`'s Mutation law: construct an
otherwise-complete, currently-valid episode and mutate exactly the identity binding the
AFDE-2604 fresh-mutations closure ("Mutation A") added, expecting refusal.

These are DELIBERATELY DIFFERENT mutations from the ones already exercised by
`test_afde_2604_fresh_mutations_qualification.py`'s own "Mutation A"
(`test_mutation_a_admission_content_not_bound_to_actuated_action_target`), which reuses
a `Standing.ADMITTED` admission for a candidate that mentions NEITHER the action NOR
the target at all. Both mutations below instead construct an admitted candidate that
DOES mention both the action_iri and target_resource -- so `_admission_covers_action_target`
returns True -- but never actually asserts that THIS action applies to THIS target. This
targets the precise implementation of the fix, read directly from
`src/autofde_lab/sa2a/brce/boundary.py`:

    nodes = graph.all_nodes()
    return URIRef(action_iri) in nodes and URIRef(target_resource) in nodes

This is a co-occurrence/presence check over the UNION of all subjects+objects in the
admitted graph -- it is not a check that any single triple (or transitive relation)
actually asserts a binding between the two. Per
`.claude/rules/no-dual-bookkeeping.md`'s "Identity is explicit or it does not exist":
"Never derive [a relation] by: ... token overlap ... matching labels ... matching
counts." Node co-occurrence in a shared graph is exactly token overlap, not an explicit
typed edge asserting `action_iri` applies to `target_resource`.

  MUTATION D1 -- unrelated co-mention: a single admitted candidate names the sensitive
    action_iri and target_resource in two SEPARATE, semantically unrelated triples
    (`<action> a afl:Action .` and `<target> a afl:Resource .`) with no predicate ever
    relating the two. `_admission_covers_action_target` returns True anyway, because
    both URIRefs sit in `graph.all_nodes()` regardless of which triple put them there.

  MUTATION D2 -- cross-pair substitution: a single admitted candidate legitimately
    links action1->target1 and action2->target2 via an explicit `afl:targetResource`
    predicate (a real, connected binding for each pair on its own). The adversary then
    executes with the CROSS combination action1+target2 -- a pairing the admitted graph
    never asserted anywhere. `_admission_covers_action_target` returns True anyway,
    because it only checks that both URIRefs are SOMEWHERE in the graph's node set, not
    that they are related to each other by any triple.

Both isolate the admission-content-binding gate specifically (not conflating it with
`AuthorityBroker`): a real, independently valid `AuthorityGrant` is registered for the
actuated action/target combination in each test, exactly as
`test_mutation_a_admission_content_not_bound_to_actuated_action_target` does -- so a
refusal, if it happens, can only be attributed to the admission-content-binding gate
itself, never to a missing authority grant.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant` / real `AdmissionPipeline.admit()` (default,
  unconfigured pipeline -- no SHACL/ShEx validators or SPARQL falsifiers are wired in by
  default anywhere in this repo's production code path either, so this is the real
  as-shipped admission surface, not an artificially weakened one).
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (genuine physical
  disk I/O) and a real `DurableDiskReceiptStore` -- the same real collaborators the
  fixing session's own tests use.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
  file.

Each test asserts the SECURE/expected outcome (refusal). A PASS means the fix defeats
this construction. A FAIL is the real, verified gap -- the assertion failure message
and the real disk/receipt state are the falsifying evidence; this file does not weaken
the assertion to make the test green, and the fix itself is NOT patched here (per this
session's explicit scope: report, do not repair).
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_ADMISSION_CONTENT_NOT_BOUND,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)


def _boundary(tmp_path: Path, name: str, broker: AuthorityBroker):
    journal = tmp_path / name / "journal.json"
    store = DurableDiskReceiptStore(tmp_path / name / "receipts")
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    boundary = ConsequenceBoundary(
        authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store
    )
    return boundary, actuator, store, journal


# ---------------------------------------------------------------------------
# Mutation D1: unrelated co-mention -- action and target each named in the admitted
# graph, but in two separate triples that never relate them to each other.
# ---------------------------------------------------------------------------

_UNRELATED_COMENTION_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:fresh-mut-d1:delete-all-records> a afl:Action .
<urn:resource:fresh-mut-d1:critical-database> a afl:Resource .
"""


def test_mutation_d1_unrelated_comention_satisfies_content_binding(tmp_path: Path) -> None:
    """A real ADMITTED AdmissionResult whose graph mentions the sensitive action_iri and
    target_resource in two UNRELATED triples (no predicate ever connects them) must not
    satisfy `_admission_covers_action_target` -- the admitted content never actually
    asserts that this action applies to this target, only that both identifiers happen
    to appear somewhere in the same graph.

    lens: identity-binding bypass -- `_admission_covers_action_target` checks
    `URIRef(action_iri) in graph.all_nodes()` and `URIRef(target_resource) in
    graph.all_nodes()` independently; it never checks that any triple relates the two.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _UNRELATED_COMENTION_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-mut-d1-actor"
    action = "urn:action:fresh-mut-d1:delete-all-records"
    target = "urn:resource:fresh-mut-d1:critical-database"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-d1",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_d1", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-mut-d1",
        action_iri=action,
        target_resource=target,
        actor_id=actor,
        # MUTATION: an admission whose graph mentions BOTH the action and target
        # identifiers, but never in a triple relating one to the other.
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    assert result.success is False, (
        "MUTATION D1 SURVIVED: execute_admitted() treated an admitted candidate that "
        f"merely CO-MENTIONS action_iri={action!r} and target_resource={target!r} in "
        "two semantically unrelated triples (no predicate connects them) as a valid "
        "content binding for this exact action/target pair. "
        "`_admission_covers_action_target()` checks only "
        "`URIRef(action_iri) in graph.all_nodes() and URIRef(target_resource) in "
        "graph.all_nodes()` -- node co-occurrence in the shared admitted graph, not any "
        "triple asserting a relation between the two (the exact 'token overlap is not "
        "a relation' failure named in .claude/rules/no-dual-bookkeeping.md). "
        f"actuator.call_count={actuator.call_count}, journal_exists={journal.exists()}, "
        f"final_receipt_state={result.final_receipt.state if result.final_receipt else None!r}."
    )
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert actuator.call_count == 0, "Zero real actuation for an unrelated-co-mention admission."
    assert journal.exists() is False, "Zero disk mutation for an unrelated-co-mention admission."


# ---------------------------------------------------------------------------
# Mutation D2: cross-pair substitution -- two legitimately, individually bound
# action/target pairs coexist in one admitted graph; the adversary executes the CROSS
# combination that was never itself asserted.
# ---------------------------------------------------------------------------

_CROSS_PAIR_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:fresh-mut-d2:read-report> afl:targetResource <urn:resource:fresh-mut-d2:report> .
<urn:action:fresh-mut-d2:wire-transfer> afl:targetResource <urn:resource:fresh-mut-d2:treasury> .
"""


def test_mutation_d2_cross_pair_substitution_satisfies_content_binding(tmp_path: Path) -> None:
    """A single admitted candidate legitimately, explicitly binds action1->target1 AND
    action2->target2 (each via its own real `afl:targetResource` triple). Executing the
    CROSS combination action1+target2 -- a pairing the admitted graph never asserts
    anywhere -- must not satisfy `_admission_covers_action_target` merely because both
    identifiers individually appear in the graph (each bound to its OWN, different
    partner).

    lens: identity-binding bypass -- the same presence-only check as Mutation D1, shown
    here with a graph that DOES contain real triple-level bindings, just never the one
    being actuated.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _CROSS_PAIR_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-mut-d2-actor"
    action1 = "urn:action:fresh-mut-d2:read-report"
    target2 = "urn:resource:fresh-mut-d2:treasury"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-d2",
            subject_id=actor,
            action_iri=action1,
            target_resource_iri=target2,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_d2", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-mut-d2",
        action_iri=action1,
        target_resource=target2,
        actor_id=actor,
        # MUTATION: the admitted graph binds action1 to target1 and action2 to target2
        # individually -- never action1 to target2 -- but both action1 and target2 are
        # each, individually, real nodes in the same admitted graph.
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    assert result.success is False, (
        "MUTATION D2 SURVIVED: execute_admitted() allowed the CROSS-PAIR combination "
        f"action_iri={action1!r} (legitimately bound only to "
        "'urn:resource:fresh-mut-d2:report') with target_resource={target2!r} "
        "(legitimately bound only to 'urn:action:fresh-mut-d2:wire-transfer') -- a "
        "pairing the admitted graph never asserts in any triple -- merely because both "
        "identifiers individually sit in graph.all_nodes(). "
        "`_admission_covers_action_target()` verifies presence of each identifier "
        "independently, never that they are related to EACH OTHER, so it cannot "
        "distinguish 'the graph admits this exact pair' from 'the graph admits this "
        "identifier paired with something else entirely'. "
        f"actuator.call_count={actuator.call_count}, journal_exists={journal.exists()}, "
        f"final_receipt_state={result.final_receipt.state if result.final_receipt else None!r}."
    )
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert actuator.call_count == 0, "Zero real actuation for a cross-pair-substituted admission."
    assert journal.exists() is False, "Zero disk mutation for a cross-pair-substituted admission."
