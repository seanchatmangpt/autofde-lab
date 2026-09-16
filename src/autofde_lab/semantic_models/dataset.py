"""Manufacture deterministic DSPy/distillation datasets from admitted receipts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .contracts import (
    AdmissionReceipt,
    AdmissionStanding,
    CandidateGraphDelta,
    SemanticExample,
)


def example_from_admission(
    *,
    observation: str,
    ontology_context: str,
    candidate: CandidateGraphDelta,
    receipt: AdmissionReceipt,
) -> SemanticExample:
    if receipt.standing is not AdmissionStanding.ADMITTED:
        raise ValueError("refused candidates may not become semantic training examples")
    if receipt.candidate_hash != candidate.candidate_hash:
        raise ValueError("receipt does not witness this candidate revision")
    return SemanticExample(
        observation=observation,
        ontology_context=ontology_context,
        expected_delta=candidate,
        admission_receipt_id=receipt.receipt_id,
    )


def export_jsonl(examples: Iterable[SemanticExample], path: str | Path) -> Path:
    """Write a byte-stable JSONL corpus ordered by receipt identity."""
    path = Path(path)
    ordered = sorted(examples, key=lambda item: item.admission_receipt_id)
    lines = [
        json.dumps(
            example.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        for example in ordered
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def distillation_records(examples: Iterable[SemanticExample]) -> list[dict[str, str]]:
    """Create teacher/student records without making natural language authoritative."""
    records: list[dict[str, str]] = []
    for example in sorted(examples, key=lambda item: item.admission_receipt_id):
        records.append(
            {
                "observation": example.observation,
                "ontology_context": example.ontology_context,
                "target_json": example.expected_delta.canonical_json(),
                "receipt_id": example.admission_receipt_id,
            }
        )
    return records


class ExperienceRecord(BaseModel):
    """Raw experience unit pairing an observation, candidate delta, and court receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation: str
    ontology_context: str
    candidate: CandidateGraphDelta
    receipt: AdmissionReceipt


class ManufacturedDataset(BaseModel):
    """Partitioned dataset manufactured from verified admission experience."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_hash: str
    ontology_hash: str
    gold_examples: list[SemanticExample]
    contrastive_examples: list[dict[str, Any]]
    manifest: dict[str, Any]


def manufacture_dataset(
    experiences: Iterable[ExperienceRecord],
    *,
    ontology_hash: str,
) -> ManufacturedDataset:
    """Deterministically partition experience into gold and contrastive sets with SHA-256 manifest."""
    gold: list[SemanticExample] = []
    contrastive: list[dict[str, Any]] = []

    for exp in sorted(experiences, key=lambda e: e.receipt.receipt_id):
        if exp.receipt.standing is AdmissionStanding.ADMITTED:
            gold.append(
                example_from_admission(
                    observation=exp.observation,
                    ontology_context=exp.ontology_context,
                    candidate=exp.candidate,
                    receipt=exp.receipt,
                )
            )
        else:
            contrastive.append(
                {
                    "observation": exp.observation,
                    "ontology_context": exp.ontology_context,
                    "refused_delta_json": exp.candidate.canonical_json(),
                    "receipt_id": exp.receipt.receipt_id,
                    "reasons": list(exp.receipt.reasons),
                }
            )

    serialized_gold = [g.model_dump(mode="json") for g in gold]
    manifest_payload = {
        "ontology_hash": ontology_hash,
        "gold_count": len(gold),
        "contrastive_count": len(contrastive),
        "gold_receipt_ids": [g.admission_receipt_id for g in gold],
        "contrastive_receipt_ids": [c["receipt_id"] for c in contrastive],
    }
    raw_for_hash = json.dumps(
        {"manifest": manifest_payload, "gold": serialized_gold},
        sort_keys=True,
        separators=(",", ":"),
    )
    dataset_hash = hashlib.sha256(raw_for_hash.encode("utf-8")).hexdigest()

    return ManufacturedDataset(
        dataset_hash=dataset_hash,
        ontology_hash=ontology_hash,
        gold_examples=gold,
        contrastive_examples=contrastive,
        manifest=manifest_payload,
    )
