"""Discriminating-probe selection over competing hypotheses.

The planner ranks inert observation/probe candidates. It does not execute the
probe. External probes remain behind a separately admitted broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log2
from typing import Mapping

from .model import digest


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    probe_id: str
    cost: float
    predictions: Mapping[str, str]
    authority_required: str = "NONE"

    def __post_init__(self) -> None:
        if self.cost <= 0:
            raise ValueError("probe cost must be positive")
        if not self.predictions:
            raise ValueError("probe requires predictions for hypotheses")
        if self.authority_required != "NONE":
            raise ValueError("probe candidates are inert SELECT artifacts")

    @property
    def candidate_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class RankedProbe:
    candidate: ProbeCandidate
    information_bits: float
    utility: float


def _entropy(predictions: Mapping[str, str]) -> float:
    counts: dict[str, int] = {}
    for outcome in predictions.values():
        counts[outcome] = counts.get(outcome, 0) + 1
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * log2(probability)
    return entropy


class ProbePlanner:
    """Prefer high-discrimination, low-cost probes."""

    def rank(self, candidates: tuple[ProbeCandidate, ...]) -> tuple[RankedProbe, ...]:
        ranked = [
            RankedProbe(
                candidate=candidate,
                information_bits=_entropy(candidate.predictions),
                utility=_entropy(candidate.predictions) / candidate.cost,
            )
            for candidate in candidates
        ]
        return tuple(
            sorted(
                ranked,
                key=lambda item: (
                    -item.utility,
                    -item.information_bits,
                    item.candidate.probe_id,
                ),
            )
        )

    def select(self, candidates: tuple[ProbeCandidate, ...]) -> RankedProbe:
        ranked = self.rank(candidates)
        if not ranked:
            raise ValueError("no probe candidates")
        return ranked[0]
