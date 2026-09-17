"""Algebra and Standing definitions for Semantic A2A (RFC-SA2A-001 v26.9.16 §41, §42, §60)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Sequence, Set


class Standing(str, Enum):
    """Standing lifecycle states (§41)."""

    CANDIDATE = "CANDIDATE"
    ADMITTED = "ADMITTED"
    SELECTED = "SELECTED"
    CONSTRUCTED = "CONSTRUCTED"
    AUTHORIZED = "AUTHORIZED"
    PREPARED = "PREPARED"
    EXECUTED = "EXECUTED"
    RECEIPTED = "RECEIPTED"
    ATTESTED = "ATTESTED"
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class RefusalCause(str, Enum):
    """Refusal and non-admissible causes (§42)."""

    REFUSED_IDENTITY = "REFUSED_IDENTITY"
    REFUSED_NAMESPACE = "REFUSED_NAMESPACE"
    REFUSED_STRUCTURE = "REFUSED_STRUCTURE"
    REFUSED_SHACL = "REFUSED_SHACL"
    REFUSED_RULE = "REFUSED_RULE"
    REFUSED_FALSIFIER = "REFUSED_FALSIFIER"
    REFUSED_PROVENANCE = "REFUSED_PROVENANCE"
    REFUSED_PROFILE = "REFUSED_PROFILE"
    REFUSED_PLAN = "REFUSED_PLAN"
    REFUSED_CAPABILITY = "REFUSED_CAPABILITY"
    REFUSED_AUTHORITY = "REFUSED_AUTHORITY"
    REFUSED_CONSEQUENCE = "REFUSED_CONSEQUENCE"
    REFUSED_RECEIPT = "REFUSED_RECEIPT"
    REFUSED_BOUNDS = "REFUSED_BOUNDS"
    REFUSED_META_RIGOR = "REFUSED_META_RIGOR"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
    BLOCKED_RESOURCE = "BLOCKED_RESOURCE"
    UNSUPPORTED_PROFILE = "UNSUPPORTED_PROFILE"


# Terminal and terminal failure/quarantine sets
TERMINAL_STANDINGS: Set[Standing] = {
    Standing.RECEIPTED,
    Standing.ATTESTED,
    Standing.REFUSED,
    Standing.BLOCKED,
    Standing.UNSUPPORTED,
    Standing.FAILED,
}

NON_ADMISSIBLE_STANDINGS: Set[Standing] = {
    Standing.REFUSED,
    Standing.BLOCKED,
    Standing.UNKNOWN,
    Standing.UNSUPPORTED,
    Standing.FAILED,
}

# Lawful forward state transitions (§41, §60)
# CANDIDATE -> ADMITTED -> SELECTED -> CONSTRUCTED -> AUTHORIZED -> PREPARED -> EXECUTED -> RECEIPTED -> ATTESTED
LAWFUL_TRANSITIONS: Mapping[Standing, Set[Standing]] = {
    Standing.CANDIDATE: {
        Standing.ADMITTED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNKNOWN,
        Standing.UNSUPPORTED,
    },
    Standing.ADMITTED: {
        Standing.SELECTED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNKNOWN,
        Standing.UNSUPPORTED,
        Standing.FAILED,
    },
    Standing.SELECTED: {
        Standing.CONSTRUCTED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNKNOWN,
        Standing.UNSUPPORTED,
        Standing.FAILED,
    },
    Standing.CONSTRUCTED: {
        Standing.AUTHORIZED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNKNOWN,
        Standing.UNSUPPORTED,
        Standing.FAILED,
    },
    Standing.AUTHORIZED: {
        Standing.PREPARED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNKNOWN,
        Standing.UNSUPPORTED,
        Standing.FAILED,
    },
    Standing.PREPARED: {
        Standing.EXECUTED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNKNOWN,
        Standing.UNSUPPORTED,
        Standing.FAILED,
    },
    Standing.EXECUTED: {
        Standing.RECEIPTED,
        Standing.REFUSED,
        Standing.FAILED,
    },
    Standing.RECEIPTED: {
        Standing.ATTESTED,
    },
    Standing.ATTESTED: set(),
    Standing.REFUSED: set(),
    Standing.BLOCKED: set(),
    Standing.UNKNOWN: {
        Standing.ADMITTED,
        Standing.REFUSED,
        Standing.BLOCKED,
        Standing.UNSUPPORTED,
    },
    Standing.UNSUPPORTED: set(),
    Standing.FAILED: set(),
}


def can_transition(current: Standing, target: Standing) -> bool:
    """Determine whether transitioning from current standing to target is lawful (§60)."""
    if current == target:
        return True
    return target in LAWFUL_TRANSITIONS.get(current, set())


def validate_transition(current: Standing, target: Standing) -> None:
    """Validate transition and raise ValueError if unlawful (§60)."""
    if not can_transition(current, target):
        raise ValueError(
            f"Unlawful standing transition: cannot transition from {current.value} to {target.value}"
        )


def is_terminal(standing: Standing) -> bool:
    """Return True if the standing is a terminal state."""
    return standing in TERMINAL_STANDINGS


def is_admissible(standing: Standing) -> bool:
    """Return True if standing represents an admitted or progressing state (not refused/blocked/etc)."""
    return standing not in NON_ADMISSIBLE_STANDINGS


def validate_refusal(standing: Standing, cause: RefusalCause | None) -> None:
    """Validate that non-admissible standings carry a valid RefusalCause (§42, §60)."""
    if standing in {Standing.REFUSED, Standing.BLOCKED, Standing.UNSUPPORTED}:
        if cause is None:
            raise ValueError(f"Standing {standing.value} requires a specific RefusalCause (§42)")
        if standing == Standing.BLOCKED and not cause.value.startswith("BLOCKED_"):
            raise ValueError(f"Standing BLOCKED requires a BLOCKED_* cause, got {cause.value}")
        if standing == Standing.UNSUPPORTED and cause != RefusalCause.UNSUPPORTED_PROFILE:
            raise ValueError(f"Standing UNSUPPORTED requires UNSUPPORTED_* cause, got {cause.value}")
        if standing == Standing.REFUSED and not cause.value.startswith("REFUSED_"):
            raise ValueError(f"Standing REFUSED requires a REFUSED_* cause, got {cause.value}")
