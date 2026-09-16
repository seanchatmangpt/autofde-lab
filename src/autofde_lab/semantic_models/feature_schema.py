"""Ontology-derived feature schema mapping admitted semantic terms to integer indices.

Provides the deterministic bridge from O* to Z^n without letting numeric representations
become the source of truth. Unknown terms fail closed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import CandidateGraphDelta, SemanticTriple


class SemanticFeature(BaseModel):
    """One deterministic feature derived from an admitted semantic IRI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_id: int = Field(ge=0)
    semantic_iri: str = Field(min_length=1)
    value_kind: str = Field(default="binary")
    description: str = Field(default="")


class SemanticFeatureSchema(BaseModel):
    """Deterministic feature schema manufactured strictly from admitted ontology terms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ontology_hash: str = Field(min_length=1)
    features: tuple[SemanticFeature, ...] = Field(min_length=1)
    feature_schema_hash: str = Field(min_length=1)

    @property
    def dimension(self) -> int:
        return len(self.features)

    @property
    def iri_to_id(self) -> dict[str, int]:
        return {f.semantic_iri: f.feature_id for f in self.features}

    @property
    def id_to_iri(self) -> dict[int, str]:
        return {f.feature_id: f.semantic_iri for f in self.features}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "ontology_hash": self.ontology_hash,
            "features": [
                {
                    "feature_id": f.feature_id,
                    "semantic_iri": f.semantic_iri,
                    "value_kind": f.value_kind,
                }
                for f in sorted(self.features, key=lambda f: f.feature_id)
            ],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        )

    @classmethod
    def manufacture(
        cls,
        *,
        ontology_hash: str,
        admitted_iris: Iterable[str],
        value_kind: str = "binary",
    ) -> SemanticFeatureSchema:
        """Manufacture an immutable schema with stable ordering from admitted IRIs."""
        distinct_iris = sorted(set(admitted_iris))
        if not distinct_iris:
            raise ValueError(
                "cannot manufacture feature schema from empty admitted IRI set"
            )

        features = tuple(
            SemanticFeature(
                feature_id=idx,
                semantic_iri=iri,
                value_kind=value_kind,
                description=f"Feature for admitted ontology predicate {iri}",
            )
            for idx, iri in enumerate(distinct_iris)
        )

        payload = {
            "ontology_hash": ontology_hash,
            "features": [
                {
                    "feature_id": f.feature_id,
                    "semantic_iri": f.semantic_iri,
                    "value_kind": f.value_kind,
                }
                for f in features
            ],
        }
        raw_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        schema_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        return cls(
            ontology_hash=ontology_hash,
            features=features,
            feature_schema_hash=schema_hash,
        )

    def vectorize(
        self,
        candidate_or_triples: CandidateGraphDelta | Sequence[SemanticTriple],
    ) -> list[int]:
        """Convert triples to an integer feature vector Z^n. Fails closed on unknown terms."""
        triples = (
            candidate_or_triples.triples
            if isinstance(candidate_or_triples, CandidateGraphDelta)
            else candidate_or_triples
        )
        mapping = self.iri_to_id
        vector = [0] * self.dimension

        for triple in triples:
            if triple.predicate not in mapping:
                raise ValueError(
                    f"fail-closed: unknown predicate {triple.predicate!r} not in feature schema"
                )
            feature_id = mapping[triple.predicate]
            vector[feature_id] += 1

        return vector
