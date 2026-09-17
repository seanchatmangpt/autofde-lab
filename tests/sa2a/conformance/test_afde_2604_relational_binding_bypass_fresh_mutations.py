# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fresh adversarial falsifiers against the AFDE-2604 architecture fix's REPLACEMENT
`_admission_covers_action_target()` (`src/autofde_lab/sa2a/brce/boundary.py`), written
under the "relational-binding bypass" lens per `.claude/rules/level4-completion-law.md`'s
Mutation law.

Scope, read directly from the REAL current source before writing this file (this
session): the fixed implementation is

    graph = admission.graph
    if graph is None:
        return False
    try:
        return (URIRef(action_iri), _AFL_TARGET_RESOURCE, URIRef(target_resource)) in graph
    except Exception:
        return False

i.e. exact RDF-triple membership: `<action_iri> afl:targetResource <target_resource>`
must be a real, directly-asserted statement in `admission.graph` (the graph that
actually reached `Standing.ADMITTED`). This supersedes the original
`graph.all_nodes()` co-occurrence check that Mutations D1/D2
(`test_afde_2604_identity_binding_bypass_qualification.py`) defeated.

This file targets a DIFFERENT, deliberately fresh angle: constructions where the
right PREDICATE is technically present in the graph, or a real relation exists, but
the exact required triple was never actually asserted -- testing whether the new,
stricter check can be fooled by something that LOOKS like a bound relation without
BEING one:

  MUTATION R1 -- blank-node intermediary (two-hop indirection): the admitted graph
    asserts `<action> afl:targetResource _:mid .` and `_:mid afl:targetResource
    <target> .` -- the SAME predicate used twice, chained through an intermediate
    blank node, so the predicate `afl:targetResource` really does connect action to
    target via a two-hop path. The exact single triple `<action> afl:targetResource
    <target>` is never asserted anywhere.

  MUTATION R2 -- reified (described, never asserted) relation: the admitted graph
    uses RDF reification to fully DESCRIBE the triple `<action> afl:targetResource
    <target>` (`rdf:subject`/`rdf:predicate`/`rdf:object` on a `rdf:Statement`
    blank node) without ever asserting that triple itself as a first-class
    statement. Every component the required relation needs is present in the
    graph's node/predicate vocabulary; the actual triple is not.

  MUTATION R3 -- owl:sameAs-bridged cross-pair: a single admitted candidate
    legitimately, explicitly binds action1->target1 via a real `afl:targetResource`
    triple, and separately asserts `target1 owl:sameAs target2` (a real, directly
    asserted equivalence triple -- not fabricated out of nothing). The adversary
    executes action1+target2: the graph never asserts `<action1> afl:targetResource
    <target2>` directly, but a semantically-aware admitter might consider target1
    and target2 "the same resource" via the owl:sameAs bridge. Combines the fresh
    angle ("a transitively-implied relation the check may accidentally accept")
    with the third example in this task ("two separate valid relations combined
    into a pairing the graph never actually asserted together") using genuinely new
    fixture content (different action/resource identifiers, different mechanism --
    owl:sameAs bridging, not two independent targetResource triples) from
    `test_afde_2604_identity_binding_bypass_qualification.py`'s Mutation D2.

Each isolates the admission-content-binding gate specifically: a real,
independently valid `AuthorityGrant` is registered for the actuated action/target
combination in every test, so a refusal (if it happens) can only be attributed to
the admission-content-binding gate itself, never to a missing authority grant.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant` / real `AdmissionPipeline.admit()`
  (default, unconfigured pipeline -- no SHACL/ShEx validators, Datalog/N3 engines,
  or SPARQL falsifiers are wired in by default anywhere in this repo's production
  code path either, so this is the real as-shipped admission surface).
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (genuine
  physical disk I/O) and a real `DurableDiskReceiptStore`.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
  this file.

Each test asserts the SECURE/expected outcome (refusal). A PASS means the fix
defeats this construction (DEFEATED). A FAIL is a real, verified gap (SURVIVED) --
the assertion failure message and the real disk/receipt state are the falsifying
evidence; this file does not weaken the assertion to make the test green, and no
gap found here is patched in this file (report, do not repair, per this task's
explicit scope).
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
# Mutation R1: blank-node intermediary -- the SAME predicate used twice, chaining
# action -> blank node -> target, never asserting the direct single-hop triple.
# ---------------------------------------------------------------------------

_BLANK_NODE_INDIRECTION_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:fresh-mut-r1:decommission-cluster> afl:targetResource _:mid .
_:mid afl:targetResource <urn:resource:fresh-mut-r1:prod-cluster> .
"""


def test_mutation_r1_blank_node_intermediary_satisfies_content_binding(tmp_path: Path) -> None:
    """A real ADMITTED AdmissionResult whose graph connects action_iri to
    target_resource ONLY via a two-hop chain through an intermediate blank node
    (`<action> afl:targetResource _:mid . _:mid afl:targetResource <target> .`) must
    not satisfy `_admission_covers_action_target` -- the exact required triple
    `<action> afl:targetResource <target>` is never itself asserted; the predicate
    merely appears twice, connecting three different nodes across two hops.

    lens: relational-binding bypass -- a technically-present-but-meaningless
    relation via blank-node indirection (the right predicate, wrong shape).
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _BLANK_NODE_INDIRECTION_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-mut-r1-actor"
    action = "urn:action:fresh-mut-r1:decommission-cluster"
    target = "urn:resource:fresh-mut-r1:prod-cluster"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-r1",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_r1", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-mut-r1",
        action_iri=action,
        target_resource=target,
        actor_id=actor,
        # MUTATION: action and target are connected only via a two-hop chain through
        # a blank node, reusing the same afl:targetResource predicate on each hop.
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    assert result.success is False, (
        "MUTATION R1 SURVIVED: execute_admitted() treated a two-hop blank-node-"
        f"mediated chain (<{action}> afl:targetResource _:mid . _:mid "
        f"afl:targetResource <{target}> .) as a valid direct content binding for "
        "this exact action/target pair, even though the single triple "
        f"<{action}> afl:targetResource <{target}> is never itself asserted. "
        "`_admission_covers_action_target()` is supposed to require the exact "
        "triple, not any path of the right predicate through intermediate nodes. "
        f"actuator.call_count={actuator.call_count}, journal_exists={journal.exists()}, "
        f"final_receipt_state={result.final_receipt.state if result.final_receipt else None!r}."
    )
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert actuator.call_count == 0, "Zero real actuation for a blank-node-indirected admission."
    assert journal.exists() is False, "Zero disk mutation for a blank-node-indirected admission."


# ---------------------------------------------------------------------------
# Mutation R2: RDF reification -- the triple is fully DESCRIBED via rdf:Statement
# reification (rdf:subject/rdf:predicate/rdf:object) but never itself ASSERTED.
# ---------------------------------------------------------------------------

_REIFIED_NEVER_ASSERTED_TTL = """
@prefix afl: <urn:autofde-lab:> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
_:stmt a rdf:Statement ;
    rdf:subject <urn:action:fresh-mut-r2:revoke-cert> ;
    rdf:predicate afl:targetResource ;
    rdf:object <urn:resource:fresh-mut-r2:root-ca> .
"""


def test_mutation_r2_reified_relation_satisfies_content_binding(tmp_path: Path) -> None:
    """A real ADMITTED AdmissionResult whose graph fully DESCRIBES the required
    triple via classic RDF reification (a blank `rdf:Statement` node carrying
    `rdf:subject`/`rdf:predicate`/`rdf:object` pointing at exactly action_iri,
    `afl:targetResource`, and target_resource) -- but never asserts the triple
    `<action> afl:targetResource <target>` itself as a first-class statement --
    must not satisfy `_admission_covers_action_target`. Reification is the
    classical RDF idiom for TALKING ABOUT a statement without ASSERTING it; every
    identifier and the predicate itself are present in the graph's vocabulary, and
    a implementation that queried "does this graph relate these two nodes via this
    predicate" with anything looser than exact triple membership (e.g. a SPARQL
    property-path or a reification-aware helper) could plausibly treat this as
    equivalent to a direct assertion.

    lens: relational-binding bypass -- a technically-present-but-meaningless
    relation (every component of the required triple is present, describing it
    rather than asserting it).
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _REIFIED_NEVER_ASSERTED_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-mut-r2-actor"
    action = "urn:action:fresh-mut-r2:revoke-cert"
    target = "urn:resource:fresh-mut-r2:root-ca"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-r2",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_r2", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-mut-r2",
        action_iri=action,
        target_resource=target,
        actor_id=actor,
        # MUTATION: the triple is fully described via RDF reification, never
        # asserted as a first-class statement in the admitted graph.
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    assert result.success is False, (
        "MUTATION R2 SURVIVED: execute_admitted() treated a REIFIED description of "
        f"the triple <{action}> afl:targetResource <{target}> (an rdf:Statement "
        "blank node carrying rdf:subject/rdf:predicate/rdf:object pointing at "
        "exactly this action/predicate/target) as equivalent to actually asserting "
        "that triple. `_admission_covers_action_target()` is supposed to require "
        "the real, first-class triple, not a description of what the triple would "
        "be. "
        f"actuator.call_count={actuator.call_count}, journal_exists={journal.exists()}, "
        f"final_receipt_state={result.final_receipt.state if result.final_receipt else None!r}."
    )
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert actuator.call_count == 0, "Zero real actuation for a reified-only admission."
    assert journal.exists() is False, "Zero disk mutation for a reified-only admission."


# ---------------------------------------------------------------------------
# Mutation R3: owl:sameAs-bridged cross-pair -- action1 legitimately, directly
# bound to target1 via a real afl:targetResource triple; target1 separately,
# legitimately asserted owl:sameAs target2. Adversary executes action1+target2.
# ---------------------------------------------------------------------------

_SAMEAS_BRIDGE_TTL = """
@prefix afl: <urn:autofde-lab:> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<urn:action:fresh-mut-r3:purge-backup> afl:targetResource <urn:resource:fresh-mut-r3:backup-vault-alias> .
<urn:resource:fresh-mut-r3:backup-vault-alias> owl:sameAs <urn:resource:fresh-mut-r3:backup-vault-real> .
"""


def test_mutation_r3_sameas_bridged_pair_satisfies_content_binding(tmp_path: Path) -> None:
    """A single admitted candidate legitimately, directly binds action1 to
    target_alias via a real `afl:targetResource` triple, and separately, also
    legitimately and directly, asserts `target_alias owl:sameAs target_real` (a
    real triple, not fabricated). The adversary executes action1+target_real: the
    graph never asserts `<action1> afl:targetResource <target_real>` directly --
    only via composing the real targetResource triple with the real owl:sameAs
    triple. `_admission_covers_action_target` performs a single, exact triple
    membership check with no OWL/RDFS entailment, so this composed (transitively
    implied) relation must not satisfy it.

    lens: relational-binding bypass -- combines "a transitively-implied relation
    the check may accidentally accept" with "two separate valid relations combined
    into a pairing the graph never actually asserted together", using a real
    owl:sameAs bridge rather than two independent targetResource pairs (a
    genuinely fresh mechanism versus
    `test_afde_2604_identity_binding_bypass_qualification.py`'s Mutation D2).
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _SAMEAS_BRIDGE_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-mut-r3-actor"
    action = "urn:action:fresh-mut-r3:purge-backup"
    target_real = "urn:resource:fresh-mut-r3:backup-vault-real"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-r3",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target_real,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_r3", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-mut-r3",
        action_iri=action,
        # MUTATION: executing against target_real, which is only reachable from
        # action via composing a real afl:targetResource triple with a real
        # owl:sameAs triple -- never asserted directly.
        target_resource=target_real,
        actor_id=actor,
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    assert result.success is False, (
        "MUTATION R3 SURVIVED: execute_admitted() treated an owl:sameAs-bridged "
        f"relation (<{action}> afl:targetResource <urn:resource:fresh-mut-r3:"
        f"backup-vault-alias> . <urn:resource:fresh-mut-r3:backup-vault-alias> "
        f"owl:sameAs <{target_real}> .) as equivalent to the direct triple "
        f"<{action}> afl:targetResource <{target_real}>, which is never itself "
        "asserted. `_admission_covers_action_target()` performs exact triple "
        "membership with no OWL/RDFS entailment; composing two real, individually "
        "valid triples must not satisfy it. "
        f"actuator.call_count={actuator.call_count}, journal_exists={journal.exists()}, "
        f"final_receipt_state={result.final_receipt.state if result.final_receipt else None!r}."
    )
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND
    assert actuator.call_count == 0, "Zero real actuation for a sameAs-bridged admission."
    assert journal.exists() is False, "Zero disk mutation for a sameAs-bridged admission."
