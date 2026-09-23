"""Value-of-information frontier for expensive semantic intelligence.

The frontier decides which UNKNOWN deserves scarce reasoning. It does not
answer the question itself and never grants actuation authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .model import digest


class UnknownKind(str, Enum):
    ORIGIN = "UNKNOWN_ORIGIN"
    GENERATOR = "UNKNOWN_GENERATOR"
    EQUIVALENCE = "UNKNOWN_EQUIVALENCE"
    AUTHORITY = "UNKNOWN_AUTHORITY"
    CONSUMER = "UNKNOWN_CONSUMER"
    RUNTIME_BEHAVIOR = "UNKNOWN_RUNTIME_BEHAVIOR"
    SEMANTIC_ROLE = "UNKNOWN_SEMANTIC_ROLE"


@dataclass(frozen=True, slots=True)
class FrontierItem:
    kind: UnknownKind
    question: str
    subject_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    expected_information_bits: float
    expected_reasoning_units: float
    recurrence_count: int = 1
    mechanization_potential: float = 0.0
    consequence_risk: float = 0.0
    dependencies: tuple[str, ...] = ()
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("frontier question must be non-empty")
        if not self.subject_ids:
            raise ValueError("frontier item requires exact subject identity")
        if self.expected_information_bits < 0:
            raise ValueError("expected information must be non-negative")
        if self.expected_reasoning_units <= 0:
            raise ValueError("expected reasoning units must be positive")
        if self.recurrence_count < 1:
            raise ValueError("recurrence_count must be >= 1")
        for name, value in (
            ("mechanization_potential", self.mechanization_potential),
            ("consequence_risk", self.consequence_risk),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
        if self.authority != "NONE":
            raise ValueError("frontier items have no execution authority")

    @property
    def item_id(self) -> str:
        return digest(self)

    @property
    def utility(self) -> float:
        """Information gain amplified by recurrence and retirement potential."""

        retirement_multiplier = 1.0 + (
            self.mechanization_potential * max(0, self.recurrence_count - 1)
        )
        risk_multiplier = 1.0 + self.consequence_risk
        return (
            self.expected_information_bits
            * retirement_multiplier
            * risk_multiplier
            / self.expected_reasoning_units
        )


@dataclass(frozen=True, slots=True)
class FrontierPlan:
    selected: tuple[FrontierItem, ...]
    deferred: tuple[FrontierItem, ...]
    budget_units: float
    allocated_units: float

    @property
    def plan_id(self) -> str:
        return digest(self)


class FrontierPlanner:
    """Greedy bounded selector over independent candidate questions.

    The budget uses abstract reasoning units because vendor token pricing and
    model accounting are external, time-varying facts.
    """

    def plan(
        self,
        items: Iterable[FrontierItem],
        *,
        budget_units: float,
    ) -> FrontierPlan:
        if budget_units <= 0:
            raise ValueError("budget_units must be positive")
        ordered = tuple(
            sorted(
                items,
                key=lambda item: (
                    -item.utility,
                    -item.mechanization_potential,
                    -item.recurrence_count,
                    item.item_id,
                ),
            )
        )
        selected: list[FrontierItem] = []
        deferred: list[FrontierItem] = []
        allocated = 0.0
        selected_ids: set[str] = set()

        pending = list(ordered)
        progress = True
        while pending and progress:
            progress = False
            next_pending: list[FrontierItem] = []
            for item in pending:
                dependencies_met = set(item.dependencies).issubset(selected_ids)
                fits = allocated + item.expected_reasoning_units <= budget_units
                if dependencies_met and fits:
                    selected.append(item)
                    selected_ids.add(item.item_id)
                    allocated += item.expected_reasoning_units
                    progress = True
                else:
                    next_pending.append(item)
            pending = next_pending

        deferred.extend(pending)
        return FrontierPlan(
            selected=tuple(selected),
            deferred=tuple(deferred),
            budget_units=budget_units,
            allocated_units=allocated,
        )
