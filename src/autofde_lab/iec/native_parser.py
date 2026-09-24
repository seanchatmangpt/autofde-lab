"""Brokered native-parser intents for languages not parsed in-process.

IEC should use a mature language-native parser rather than regex when one is
available. This registry describes those parser capabilities but does not run
them or claim they are installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .model import digest


class ParserCapabilityStanding(str, Enum):
    CANDIDATE = "CANDIDATE"
    ADMITTED = "ADMITTED"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class NativeParserCapability:
    capability_id: str
    language: str
    suffixes: tuple[str, ...]
    tool_identity: str
    tool_revision: str | None
    output_contract: str
    standing: ParserCapabilityStanding
    evidence_ids: tuple[str, ...] = ()

    @property
    def capability_identity(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class NativeParserIntent:
    capability_identity: str
    subject_id: str
    source_path: str
    source_digest: str
    tool_identity: str
    tool_revision: str | None
    output_contract: str
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if self.authority != "NONE":
            raise ValueError("native parser intent carries no execution authority")

    @property
    def intent_id(self) -> str:
        return digest(self)


class NativeParserRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, NativeParserCapability] = {}

    def register(self, capability: NativeParserCapability) -> None:
        if capability.capability_id in self._capabilities:
            raise ValueError(f"duplicate parser capability: {capability.capability_id}")
        self._capabilities[capability.capability_id] = capability

    def intent_for(
        self,
        *,
        suffix: str,
        subject_id: str,
        source_path: str,
        source_digest: str,
    ) -> NativeParserIntent | None:
        suffix = suffix.lower()
        candidates = [
            capability
            for capability in self._capabilities.values()
            if suffix in capability.suffixes
            and capability.standing
            in {ParserCapabilityStanding.ADMITTED, ParserCapabilityStanding.ALIVE}
        ]
        if not candidates:
            return None
        standing_rank = {
            ParserCapabilityStanding.ALIVE: 0,
            ParserCapabilityStanding.ADMITTED: 1,
        }
        selected = sorted(
            candidates,
            key=lambda capability: (
                standing_rank[capability.standing],
                capability.capability_id,
            ),
        )[0]
        return NativeParserIntent(
            capability_identity=selected.capability_identity,
            subject_id=subject_id,
            source_path=source_path,
            source_digest=source_digest,
            tool_identity=selected.tool_identity,
            tool_revision=selected.tool_revision,
            output_contract=selected.output_contract,
        )

    def capabilities(self) -> tuple[NativeParserCapability, ...]:
        return tuple(
            self._capabilities[key] for key in sorted(self._capabilities)
        )


def candidate_native_parsers() -> tuple[NativeParserCapability, ...]:
    """Candidate prior-art adapters; not admitted until independently observed."""

    return (
        NativeParserCapability(
            capability_id="elixir/code-string-to-quoted",
            language="elixir",
            suffixes=(".ex", ".exs"),
            tool_identity="Elixir.Code.string_to_quoted",
            tool_revision=None,
            output_contract="elixir-quoted-ast/v1",
            standing=ParserCapabilityStanding.CANDIDATE,
        ),
        NativeParserCapability(
            capability_id="rust/rust-analyzer-syntax",
            language="rust",
            suffixes=(".rs",),
            tool_identity="rust-analyzer",
            tool_revision=None,
            output_contract="rust-syntax-tree/v1",
            standing=ParserCapabilityStanding.CANDIDATE,
        ),
    )
