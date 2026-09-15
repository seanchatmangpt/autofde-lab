from __future__ import annotations

import json

import pytest

from autofde_lab.semantic_models.admission import SemanticAdmissionCourt
from autofde_lab.semantic_models.constrained import parse_candidate_json
from autofde_lab.semantic_models.contracts import (
    AdmissionStanding,
    CandidateGraphDelta,
    SemanticTriple,
)
from autofde_lab.semantic_models.dataset import example_from_admission
from autofde_lab.semantic_models.pipeline import SemanticModelPipeline

PREDICATE = "urn:test:knows"


def candidate(*, predicate: str = PREDICATE) -> CandidateGraphDelta:
    return CandidateGraphDelta(
        observation_id="urn:observation:1",
        triples=(
            SemanticTriple(
                subject="urn:person:sean",
                predicate=predicate,
                object="urn:concept:planning",
            ),
        ),
        source_iris=("urn:source:interview",),
        generator_id="test-producer",
        generator_revision="exact-head",
        confidence=0.9,
    )


def test_unknown_predicate_refuses_without_invoking_rdf_stack() -> None:
    court = SemanticAdmissionCourt(known_predicates={PREDICATE})
    decision = court.decide(candidate(predicate="urn:test:invented"))

    assert decision.receipt.standing is AdmissionStanding.REFUSED
    assert decision.canonical_ntriples is None
    assert decision.receipt.admitted_triple_count == 0
    assert decision.receipt.reasons == ("UNSUPPORTED_PREDICATE:urn:test:invented",)


def test_admitted_candidate_has_deterministic_receipt_and_graph_hash() -> None:
    pytest.importorskip("rdflib")
    court = SemanticAdmissionCourt(known_predicates={PREDICATE})

    first = court.decide(candidate())
    second = court.decide(candidate())

    assert first.receipt.standing is AdmissionStanding.ADMITTED
    assert first.receipt == second.receipt
    assert first.canonical_ntriples == second.canonical_ntriples
    assert first.receipt.graph_hash
    assert first.receipt.admitted_triple_count == 1


def test_refused_candidate_cannot_manufacture_training_example() -> None:
    court = SemanticAdmissionCourt(known_predicates={PREDICATE})
    rejected = candidate(predicate="urn:test:invented")
    receipt = court.decide(rejected).receipt

    with pytest.raises(ValueError, match="refused candidates"):
        example_from_admission(
            observation="Sean knows planning",
            ontology_context="test",
            candidate=rejected,
            receipt=receipt,
        )


def test_structured_output_rejects_extra_fields() -> None:
    payload = candidate().model_dump(mode="json")
    payload["semantic_authority"] = True

    with pytest.raises(ValueError, match="candidate schema"):
        parse_candidate_json(json.dumps(payload))


def test_pipeline_score_is_advisory_and_cannot_override_refusal() -> None:
    rejected = candidate(predicate="urn:test:invented")
    pipeline = SemanticModelPipeline(
        producer=lambda _o, _c, _p: rejected,
        admission_court=SemanticAdmissionCourt(known_predicates={PREDICATE}),
        scorer=lambda _candidate: 1.0,
    )

    result = pipeline.run(
        observation="observation",
        ontology_context="ontology",
        provenance_context="source",
    )

    assert result.advisory_score == 1.0
    assert result.receipt.standing is AdmissionStanding.REFUSED
