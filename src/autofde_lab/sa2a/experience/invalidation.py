"""Invalidation check: current dependency digests -> INVALIDATED MachineExperience + route (ARD §12).

`MachineExperience.is_invalidated_by()` (types.py) is the pure predicate; this module
is the orchestration that actually transitions an ACTIVE experience to INVALIDATED
and deactivates its registered route the moment ANY declared dependency digest no
longer matches -- so a stale route is never left reachable via
`KnownRouteRegistry.lookup()` after its declared dependencies changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry
from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience


@dataclass(frozen=True, slots=True)
class InvalidationCheckResult:
    experience: MachineExperience
    invalidated: bool
    changed_dependencies: tuple[str, ...]


def check_and_invalidate(
    experience: MachineExperience,
    current_digests: Mapping[str, str],
    route_registry: KnownRouteRegistry,
) -> InvalidationCheckResult:
    """Check `experience` against `current_digests`; invalidate + deactivate if stale.

    No-op (returns the experience unchanged) unless the experience is ACTIVE --
    an experience that never reached ACTIVE has no live route to deactivate.
    """
    if experience.state != ExperienceState.ACTIVE:
        return InvalidationCheckResult(
            experience=experience, invalidated=False, changed_dependencies=()
        )

    invalidated, changed = experience.is_invalidated_by(current_digests)
    if not invalidated:
        return InvalidationCheckResult(
            experience=experience, invalidated=False, changed_dependencies=()
        )

    if experience.known_route_id:
        route_registry.deactivate(experience.known_route_id)

    invalidated_experience = experience.with_state(ExperienceState.INVALIDATED)
    return InvalidationCheckResult(
        experience=invalidated_experience,
        invalidated=True,
        changed_dependencies=changed,
    )
