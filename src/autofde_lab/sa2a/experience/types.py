"""MachineExperience data model (v26.9.17 ARD §5.7) and its lawful lifecycle.

A MachineExperience is a durable, admitted, compiled result of a solved semantic
class -- never conversation history, model memory, a cached answer, or vector
similarity (PRD §8). It carries provenance back to the exact Episode 1 evidence
that produced it (source_episode_id, source_candidate_digest,
source_admission_receipt), and it lists the identities its validity depends on
(invalidation_set, ARD §12) so a changed dependency makes it ineligible for
automatic KNOWN standing until requalification.

State machine mirrors the existing `autofde_lab.sa2a.algebra.Standing` lifecycle
pattern (a frozen enum + an explicit lawful-transitions table + a
validate_transition() that raises on an unlawful edge) rather than reusing that
enum directly: MachineExperience needs QUALIFIED/ACTIVE/INVALIDATED/SUPERSEDED
states that have no analogue in the generic envelope lifecycle Standing models.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Set


class ExperienceState(str, Enum):
    """Lawful MachineExperience lifecycle states (ARD §5.7)."""

    CANDIDATE = "CANDIDATE"
    ADMITTED = "ADMITTED"
    QUALIFIED = "QUALIFIED"
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"


# CANDIDATE -> ADMITTED -> QUALIFIED -> ACTIVE -> {INVALIDATED, SUPERSEDED}.
# INVALIDATED re-enters at ADMITTED (requalification, ARD §12 -- never skips the
# qualification gate a second time). BLOCKED can retry admission once unblocked,
# mirroring algebra.py's UNKNOWN -> ADMITTED lawful edge. REFUSED/SUPERSEDED are
# terminal: a refused or superseded experience is never silently revived.
LAWFUL_EXPERIENCE_TRANSITIONS: Mapping[ExperienceState, Set[ExperienceState]] = {
    ExperienceState.CANDIDATE: {
        ExperienceState.ADMITTED,
        ExperienceState.REFUSED,
        ExperienceState.BLOCKED,
    },
    ExperienceState.ADMITTED: {
        ExperienceState.QUALIFIED,
        ExperienceState.REFUSED,
        ExperienceState.BLOCKED,
    },
    ExperienceState.QUALIFIED: {
        ExperienceState.ACTIVE,
        ExperienceState.REFUSED,
        ExperienceState.BLOCKED,
    },
    ExperienceState.ACTIVE: {
        ExperienceState.INVALIDATED,
        ExperienceState.SUPERSEDED,
    },
    ExperienceState.INVALIDATED: {
        ExperienceState.ADMITTED,
    },
    ExperienceState.BLOCKED: {
        ExperienceState.ADMITTED,
    },
    ExperienceState.REFUSED: set(),
    ExperienceState.SUPERSEDED: set(),
}


def can_transition_experience(
    current: ExperienceState, target: ExperienceState
) -> bool:
    if current == target:
        return True
    return target in LAWFUL_EXPERIENCE_TRANSITIONS.get(current, set())


def validate_experience_transition(
    current: ExperienceState, target: ExperienceState
) -> None:
    if not can_transition_experience(current, target):
        raise ValueError(
            f"Unlawful MachineExperience transition: cannot go from {current.value} to {target.value}"
        )


@dataclass(frozen=True, slots=True)
class MachineExperience:
    """Durable, admitted result of a solved semantic class (ARD §5.7).

    Immutable by construction, matching every other receipted object in sa2a/
    (PreparedReceipt, AdmissionResult, ...): a state transition produces a NEW
    MachineExperience via `with_state()`, it never mutates one in place -- so a
    reference held by one caller can never observe another caller's transition.
    """

    experience_id: str
    semantic_class_id: str
    source_episode_id: str
    source_candidate_digest: str
    source_admission_receipt: str
    discovery_identity: str
    discovery_resource_receipt: str
    solution_candidate_digest: str
    solution_admission_receipt: str
    compiled_artifact_ids: tuple[str, ...]
    equivalence_predicate_id: str
    # Populated once QUALIFIED (ARD §19); empty for a bare CANDIDATE/ADMITTED experience.
    known_route_id: str = ""
    qualification_receipt: str = ""
    # ARD §12: identities this experience's validity depends on (ontology digest,
    # rule digest, planner/domain digest, authority-contract version, ...). Any one
    # of these changing makes `is_invalidated_by()` True.
    invalidation_set: Mapping[str, str] = field(default_factory=dict)
    state: ExperienceState = ExperienceState.CANDIDATE
    refusal_code: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_state(
        self,
        new_state: ExperienceState,
        *,
        known_route_id: str | None = None,
        qualification_receipt: str | None = None,
        refusal_code: str | None = None,
    ) -> "MachineExperience":
        """Return a new MachineExperience at `new_state`, refusing an unlawful edge."""
        validate_experience_transition(self.state, new_state)
        import dataclasses

        return dataclasses.replace(
            self,
            state=new_state,
            known_route_id=known_route_id
            if known_route_id is not None
            else self.known_route_id,
            qualification_receipt=(
                qualification_receipt
                if qualification_receipt is not None
                else self.qualification_receipt
            ),
            refusal_code=refusal_code
            if refusal_code is not None
            else self.refusal_code,
        )

    def is_invalidated_by(
        self, current_digests: Mapping[str, str]
    ) -> tuple[bool, tuple[str, ...]]:
        """Check every tracked dependency against its current digest (ARD §12).

        Returns (invalidated, changed_keys). A dependency this experience never
        declared is not checked -- invalidation is scoped to what was explicitly
        bound, never inferred from absence (`.claude/rules/absence-is-not-evidence.md`).
        """
        changed = tuple(
            key
            for key, expected in self.invalidation_set.items()
            if current_digests.get(key) != expected
        )
        return (len(changed) > 0, changed)

    @property
    def digest(self) -> str:
        """Content-addressed digest over identity-bearing fields (excludes state/metadata)."""
        payload = {
            "experience_id": self.experience_id,
            "semantic_class_id": self.semantic_class_id,
            "source_episode_id": self.source_episode_id,
            "source_candidate_digest": self.source_candidate_digest,
            "source_admission_receipt": self.source_admission_receipt,
            "discovery_identity": self.discovery_identity,
            "discovery_resource_receipt": self.discovery_resource_receipt,
            "solution_candidate_digest": self.solution_candidate_digest,
            "solution_admission_receipt": self.solution_admission_receipt,
            "compiled_artifact_ids": sorted(self.compiled_artifact_ids),
            "equivalence_predicate_id": self.equivalence_predicate_id,
            "invalidation_set": dict(sorted(self.invalidation_set.items())),
        }
        dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
