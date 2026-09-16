"""Closed-loop semantic model manufacturing cycle.

Observation -> Candidate -> Court -> Receipt -> Experience -> Dataset -> Optimize -> Qualify -> O*
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .admission import SemanticAdmissionCourt
from .contracts import (
    AdmissionReceipt,
    CandidateGraphDelta,
    ModelQualificationRecord,
    OptimizationReceipt,
)
from .dataset import ExperienceRecord, ManufacturedDataset, manufacture_dataset
from .distillation import qualify_model_candidate
from .sklearn_search import fit_and_receipt_baseline


@dataclass(frozen=True)
class ClosedManufacturingCycleResult:
    """End-to-end receipt-bearing artifact of a complete closed manufacturing pass."""

    admission_receipts: list[AdmissionReceipt]
    dataset: ManufacturedDataset
    optimization_receipts: list[OptimizationReceipt]
    qualification_records: list[ModelQualificationRecord]
    winning_candidate_id: str


def run_closed_manufacturing_cycle(
    *,
    observations: Sequence[
        tuple[str, str, str]
    ],  # (obs, ontology_context, provenance_context)
    producers: dict[str, Callable[[str, str], CandidateGraphDelta | str]],
    gold_generator: Callable[[str, str], CandidateGraphDelta],
    court: SemanticAdmissionCourt,
    known_predicates: set[str] | frozenset[str],
    ontology_hash: str,
    cost_table: dict[str, float] | None = None,
) -> ClosedManufacturingCycleResult:
    """Execute the closed manufacturing cycle with exact cryptographic replay receipts."""
    costs = cost_table or {
        "teacher": 0.001,
        "student": 0.0001,
        "statistical_pipeline": 0.00001,
    }

    # 1. Experience Generation & Admission Court
    experiences: list[ExperienceRecord] = []
    admission_receipts: list[AdmissionReceipt] = []

    for obs, ont, _ in observations:
        # Generate proposal from primary/gold generator
        candidate = gold_generator(obs, ont)
        receipt, _ = court.admit(candidate)
        admission_receipts.append(receipt)
        experiences.append(
            ExperienceRecord(
                observation=obs,
                ontology_context=ont,
                candidate=candidate,
                receipt=receipt,
            )
        )

    # 2. Deterministic Dataset Manufacture
    dataset = manufacture_dataset(experiences, ontology_hash=ontology_hash)

    # 3. Statistical Baseline Optimization & Receipt
    candidates_list: list[CandidateGraphDelta] = [e.candidate for e in experiences]
    labels: list[int] = [
        1 if e.receipt.standing.value == "ADMITTED" else 0 for e in experiences
    ]

    opt_receipts: list[OptimizationReceipt] = []
    if len(set(labels)) >= 2:
        try:
            _, base_opt_receipt = fit_and_receipt_baseline(
                candidates_list,
                labels,
                known_predicates=known_predicates,
                dataset_hash=dataset.dataset_hash,
                ontology_hash=ontology_hash,
            )
            opt_receipts.append(base_opt_receipt)
        except RuntimeError:
            # scikit-learn is an optional dependency boundary
            pass

    # 4. Comparative Court Qualification
    qualification_records: list[ModelQualificationRecord] = []
    if dataset.gold_examples:
        for candidate_id, producer_fn in producers.items():
            role = (
                "teacher"
                if "teacher" in candidate_id.lower()
                else "student"
                if "student" in candidate_id.lower()
                else "statistical_pipeline"
            )
            cost = costs.get(role, 0.0001)
            record = qualify_model_candidate(
                candidate_id=candidate_id,
                model_role=role,
                producer=producer_fn,
                eval_examples=dataset.gold_examples,
                court=court,
                known_predicates=known_predicates,
                cost_per_1k_tokens=cost,
            )
            qualification_records.append(record)

    # 5. Envelope Selection: cheapest admissible candidate
    admissible = [r for r in qualification_records if r.admissible]
    if admissible:
        winning = min(
            admissible, key=lambda r: (r.cost_per_1k_tokens, -r.graph_exactness)
        )
        winning_id = winning.candidate_id
    else:
        winning_id = (
            qualification_records[0].candidate_id if qualification_records else "none"
        )

    return ClosedManufacturingCycleResult(
        admission_receipts=admission_receipts,
        dataset=dataset,
        optimization_receipts=opt_receipts,
        qualification_records=qualification_records,
        winning_candidate_id=winning_id,
    )
