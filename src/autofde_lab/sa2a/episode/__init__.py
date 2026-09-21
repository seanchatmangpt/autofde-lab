"""Episode 1 / Episode 2 orchestration: UNKNOWN -> MachineExperience -> KNOWN, once.

v26.9.17 PRD §6.11-6.13, §7; ARD §5.9-5.10, §16, §20-23. Composes the real, already-
admission-fenced, already-Chicago-tested sa2a/ components (UnknownResolutionPipeline,
CMCACandidateAllocator, ConsequenceBoundary, AuthorityBroker, the disk actuator/
verifier/receipt-store from `conformance.courts.consequence_court`) end to end, plus
this repo's new `sa2a.experience` layer, so a fresh Episode 2 request can prove it
routed through KNOWN machinery with zero equivalent exploratory inference
(`frontier_clean`) instead of merely asserting it.
"""

from __future__ import annotations

from autofde_lab.sa2a.episode.types import (
    Episode,
    EpisodeKind,
    ExplorationMeter,
    IntelligenceUsage,
)

__all__ = ["Episode", "EpisodeKind", "IntelligenceUsage", "ExplorationMeter"]
