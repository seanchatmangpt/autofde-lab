"""Single seam onto the fortune5_safe DfCM relations the lab reuses.

``fortune5_safe.dfcm`` exposes feasibility, dominance and diversity only as
module-private helpers. The lab binds them here, once, under public names, so a
future public API in ``fortune5_safe`` is a one-file rebind and no other lab
module reaches into private names.

``pareto_front`` is the lab's only frontier. ``dfcm._pareto_frontier`` is not
reused because it keys candidates by ``PolicyAggregate.policy.id``: two doctrine
strategies whose primitive compositions collapse to one policy (see the report's
``primitive_equivalence_clusters``) share that id and would shadow each other's
dominance. The lab keys by strategy id and delegates dominance to ``dominates``.
"""

from __future__ import annotations

from typing import Hashable, Iterable

from autofde_lab.simulation.fortune5_safe.dfcm import (
    _diversity as diversity,
    _dominates as dominates,
    _is_feasible as is_feasible,
)
from autofde_lab.simulation.fortune5_safe.model import PolicyAggregate


def pareto_front(
    candidates: Iterable[tuple[Hashable, PolicyAggregate]],
) -> tuple[Hashable, ...]:
    """Sorted keys of the feasible candidates no other feasible candidate dominates."""
    feasible = [(k, a) for k, a in candidates if a.feasible]
    return tuple(
        sorted(
            k
            for k, a in feasible
            if not any(o != k and dominates(b, a) for o, b in feasible)
        )
    )


__all__ = ["diversity", "dominates", "is_feasible", "pareto_front"]
