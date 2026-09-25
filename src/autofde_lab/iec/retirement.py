"""Retirement ledger for repeated semantic reasoning classes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .model import digest


class RetirementStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    OBSERVED_ONCE = "OBSERVED_ONCE"
    REPEATED = "REPEATED"
    MECHANIZATION_CANDIDATE = "MECHANIZATION_CANDIDATE"
    MECHANIZED = "MECHANIZED"
    RETIRED_FROM_LLM = "RETIRED_FROM_LLM"


@dataclass(frozen=True, slots=True)
class ReasoningClass:
    identity: str
    occurrence_ids: tuple[str, ...]
    current_executor: str
    deterministic_replacement: str | None = None
    verifier_id: str | None = None
    replay_receipt: str | None = None
    status: RetirementStatus = RetirementStatus.UNKNOWN

    @property
    def reasoning_class_id(self) -> str:
        return digest(
            {
                "identity": self.identity,
                "current_executor": self.current_executor,
            }
        )

    @property
    def recurrence_count(self) -> int:
        return len(set(self.occurrence_ids))


class RetirementLedger:
    """Append-by-value ledger with fail-closed retirement transitions."""

    def __init__(self, *, recurrence_threshold: int = 2) -> None:
        if recurrence_threshold < 2:
            raise ValueError("recurrence_threshold must be >= 2")
        self.recurrence_threshold = recurrence_threshold
        self._entries: dict[str, ReasoningClass] = {}

    def observe(
        self,
        identity: str,
        occurrence_id: str,
        *,
        executor: str = "LLM",
    ) -> ReasoningClass:
        if not identity.strip() or not occurrence_id.strip():
            raise ValueError("identity and occurrence_id must be non-empty")
        current = self._entries.get(identity)
        if current is None:
            next_entry = ReasoningClass(
                identity=identity,
                occurrence_ids=(occurrence_id,),
                current_executor=executor,
                status=RetirementStatus.OBSERVED_ONCE,
            )
        else:
            occurrences = tuple(sorted(set(current.occurrence_ids + (occurrence_id,))))
            status = current.status
            if len(occurrences) >= self.recurrence_threshold:
                if status in {
                    RetirementStatus.UNKNOWN,
                    RetirementStatus.OBSERVED_ONCE,
                }:
                    status = RetirementStatus.MECHANIZATION_CANDIDATE
                elif status is RetirementStatus.REPEATED:
                    status = RetirementStatus.MECHANIZATION_CANDIDATE
            elif len(occurrences) > 1:
                status = RetirementStatus.REPEATED

            next_entry = replace(
                current,
                occurrence_ids=occurrences,
                status=status,
            )
        self._entries[identity] = next_entry
        return next_entry

    def bind_replacement(
        self,
        identity: str,
        *,
        deterministic_replacement: str,
        verifier_id: str,
    ) -> ReasoningClass:
        current = self._require(identity)
        if current.recurrence_count < self.recurrence_threshold:
            raise ValueError("reasoning class has not recurred enough to mechanize")
        if not deterministic_replacement.strip() or not verifier_id.strip():
            raise ValueError("replacement and verifier_id must be non-empty")
        next_entry = replace(
            current,
            deterministic_replacement=deterministic_replacement,
            verifier_id=verifier_id,
            status=RetirementStatus.MECHANIZED,
        )
        self._entries[identity] = next_entry
        return next_entry

    def verify_replay(
        self,
        identity: str,
        *,
        replay_receipt: str,
        equivalent: bool,
    ) -> ReasoningClass:
        current = self._require(identity)
        if current.status is not RetirementStatus.MECHANIZED:
            raise ValueError("reasoning class must be mechanized before replay")
        if not equivalent:
            return current
        if not replay_receipt.strip():
            raise ValueError("equivalent replay requires receipt identity")
        next_entry = replace(
            current,
            replay_receipt=replay_receipt,
            status=RetirementStatus.RETIRED_FROM_LLM,
        )
        self._entries[identity] = next_entry
        return next_entry

    def _require(self, identity: str) -> ReasoningClass:
        try:
            return self._entries[identity]
        except KeyError as exc:
            raise KeyError(f"unknown reasoning class: {identity}") from exc

    def entries(self) -> tuple[ReasoningClass, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    @property
    def ledger_id(self) -> str:
        return digest(self.entries())
