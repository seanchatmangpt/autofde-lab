"""Chicago-style tests for the closed semantic model manufacturing loop.

Verifies:
Observation -> Candidate -> Court -> Receipt -> Experience -> Dataset -> Optimize -> Qualify -> O*
with exact-head cryptographic replay verification.
"""

from __future__ import annotations

import hashlib

from autofde_lab.semantic_models import (
    CandidateGraphDelta,
    SemanticAdmissionCourt,
    SemanticTriple,
    run_closed_manufacturing_cycle,
)
from autofde_lab.semantic_models.dspy_program import (
    DSPyCompileConfig,
    compile_and_receipt_extractor,
)

KNOWN = frozenset(
    {"http://example.org/pred/status", "http://example.org/pred/hasError"}
)
ONTOLOGY_HASH = hashlib.sha256(b"mock-ontology-definition").hexdigest()


def _make_candidate(
    triples: list[SemanticTriple],
    *,
    obs_id: str = "obs-test",
    confidence: float = 0.95,
) -> CandidateGraphDelta:
    return CandidateGraphDelta(
        observation_id=obs_id,
        triples=tuple(triples),
        source_iris=("urn:source:test-1",),
        generator_id="test-producer",
        generator_revision="rev-1",
        confidence=confidence,
    )


def test_closed_manufacturing_cycle_end_to_end():
    court = SemanticAdmissionCourt(known_predicates=KNOWN)

    observations = [
        ("Pod 1 healthy", "ctx1", "urn:source:test-1"),
        ("Pod 2 degraded", "ctx2", "urn:source:test-1"),
        ("Pod 3 illegal predicate", "ctx3", "urn:source:test-1"),
        ("Pod 4 missing provenance", "ctx4", "urn:source:test-1"),
    ]

    def gold_gen(obs: str, ctx: str) -> CandidateGraphDelta:
        if "illegal" in obs:
            # Unadmitted predicate -> will be REFUSED
            return CandidateGraphDelta(
                observation_id="obs-pod-3",
                triples=(
                    SemanticTriple(
                        subject="http://example.org/pod/3",
                        predicate="http://example.org/pred/unsupportedPredicate",
                        object="error",
                        object_kind="literal",
                    ),
                ),
                source_iris=("urn:source:test-1",),
                generator_id="gen",
                generator_revision="v1",
            )
        if "missing" in obs:
            # Another unadmitted predicate -> will be REFUSED
            return CandidateGraphDelta(
                observation_id="obs-pod-4",
                triples=(
                    SemanticTriple(
                        subject="http://example.org/pod/4",
                        predicate="http://example.org/pred/anotherUnsupported",
                        object="failed",
                        object_kind="literal",
                    ),
                ),
                source_iris=("urn:source:test-1",),
                generator_id="gen",
                generator_revision="v1",
            )
        # Healthy / degraded valid triples -> will be ADMITTED
        pod_id = "1" if "1" in obs else "2"
        status_val = "healthy" if "healthy" in obs else "degraded"
        return _make_candidate(
            [
                SemanticTriple(
                    subject=f"http://example.org/pod/{pod_id}",
                    predicate="http://example.org/pred/status",
                    object=status_val,
                    object_kind="literal",
                )
            ]
        )

    producers = {
        "frontier_teacher": lambda obs, ctx: gold_gen(obs, ctx),
        "distilled_student": lambda obs, ctx: gold_gen(obs, ctx),
    }

    result = run_closed_manufacturing_cycle(
        observations=observations,
        producers=producers,
        gold_generator=gold_gen,
        court=court,
        known_predicates=KNOWN,
        ontology_hash=ONTOLOGY_HASH,
        cost_table={
            "teacher": 0.005,
            "student": 0.0002,
            "statistical_pipeline": 0.00001,
        },
    )

    # 1. Experience & Receipts
    assert len(result.admission_receipts) == 4
    admitted = [r for r in result.admission_receipts if r.standing.value == "ADMITTED"]
    refused = [r for r in result.admission_receipts if r.standing.value == "REFUSED"]
    assert len(admitted) == 2
    assert len(refused) == 2

    # 2. Partitioned Dataset
    assert len(result.dataset.gold_examples) == 2
    assert len(result.dataset.contrastive_examples) == 2
    assert result.dataset.dataset_hash
    assert result.dataset.ontology_hash == ONTOLOGY_HASH

    # 3. Statistical Baseline Optimization Receipt
    assert len(result.optimization_receipts) >= 1
    opt_receipt = result.optimization_receipts[0]
    assert opt_receipt.receipt_id
    assert opt_receipt.dataset_hash == result.dataset.dataset_hash
    assert opt_receipt.ontology_hash == ONTOLOGY_HASH
    assert opt_receipt.optimizer_name == "sklearn-logistic-baseline"
    assert "accuracy" in opt_receipt.metric_vector

    # 4. Comparative Qualification Records
    assert len(result.qualification_records) == 2
    for qual in result.qualification_records:
        assert qual.court_pass_rate == 1.0
        assert qual.graph_exactness == 1.0
        assert qual.admissible is True

    # 5. Envelope Selection: student should win because it is cheaper than teacher for the same pass rate
    assert result.winning_candidate_id == "distilled_student"


def test_exact_head_replay_produces_identical_receipts():
    court1 = SemanticAdmissionCourt(known_predicates=KNOWN)
    court2 = SemanticAdmissionCourt(known_predicates=KNOWN)

    observations = [
        ("Node A operational", "ctxA", "urn:source:test-1"),
        ("Node B fault", "ctxB", "urn:source:test-1"),
        ("Node C unknown", "ctxC", "urn:source:test-1"),
    ]

    def gen(obs: str, ctx: str) -> CandidateGraphDelta:
        if "unknown" in obs:
            return CandidateGraphDelta(
                observation_id="obs-node-C",
                triples=(
                    SemanticTriple(
                        subject="http://example.org/node/C",
                        predicate="http://example.org/pred/bogus",
                        object="bad",
                        object_kind="literal",
                    ),
                ),
                source_iris=("urn:source:test-1",),
                generator_id="gen",
                generator_revision="v1",
            )
        node_id = "A" if "A" in obs else "B"
        return _make_candidate(
            [
                SemanticTriple(
                    subject=f"http://example.org/node/{node_id}",
                    predicate="http://example.org/pred/status",
                    object="active",
                    object_kind="literal",
                )
            ]
        )

    producers = {"student_fast": gen}

    run1 = run_closed_manufacturing_cycle(
        observations=observations,
        producers=producers,
        gold_generator=gen,
        court=court1,
        known_predicates=KNOWN,
        ontology_hash=ONTOLOGY_HASH,
    )

    run2 = run_closed_manufacturing_cycle(
        observations=observations,
        producers=producers,
        gold_generator=gen,
        court=court2,
        known_predicates=KNOWN,
        ontology_hash=ONTOLOGY_HASH,
    )

    # Exact-head replay assert: all hashes and receipts match exactly
    assert run1.dataset.dataset_hash == run2.dataset.dataset_hash
    assert [r.receipt_id for r in run1.admission_receipts] == [
        r.receipt_id for r in run2.admission_receipts
    ]
    assert [r.receipt_id for r in run1.optimization_receipts] == [
        r.receipt_id for r in run2.optimization_receipts
    ]
    assert run1.winning_candidate_id == run2.winning_candidate_id


def test_dspy_compile_and_receipt_extractor():
    from autofde_lab.semantic_models.dataset import example_from_admission

    cand = _make_candidate(
        [
            SemanticTriple(
                subject="http://example.org/pod/1",
                predicate="http://example.org/pred/status",
                object="healthy",
                object_kind="literal",
            )
        ]
    )
    court = SemanticAdmissionCourt(known_predicates=KNOWN)
    receipt, _ = court.admit(cand)
    example = example_from_admission(
        observation="Pod 1 is healthy",
        ontology_context="Status schema",
        candidate=cand,
        receipt=receipt,
    )

    dataset_hash = hashlib.sha256(b"dataset-v1").hexdigest()
    config = DSPyCompileConfig(
        optimizer="bootstrapfewshot", max_bootstrapped_demos=1, max_labeled_demos=1
    )

    _compiled, opt_receipt = compile_and_receipt_extractor(
        [example],
        known_predicates=KNOWN,
        dataset_hash=dataset_hash,
        ontology_hash=ONTOLOGY_HASH,
        config=config,
        lm_identity="mock-lm",
    )

    assert opt_receipt.receipt_id
    assert opt_receipt.dataset_hash == dataset_hash
    assert opt_receipt.ontology_hash == ONTOLOGY_HASH
    assert opt_receipt.optimizer_name == "bootstrapfewshot"
    assert "mean_score" in opt_receipt.metric_vector
    assert opt_receipt.program_hash
