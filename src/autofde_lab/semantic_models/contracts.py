"""Typed contracts for semantic-model manufacture.

These types are intentionally representation-small.  Domain semantics live in public
ontologies; these classes only carry candidate graph deltas and their receipts.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdmissionStanding(str, Enum):
    """Standing of a candidate semantic delta."""

    ADMITTED = "ADMITTED"
    REFUSED = "REFUSED"


class SemanticTriple(BaseModel):
    """One RDF-like statement proposed for admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str = Field(min_length=1)
    object_kind: Literal["iri", "literal"] = "iri"
    datatype: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def validate_literal_metadata(self) -> SemanticTriple:
        if self.object_kind == "iri" and (self.datatype or self.language):
            raise ValueError("IRI objects cannot carry datatype or language")
        if self.datatype and self.language:
            raise ValueError("literal cannot specify both datatype and language")
        return self

    def canonical_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.subject,
            self.predicate,
            self.object_kind,
            self.object,
            self.datatype or "",
            self.language or "",
        )


class CandidateGraphDelta(BaseModel):
    """Untrusted semantic delta manufactured from an observation.

    A CandidateGraphDelta never has standing merely because it validates here.  It must
    pass SemanticAdmissionCourt before it can become O*.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    triples: tuple[SemanticTriple, ...] = Field(min_length=1)
    source_iris: tuple[str, ...] = Field(min_length=1)
    generator_id: str = Field(min_length=1)
    generator_revision: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "triples": [
                {
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object_kind": t.object_kind,
                    "object": t.object,
                    "datatype": t.datatype,
                    "language": t.language,
                }
                for t in sorted(self.triples, key=SemanticTriple.canonical_key)
            ],
            "source_iris": sorted(set(self.source_iris)),
            "generator_id": self.generator_id,
            "generator_revision": self.generator_revision,
            "confidence": self.confidence,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        )

    @property
    def candidate_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class AdmissionReceipt(BaseModel):
    """Replayable court decision for one candidate graph delta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    standing: AdmissionStanding
    candidate_hash: str
    graph_hash: str | None = None
    shacl_conforms: bool | None = None
    reasons: tuple[str, ...] = ()
    source_iris: tuple[str, ...] = ()
    admitted_triple_count: int = Field(default=0, ge=0)


class SemanticExample(BaseModel):
    """Training/evaluation example manufactured only from admitted semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation: str
    ontology_context: str
    expected_delta: CandidateGraphDelta
    admission_receipt_id: str


class OptimizationReceipt(BaseModel):
    """Immutable receipt binding dataset, ontology, optimizer and program digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    dataset_hash: str
    ontology_hash: str
    optimizer_name: str
    optimizer_config: dict[str, Any]
    metric_vector: dict[str, float]
    program_hash: str
    lm_identity: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "dataset_hash": self.dataset_hash,
            "ontology_hash": self.ontology_hash,
            "optimizer_name": self.optimizer_name,
            "optimizer_config": self.optimizer_config,
            "metric_vector": {
                k: round(v, 6) for k, v in sorted(self.metric_vector.items())
            },
            "program_hash": self.program_hash,
            "lm_identity": self.lm_identity,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        )

    @classmethod
    def manufacture(
        cls,
        *,
        dataset_hash: str,
        ontology_hash: str,
        optimizer_name: str,
        optimizer_config: dict[str, Any],
        metric_vector: dict[str, float],
        program_hash: str,
        lm_identity: str | None = None,
    ) -> OptimizationReceipt:
        payload = {
            "dataset_hash": dataset_hash,
            "ontology_hash": ontology_hash,
            "optimizer_name": optimizer_name,
            "optimizer_config": optimizer_config,
            "metric_vector": {k: round(v, 6) for k, v in sorted(metric_vector.items())},
            "program_hash": program_hash,
            "lm_identity": lm_identity,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        receipt_id = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return cls(
            receipt_id=receipt_id,
            dataset_hash=dataset_hash,
            ontology_hash=ontology_hash,
            optimizer_name=optimizer_name,
            optimizer_config=optimizer_config,
            metric_vector=metric_vector,
            program_hash=program_hash,
            lm_identity=lm_identity,
        )


class ModelQualificationRecord(BaseModel):
    """Comparative performance and admission conformance record for candidate models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    model_role: Literal["teacher", "student", "statistical_pipeline"]
    court_pass_rate: float
    graph_exactness: float
    p95_latency_ms: float
    cost_per_1k_tokens: float
    admissible: bool
