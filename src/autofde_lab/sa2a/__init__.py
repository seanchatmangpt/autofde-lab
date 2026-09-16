"""Semantic Agent-to-Agent (SA2A) protocol package (RFC-SA2A-001 v26.9.16)."""

from __future__ import annotations

from autofde_lab.sa2a.algebra import (
    LAWFUL_TRANSITIONS,
    NON_ADMISSIBLE_STANDINGS,
    TERMINAL_STANDINGS,
    RefusalCause,
    Standing,
    can_transition,
    is_admissible,
    is_terminal,
    validate_refusal,
    validate_transition,
)
from autofde_lab.sa2a.envelope import (
    AuthorityRequirement,
    EnvelopeBounds,
    ProvenanceRecord,
    SemanticEnvelope,
    SemanticGraph,
)
from autofde_lab.sa2a.root_manifest import RootManifest

__all__ = [
    "Standing",
    "RefusalCause",
    "TERMINAL_STANDINGS",
    "NON_ADMISSIBLE_STANDINGS",
    "LAWFUL_TRANSITIONS",
    "can_transition",
    "validate_transition",
    "is_terminal",
    "is_admissible",
    "validate_refusal",
    "SemanticGraph",
    "ProvenanceRecord",
    "AuthorityRequirement",
    "EnvelopeBounds",
    "SemanticEnvelope",
    "RootManifest",
]
