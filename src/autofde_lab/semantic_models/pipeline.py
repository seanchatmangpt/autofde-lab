"""End-to-end O -> Candidate(O*) -> admission -> receipt orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .admission import SemanticAdmissionCourt
from .contracts import AdmissionReceipt, CandidateGraphDelta
from .constrained import parse_candidate_json

CandidateProducer = Callable[[str, str, str], CandidateGraphDelta | str]
CandidateScorer = Callable[[CandidateGraphDelta], float]


@dataclass(frozen=True)
class SemanticPipelineResult:
    candidate: CandidateGraphDelta
    receipt: AdmissionReceipt
    canonical_ntriples: str | None
    advisory_score: float | None = None


class SemanticModelPipeline:
    """Manufacture candidates, optionally rank them, then ask the court for standing."""

    def __init__(
        self,
        *,
        producer: CandidateProducer,
        admission_court: SemanticAdmissionCourt,
        scorer: CandidateScorer | None = None,
    ) -> None:
        self._producer = producer
        self._admission_court = admission_court
        self._scorer = scorer

    def run(
        self,
        *,
        observation: str,
        ontology_context: str,
        provenance_context: str,
    ) -> SemanticPipelineResult:
        produced = self._producer(observation, ontology_context, provenance_context)
        candidate = parse_candidate_json(produced) if isinstance(produced, str) else produced
        score = self._scorer(candidate) if self._scorer is not None else None
        decision = self._admission_court.decide(candidate)
        return SemanticPipelineResult(
            candidate=candidate,
            receipt=decision.receipt,
            canonical_ntriples=decision.canonical_ntriples,
            advisory_score=score,
        )
