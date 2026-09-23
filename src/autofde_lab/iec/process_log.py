"""Deterministic event log for IEC process/conformance analysis.

The log is OCEL-compatible in spirit (events can reference multiple objects),
but this module intentionally does not claim conformance to an external OCEL
serialization schema. A separate adapter may project it to admitted OCEL 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .model import digest


class IECActivity(str, Enum):
    CORPUS_FREEZE = "CORPUS_FREEZE"
    OBSERVE = "OBSERVE"
    PARSE = "PARSE"
    CORRESPONDENCE = "CORRESPONDENCE"
    GENERALIZE = "GENERALIZE"
    FALSIFY = "FALSIFY"
    MANUFACTURE = "MANUFACTURE"
    VALIDATE = "VALIDATE"
    RETIRE_REASONING = "RETIRE_REASONING"
    PROMOTE = "PROMOTE"


@dataclass(frozen=True, slots=True)
class IECEvent:
    sequence: int
    activity: IECActivity
    object_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("event sequence must be non-negative")
        if not self.object_ids:
            raise ValueError("IEC event requires at least one object")

    @property
    def event_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class ProcessConformanceIssue:
    event_id: str
    rule: str
    detail: str

    @property
    def issue_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class IECProcessLog:
    events: tuple[IECEvent, ...]

    @classmethod
    def build(cls, events: Iterable[IECEvent]) -> "IECProcessLog":
        ordered = tuple(sorted(events, key=lambda event: event.sequence))
        sequences = [event.sequence for event in ordered]
        if len(sequences) != len(set(sequences)):
            raise ValueError("duplicate IEC event sequence")
        return cls(ordered)

    @property
    def log_id(self) -> str:
        return digest(self.events)

    def by_object(self, object_id: str) -> tuple[IECEvent, ...]:
        return tuple(event for event in self.events if object_id in event.object_ids)


class IECProcessCourt:
    """Check core process-ordering laws without claiming external execution."""

    _REQUIRES_PRIOR = {
        IECActivity.OBSERVE: {IECActivity.CORPUS_FREEZE},
        IECActivity.PARSE: {IECActivity.OBSERVE},
        IECActivity.CORRESPONDENCE: {IECActivity.OBSERVE},
        IECActivity.GENERALIZE: {IECActivity.CORRESPONDENCE},
        IECActivity.FALSIFY: {IECActivity.CORRESPONDENCE},
        IECActivity.MANUFACTURE: {IECActivity.GENERALIZE},
        IECActivity.VALIDATE: {IECActivity.MANUFACTURE},
        IECActivity.RETIRE_REASONING: {IECActivity.VALIDATE},
        IECActivity.PROMOTE: {IECActivity.VALIDATE},
    }

    def check(self, log: IECProcessLog) -> tuple[ProcessConformanceIssue, ...]:
        issues: list[ProcessConformanceIssue] = []
        prior_by_object: dict[str, set[IECActivity]] = {}

        for event in log.events:
            required = self._REQUIRES_PRIOR.get(event.activity, set())
            for object_id in event.object_ids:
                observed = prior_by_object.setdefault(object_id, set())
                missing = required - observed
                if missing:
                    issues.append(
                        ProcessConformanceIssue(
                            event_id=event.event_id,
                            rule="REQUIRES_PRIOR_ACTIVITY",
                            detail=(
                                f"{event.activity.value} for {object_id} missing "
                                + ",".join(sorted(item.value for item in missing))
                            ),
                        )
                    )
                observed.add(event.activity)

        return tuple(issues)
