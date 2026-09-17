"""KnownRoute registry: semantic-class lookup, never prompt/content-digest similarity.

v26.9.17 PRD §6.9 names the anti-pattern this module exists to refuse: the one real
lookup structure that existed before this package
(`autofde_lab.sa2a.unknown.compilation.MachineExperienceCompiler._rule_registry`) is
keyed by an exact content-digest string
(`f"{CROWN_SCHEMA}:{contract['case_id']}:{_digest(contract)}"` in
`autofde_lab.agent.cmca_dogfood_crown`) -- i.e. route matching IS content identity,
precisely what PRD §6.9 and §6.10 forbid ("equivalent does not mean same string/
prompt/embedding neighborhood/endpoint/user"). `KnownRouteRegistry.lookup()` below
matches on `semantic_class_id` first, then requires the registered
`equivalence_predicate` to accept the candidate -- a candidate whose payload is
byte-for-byte different from the one that qualified the route still resolves KNOWN
if it is in the same admitted operational problem class, and a byte-identical
payload in a DIFFERENT semantic class does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping


@dataclass(frozen=True, slots=True)
class KnownRoute:
    """Qualified, reusable route from a semantic class to admitted machinery (ARD §5.8)."""

    route_id: str
    semantic_class_id: str
    experience_id: str
    equivalence_predicate_id: str
    required_preconditions: tuple[str, ...]
    planner_or_policy_identity: str
    manufacturer_identity: str
    expected_capabilities: tuple[str, ...]
    resource_envelope: Mapping[str, int]
    qualification_receipt: str
    invalidation_set: Mapping[str, str] = field(default_factory=dict)
    state: str = "ACTIVE"  # mirrors the owning MachineExperience.state at registration time


class KnownRouteRegistry:
    """Real semantic-class + equivalence-predicate lookup (ARD §11, PRD §6.9).

    Lookup requires ALL of:
      1. semantic class match
      2. the route's registered equivalence predicate accepts the candidate
      3. route.state == ACTIVE
      4. no invalidation dependency has changed (checked by the caller via
         MachineExperience.is_invalidated_by before calling register/activate again)

    A classifier that only checked (1) would degrade back to "any candidate in this
    class resolves KNOWN regardless of preconditions" -- ARD §11's own wording
    ("classifier SHALL NOT infer KNOWN solely from similarity") is read here as
    "solely from CLASS similarity" too, not just string similarity; (2) is what
    keeps this a real equivalence check rather than a bare dict.get(semantic_class).
    """

    def __init__(self) -> None:
        self._routes_by_class: dict[str, list[KnownRoute]] = {}
        self._predicates: dict[str, Callable[[object], bool]] = {}

    def register_predicate(self, predicate_id: str, predicate: Callable[[object], bool]) -> None:
        self._predicates[predicate_id] = predicate

    def register_route(self, route: KnownRoute) -> None:
        self._routes_by_class.setdefault(route.semantic_class_id, []).append(route)

    def deactivate(self, route_id: str) -> None:
        """Mark a route INVALIDATED so lookup() stops returning it (ARD §12)."""
        for routes in self._routes_by_class.values():
            for i, r in enumerate(routes):
                if r.route_id == route_id:
                    import dataclasses

                    routes[i] = dataclasses.replace(r, state="INVALIDATED")

    def lookup(self, semantic_class_id: str, candidate: object) -> KnownRoute | None:
        """Return the first ACTIVE route whose equivalence predicate accepts `candidate`.

        Returns None (UNKNOWN) if no class match, no active route, or the
        equivalence predicate rejects the candidate -- never falls back to
        "close enough" matching.
        """
        for route in self._routes_by_class.get(semantic_class_id, ()):
            if route.state != "ACTIVE":
                continue
            predicate = self._predicates.get(route.equivalence_predicate_id)
            if predicate is None:
                continue
            if predicate(candidate):
                return route
        return None

    def routes_for_class(self, semantic_class_id: str) -> tuple[KnownRoute, ...]:
        return tuple(self._routes_by_class.get(semantic_class_id, ()))
