"""Reusable deterministic falsifier court.

Falsifiers convert hypotheses into observations that can reject them. A passing
falsifier means only that this particular falsification attempt did not reject
the claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .model import digest

Check = Callable[[Any], tuple[bool, str]]


@dataclass(frozen=True, slots=True)
class Falsifier:
    falsifier_id: str
    description: str
    check: Check

    def __post_init__(self) -> None:
        if not self.falsifier_id.strip() or not self.description.strip():
            raise ValueError("falsifier requires identity and description")


@dataclass(frozen=True, slots=True)
class FalsifierResult:
    falsifier_id: str
    rejected: bool
    detail: str
    subject_digest: str

    @property
    def result_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class FalsificationReport:
    subject_digest: str
    results: tuple[FalsifierResult, ...]

    @property
    def rejected(self) -> bool:
        return any(result.rejected for result in self.results)

    @property
    def report_id(self) -> str:
        return digest(self)


class FalsifierCourt:
    def run(
        self,
        subject: Any,
        falsifiers: Iterable[Falsifier],
    ) -> FalsificationReport:
        subject_digest = digest(subject)
        results: list[FalsifierResult] = []
        for falsifier in sorted(falsifiers, key=lambda item: item.falsifier_id):
            rejected, detail = falsifier.check(subject)
            results.append(
                FalsifierResult(
                    falsifier_id=falsifier.falsifier_id,
                    rejected=bool(rejected),
                    detail=detail,
                    subject_digest=subject_digest,
                )
            )
        if not results:
            raise ValueError("falsification report requires at least one falsifier")
        return FalsificationReport(subject_digest, tuple(results))
