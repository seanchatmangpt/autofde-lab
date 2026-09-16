"""Portable fixed-point compiler transforming learned models into Python-free primitive tables.

Implements fixed-point integer arithmetic:
    y = argmax_k ( b_k + sum_i w_{ki} * x_i )
and tabular decision trees with zero external ML-framework imports during execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .feature_schema import SemanticFeatureSchema
from .tiny_operator import (
    QuantizationKind,
    RuntimeTarget,
    TinyOperatorManifest,
    TinySemanticOperator,
)


@dataclass(frozen=True)
class PortableLinearWeights:
    """Fixed-point integer representation of a linear multi-class classifier."""

    fixed_weights: list[list[int]]  # [num_classes, num_features]
    fixed_biases: list[int]  # [num_classes]
    scale: int  # e.g., 65536 for Q16.16
    quantization: QuantizationKind

    def predict(self, features: Sequence[int]) -> int:
        best_score = -9223372036854775807
        best_class = 0
        for class_idx, (weights, bias) in enumerate(
            zip(self.fixed_weights, self.fixed_biases, strict=False)
        ):
            score = bias
            for w, x in zip(weights, features, strict=False):
                score += w * x
            if score > best_score:
                best_score = score
                best_class = class_idx
        return best_class


@dataclass(frozen=True)
class PortableTreeNode:
    """One immutable node in a fixed-point tabular decision tree."""

    feature_id: int  # -2 for leaf
    threshold_fixed: int
    left_child: int
    right_child: int
    class_id: int


@dataclass(frozen=True)
class PortableDecisionTree:
    """Fixed-point integer tabular decision tree."""

    nodes: list[PortableTreeNode]
    scale: int
    quantization: QuantizationKind

    def predict(self, features: Sequence[int]) -> int:
        curr = 0
        while True:
            node = self.nodes[curr]
            if node.feature_id == -2 or (
                node.left_child == -1 and node.right_child == -1
            ):
                return node.class_id
            val_fixed = features[node.feature_id] * self.scale
            if val_fixed <= node.threshold_fixed:
                curr = node.left_child
            else:
                curr = node.right_child


def compile_linear_to_fixed_point(
    estimator: Any,
    *,
    scale_bits: int = 16,
) -> tuple[PortableLinearWeights, str, int]:
    """Extract and quantize a linear classifier (e.g. LogisticRegression) into fixed-point integers."""
    import numpy as np

    raw_coef = np.asarray(estimator.coef_, dtype=np.float64)
    raw_intercept = np.asarray(estimator.intercept_, dtype=np.float64)

    # If binary classification, scikit-learn stores 1 row [1, n_features].
    # Expand to 2 classes for symmetric argmax: [-score, +score]
    if raw_coef.shape[0] == 1:
        raw_coef = np.vstack([-raw_coef, raw_coef])
        raw_intercept = np.array(
            [-raw_intercept[0], raw_intercept[0]], dtype=np.float64
        )

    scale = 1 << scale_bits
    quant = (
        QuantizationKind.FIXED_POINT_Q16
        if scale_bits == 16
        else QuantizationKind.FIXED_POINT_Q8
    )

    fixed_weights = np.round(raw_coef * scale).astype(np.int64).tolist()
    fixed_biases = np.round(raw_intercept * scale).astype(np.int64).tolist()

    model_bytes = {
        "fixed_weights": fixed_weights,
        "fixed_biases": fixed_biases,
        "scale": scale,
        "quantization": quant.value,
    }
    dumped = json.dumps(model_bytes, sort_keys=True, separators=(",", ":"))
    param_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()
    estimated_bytes = len(dumped.encode("utf-8"))

    linear = PortableLinearWeights(
        fixed_weights=fixed_weights,
        fixed_biases=fixed_biases,
        scale=scale,
        quantization=quant,
    )
    return linear, param_hash, estimated_bytes


def compile_tree_to_fixed_point(
    tree_estimator: Any,
    *,
    scale_bits: int = 16,
) -> tuple[PortableDecisionTree, str, int]:
    """Extract and quantize a DecisionTreeClassifier into a fixed-point node table."""
    import numpy as np

    tree = tree_estimator.tree_
    scale = 1 << scale_bits
    quant = (
        QuantizationKind.FIXED_POINT_Q16
        if scale_bits == 16
        else QuantizationKind.FIXED_POINT_Q8
    )

    nodes: list[PortableTreeNode] = []
    for i in range(tree.node_count):
        feat = int(tree.feature[i])
        thresh = int(np.round(float(tree.threshold[i]) * scale))
        left = int(tree.children_left[i])
        right = int(tree.children_right[i])
        class_id = int(np.argmax(tree.value[i]))
        nodes.append(
            PortableTreeNode(
                feature_id=feat,
                threshold_fixed=thresh,
                left_child=left,
                right_child=right,
                class_id=class_id,
            )
        )

    dumped = json.dumps(
        [n.__dict__ for n in nodes], sort_keys=True, separators=(",", ":")
    )
    param_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()
    estimated_bytes = len(dumped.encode("utf-8"))

    dt = PortableDecisionTree(nodes=nodes, scale=scale, quantization=quant)
    return dt, param_hash, estimated_bytes


def build_tiny_operator_from_linear(
    estimator: Any,
    *,
    ontology_hash: str,
    feature_schema: SemanticFeatureSchema,
    dataset_hash: str,
    optimization_receipt_id: str,
    output_semantic_iris: Sequence[str],
    model_revision: str = "v26.9.14-linear-q16",
    scale_bits: int = 16,
) -> TinySemanticOperator:
    """Manufacture a qualified TinySemanticOperator from a trained linear model."""
    linear, param_hash, est_bytes = compile_linear_to_fixed_point(
        estimator, scale_bits=scale_bits
    )

    manifest = TinyOperatorManifest(
        ontology_hash=ontology_hash,
        feature_schema_hash=feature_schema.feature_schema_hash,
        dataset_hash=dataset_hash,
        optimization_receipt_id=optimization_receipt_id,
        model_family="linear_fixed_point",
        model_revision=model_revision,
        parameter_hash=param_hash,
        quantization=linear.quantization,
        input_dimensions=feature_schema.dimension,
        output_semantic_iris=tuple(output_semantic_iris),
        estimated_parameter_bytes=est_bytes,
        runtime_target=RuntimeTarget.PORTABLE_FIXED,
    )

    return TinySemanticOperator(
        manifest=manifest,
        feature_schema=feature_schema,
        predict_fn=linear.predict,
    )
