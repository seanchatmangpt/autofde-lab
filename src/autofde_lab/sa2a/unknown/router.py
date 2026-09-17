"""DiscoveryRouter: select among discovery mechanisms in ARD §15's stated precedence
(PRD §6.6, ARD §14-15).

Before routing UNKNOWN to general exploratory intelligence, test whether the class
maps to an already-known formal problem family:

    existing exact reusable machinery -> composition -> formal planner/solver
    -> bounded local synthesis -> general exploratory intelligence

Scoped deliberately: this router does not itself wrap `fabric.pddl_engine` or
`match_solvers` (those live in a differently-governed part of this repo, per
`.claude/rules/ecosystem-boundary.md`'s path scope) -- a caller registers real
engines (each tagged with its `DiscoveryEngineKind`), and this router enforces two
real properties: (1) precedence ordering (cheaper/more-certain machinery is always
tried before general exploratory intelligence), and (2) the candidate-only boundary
-- `route()` returns a `CandidateResolution` or `None`, never anything resembling
admitted standing, so a registered engine cannot self-admit by construction (its
return type has no `admitted`/`standing` field at all, matching
`unknown/resolution.py`'s `CandidateResolution`'s own documented invariant).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery


class DiscoveryEngineKind(str, Enum):
    EXACT_REUSABLE_MACHINERY = "EXACT_REUSABLE_MACHINERY"
    COMPOSITION = "COMPOSITION"
    FORMAL_PLANNER_OR_SOLVER = "FORMAL_PLANNER_OR_SOLVER"
    BOUNDED_LOCAL_SYNTHESIS = "BOUNDED_LOCAL_SYNTHESIS"
    GENERAL_EXPLORATORY_INTELLIGENCE = "GENERAL_EXPLORATORY_INTELLIGENCE"


#: ARD §15's stated precedence, most-certain/cheapest first.
PRECEDENCE: tuple[DiscoveryEngineKind, ...] = (
    DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY,
    DiscoveryEngineKind.COMPOSITION,
    DiscoveryEngineKind.FORMAL_PLANNER_OR_SOLVER,
    DiscoveryEngineKind.BOUNDED_LOCAL_SYNTHESIS,
    DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE,
)


@dataclass(frozen=True, slots=True)
class DiscoveryEngine:
    """One registered discovery mechanism.

    `attempt` returns a real `CandidateResolution` if this engine can handle the
    query, or `None` if it cannot (never raises for "I don't know this one" --
    only for a genuine internal failure) so the router can fall through to the
    next engine in precedence order.
    """

    engine_id: str
    kind: DiscoveryEngineKind
    attempt: Callable[[UnknownQuery], Optional[CandidateResolution]]


@dataclass(frozen=True, slots=True)
class DiscoveryRoutingResult:
    query_id: str
    selected_engine_id: Optional[str]
    selected_kind: Optional[DiscoveryEngineKind]
    candidate: Optional[CandidateResolution]
    attempted_engine_ids: tuple[str, ...]

    @property
    def used_general_exploratory_intelligence(self) -> bool:
        return self.selected_kind == DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE


class DiscoveryRouter:
    """Selects among registered discovery engines in ARD §15 precedence order."""

    def __init__(self) -> None:
        self._engines: list[DiscoveryEngine] = []

    def register(self, engine: DiscoveryEngine) -> None:
        if any(e.engine_id == engine.engine_id for e in self._engines):
            raise ValueError(f"DiscoveryEngine {engine.engine_id!r} already registered")
        self._engines.append(engine)

    def route(self, query: UnknownQuery) -> DiscoveryRoutingResult:
        attempted: list[str] = []
        for kind in PRECEDENCE:
            for engine in (e for e in self._engines if e.kind == kind):
                attempted.append(engine.engine_id)
                candidate = engine.attempt(query)
                if candidate is not None:
                    return DiscoveryRoutingResult(
                        query_id=query.query_id, selected_engine_id=engine.engine_id,
                        selected_kind=kind, candidate=candidate, attempted_engine_ids=tuple(attempted),
                    )
        return DiscoveryRoutingResult(
            query_id=query.query_id, selected_engine_id=None, selected_kind=None,
            candidate=None, attempted_engine_ids=tuple(attempted),
        )
