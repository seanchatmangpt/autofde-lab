from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from math import prod
from typing import Iterable, Iterator, Mapping, Sequence

from .models import BasisChoice, BudgetPolicy, DecisionBasis


@dataclass(frozen=True, slots=True)
class CompatibilityRule:
    """Declarative compatibility law over DecisionBasis dimension names.

    A rule is active only when every pair in ``when`` matches. Once active,
    every pair in ``require`` must match and no pair in ``forbid`` may match.
    This keeps architecture constraints serializable and inspectable instead
    of hiding them in arbitrary Python predicates.
    """

    when: tuple[tuple[str, str], ...] = ()
    require: tuple[tuple[str, str], ...] = ()
    forbid: tuple[tuple[str, str], ...] = ()
    reason: str = ""

    @classmethod
    def from_mappings(
        cls,
        *,
        when: Mapping[str, str] | None = None,
        require: Mapping[str, str] | None = None,
        forbid: Mapping[str, str] | None = None,
        reason: str = "",
    ) -> "CompatibilityRule":
        return cls(
            when=tuple(sorted((when or {}).items())),
            require=tuple(sorted((require or {}).items())),
            forbid=tuple(sorted((forbid or {}).items())),
            reason=reason,
        )

    def allows(self, basis: DecisionBasis) -> bool:
        dims = basis.dimension_values()
        active = all(dims.get(key) == value for key, value in self.when)
        if not active:
            return True
        if any(dims.get(key) != value for key, value in self.require):
            return False
        if any(dims.get(key) == value for key, value in self.forbid):
            return False
        return True


@dataclass(frozen=True, slots=True)
class DecisionSpace:
    models: tuple[BasisChoice, ...]
    planners: tuple[BasisChoice, ...]
    tool_policies: tuple[BasisChoice, ...]
    repair_policies: tuple[BasisChoice, ...]
    replanning_policies: tuple[BasisChoice, ...]
    verification_policies: tuple[BasisChoice, ...]
    projection_policies: tuple[BasisChoice, ...]
    memory_policies: tuple[BasisChoice, ...]
    budgets: tuple[BudgetPolicy, ...]
    rules: tuple[CompatibilityRule, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "models",
            "planners",
            "tool_policies",
            "repair_policies",
            "replanning_policies",
            "verification_policies",
            "projection_policies",
            "memory_policies",
            "budgets",
        ):
            values = getattr(self, field_name)
            if not values:
                raise ValueError(f"decision-space dimension {field_name} must be non-empty")
            names = [value.name for value in values]
            if len(names) != len(set(names)):
                raise ValueError(f"decision-space dimension {field_name} contains duplicate names")

    @property
    def upper_bound_size(self) -> int:
        return prod(
            len(values)
            for values in (
                self.models,
                self.planners,
                self.tool_policies,
                self.repair_policies,
                self.replanning_policies,
                self.verification_policies,
                self.projection_policies,
                self.memory_policies,
                self.budgets,
            )
        )

    def iter_decisions(self, *, limit: int | None = None) -> Iterator[DecisionBasis]:
        emitted = 0
        for values in product(
            self.models,
            self.planners,
            self.tool_policies,
            self.repair_policies,
            self.replanning_policies,
            self.verification_policies,
            self.projection_policies,
            self.memory_policies,
            self.budgets,
        ):
            basis = DecisionBasis(
                model=values[0],
                planner=values[1],
                tool_policy=values[2],
                repair_policy=values[3],
                replanning_policy=values[4],
                verification_policy=values[5],
                projection_policy=values[6],
                memory_policy=values[7],
                budget=values[8],
            )
            if not all(rule.allows(basis) for rule in self.rules):
                continue
            yield basis
            emitted += 1
            if limit is not None and emitted >= limit:
                return

    def materialize(self, *, candidate_limit: int = 100_000) -> tuple[DecisionBasis, ...]:
        if candidate_limit <= 0:
            raise ValueError("candidate_limit must be > 0")
        decisions = tuple(self.iter_decisions(limit=candidate_limit + 1))
        if len(decisions) > candidate_limit:
            raise ValueError(
                f"REFUSED:ARCHITECTURE_SPACE_TOO_LARGE:{len(decisions)}>{candidate_limit}; "
                "add constraints or use a larger explicit candidate_limit"
            )
        return decisions


def hamming_distance(left: DecisionBasis, right: DecisionBasis) -> int:
    lvals = left.dimension_values()
    rvals = right.dimension_values()
    return sum(lvals[key] != rvals[key] for key in DecisionBasis.DIMENSIONS)


def one_factor_at_a_time(
    decisions: Sequence[DecisionBasis], baseline: DecisionBasis
) -> tuple[DecisionBasis, ...]:
    chosen = [decision for decision in decisions if decision.digest == baseline.digest]
    chosen.extend(
        decision
        for decision in decisions
        if decision.digest != baseline.digest and hamming_distance(decision, baseline) == 1
    )
    if not chosen:
        raise ValueError("baseline does not exist in the lawful DecisionSpace")
    return (chosen[0], *sorted(chosen[1:], key=lambda item: item.digest))


def _pair_tokens(basis: DecisionBasis) -> frozenset[tuple[str, str, str, str]]:
    values = sorted(basis.dimension_values().items())
    return frozenset((a, av, b, bv) for (a, av), (b, bv) in combinations(values, 2))


def pairwise_covering(
    decisions: Sequence[DecisionBasis], *, max_architectures: int | None = None
) -> tuple[DecisionBasis, ...]:
    """Greedy deterministic pairwise covering selection.

    This is intentionally a bounded experimental-design primitive, not a claim
    of optimal minimum covering-array size. It preserves all pairwise observed
    option interactions represented by the lawful candidate set while avoiding
    blind full-factorial execution when possible.
    """

    if not decisions:
        return ()
    token_map = {decision.digest: _pair_tokens(decision) for decision in decisions}
    uncovered = set().union(*(tokens for tokens in token_map.values()))
    remaining = {decision.digest: decision for decision in decisions}
    selected: list[DecisionBasis] = []

    while uncovered and remaining:
        if max_architectures is not None and len(selected) >= max_architectures:
            break
        ranked = sorted(
            remaining.values(),
            key=lambda decision: (
                -len(token_map[decision.digest] & uncovered),
                decision.digest,
            ),
        )
        winner = ranked[0]
        selected.append(winner)
        uncovered.difference_update(token_map[winner.digest])
        remaining.pop(winner.digest)

    if max_architectures is None and uncovered:
        raise AssertionError("pairwise covering failed to cover lawful pair tokens")
    return tuple(selected)


def unique_by_digest(decisions: Iterable[DecisionBasis]) -> tuple[DecisionBasis, ...]:
    by_digest = {decision.digest: decision for decision in decisions}
    return tuple(by_digest[key] for key in sorted(by_digest))
