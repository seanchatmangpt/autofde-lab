"""GALL-011 active bounded invariant falsification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Invariant(Generic[T]):
    invariant_id: str
    predicate: Callable[[Sequence[T]], bool]


@dataclass(frozen=True, slots=True)
class FalsifierResult(Generic[T]):
    invariant_id: str
    attempted: int
    budget: int
    found: bool
    counterexample: tuple[T, ...] | None
    counterexample_digest: str | None
    standing: str


class ActiveFalsifier(Generic[T]):
    def __init__(self, *, budget: int = 100) -> None:
        if budget <= 0:
            raise ValueError("falsification budget must be positive")
        self.budget = budget

    def search(
        self,
        invariant: Invariant[T],
        candidates: Iterable[Sequence[T]],
        *,
        execute: Callable[[Sequence[T]], Sequence[T]] = lambda trace: trace,
    ) -> FalsifierResult[T]:
        attempted = 0
        for candidate in candidates:
            if attempted >= self.budget:
                break
            attempted += 1
            observed = tuple(execute(tuple(candidate)))
            if not invariant.predicate(observed):
                minimal = self._minimize(invariant, observed, execute)
                payload = json.dumps(list(minimal), sort_keys=True, default=str)
                return FalsifierResult(
                    invariant_id=invariant.invariant_id,
                    attempted=attempted,
                    budget=self.budget,
                    found=True,
                    counterexample=minimal,
                    counterexample_digest="sha256:"
                    + hashlib.sha256(payload.encode()).hexdigest(),
                    standing="COUNTEREXAMPLE_OBSERVED",
                )
        return FalsifierResult(
            invariant_id=invariant.invariant_id,
            attempted=attempted,
            budget=self.budget,
            found=False,
            counterexample=None,
            counterexample_digest=None,
            standing="NO_COUNTEREXAMPLE_WITHIN_BUDGET",
        )

    def _minimize(
        self,
        invariant: Invariant[T],
        trace: tuple[T, ...],
        execute: Callable[[Sequence[T]], Sequence[T]],
    ) -> tuple[T, ...]:
        current = trace
        changed = True
        while changed and len(current) > 1:
            changed = False
            for index in range(len(current)):
                trial = current[:index] + current[index + 1 :]
                if trial and not invariant.predicate(tuple(execute(trial))):
                    current = trial
                    changed = True
                    break
        return current
