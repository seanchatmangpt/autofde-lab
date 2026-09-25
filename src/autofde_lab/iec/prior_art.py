"""Prior-art novelty court.

The court turns "research before invention" into a deterministic semantic
classification. It is powerless: it may classify required semantics against
declared prior-art candidates but cannot grant execution authority or external
standing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class NoveltyRefusal(ValueError):
    """Typed refusal emitted by the prior-art court."""


class PriorArtDisposition(StrEnum):
    """Bounded extension order."""

    REUSE = "REUSE"
    COMPOSE = "COMPOSE"
    EXTEND = "EXTEND"
    NOVEL_GAP = "NOVEL_GAP"


@dataclass(frozen=True, slots=True)
class PriorArtCandidate:
    """One exact candidate prior-art reference."""

    id: str
    semantics: frozenset[str]
    provenance: str
    exact_subject: str | None = None

    def __post_init__(self) -> None:
        if not self.id.startswith("prior:"):
            raise NoveltyRefusal(f"REFUSED:PRIOR_ART_ID:{self.id}")
        if not self.semantics:
            raise NoveltyRefusal(f"REFUSED:PRIOR_ART_EMPTY_SEMANTICS:{self.id}")
        if not self.provenance:
            raise NoveltyRefusal(f"REFUSED:PRIOR_ART_PROVENANCE:{self.id}")


@dataclass(frozen=True, slots=True)
class CandidateFailure:
    """Why a searched candidate does not satisfy the required semantics."""

    id: str
    missing_semantics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PriorArtVerdict:
    """Deterministic court result."""

    required_semantics: tuple[str, ...]
    searched: tuple[str, ...]
    selected: tuple[str, ...]
    disposition: PriorArtDisposition
    residual: tuple[str, ...]
    failures: tuple[CandidateFailure, ...]
    standing: str = "NONE"
    authority: str = "NONE"

    @property
    def novelty_claimed(self) -> bool:
        """Whether the verdict reaches the irreducible-invention boundary."""

        return self.disposition is PriorArtDisposition.NOVEL_GAP


def _normalized(values: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(value.strip() for value in values if value.strip())
    if not normalized:
        raise NoveltyRefusal("REFUSED:REQUIRED_SEMANTICS_MISSING")
    return normalized


def classify_prior_art(
    required_semantics: Iterable[str],
    candidates: Iterable[PriorArtCandidate],
) -> PriorArtVerdict:
    """Classify required semantics under reuse -> compose -> extend -> invent.

    REUSE:
        One candidate covers the requirement.
    COMPOSE:
        Multiple candidates together cover the requirement.
    EXTEND:
        Candidate prior art covers at least one required semantic, but a
        residual remains.
    NOVEL_GAP:
        No searched candidate covers any required semantic. This is the only
        result that authorizes a *candidate* novelty claim, and it still grants
        no truth, authority, execution, or standing.
    """

    required = _normalized(required_semantics)
    candidate_list = tuple(candidates)
    if not candidate_list:
        raise NoveltyRefusal("REFUSED:PRIOR_ART_SEARCH_MISSING")

    ids = [candidate.id for candidate in candidate_list]
    if len(ids) != len(set(ids)):
        raise NoveltyRefusal("REFUSED:DUPLICATE_PRIOR_ART_CANDIDATE")

    failures = tuple(
        CandidateFailure(
            id=candidate.id,
            missing_semantics=tuple(sorted(required - candidate.semantics)),
        )
        for candidate in candidate_list
        if not required.issubset(candidate.semantics)
    )

    complete = [
        candidate for candidate in candidate_list if required.issubset(candidate.semantics)
    ]
    if complete:
        selected = min(complete, key=lambda item: (len(item.semantics), item.id))
        return PriorArtVerdict(
            required_semantics=tuple(sorted(required)),
            searched=tuple(ids),
            selected=(selected.id,),
            disposition=PriorArtDisposition.REUSE,
            residual=(),
            failures=failures,
        )

    union: frozenset[str] = frozenset().union(
        *(candidate.semantics for candidate in candidate_list)
    )
    if required.issubset(union):
        remaining = set(required)
        selected_ids: list[str] = []
        # Deterministic greedy set cover. This is only selection of candidate
        # prior art; it is not a proof of semantic equivalence.
        pool = list(candidate_list)
        while remaining:
            ranked = sorted(
                pool,
                key=lambda item: (
                    -len(remaining & item.semantics),
                    item.id,
                ),
            )
            best = ranked[0]
            gain = remaining & best.semantics
            if not gain:
                raise NoveltyRefusal("REFUSED:PRIOR_ART_COMPOSITION_STALLED")
            selected_ids.append(best.id)
            remaining -= gain
            pool.remove(best)

        return PriorArtVerdict(
            required_semantics=tuple(sorted(required)),
            searched=tuple(ids),
            selected=tuple(selected_ids),
            disposition=PriorArtDisposition.COMPOSE,
            residual=(),
            failures=failures,
        )

    covered = required & union
    residual = required - union
    if covered:
        selected = tuple(
            candidate.id
            for candidate in candidate_list
            if candidate.semantics & required
        )
        return PriorArtVerdict(
            required_semantics=tuple(sorted(required)),
            searched=tuple(ids),
            selected=selected,
            disposition=PriorArtDisposition.EXTEND,
            residual=tuple(sorted(residual)),
            failures=failures,
        )

    return PriorArtVerdict(
        required_semantics=tuple(sorted(required)),
        searched=tuple(ids),
        selected=(),
        disposition=PriorArtDisposition.NOVEL_GAP,
        residual=tuple(sorted(required)),
        failures=failures,
    )


def assert_novelty_receipt(verdict: PriorArtVerdict) -> None:
    """Fail closed if a NOVEL_GAP verdict lacks discharged candidate failures."""

    if verdict.disposition is not PriorArtDisposition.NOVEL_GAP:
        raise NoveltyRefusal("REFUSED:VERDICT_IS_NOT_NOVEL_GAP")
    if verdict.selected:
        raise NoveltyRefusal("REFUSED:NOVELTY_WITH_SELECTED_PRIOR_ART")

    failed = {failure.id for failure in verdict.failures}
    if set(verdict.searched) != failed:
        raise NoveltyRefusal("REFUSED:NOVELTY_SEARCH_NOT_DISCHARGED")
    if not verdict.residual:
        raise NoveltyRefusal("REFUSED:NOVELTY_WITHOUT_RESIDUAL")
    for failure in verdict.failures:
        if not failure.missing_semantics:
            raise NoveltyRefusal(
                f"REFUSED:NOVELTY_FAILURE_UNTYPED:{failure.id}"
            )
