# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `certification.stride_sampler` —
`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR2, Correction 6.

`FixedIdRegistry` below is a real, simple object implementing the real
`ScenarioRegistry` protocol (a plain `get_scenario_ids()` returning a real
list) — not a mock: it has real, if simple, behavior, and the code under
test never knows it isn't sregym's own `ProblemRegistry`. Assertions are on
the real returned `StrideSample` state, never on "was `get_scenario_ids`
called."
"""

from __future__ import annotations

import hashlib

from autofde_lab.certification.stride_sampler import stride_sample


class FixedIdRegistry:
    """A real, minimal `ScenarioRegistry` over a fixed, real list of IDs."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def get_scenario_ids(self) -> list[str]:
        return list(self._ids)


def test_stride_sample_sorts_then_takes_every_nth() -> None:
    registry = FixedIdRegistry(["b", "d", "a", "c", "e", "f", "g"])

    sample = stride_sample(registry, domain="fixture", stride=2)

    # sorted: a b c d e f g -> stride 2 from index 0: a c e g
    assert sample.sample_ids == ("a", "c", "e", "g")
    assert sample.registry_size == 7
    assert sample.stride == 2
    assert sample.domain == "fixture"


def test_stride_sample_is_deterministic_and_content_addressed() -> None:
    registry = FixedIdRegistry(["z", "y", "x"])

    first = stride_sample(registry, domain="fixture", stride=1)
    second = stride_sample(registry, domain="fixture", stride=1)

    assert first == second
    expected_digest = hashlib.sha256(b"x\ny\nz").hexdigest()
    assert first.registry_digest == expected_digest


def test_stride_sample_digest_changes_when_registry_content_changes() -> None:
    before = stride_sample(FixedIdRegistry(["a", "b"]), domain="fixture", stride=1)
    after = stride_sample(FixedIdRegistry(["a", "b", "c"]), domain="fixture", stride=1)

    assert before.registry_digest != after.registry_digest
    assert before.registry_size == 2
    assert after.registry_size == 3


def test_stride_of_one_returns_full_sorted_registry() -> None:
    registry = FixedIdRegistry(["3", "1", "2"])

    sample = stride_sample(registry, domain="fixture", stride=1)

    assert sample.sample_ids == ("1", "2", "3")


def test_invalid_stride_is_refused() -> None:
    import pytest

    with pytest.raises(ValueError, match="stride must be >= 1"):
        stride_sample(FixedIdRegistry(["a"]), domain="fixture", stride=0)
