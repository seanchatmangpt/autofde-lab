# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Generalizes `docs/STATUS.md` Pass 20's stride-sampling discipline into
reusable code.

Confirmed (`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` Correction 6, 5-agent
audit 2026-08-12) that the real Pass-20 sample — "a real, programmatically-
generated stride-5 systematic sample (25 of 123 active registrations)" —
was a one-off manual operation (sort the registry's IDs, take every 5th),
never committed as a function. `sregym`'s own
`ProblemRegistry.get_problem_ids(all=True)` just returns all IDs, unordered
— it does not sample.

This module is that missing function, generalized past sregym: it takes any
`ScenarioRegistry` (a real, closed set of scenario IDs a domain admits) and
produces the same discipline — sort, fixed stride, computed once from the
registry's own real content, never hand-picked — with the registry's content
hash recorded alongside the sample, so a later re-run can prove the sample
was drawn from the same registry state, not a different one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class ScenarioRegistry(Protocol):
    """The minimal real contract a domain's scenario source must satisfy to
    be stride-sampled. Deliberately narrow: `get_scenario_ids()` is the only
    method this module needs, so any real registry (sregym's
    `ProblemRegistry`, or a future per-`*goat`-domain registry — none exist
    yet, per Correction 7) can satisfy this without adapting its own shape.
    """

    def get_scenario_ids(self) -> list[str]: ...


@dataclass(frozen=True)
class StrideSample:
    """The real, checkable output of one stride-sampling run."""

    domain: str
    stride: int
    registry_size: int
    registry_digest: str
    """SHA-256 of the sorted, newline-joined full ID list — proves which
    exact registry contents produced this sample, so a later claim "this
    sample is still representative" can be checked against a fresh registry
    read rather than assumed."""
    sample_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.stride < 1:
            raise ValueError(f"stride must be >= 1, got {self.stride}")
        if self.registry_size < 0:
            raise ValueError(f"registry_size must be >= 0, got {self.registry_size}")


def _registry_digest(sorted_ids: list[str]) -> str:
    joined = "\n".join(sorted_ids)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def stride_sample(registry: ScenarioRegistry, *, domain: str, stride: int = 5) -> StrideSample:
    """Sort the registry's real IDs, take every `stride`-th one, starting at
    index 0 — exactly the Pass-20 discipline, computed once, never
    hand-picked. `stride=5` matches Pass 20's own real sample; callers may
    choose a different stride for a smaller/larger registry, but must state
    it, never tune it after seeing which IDs would be selected (that would
    reintroduce hand-picking through the back door).
    """
    if stride < 1:
        raise ValueError(f"stride must be >= 1, got {stride}")
    all_ids = registry.get_scenario_ids()
    sorted_ids = sorted(all_ids)
    sample_ids = tuple(sorted_ids[::stride])
    return StrideSample(
        domain=domain,
        stride=stride,
        registry_size=len(sorted_ids),
        registry_digest=_registry_digest(sorted_ids),
        sample_ids=sample_ids,
    )
