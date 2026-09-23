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

import threading
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
    state: str = (
        "ACTIVE"  # mirrors the owning MachineExperience.state at registration time
    )


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
        # Concurrency hardening (2026-09-17, real OS-thread stress-test pass): a
        # single re-entrant lock guarding every method that touches
        # `_routes_by_class`/`_predicates`. Real threading.Thread stress testing
        # (tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py, N=8 threads x 5
        # trials on register_route()/lookup(), plus a separate 30-trial
        # register_route()/deactivate() probe) observed ZERO RuntimeErrors or lost
        # registrations even unlocked -- CPython's GIL happens to make the
        # individual dict/list operations here atomic enough at this test's scale.
        # This lock is added as DEFENSIVE hardening for the real, code-inspection-
        # confirmed hazard `deactivate()`'s docstring already names (`for routes in
        # self._routes_by_class.values(): ...` iterating the SAME dict
        # `register_route()`'s `setdefault()` can insert a new key into --
        # CPython's well-known "dictionary changed size during iteration"
        # RuntimeError shape), not as a fix for an empirically observed failure --
        # see docs/jira/v26.9.17/benchmarks/concurrency-stress-findings.md for the
        # honest, un-overclaimed account of what was and was not observed.
        self._lock = threading.RLock()

    def register_predicate(
        self, predicate_id: str, predicate: Callable[[object], bool]
    ) -> None:
        with self._lock:
            self._predicates[predicate_id] = predicate

    def register_route(self, route: KnownRoute) -> None:
        """Register `route`, refusing a second ACTIVE route for the same experience.

        Hardening (2026-09-17): `MachineExperience` carries a single
        `known_route_id` field -- one experience has at most one live route by
        design. But `MachineExperience` is immutable and `ExperienceQualifier.
        qualify()` only checks `experience.state == ADMITTED` on the OBJECT it was
        given; calling `qualify()` twice with the same still-ADMITTED reference (a
        caller retry, a double-dispatch bug) previously passed that check both
        times and silently registered TWO separate ACTIVE `KnownRoute`s for the
        SAME `experience_id` under different `route_id`s -- confirmed live, with
        no error anywhere in the chain. That is exactly the class of defect
        `.claude/rules/no-dual-bookkeeping.md` names: two records of "this
        experience is qualified" that can silently drift apart. Refuse it here,
        at the single place the duplicate would actually be written, so every
        caller of `register_route()` is protected, not only `qualify()`.
        """
        with self._lock:
            existing_active = [
                r
                for r in self._routes_by_class.get(route.semantic_class_id, [])
                if r.experience_id == route.experience_id and r.state == "ACTIVE"
            ]
            if route.state == "ACTIVE" and existing_active:
                raise ValueError(
                    f"KnownRouteRegistry.register_route() refused: experience "
                    f"{route.experience_id!r} already has an ACTIVE route "
                    f"({existing_active[0].route_id!r}) for semantic class "
                    f"{route.semantic_class_id!r} -- qualify() must not be called twice "
                    "on the same experience without an intervening invalidation"
                )
            self._routes_by_class.setdefault(route.semantic_class_id, []).append(route)

    def deactivate(self, route_id: str) -> None:
        """Mark a route INVALIDATED so lookup() stops returning it (ARD §12)."""
        import dataclasses

        with self._lock:
            for routes in self._routes_by_class.values():
                for i, r in enumerate(routes):
                    if r.route_id == route_id:
                        routes[i] = dataclasses.replace(r, state="INVALIDATED")

    def lookup(self, semantic_class_id: str, candidate: object) -> KnownRoute | None:
        """Return the first ACTIVE route whose equivalence predicate accepts `candidate`.

        Returns None (UNKNOWN) if no class match, no active route, or the
        equivalence predicate rejects the candidate -- never falls back to
        "close enough" matching.

        Hardening (2026-09-17): a registered predicate that RAISES (a bug in that
        predicate's own implementation, e.g. it assumes an attribute a malformed
        candidate doesn't have) is treated as "this route rejects this candidate,"
        not as a crash that takes the whole lookup down -- one broken route must
        not prevent another ACTIVE route for the same class from being tried.
        """
        with self._lock:
            # Snapshot under the lock, then release before calling the caller-supplied
            # `predicate` below -- predicates are foreign code (may be slow, may raise,
            # must never be called while holding this registry's own lock).
            candidate_routes = tuple(self._routes_by_class.get(semantic_class_id, ()))
            predicates_snapshot = dict(self._predicates)
        for route in candidate_routes:
            if route.state != "ACTIVE":
                continue
            predicate = predicates_snapshot.get(route.equivalence_predicate_id)
            if predicate is None:
                continue
            try:
                accepted = predicate(candidate)
            except Exception:
                continue
            if accepted:
                return route
        return None

    def routes_for_class(self, semantic_class_id: str) -> tuple[KnownRoute, ...]:
        with self._lock:
            return tuple(self._routes_by_class.get(semantic_class_id, ()))
