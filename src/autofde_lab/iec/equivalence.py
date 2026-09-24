"""Dimensioned translation-validation courts.

The translator never certifies itself. Callers register verifier functions,
then the court binds verifier identity, exact subjects, results, and any
counterexamples into an immutable TranslationValidation object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .model import (
    ClaimCeiling,
    Counterexample,
    EquivalenceDimension,
    TranslationValidation,
    digest,
)

Verifier = Callable[[Any, Any], tuple[bool, Any, Any, str]]


@dataclass(frozen=True, slots=True)
class VerifierSpec:
    verifier_id: str
    dimension: EquivalenceDimension
    verifier: Verifier

    @property
    def spec_id(self) -> str:
        # Function bytecode is deliberately not treated as portable identity.
        # Version verifier_id whenever verifier semantics change.
        return digest(
            {
                "verifier_id": self.verifier_id,
                "dimension": self.dimension.value,
            }
        )


class EquivalenceCourt:
    """Translation validation over explicitly registered dimensions."""

    def __init__(self) -> None:
        self._verifiers: dict[EquivalenceDimension, VerifierSpec] = {}

    def register(
        self,
        dimension: EquivalenceDimension,
        verifier_id: str,
        verifier: Verifier,
    ) -> None:
        if dimension in self._verifiers:
            raise ValueError(f"verifier already registered for {dimension.value}")
        if not verifier_id.strip():
            raise ValueError("verifier_id must be non-empty")
        self._verifiers[dimension] = VerifierSpec(
            verifier_id=verifier_id.strip(),
            dimension=dimension,
            verifier=verifier,
        )

    @property
    def verifier_set_id(self) -> str:
        if not self._verifiers:
            raise ValueError("empty verifier set has no equivalence meaning")
        return digest(
            [
                self._verifiers[dimension].spec_id
                for dimension in sorted(
                    self._verifiers, key=lambda item: item.value
                )
            ]
        )

    def validate(
        self,
        *,
        original_subject_id: str,
        generated_subject_id: str,
        original: Any,
        generated: Any,
        dimensions: Iterable[EquivalenceDimension],
        claim_ceiling: ClaimCeiling,
    ) -> TranslationValidation:
        ordered_dimensions = tuple(
            sorted(set(dimensions), key=lambda dimension: dimension.value)
        )
        if not ordered_dimensions:
            raise ValueError("at least one equivalence dimension is required")

        counterexamples: list[Counterexample] = []
        receipts: list[str] = []

        for dimension in ordered_dimensions:
            spec = self._verifiers.get(dimension)
            if spec is None:
                raise KeyError(
                    f"UNSUPPORTED_EQUIVALENCE_DIMENSION:{dimension.value}"
                )

            passed, expected, actual, detail = spec.verifier(original, generated)
            receipt = digest(
                {
                    "verifier": spec.spec_id,
                    "original_subject_id": original_subject_id,
                    "generated_subject_id": generated_subject_id,
                    "dimension": dimension.value,
                    "passed": bool(passed),
                    "expected": expected,
                    "actual": actual,
                    "detail": detail,
                }
            )
            receipts.append(receipt)

            if not passed:
                counterexamples.append(
                    Counterexample(
                        hypothesis_id=digest(
                            {
                                "original": original_subject_id,
                                "generated": generated_subject_id,
                                "dimension": dimension.value,
                            }
                        ),
                        dimension=dimension,
                        verifier_id=spec.verifier_id,
                        expected=expected,
                        actual=actual,
                        detail=detail or f"{dimension.value} mismatch",
                        evidence_ids=(receipt,),
                    )
                )

        return TranslationValidation(
            original_subject_id=original_subject_id,
            generated_subject_id=generated_subject_id,
            verifier_set_id=self.verifier_set_id,
            dimensions=ordered_dimensions,
            claim_ceiling=claim_ceiling,
            passed=not counterexamples,
            counterexamples=tuple(counterexamples),
            verifier_receipts=tuple(receipts),
        )


def exact_equality_verifier(
    original: Any, generated: Any
) -> tuple[bool, Any, Any, str]:
    """Structural verifier; never substitute it for behavioral equivalence."""
    passed = original == generated
    return (
        passed,
        original,
        generated,
        "exact structural equality" if passed else "structural values differ",
    )


def mapping_keys_verifier(
    original: Mapping[str, Any], generated: Mapping[str, Any]
) -> tuple[bool, Any, Any, str]:
    """Verify only the public mapping key surface."""
    left = tuple(sorted(original))
    right = tuple(sorted(generated))
    return left == right, left, right, "public mapping key surface"
