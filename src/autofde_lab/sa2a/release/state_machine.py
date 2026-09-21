"""ReleaseState: the release-level state machine (PRD §12), separate from
`autofde_lab.sa2a.algebra.Standing` (which models one semantic envelope's ADM/DO
lifecycle, a different and narrower scope -- ARD §5.9's `Episode.standing` already
reuses that enum; this file is the release-scoped wrapper PRD §12 asks for on top
of it).
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Set


class ReleaseState(str, Enum):
    CREATED = "CREATED"
    SUBJECT_FENCED = "SUBJECT_FENCED"
    PREFLIGHTED = "PREFLIGHTED"
    EPISODE_1_RUNNING = "EPISODE_1_RUNNING"
    EPISODE_1_VERIFIED = "EPISODE_1_VERIFIED"
    EXPERIENCE_ADMITTED = "EXPERIENCE_ADMITTED"
    EPISODE_2_RUNNING = "EPISODE_2_RUNNING"
    EPISODE_2_VERIFIED = "EPISODE_2_VERIFIED"
    CHICAGO_RUNNING = "CHICAGO_RUNNING"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    CROWNED = "CROWNED"
    # Lawful exits (PRD §12) -- reachable from ANY non-terminal state above.
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"
    NONCONFORMANT = "NONCONFORMANT"
    UNKNOWN = "UNKNOWN"


_MAIN_SEQUENCE: tuple[ReleaseState, ...] = (
    ReleaseState.CREATED,
    ReleaseState.SUBJECT_FENCED,
    ReleaseState.PREFLIGHTED,
    ReleaseState.EPISODE_1_RUNNING,
    ReleaseState.EPISODE_1_VERIFIED,
    ReleaseState.EXPERIENCE_ADMITTED,
    ReleaseState.EPISODE_2_RUNNING,
    ReleaseState.EPISODE_2_VERIFIED,
    ReleaseState.CHICAGO_RUNNING,
    ReleaseState.EVIDENCE_VALIDATED,
    ReleaseState.CROWNED,
)

_LAWFUL_EXITS: Set[ReleaseState] = {
    ReleaseState.REFUSED,
    ReleaseState.BLOCKED,
    ReleaseState.BUILD_BROKEN,
    ReleaseState.UNSUPPORTED,
    ReleaseState.NONCONFORMANT,
    ReleaseState.UNKNOWN,
}

LAWFUL_RELEASE_TRANSITIONS: Mapping[ReleaseState, Set[ReleaseState]] = {
    # Every non-terminal main-sequence state may advance to its successor OR exit
    # early via any lawful exit. CROWNED is the main sequence's own terminal
    # SUCCESS state -- it gets no successor and no exit edges (a crowned run
    # cannot retroactively become REFUSED); excluded from the `| _LAWFUL_EXITS`
    # every other main-sequence state receives.
    state: (
        set()
        if state is ReleaseState.CROWNED
        else ({_MAIN_SEQUENCE[i + 1]} if i + 1 < len(_MAIN_SEQUENCE) else set())
        | _LAWFUL_EXITS
    )
    for i, state in enumerate(_MAIN_SEQUENCE)
}
for _exit in _LAWFUL_EXITS:
    LAWFUL_RELEASE_TRANSITIONS[_exit] = set()  # terminal


def can_transition_release(current: ReleaseState, target: ReleaseState) -> bool:
    if current == target:
        return True
    return target in LAWFUL_RELEASE_TRANSITIONS.get(current, set())


def validate_release_transition(current: ReleaseState, target: ReleaseState) -> None:
    """Raise if `target` would skip a required predecessor (PRD §12: 'No transition
    may skip a required predecessor') -- e.g. CREATED -> EPISODE_1_RUNNING directly,
    bypassing SUBJECT_FENCED/PREFLIGHTED, is refused here even though both states
    individually exist."""
    if not can_transition_release(current, target):
        raise ValueError(
            f"Unlawful release transition: cannot go from {current.value} to {target.value} "
            "(would skip a required predecessor, or the current state is already terminal)"
        )
