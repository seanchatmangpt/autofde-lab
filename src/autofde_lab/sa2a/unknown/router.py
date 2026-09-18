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
    #: Hardening (2026-09-17): engine_ids whose `attempt()` raised, OR whose
    #: `attempt()` returned a non-None value that is not a real
    #: `CandidateResolution` -- both are genuine internal failures, distinct from
    #: "this engine cannot handle this query" (which returns None and leaves no
    #: trace here). Kept separate so a caller can tell "nothing matched" apart
    #: from "something broke along the way," even though routing gracefully falls
    #: through to the next engine in precedence order either way.
    errored_engine_ids: tuple[str, ...] = ()

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
        """Route `query` through registered engines in precedence order.

        Hardening (2026-09-17): an engine whose `attempt()` raises (a genuine
        internal failure, per that method's own contract) is recorded in
        `errored_engine_ids` and treated as "did not answer" -- routing falls
        through to the next engine rather than letting one broken engine take
        the whole router down.

        Hardening (2026-09-17, part 2): `DiscoveryEngine.attempt`'s declared
        contract is "a real `CandidateResolution`, or `None`" -- nothing else.
        Before this check, a misbehaving engine returning any other non-None
        value (a bare string, an int, an empty dict, ...) was accepted at face
        value: `DiscoveryRoutingResult.candidate` ended up holding that
        wrong-type value, and the first downstream read of a real
        `CandidateResolution` attribute (`Episode1Runner.run()`'s
        `candidate.consumed_tokens`) crashed with an uncaught `AttributeError`
        -- confirmed live pre-fix. A caller-supplied engine is exactly as
        untrusted as a caller-supplied `discover` callable (episode1.py's own
        hardening for that path), so the same rule applies here: validate the
        return type at the boundary, treat a violation identically to a raise
        (recorded in `errored_engine_ids`, fall through to the next engine),
        and never let a malformed return escape as if it were a real candidate.
        """
        attempted: list[str] = []
        errored: list[str] = []
        for kind in PRECEDENCE:
            for engine in (e for e in self._engines if e.kind == kind):
                attempted.append(engine.engine_id)
                try:
                    candidate = engine.attempt(query)
                except Exception:
                    errored.append(engine.engine_id)
                    continue
                if candidate is not None and not isinstance(candidate, CandidateResolution):
                    errored.append(engine.engine_id)
                    continue
                if candidate is not None:
                    return DiscoveryRoutingResult(
                        query_id=query.query_id, selected_engine_id=engine.engine_id,
                        selected_kind=kind, candidate=candidate, attempted_engine_ids=tuple(attempted),
                        errored_engine_ids=tuple(errored),
                    )
        return DiscoveryRoutingResult(
            query_id=query.query_id, selected_engine_id=None, selected_kind=None,
            candidate=None, attempted_engine_ids=tuple(attempted), errored_engine_ids=tuple(errored),
        )
