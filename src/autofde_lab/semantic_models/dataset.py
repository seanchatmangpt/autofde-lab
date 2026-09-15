"""Manufacture deterministic DSPy/distillation datasets from admitted receipts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

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
