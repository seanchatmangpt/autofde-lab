"""Discover semantic manufacture gaps without silently writing residue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .manufacture import ManufactureRequirement, ManufactureRoute, ManufactureRouter
from .model import ArtifactClass, ArtifactRecord, Failure, digest


@dataclass(frozen=True, slots=True)
class GeneratorGap:
    subject_id: str
    path: str
    desired_output_kind: str
    observed_artifact_class: ArtifactClass
    route: ManufactureRoute
    failure: Failure

    @property
    def gap_id(self) -> str:
        return digest(self)


class GeneratorGapDetector:
    """Route candidate generated/unknown artifacts and preserve unsupported gaps."""

    def __init__(
        self,
        router: ManufactureRouter,
        *,
        requirement_for: Callable[[ArtifactRecord], tuple[str, str] | None],
    ) -> None:
        self.router = router
        self.requirement_for = requirement_for

    def detect(
        self,
        artifacts: Iterable[ArtifactRecord],
    ) -> tuple[GeneratorGap, ...]:
        gaps: list[GeneratorGap] = []
        for artifact in artifacts:
            required = self.requirement_for(artifact)
            if required is None:
                continue
            input_kind, output_kind = required
            requirement = ManufactureRequirement(
                input_kind=input_kind,
                output_kind=output_kind,
                subject_id=artifact.subject_id,
                semantic_requirements=(artifact.path,),
            )
            route = self.router.route(requirement)
            if route.routable:
                continue
            failure = route.failure
            if failure is None:
                raise AssertionError("unroutable manufacture route missing failure")
            gaps.append(
                GeneratorGap(
                    subject_id=artifact.subject_id,
                    path=artifact.path,
                    desired_output_kind=output_kind,
                    observed_artifact_class=artifact.artifact_class,
                    route=route,
                    failure=failure,
                )
            )
        return tuple(sorted(gaps, key=lambda gap: (gap.subject_id, gap.path)))


def unknown_source_requirement(
    artifact: ArtifactRecord,
) -> tuple[str, str] | None:
    """Conservative default: unknown source needs an explicit generator capability."""

    if artifact.artifact_class is ArtifactClass.UNKNOWN:
        return "semantic-source", "source-projection"
    return None
