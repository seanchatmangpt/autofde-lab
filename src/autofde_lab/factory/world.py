"""A deterministic fault world that can say no.

The hidden cause of each failure class lives only here. The producer never
reads it; it can only spend probes, and a class the world has no ground truth
for yields no observation (absence is not evidence -- the case stays UNKNOWN).
The world's identity is the independent verifier identity on every receipt.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from autofde_lab.wd_fa.domain import FailureCase
from autofde_lab.wd_fa.synthetic import make_case

WORLD_ID = "fault-world-independent-observer"
PRODUCER_ID = "autofde-factory"
CLASS_KEYS = ("symptom_code", "firmware", "supplier", "station")
_CAUSES = ("MECH", "FW", "SUPPLY", "THERMAL", "SERVO", "CONTAM")


def class_key(facts: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(facts[k] for k in CLASS_KEYS)


@dataclass(frozen=True)
class Observation:
    mode_id: str
    probes: int
    observer_id: str = WORLD_ID


class FaultWorld:
    def __init__(self, seed: int, unobservable: frozenset[tuple] = frozenset()):
        self._seed = seed
        self._unobservable = unobservable

    def _cause(self, key: tuple) -> str:
        h = hashlib.sha256(f"{self._seed}:{key}".encode()).digest()
        return _CAUSES[h[0] % len(_CAUSES)]

    def investigate(self, case: FailureCase, budget: int) -> Observation | None:
        """Spend probes walking candidate causes; refuse if the budget runs out."""
        key = class_key(case.facts)
        if key in self._unobservable:
            return None
        truth = self._cause(key)
        for probes, cause in enumerate(_CAUSES, start=1):
            if probes > budget:
                return None
            if cause == truth:
                return Observation(mode_id=f"MODE-{truth}-{_tag(key)}", probes=probes)
        return None


def _tag(key: tuple) -> str:
    return hashlib.sha256(str(key).encode()).hexdigest()[:6].upper()


def generate_stream(
    n_classes: int, repeats: int, seed: int = 7
) -> tuple[list[FailureCase], FaultWorld]:
    """Novel classes (symptom_code >= 100, never in the seed rules), each seen
    ``repeats`` times with jittered non-identity facts, plus one unobservable
    class. Order interleaves first sightings with earlier classes' repeats."""
    unobservable_key = (999, 9, 9, 99)
    world = FaultWorld(seed, frozenset({unobservable_key}))
    keys = [(100 + i, 1 + i % 3, 1 + i % 4, 10 + i) for i in range(n_classes)]
    cases: list[FailureCase] = []

    def mk(key: tuple, n: int) -> FailureCase:
        return make_case(
            f"C{key[0]}-{n}",
            symptom_code=key[0],
            firmware=key[1],
            supplier=key[2],
            station=key[3],
            lot_risk=round(0.1 + (n * 0.013) % 0.8, 3),
            rework_count=n % 3,
            vibration=round(0.2 + (n * 0.029) % 0.7, 3),
            kinds=("test", "waveform"),
            process=("drive_built", "test_failed", "evidence_collected"),
        )

    for n in range(repeats):
        for key in keys:
            cases.append(mk(key, n))
        if n == 0:
            cases.append(mk(unobservable_key, 0))
    return cases, world
