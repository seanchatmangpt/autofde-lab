"""GALL-010 explicit partial observability for planning inputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class EpistemicValue(str, Enum):
    KNOWN_TRUE = "KNOWN_TRUE"
    KNOWN_FALSE = "KNOWN_FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class InformationAction:
    fact: str
    action_id: str


@dataclass(frozen=True, slots=True)
class BeliefState:
    facts: Mapping[str, EpistemicValue]
    observation_projection: str
    provenance_digest: str

    @property
    def digest(self) -> str:
        payload = {
            "facts": {key: value.value for key, value in sorted(self.facts.items())},
            "observation_projection": self.observation_projection,
            "provenance_digest": self.provenance_digest,
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def require(self, requirements: Mapping[str, bool]) -> tuple[bool, tuple[str, ...]]:
        unknown: list[str] = []
        for fact, expected in requirements.items():
            value = self.facts.get(fact, EpistemicValue.UNKNOWN)
            if value is EpistemicValue.UNKNOWN:
                unknown.append(fact)
                continue
            actual = value is EpistemicValue.KNOWN_TRUE
            if actual != expected:
                return False, tuple(unknown)
        return not unknown, tuple(unknown)

    def information_actions(
        self,
        requirements: Mapping[str, bool],
        *,
        prefix: str = "observe",
    ) -> tuple[InformationAction, ...]:
        _, unknown = self.require(requirements)
        return tuple(InformationAction(fact=fact, action_id=f"{prefix}:{fact}") for fact in unknown)

    def observe(self, fact: str, value: bool) -> "BeliefState":
        next_facts = dict(self.facts)
        next_facts[fact] = (
            EpistemicValue.KNOWN_TRUE if value else EpistemicValue.KNOWN_FALSE
        )
        return BeliefState(
            facts=next_facts,
            observation_projection=self.observation_projection,
            provenance_digest=self.provenance_digest,
        )

    def to_fond_atoms(self) -> tuple[str, ...]:
        atoms: list[str] = []
        for fact, value in sorted(self.facts.items()):
            if value is EpistemicValue.KNOWN_TRUE:
                atoms.append(f"known_true({fact})")
            elif value is EpistemicValue.KNOWN_FALSE:
                atoms.append(f"known_false({fact})")
            else:
                atoms.append(f"unknown({fact})")
        return tuple(atoms)
