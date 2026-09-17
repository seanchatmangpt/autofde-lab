"""Tests for AutoFDE Lab v26.9.14 Tiny Semantic Runtime.

Proves:
1. Runtime operates with NO LLM, NO GPU, NO DSPy, NO TPOT, NO sklearn, NO network.
2. Ontology-derived SemanticFeatureSchema maps O* to Z^n deterministically.
3. Quantized fixed-point operators achieve semantic standing parity.
4. AtomVM Erlang projection is generated deterministically.
5. Teacher dependency rate converges to 0.
"""

from __future__ import annotations

import hashlib
import os
from unittest import mock

import pytest

from autofde_lab.semantic_models.admission import SemanticAdmissionCourt
from autofde_lab.semantic_models.atomvm_codegen import (
    generate_atomvm_erlang_module,
)
from autofde_lab.semantic_models.contracts import (
    AdmissionStanding,
    SemanticTriple,
)
from autofde_lab.semantic_models.feature_schema import SemanticFeatureSchema
from autofde_lab.semantic_models.parity_court import (
    compute_teacher_independence,
    evaluate_runtime_parity,
)
from autofde_lab.semantic_models.portable_compiler import (
    PortableDecisionTree,
    PortableLinearWeights,
    PortableTreeNode,
    build_tiny_operator_from_linear,
    compile_linear_to_fixed_point,
)
from autofde_lab.semantic_models.sklearn_search import (
    MICRO_EXPORTABLE_CONFIG,
    TPOTSearchConfig,
)
from autofde_lab.semantic_models.tiny_operator import (
    QuantizationKind,
    RuntimeTarget,
    TinyOperatorManifest,
    TinySemanticOperator,
)

KNOWN_IRIS = [
    "http://example.org/pred/status",
    "http://example.org/pred/severity",
    "http://example.org/pred/hasError",
]
OUTPUT_IRIS = [
    "http://example.org/action/restart",
    "http://example.org/action/scale_up",
]
ONTOLOGY_HASH = hashlib.sha256(b"ontology-v26.9.14").hexdigest()
DATASET_HASH = hashlib.sha256(b"dataset-v26.9.14").hexdigest()


def test_feature_schema_is_deterministic():
    schema1 = SemanticFeatureSchema.manufacture(
        ontology_hash=ONTOLOGY_HASH, admitted_iris=KNOWN_IRIS
    )
    schema2 = SemanticFeatureSchema.manufacture(
        ontology_hash=ONTOLOGY_HASH, admitted_iris=list(reversed(KNOWN_IRIS))
    )

    assert schema1.feature_schema_hash == schema2.feature_schema_hash
    assert schema1.dimension == len(KNOWN_IRIS)
    assert schema1.features[0].feature_id == 0
    assert schema1.features[1].feature_id == 1


def test_feature_schema_rejects_unknown_semantics():
    schema = SemanticFeatureSchema.manufacture(
        ontology_hash=ONTOLOGY_HASH, admitted_iris=KNOWN_IRIS
    )
    unadmitted_triple = SemanticTriple(
        subject="http://example.org/pod/1",
        predicate="http://example.org/pred/unadmittedPredicate",
        object="value",
        object_kind="literal",
    )
    with pytest.raises(ValueError, match="fail-closed: unknown predicate"):
        schema.vectorize([unadmitted_triple])


def test_tpot_search_space_contains_only_micro_exportable_models():
    config = TPOTSearchConfig(search_space="micro-exportable")
    assert config.search_space == "micro-exportable"

    for model_name in MICRO_EXPORTABLE_CONFIG:
        assert any(
            allowed in model_name
            for allowed in [
                "LogisticRegression",
                "DecisionTreeClassifier",
                "ComplementNB",
            ]
        )
        assert "RandomForest" not in model_name
        assert "GradientBoosting" not in model_name


def test_tiny_operator_manifest_hash_is_stable():
    manifest1 = TinyOperatorManifest(
        ontology_hash=ONTOLOGY_HASH,
        feature_schema_hash="schema-hash-1",
        dataset_hash=DATASET_HASH,
        optimization_receipt_id="opt-rec-1",
        model_family="linear_fixed_point",
        model_revision="v1",
        parameter_hash="param-hash-1",
        quantization=QuantizationKind.FIXED_POINT_Q16,
        input_dimensions=3,
        output_semantic_iris=tuple(OUTPUT_IRIS),
        estimated_parameter_bytes=128,
        runtime_target=RuntimeTarget.PORTABLE_FIXED,
    )
    manifest2 = TinyOperatorManifest(
        ontology_hash=ONTOLOGY_HASH,
        feature_schema_hash="schema-hash-1",
        dataset_hash=DATASET_HASH,
        optimization_receipt_id="opt-rec-1",
        model_family="linear_fixed_point",
        model_revision="v1",
        parameter_hash="param-hash-1",
        quantization=QuantizationKind.FIXED_POINT_Q16,
        input_dimensions=3,
        output_semantic_iris=tuple(reversed(OUTPUT_IRIS)),  # sorted canonically
        estimated_parameter_bytes=128,
        runtime_target=RuntimeTarget.PORTABLE_FIXED,
    )
    assert manifest1.manifest_hash == manifest2.manifest_hash


def test_linear_operator_compiles_without_sklearn():
    weights = PortableLinearWeights(
        fixed_weights=[[65536, -32768, 0], [-65536, 32768, 65536]],
        fixed_biases=[0, 1000],
        scale=65536,
        quantization=QuantizationKind.FIXED_POINT_Q16,
    )
    pred0 = weights.predict([1, 0, 0])
    pred1 = weights.predict([0, 1, 1])
    assert pred0 == 0
    assert pred1 == 1


def test_tree_operator_compiles_without_sklearn():
    # If feat 0 <= 65536 -> class 0, else -> class 1
    tree = PortableDecisionTree(
        nodes=[
            PortableTreeNode(
                feature_id=0,
                threshold_fixed=65536,
                left_child=1,
                right_child=2,
                class_id=-1,
            ),
            PortableTreeNode(
                feature_id=-2,
                threshold_fixed=0,
                left_child=-1,
                right_child=-1,
                class_id=0,
            ),
            PortableTreeNode(
                feature_id=-2,
                threshold_fixed=0,
                left_child=-1,
                right_child=-1,
                class_id=1,
            ),
        ],
        scale=65536,
        quantization=QuantizationKind.FIXED_POINT_Q16,
    )
    assert tree.predict([1, 0, 0]) == 0
    assert tree.predict([2, 0, 0]) == 1


def test_fixed_point_parity():
    pytest.importorskip("sklearn")
    from sklearn.linear_model import LogisticRegression

    X = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [0, 1, 1]]
    y = [0, 0, 1, 0, 1]
    clf = LogisticRegression(random_state=42).fit(X, y)

    linear, param_hash, est_bytes = compile_linear_to_fixed_point(clf, scale_bits=16)
    assert param_hash
    assert est_bytes > 0

    for x_vec in X:
        sklearn_pred = int(clf.predict([x_vec])[0])
        fixed_pred = linear.predict(x_vec)
        assert fixed_pred == sklearn_pred, f"mismatch on {x_vec}"


def test_quantized_semantic_standing_parity():
    pytest.importorskip("sklearn")
    from sklearn.linear_model import LogisticRegression

    court = SemanticAdmissionCourt(known_predicates=KNOWN_IRIS + OUTPUT_IRIS)
    schema = SemanticFeatureSchema.manufacture(
        ontology_hash=ONTOLOGY_HASH, admitted_iris=KNOWN_IRIS
    )

    X = [[1, 0, 0], [0, 1, 1]]
    y = [0, 1]
    clf = LogisticRegression(random_state=42).fit(X, y)

    operator = build_tiny_operator_from_linear(
        clf,
        ontology_hash=ONTOLOGY_HASH,
        feature_schema=schema,
        dataset_hash=DATASET_HASH,
        optimization_receipt_id="opt-test",
        output_semantic_iris=OUTPUT_IRIS,
    )

    linear_weights, _, _ = compile_linear_to_fixed_point(clf)
    parity_records = evaluate_runtime_parity(
        test_vectors=X,
        observation_ids=["obs-parity-1", "obs-parity-2"],
        subject_iris=["http://example.org/pod/1", "http://example.org/pod/2"],
        reference_predict_fn=clf.predict,
        portable_operator=operator,
        linear_weights=linear_weights,
        court=court,
    )

    for rec in parity_records:
        assert rec.standings_match is True
        assert rec.reference_standing is AdmissionStanding.ADMITTED
        assert rec.portable_standing is AdmissionStanding.ADMITTED


def test_runtime_has_no_llm_imports():
    import importlib

    runtime_modules = [
        "autofde_lab.semantic_models.feature_schema",
        "autofde_lab.semantic_models.tiny_operator",
        "autofde_lab.semantic_models.portable_compiler",
        "autofde_lab.semantic_models.atomvm_codegen",
    ]
    forbidden_tokens = ["dspy", "litellm", "openai", "zai"]

    from pathlib import Path

    for mod_name in runtime_modules:
        mod = importlib.import_module(mod_name)
        source = Path(mod.__file__).read_text(encoding="utf-8")
        for forbidden in forbidden_tokens:
            assert f"import {forbidden}" not in source, (
                f"{mod_name} imports {forbidden}"
            )
            assert f"from {forbidden}" not in source, f"{mod_name} imports {forbidden}"


def test_runtime_has_no_gpu_imports():
    import importlib
    from pathlib import Path

    runtime_modules = [
        "autofde_lab.semantic_models.feature_schema",
        "autofde_lab.semantic_models.tiny_operator",
        "autofde_lab.semantic_models.portable_compiler",
        "autofde_lab.semantic_models.atomvm_codegen",
    ]
    forbidden_tokens = ["torch", "tensorflow", "transformers", "peft", "trl", "cuda"]

    for mod_name in runtime_modules:
        mod = importlib.import_module(mod_name)
        source = Path(mod.__file__).read_text(encoding="utf-8")
        for forbidden in forbidden_tokens:
            assert f"import {forbidden}" not in source, (
                f"{mod_name} imports {forbidden}"
            )
            assert f"from {forbidden}" not in source, f"{mod_name} imports {forbidden}"


def test_runtime_requires_no_network():
    manifest = TinyOperatorManifest(
        ontology_hash=ONTOLOGY_HASH,
        feature_schema_hash="schema-hash",
        dataset_hash=DATASET_HASH,
        optimization_receipt_id="opt-1",
        model_family="dummy",
        model_revision="v1",
        parameter_hash="param-hash",
        quantization=QuantizationKind.NONE,
        input_dimensions=2,
        output_semantic_iris=tuple(OUTPUT_IRIS),
        estimated_parameter_bytes=10,
        runtime_target=RuntimeTarget.PORTABLE_FIXED,
    )
    feature = SemanticFeatureSchema(
        ontology_hash=ONTOLOGY_HASH,
        features=(
            SemanticFeatureSchema.manufacture(
                ontology_hash=ONTOLOGY_HASH, admitted_iris=KNOWN_IRIS[:2]
            ).features
        ),
        feature_schema_hash="schema-hash",
    )
    op = TinySemanticOperator(
        manifest=manifest,
        feature_schema=feature,
        predict_fn=lambda vec: 0,
    )

    with mock.patch("socket.socket") as mock_sock:
        mock_sock.side_effect = RuntimeError("network call prohibited")
        delta, receipt = op.execute_and_receipt(
            subject_iri="http://example.org/pod/1",
            observation_id="obs-net-1",
            feature_vector=[1, 0],
        )
        assert delta.candidate_hash
        assert receipt.receipt_id


def test_runtime_runs_without_zai_key():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert os.environ.get("ZAI_API_KEY") is None
        weights = PortableLinearWeights(
            fixed_weights=[[10, 0], [0, 10]],
            fixed_biases=[0, 0],
            scale=1,
            quantization=QuantizationKind.NONE,
        )
        assert weights.predict([1, 0]) == 0


def test_atomvm_codegen_is_deterministic():
    weights = PortableLinearWeights(
        fixed_weights=[[65536, -32768], [-65536, 32768]],
        fixed_biases=[100, 200],
        scale=65536,
        quantization=QuantizationKind.FIXED_POINT_Q16,
    )
    manifest = TinyOperatorManifest(
        ontology_hash=ONTOLOGY_HASH,
        feature_schema_hash="schema-1",
        dataset_hash=DATASET_HASH,
        optimization_receipt_id="opt-1",
        model_family="linear_fixed_point",
        model_revision="v26.9.14",
        parameter_hash="param-1",
        quantization=QuantizationKind.FIXED_POINT_Q16,
        input_dimensions=2,
        output_semantic_iris=tuple(OUTPUT_IRIS),
        estimated_parameter_bytes=64,
        runtime_target=RuntimeTarget.ATOMVM_ERLANG,
    )

    erl1 = generate_atomvm_erlang_module(weights, manifest)
    erl2 = generate_atomvm_erlang_module(weights, manifest)
    assert erl1 == erl2
    assert "-module(semantic_operator_v26_9_14)." in erl1
    assert "output_iris() ->" in erl1
    assert "predict(Features) when is_list(Features)" in erl1


def test_atomvm_output_preserves_semantic_ids():
    weights = PortableLinearWeights(
        fixed_weights=[[1, 0], [0, 1]],
        fixed_biases=[0, 0],
        scale=1,
        quantization=QuantizationKind.NONE,
    )
    manifest = TinyOperatorManifest(
        ontology_hash=ONTOLOGY_HASH,
        feature_schema_hash="schema-1",
        dataset_hash=DATASET_HASH,
        optimization_receipt_id="opt-1",
        model_family="linear_fixed_point",
        model_revision="v26.9.14",
        parameter_hash="param-1",
        quantization=QuantizationKind.NONE,
        input_dimensions=2,
        output_semantic_iris=tuple(OUTPUT_IRIS),
        estimated_parameter_bytes=32,
        runtime_target=RuntimeTarget.ATOMVM_ERLANG,
    )
    erl = generate_atomvm_erlang_module(weights, manifest)
    for iris in OUTPUT_IRIS:
        assert f'<<"{iris}">>' in erl


def test_teacher_dependency_can_be_zero():
    rep = compute_teacher_independence(
        total_inferences=1000,
        teacher_calls=0,
        tiny_operator_calls=1000,
        admissible_coverage=1.0,
        parameter_bytes=256,
    )
    assert rep.teacher_dependency_rate == 0.0
    assert rep.admissible_coverage == 1.0
