"""Tiny semantic operator contracts and standalone runtime.

Framework-independent runtime executing tiny, quantized models without ML libraries,
GPUs, LLMs, or network access.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import CandidateGraphDelta, SemanticTriple
from .feature_schema import SemanticFeatureSchema


class RuntimeTarget(str, Enum):
    """Execution targets for manufactured semantic operators."""

    REFERENCE_CPU = "REFERENCE_CPU"
    PORTABLE_FIXED = "PORTABLE_FIXED"
    ATOMVM_ERLANG = "ATOMVM_ERLANG"
    TFLITE_MICRO = "TFLITE_MICRO"
    ATOMVM_TFLM_NIF = "ATOMVM_TFLM_NIF"


class QuantizationKind(str, Enum):
    """Quantization formats for portable execution."""

    NONE = "NONE"
    FIXED_POINT_Q16 = "FIXED_POINT_Q16"
    FIXED_POINT_Q8 = "FIXED_POINT_Q8"
    INT8 = "INT8"


class TinyOperatorManifest(BaseModel):
    """Cryptographic manifest binding a tiny runtime operator back to O*."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ontology_hash: str = Field(min_length=1)
    feature_schema_hash: str = Field(min_length=1)
    dataset_hash: str = Field(min_length=1)
    optimization_receipt_id: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    parameter_hash: str = Field(min_length=1)
    quantization: QuantizationKind
    input_dimensions: int = Field(gt=0)
    output_semantic_iris: tuple[str, ...] = Field(min_length=1)
    estimated_parameter_bytes: int = Field(ge=0)
    runtime_target: RuntimeTarget
    qualification_receipt_id: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "ontology_hash": self.ontology_hash,
            "feature_schema_hash": self.feature_schema_hash,
            "dataset_hash": self.dataset_hash,
            "optimization_receipt_id": self.optimization_receipt_id,
            "model_family": self.model_family,
            "model_revision": self.model_revision,
            "parameter_hash": self.parameter_hash,
            "quantization": self.quantization.value,
            "input_dimensions": self.input_dimensions,
            "output_semantic_iris": sorted(self.output_semantic_iris),
            "estimated_parameter_bytes": self.estimated_parameter_bytes,
            "runtime_target": self.runtime_target.value,
            "qualification_receipt_id": self.qualification_receipt_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        )

    @property
    def manifest_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class TinyOperatorReceipt(BaseModel):
    """Inference receipt witnessing an execution of a tiny semantic operator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    manifest_hash: str
    input_vector_hash: str
    candidate_hash: str
    latency_us: int
    predicted_class_index: int
    predicted_semantic_iri: str


class TinySemanticOperator:
    """Standalone, framework-independent runtime operator.

    Requires NO PyTorch, NO Transformers, NO scikit-learn, NO LLM, NO GPU, and NO network.
    """

    def __init__(
        self,
        *,
        manifest: TinyOperatorManifest,
        feature_schema: SemanticFeatureSchema,
        predict_fn: Any,  # Callable[[Sequence[int]], int]
    ) -> None:
        if manifest.feature_schema_hash != feature_schema.feature_schema_hash:
            raise ValueError(
                "manifest feature_schema_hash does not match provided schema"
            )
        self.manifest = manifest
        self.feature_schema = feature_schema
        self._predict_fn = predict_fn

    def predict(self, feature_vector: Sequence[int]) -> int:
        if len(feature_vector) != self.manifest.input_dimensions:
            raise ValueError(
                f"expected feature vector dimension {self.manifest.input_dimensions}, "
                f"got {len(feature_vector)}"
            )
        return int(self._predict_fn(feature_vector))

    def predict_delta(
        self,
        *,
        subject_iri: str,
        observation_id: str,
        feature_vector: Sequence[int],
    ) -> CandidateGraphDelta:
        class_idx = self.predict(feature_vector)
        if class_idx < 0 or class_idx >= len(self.manifest.output_semantic_iris):
            raise ValueError(f"predicted class index {class_idx} out of range")
        output_iri = self.manifest.output_semantic_iris[class_idx]

        triple = SemanticTriple(
            subject=subject_iri,
            predicate=output_iri,
            object="true",
            object_kind="literal",
        )
        return CandidateGraphDelta(
            observation_id=observation_id,
            triples=(triple,),
            source_iris=(f"urn:operator:{self.manifest.model_revision}",),
            generator_id=f"tiny-operator:{self.manifest.model_family}",
            generator_revision=self.manifest.model_revision,
            confidence=1.0,
        )

    def execute_and_receipt(
        self,
        *,
        subject_iri: str,
        observation_id: str,
        feature_vector: Sequence[int],
    ) -> tuple[CandidateGraphDelta, TinyOperatorReceipt]:
        t0 = time.monotonic_ns()
        class_idx = self.predict(feature_vector)
        latency_us = max(1, (time.monotonic_ns() - t0) // 1000)

        output_iri = self.manifest.output_semantic_iris[class_idx]
        delta = self.predict_delta(
            subject_iri=subject_iri,
            observation_id=observation_id,
            feature_vector=feature_vector,
        )

        vec_serialized = json.dumps(list(feature_vector), separators=(",", ":"))
        vec_hash = hashlib.sha256(vec_serialized.encode("utf-8")).hexdigest()

        receipt_payload = {
            "manifest_hash": self.manifest.manifest_hash,
            "input_vector_hash": vec_hash,
            "candidate_hash": delta.candidate_hash,
            "latency_us": latency_us,
            "predicted_class_index": class_idx,
            "predicted_semantic_iri": output_iri,
        }
        receipt_id = hashlib.sha256(
            json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()

        receipt = TinyOperatorReceipt(
            receipt_id=receipt_id,
            manifest_hash=self.manifest.manifest_hash,
            input_vector_hash=vec_hash,
            candidate_hash=delta.candidate_hash,
            latency_us=latency_us,
            predicted_class_index=class_idx,
            predicted_semantic_iri=output_iri,
        )
        return delta, receipt
