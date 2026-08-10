# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test: real phi() output dispatched into the real solver-match filter.

Phase 2 of the phi -> dispatch line: Phase 1 (`phi.py`) already proved each closed
`RelationClass` encodes into a real, instantiated scikit-decide domain object. This
test proves the *next* real hop -- that the existing, unmodified compatibility-filter
dispatch (`autofde_lab.fabric.service.DecisionFabric.match()`'s own solver-matching
step, `ScikitDecideBackend.match_solvers()`, which is `autofde_lab.utils.match_solvers()`
under the hood) returns a real, non-empty `compatible_solvers` tuple for each of those
real domain instances.

No new dispatch code is written here. This only tests the existing real dispatch
against phi's real output, per the task boundary and
`.claude/rules/testing-chicago-style.md`: every domain instance is the real object
`phi()` constructs (`ReconcileDomain`, `GraphDomain`, `RCPSP`), and
`ScikitDecideBackend.match_solvers()` is called directly and for real -- no mock, no
stub, no patched registry. `_utils().match_solvers()` iterates the *actually
registered* solver entry points and calls each one's real `check_domain(domain)`.
"""

from __future__ import annotations

import pytest

from autofde_lab.fabric.backend import ScikitDecideBackend
from autofde_lab.fabric.phi import _ENCODERS, phi
from autofde_lab_planner.scanner.models import Anomaly, RelationClass


def _anomaly(**overrides) -> Anomaly:
    base = dict(
        kind="Deployment",
        object_name="web",
        namespace="default",
        relation_class="declared_vs_observed",
        field="replicas",
        observed="1",
        expected="3",
        detail="declared 3 replicas, observed 1 ready",
    )
    base.update(overrides)
    return Anomaly(**base)


# One real, representable (non-UNREPRESENTABLE) Anomaly per closed RelationClass
# entry -- each of these is asserted elsewhere (test_phi_chicago.py) to produce a
# real domain instance via phi(), not an UNREPRESENTABLE result.
_REPRESENTABLE_ANOMALIES: dict[RelationClass, Anomaly] = {
    "declared_vs_observed": _anomaly(
        relation_class="declared_vs_observed",
        object_name="web",
        namespace="default",
        observed="1",
        expected="3",
    ),
    "dangling_reference": _anomaly(
        relation_class="dangling_reference",
        kind="Ingress",
        object_name="checkout-ingress",
        namespace="shop",
        field="backend.service.name",
        observed="checkout-svc",
        expected=None,
        detail="Ingress references Service checkout-svc which does not exist",
    ),
    "insufficient_capability": _anomaly(
        relation_class="insufficient_capability",
        kind="Pod",
        object_name="worker-0",
        namespace="batch",
        field="cpu",
        observed="4",
        expected="2",
        detail="Pod requests 4 CPU against a 2 CPU node capacity",
    ),
    "aggregate_threshold": _anomaly(
        relation_class="aggregate_threshold",
        kind="ResourceQuota",
        object_name="team-quota",
        namespace="team-a",
        field="requests.cpu",
        observed="12",
        expected="8",
        detail="aggregate CPU requests 12 exceed quota threshold 8",
    ),
}


def test_fixture_covers_every_closed_relation_class():
    """Guard the fixture itself against drifting out of sync with the closed table."""
    assert set(_REPRESENTABLE_ANOMALIES.keys()) == set(_ENCODERS.keys())
    assert set(_ENCODERS.keys()) == set(RelationClass.__args__)


@pytest.mark.parametrize(
    "relation_class", sorted(_REPRESENTABLE_ANOMALIES), ids=sorted(_REPRESENTABLE_ANOMALIES)
)
def test_phi_output_dispatches_to_a_real_nonempty_compatible_solver_set(relation_class):
    """For each phi()-produced real domain instance, match_solvers() is non-empty.

    This is the real gap-detection assertion the task asks for: if
    `ScikitDecideBackend.match_solvers()` (i.e. `autofde_lab.utils.match_solvers()`
    run against the *actually registered* solver entry points) returns an empty list
    for any of these real domain instances, that is a real dispatch gap between phi's
    output and the existing compatibility filter -- reported here, not silently
    worked around.
    """
    anomaly = _REPRESENTABLE_ANOMALIES[relation_class]

    domain_instance = phi(anomaly)

    backend = ScikitDecideBackend()
    compatible_solvers = backend.match_solvers(domain_instance)

    assert compatible_solvers, (
        f"real phi() output for relation_class={relation_class!r} "
        f"(domain type {type(domain_instance).__name__}) matched zero registered "
        f"solvers via ScikitDecideBackend.match_solvers() -- a real dispatch gap "
        f"between phi's output and the existing compatibility filter"
    )
    # Every match must be a real solver type this repo actually registered, not a
    # coincidental truthy value.
    for solver_type in compatible_solvers:
        assert isinstance(solver_type, type)
