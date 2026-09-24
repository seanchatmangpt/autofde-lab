"""Sandboxed verification intents for build/test/runtime courts.

These are execution requests, not executors. A broker outside this module must
admit and perform any subprocess/network/filesystem consequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .model import ClaimCeiling, EquivalenceDimension, digest


class FilesystemMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    ISOLATED_WRITE = "ISOLATED_WRITE"


@dataclass(frozen=True, slots=True)
class SandboxProfile:
    filesystem: FilesystemMode
    network: bool
    timeout_seconds: int
    cpu_limit: float | None = None
    memory_mb: int | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.cpu_limit is not None and self.cpu_limit <= 0:
            raise ValueError("cpu_limit must be positive")
        if self.memory_mb is not None and self.memory_mb <= 0:
            raise ValueError("memory_mb must be positive")

    @property
    def profile_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class VerificationCommandIntent:
    intent_id_hint: str
    subject_id: str
    verifier_id: str
    dimension: EquivalenceDimension
    argv: tuple[str, ...]
    cwd: str
    sandbox: SandboxProfile
    executable_digest: str | None = None
    environment_digest: str | None = None
    expected_exit_codes: tuple[int, ...] = (0,)
    authority: str = "NONE"

    def __post_init__(self) -> None:
        for value, label in (
            (self.intent_id_hint, "intent_id_hint"),
            (self.subject_id, "subject_id"),
            (self.verifier_id, "verifier_id"),
            (self.cwd, "cwd"),
        ):
            if not value.strip():
                raise ValueError(f"{label} must be non-empty")
        if not self.argv:
            raise ValueError("verification command requires argv")
        if not self.expected_exit_codes:
            raise ValueError("expected_exit_codes must be non-empty")
        if self.authority != "NONE":
            raise ValueError("verification intent carries no execution authority")

    @property
    def intent_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class VerifierSet:
    name: str
    intents: tuple[VerificationCommandIntent, ...]
    claim_ceiling: ClaimCeiling

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("verifier set name must be non-empty")
        if not self.intents:
            raise ValueError("verifier set requires at least one intent")
        ids = [intent.intent_id for intent in self.intents]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate verifier intent")

    @property
    def verifier_set_id(self) -> str:
        return digest(
            {
                "name": self.name,
                "intents": tuple(intent.intent_id for intent in self.intents),
                "claim_ceiling": self.claim_ceiling.value,
            }
        )

    @property
    def dimensions(self) -> tuple[EquivalenceDimension, ...]:
        return tuple(
            sorted(
                {intent.dimension for intent in self.intents},
                key=lambda dimension: dimension.value,
            )
        )


class VerifierSetBuilder:
    """Compose known verification intents without executing them."""

    def build(
        self,
        *,
        name: str,
        intents: Iterable[VerificationCommandIntent],
        claim_ceiling: ClaimCeiling,
    ) -> VerifierSet:
        ordered = tuple(
            sorted(
                intents,
                key=lambda intent: (
                    intent.dimension.value,
                    intent.verifier_id,
                    intent.intent_id,
                ),
            )
        )
        return VerifierSet(name, ordered, claim_ceiling)
