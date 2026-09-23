"""Evidence contracts for SANY/TLC/TLAPS or equivalent formal tools.

IEC may construct verification intents and normalize already-observed evidence.
It does not execute the external tools here and cannot infer a PASS from the
existence of a TLA+ projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import digest
from .tla_projection import TlaProjection


class FormalResult(str, Enum):
    PASS = "PASS"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    TOOL_ERROR = "TOOL_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FormalVerificationIntent:
    projection_id: str
    tool_identity: str
    tool_version: str
    executable_digest: str
    argv: tuple[str, ...]
    authority: str = "NONE"

    def __post_init__(self) -> None:
        for value, label in (
            (self.projection_id, "projection_id"),
            (self.tool_identity, "tool_identity"),
            (self.tool_version, "tool_version"),
            (self.executable_digest, "executable_digest"),
        ):
            if not value.strip():
                raise ValueError(f"{label} must be non-empty")
        if not self.argv:
            raise ValueError("formal verification intent requires argv")
        if self.authority != "NONE":
            raise ValueError("formal verification intent has no external authority")

    @property
    def intent_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class FormalCounterexampleTrace:
    property_name: str
    state_digests: tuple[str, ...]
    trace_digest: str

    @classmethod
    def from_states(
        cls,
        property_name: str,
        state_digests: tuple[str, ...],
    ) -> "FormalCounterexampleTrace":
        if not property_name.strip() or not state_digests:
            raise ValueError("counterexample trace requires property and states")
        return cls(
            property_name=property_name,
            state_digests=state_digests,
            trace_digest=digest(
                {
                    "property_name": property_name,
                    "state_digests": state_digests,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class FormalVerificationEvidence:
    intent_id: str
    projection_id: str
    exit_code: int
    result: FormalResult
    properties_checked: tuple[str, ...]
    stdout_digest: str
    stderr_digest: str
    states_generated: int | None = None
    distinct_states: int | None = None
    counterexample: FormalCounterexampleTrace | None = None

    def __post_init__(self) -> None:
        if not self.properties_checked:
            raise ValueError("formal evidence requires named checked properties")
        if self.result is FormalResult.PASS:
            if self.exit_code != 0:
                raise ValueError("PASS requires exit code 0")
            if self.counterexample is not None:
                raise ValueError("PASS cannot contain counterexample")
        if self.result is FormalResult.COUNTEREXAMPLE and self.counterexample is None:
            raise ValueError("COUNTEREXAMPLE result requires trace")
        for value in (self.states_generated, self.distinct_states):
            if value is not None and value < 0:
                raise ValueError("state counts must be non-negative")

    @property
    def evidence_id(self) -> str:
        return digest(self)


def make_tlc_intent(
    projection: TlaProjection,
    *,
    tool_version: str,
    executable_digest: str,
    module_path: str,
    config_path: str,
) -> FormalVerificationIntent:
    return FormalVerificationIntent(
        projection_id=projection.projection_id,
        tool_identity="tlc2.TLC",
        tool_version=tool_version,
        executable_digest=executable_digest,
        argv=(
            "java",
            "tlc2.TLC",
            "-config",
            config_path,
            module_path,
        ),
    )
