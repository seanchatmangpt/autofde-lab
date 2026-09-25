"""Composition root for the first executable IEC slice.

The engine coordinates passive observation, candidate correspondence,
anti-unification, dimensioned translation validation, and reasoning retirement.
It deliberately exposes no filesystem mutation, process execution, network
actuation, merge, deployment, or repository deletion method.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .anti_unification import AntiUnifier, Generalization
from .corpus import CorpusFreezer, CorpusRevision
from .correspondence import CorrespondenceCandidate, CorrespondenceEngine
from .equivalence import EquivalenceCourt
from .model import (
    ArtifactRecord,
    ClaimCeiling,
    EquivalenceDimension,
    Observation,
    RepositorySubject,
    TranslationValidation,
    digest,
)
from .observations import ObservationExtractor, PassiveFile, observation_set_digest
from .retirement import ReasoningClass, RetirementLedger


@dataclass(frozen=True, slots=True)
class RepositoryAnalysis:
    subject: RepositorySubject
    artifacts: tuple[ArtifactRecord, ...]
    observations: tuple[Observation, ...]

    @property
    def analysis_id(self) -> str:
        return digest(
            {
                "subject": self.subject,
                "artifacts": self.artifacts,
                "observation_set": observation_set_digest(self.observations),
            }
        )


@dataclass(frozen=True, slots=True)
class IECSession:
    corpus: CorpusRevision
    analyses: tuple[RepositoryAnalysis, ...]
    correspondence_candidates: tuple[CorrespondenceCandidate, ...] = ()
    generalizations: tuple[Generalization, ...] = ()
    validations: tuple[TranslationValidation, ...] = ()
    reasoning_classes: tuple[ReasoningClass, ...] = ()

    @property
    def session_id(self) -> str:
        return digest(self)


class InverseEcosystemCompiler:
    """Pure SELECT/CONSTRUCT/VERIFY coordinator for IEC experiments."""

    def __init__(
        self,
        *,
        permit_private: bool = False,
        correspondence_threshold: float = 0.55,
        recurrence_threshold: int = 2,
    ) -> None:
        self.corpus = CorpusFreezer(permit_private=permit_private)
        self.observer = ObservationExtractor()
        self.correspondence = CorrespondenceEngine(threshold=correspondence_threshold)
        self.anti_unifier = AntiUnifier()
        self.retirement = RetirementLedger(recurrence_threshold=recurrence_threshold)

    def freeze(self, subjects: Iterable[RepositorySubject]) -> IECSession:
        revision = self.corpus.freeze(subjects)
        return IECSession(corpus=revision, analyses=())

    def observe(
        self,
        session: IECSession,
        subject: RepositorySubject,
        files: Iterable[PassiveFile],
    ) -> IECSession:
        if subject not in session.corpus.subjects:
            raise ValueError("subject is outside the frozen corpus")

        records, observations = self.observer.extract_repository(subject, files)
        analysis = RepositoryAnalysis(
            subject=subject,
            artifacts=records,
            observations=observations,
        )
        analyses_by_repo = {item.subject.repository: item for item in session.analyses}
        analyses_by_repo[subject.repository] = analysis
        analyses = tuple(analyses_by_repo[key] for key in sorted(analyses_by_repo))

        return IECSession(
            corpus=session.corpus,
            analyses=analyses,
            correspondence_candidates=session.correspondence_candidates,
            generalizations=session.generalizations,
            validations=session.validations,
            reasoning_classes=session.reasoning_classes,
        )

    def discover_correspondence(
        self,
        session: IECSession,
        documents: Sequence[tuple[str, str, tuple[str, ...]]],
    ) -> IECSession:
        candidates = self.correspondence.lexical_candidates(documents)
        return IECSession(
            corpus=session.corpus,
            analyses=session.analyses,
            correspondence_candidates=candidates,
            generalizations=session.generalizations,
            validations=session.validations,
            reasoning_classes=session.reasoning_classes,
        )

    def generalize(
        self,
        session: IECSession,
        members: Sequence[Any],
        *,
        member_ids: Sequence[str],
    ) -> IECSession:
        generalization = self.anti_unifier.generalize(
            members,
            member_ids=member_ids,
        )
        return IECSession(
            corpus=session.corpus,
            analyses=session.analyses,
            correspondence_candidates=session.correspondence_candidates,
            generalizations=session.generalizations + (generalization,),
            validations=session.validations,
            reasoning_classes=session.reasoning_classes,
        )

    def validate(
        self,
        session: IECSession,
        *,
        court: EquivalenceCourt,
        original_subject_id: str,
        generated_subject_id: str,
        original: Any,
        generated: Any,
        dimensions: Iterable[EquivalenceDimension],
        claim_ceiling: ClaimCeiling,
    ) -> IECSession:
        result = court.validate(
            original_subject_id=original_subject_id,
            generated_subject_id=generated_subject_id,
            original=original,
            generated=generated,
            dimensions=dimensions,
            claim_ceiling=claim_ceiling,
        )
        return IECSession(
            corpus=session.corpus,
            analyses=session.analyses,
            correspondence_candidates=session.correspondence_candidates,
            generalizations=session.generalizations,
            validations=session.validations + (result,),
            reasoning_classes=session.reasoning_classes,
        )

    def observe_reasoning(
        self,
        session: IECSession,
        *,
        identity: str,
        occurrence_id: str,
        executor: str = "LLM",
    ) -> IECSession:
        self.retirement.observe(identity, occurrence_id, executor=executor)
        return self._with_reasoning(session)

    def bind_reasoning_replacement(
        self,
        session: IECSession,
        *,
        identity: str,
        deterministic_replacement: str,
        verifier_id: str,
    ) -> IECSession:
        self.retirement.bind_replacement(
            identity,
            deterministic_replacement=deterministic_replacement,
            verifier_id=verifier_id,
        )
        return self._with_reasoning(session)

    def retire_reasoning(
        self,
        session: IECSession,
        *,
        identity: str,
        replay_receipt: str,
        equivalent: bool,
    ) -> IECSession:
        self.retirement.verify_replay(
            identity,
            replay_receipt=replay_receipt,
            equivalent=equivalent,
        )
        return self._with_reasoning(session)

    def _with_reasoning(self, session: IECSession) -> IECSession:
        return IECSession(
            corpus=session.corpus,
            analyses=session.analyses,
            correspondence_candidates=session.correspondence_candidates,
            generalizations=session.generalizations,
            validations=session.validations,
            reasoning_classes=self.retirement.entries(),
        )
