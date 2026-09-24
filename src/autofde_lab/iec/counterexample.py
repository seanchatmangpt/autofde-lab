"""Durable in-process counterexample ledger for CEGIS experiments."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Counterexample, digest


@dataclass(frozen=True, slots=True)
class CounterexampleResolution:
    counterexample_id: str
    repaired_by_hypothesis_id: str
    verifier_receipt: str

    @property
    def resolution_id(self) -> str:
        return digest(self)


class CounterexampleLedger:
    def __init__(self) -> None:
        self._items: dict[str, Counterexample] = {}
        self._resolutions: dict[str, CounterexampleResolution] = {}

    def record(self, counterexample: Counterexample) -> Counterexample:
        self._items[counterexample.counterexample_id] = counterexample
        return counterexample

    def resolve(
        self,
        counterexample_id: str,
        *,
        repaired_by_hypothesis_id: str,
        verifier_receipt: str,
    ) -> CounterexampleResolution:
        if counterexample_id not in self._items:
            raise KeyError(f"unknown counterexample: {counterexample_id}")
        if not repaired_by_hypothesis_id.strip() or not verifier_receipt.strip():
            raise ValueError("resolution requires hypothesis and verifier receipt")
        resolution = CounterexampleResolution(
            counterexample_id=counterexample_id,
            repaired_by_hypothesis_id=repaired_by_hypothesis_id,
            verifier_receipt=verifier_receipt,
        )
        self._resolutions[counterexample_id] = resolution
        return resolution

    def unresolved(self) -> tuple[Counterexample, ...]:
        return tuple(
            self._items[key]
            for key in sorted(self._items)
            if key not in self._resolutions
        )

    def all(self) -> tuple[Counterexample, ...]:
        return tuple(self._items[key] for key in sorted(self._items))
