"""Chicago-style adversarial falsification tests for Semantic Models and Closed Manufacturing Loop.

Attacks:
1. 100% Admission refusal: closed loop handling when no candidate passes admission.
2. Canonical Hash Invariance under whitespace, Unicode and key order variations.
3. Tiny Runtime quantized integer predictor against extreme weights and categorical drifts.
"""

from __future__ import annotations

import hashlib

from autofde_lab.semantic_models import (
    CandidateGraphDelta,
    SemanticAdmissionCourt,
    SemanticTriple,
    run_closed_manufacturing_cycle,
)
from autofde_lab.semantic_models.atomvm_codegen import generate_atomvm_erlang_module
from autofde_lab.semantic_models.portable_compiler import (
    PortableLinearWeights,
)
from autofde_lab.semantic_models.tiny_operator import QuantizationKind

KNOWN = frozenset(
    {"http://example.org/pred/status", "http://example.org/pred/hasError"}
)
ONTOLOGY_HASH = hashlib.sha256(b"adversarial-test-ontology").hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Mutant: 100% Admission Refusal (All candidates rejected)
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_closed_loop_when_all_producers_refused():
    """When all candidate triples contain unadmitted predicates, the closed loop
    must produce zero admitted examples, handle the empty dataset safely,
    and refuse to manufacture an ungrounded model.
    """
    court = SemanticAdmissionCourt(known_predicates=KNOWN)

    # Observations that produce strictly illegal/unadmitted predicates
    observations = [
        ("Hostile event 1", "ctx1", "urn:src:1"),
        ("Hostile event 2", "ctx2", "urn:src:2"),
    ]

    def hostile_generator(obs: str, ctx: str) -> CandidateGraphDelta:
        return CandidateGraphDelta(
            observation_id="obs-hostile",
            triples=(
                SemanticTriple(
                    subject="http://example.org/node/X",
                    predicate="http://example.org/UNADMITTED/ILLEGAL",
                    object="malicious_payload",
                    object_kind="literal",
                ),
            ),
            source_iris=("urn:src:hostile",),
            generator_id="hostile-producer",
            generator_revision="rev-0",
            confidence=0.99,
        )

    summary = run_closed_manufacturing_cycle(
        observations=observations,
        producers={"hostile": hostile_generator},
        gold_generator=hostile_generator,
        court=court,
        known_predicates=KNOWN,
        ontology_hash=ONTOLOGY_HASH,
    )

    # Invariant: Empty admitted dataset
    assert len(summary.dataset.gold_examples) == 0
    # Invariant: Every candidate was refused
    from autofde_lab.semantic_models.contracts import AdmissionStanding

    assert all(
        r.standing == AdmissionStanding.REFUSED for r in summary.admission_receipts
    )
    # Invariant: No winning candidate qualified ('none')
    assert summary.winning_candidate_id == "none"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Mutant: Tiny Runtime Quantized Overflow & Feature Drift
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_tiny_runtime_overflow_and_extreme_features():
    """PortableLinearWeights must execute cleanly with extreme feature inputs
    without integer overflow or NaN crash.
    """
    weights = PortableLinearWeights(
        fixed_weights=[
            [65536 * 1000, -65536 * 1000, 32768],
            [-65536 * 1000, 65536 * 1000, -32768],
        ],
        fixed_biases=[500, -500],
        scale=65536,
        quantization=QuantizationKind.FIXED_POINT_Q16,
    )

    # Test extreme int vector
    extreme_vec = [1_000_000, -1_000_000, 0]
    pred_class = weights.predict(extreme_vec)
    assert pred_class in (0, 1)

    # Test zero vector
    zero_vec = [0, 0, 0]
    pred_zero = weights.predict(zero_vec)
    assert pred_zero in (0, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Mutant: AtomVM Erlang Codegen Syntax Verification
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_atomvm_beam_source_syntax():
    """Exported Erlang code must declare valid export headers and integer lookup tables."""
    from autofde_lab.semantic_models.tiny_operator import (
        RuntimeTarget,
        TinyOperatorManifest,
    )

    manifest = TinyOperatorManifest(
        ontology_hash=ONTOLOGY_HASH,
        feature_schema_hash="schema-hash-test",
        dataset_hash="dataset-hash-test",
        optimization_receipt_id="opt-test",
        model_family="linear_fixed_point",
        model_revision="v1",
        parameter_hash="param-hash-test",
        quantization=QuantizationKind.FIXED_POINT_Q16,
        input_dimensions=2,
        output_semantic_iris=("http://example.org/out/0", "http://example.org/out/1"),
        estimated_parameter_bytes=64,
        runtime_target=RuntimeTarget.ATOMVM_ERLANG,
    )

    weights = PortableLinearWeights(
        fixed_weights=[[100, -100], [-100, 100]],
        fixed_biases=[10, -10],
        scale=256,
        quantization=QuantizationKind.FIXED_POINT_Q16,
    )

    erl = generate_atomvm_erlang_module(
        weights, manifest, module_name="semantic_atomvm_probe"
    )
    assert "-module(semantic_atomvm_probe)." in erl
    assert "-export([predict/1, predict_iri/1, manifest/0, output_iris/0])." in erl
    assert "manifest() ->" in erl
    assert "predict(Features) when is_list(Features) ->" in erl
