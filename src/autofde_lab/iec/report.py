"""Structured IEC run report projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import Failure, TranslationValidation, digest
from .receipts import IECReceipt
from .retirement import ReasoningClass


@dataclass(frozen=True, slots=True)
class RunReport:
    corpus_revision_id: str
    exact_subject_ids: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    failure_ids: tuple[str, ...]
    reasoning_class_ids: tuple[str, ...]
    generated_artifact_ids: tuple[str, ...] = ()
    handwritten_residue_ids: tuple[str, ...] = ()
    external_do_observed: bool = False

    def __post_init__(self) -> None:
        if self.external_do_observed:
            raise ValueError(
                "IEC report cannot certify external DO; use BRCE consequence evidence"
            )

    @property
    def report_id(self) -> str:
        return digest(self)


class ReportBuilder:
    def build(
        self,
        *,
        corpus_revision_id: str,
        exact_subject_ids: Iterable[str],
        receipts: Iterable[IECReceipt] = (),
        validations: Iterable[TranslationValidation] = (),
        failures: Iterable[Failure] = (),
        reasoning_classes: Iterable[ReasoningClass] = (),
        generated_artifact_ids: Iterable[str] = (),
        handwritten_residue_ids: Iterable[str] = (),
    ) -> RunReport:
        return RunReport(
            corpus_revision_id=corpus_revision_id,
            exact_subject_ids=tuple(sorted(set(exact_subject_ids))),
            receipt_ids=tuple(sorted(receipt.receipt_id for receipt in receipts)),
            validation_ids=tuple(
                sorted(validation.validation_id for validation in validations)
            ),
            failure_ids=tuple(sorted(failure.failure_id for failure in failures)),
            reasoning_class_ids=tuple(
                sorted(item.reasoning_class_id for item in reasoning_classes)
            ),
            generated_artifact_ids=tuple(sorted(set(generated_artifact_ids))),
            handwritten_residue_ids=tuple(sorted(set(handwritten_residue_ids))),
        )
