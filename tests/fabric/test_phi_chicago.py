# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `autofde_lab.fabric.phi`.

Every test constructs a real `Anomaly` (the scanner's actual dataclass) and
calls the real `phi()` encoder table, then asserts on the real returned
domain object's real state -- its class, its real `_get_initial_state_()` /
`next_state_map` / `tasks_mode` content -- never a mock of `phi()` or of the
domain constructors it calls. Per `.claude/rules/testing-chicago-style.md`.
"""

from __future__ import annotations

import pytest

from autofde_lab.fabric.phi import (
    PhiUnrepresentable,
    PhiUnrepresentableError,
    ReconcileDomain,
    _ENCODERS,
    phi,
)
from autofde_lab.hub.domain.graph_domain.GraphDomain import GraphDomain
from autofde_lab.hub.domain.rcpsp.rcpsp_sk import RCPSP
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


def test_encoder_table_is_closed_over_relation_class():
    """The table's keys are exactly the scanner's RelationClass literal set."""
    assert set(_ENCODERS.keys()) == set(RelationClass.__args__)


def test_declared_vs_observed_yields_real_reconcile_domain():
    anomaly = _anomaly(
        relation_class="declared_vs_observed",
        object_name="web",
        namespace="default",
        observed="1",
        expected="3",
    )

    domain = phi(anomaly)

    assert isinstance(domain, ReconcileDomain)
    initial_state = domain._get_initial_state_()
    assert initial_state == "default/web:1"
    assert domain._is_terminal(initial_state) is False
    next_state = domain._get_next_state(initial_state, "reconcile")
    assert next_state == "default/web:3"
    assert domain._is_terminal(next_state) is True
    applicable = domain._get_applicable_actions_from(initial_state)
    assert list(applicable.get_elements()) == ["reconcile"]


def test_dangling_reference_yields_real_graph_domain_with_no_goal_path():
    anomaly = _anomaly(
        relation_class="dangling_reference",
        kind="Ingress",
        object_name="checkout-ingress",
        namespace="shop",
        field="backend.service.name",
        observed="checkout-svc",
        expected=None,
        detail="Ingress references Service checkout-svc which does not exist",
    )

    domain = phi(anomaly)

    assert isinstance(domain, GraphDomain)
    dangling_state = "shop/checkout-ingress"
    assert dangling_state in domain.next_state_map
    # No outgoing transitions: the referenced target cannot be reached.
    assert domain.next_state_map[dangling_state] == {}
    # No goal states at all: nothing satisfies "reference resolves".
    assert domain.targets == set()
    assert domain.is_goal(dangling_state) is False


def test_insufficient_capability_yields_real_rcpsp_domain():
    anomaly = _anomaly(
        relation_class="insufficient_capability",
        kind="Pod",
        object_name="worker-0",
        namespace="batch",
        field="cpu",
        observed="4",
        expected="2",
        detail="Pod requests 4 cpu but node capacity is 2 cpu",
    )

    domain = phi(anomaly)

    assert isinstance(domain, RCPSP)
    assert domain.resource_names == ["cpu"]
    assert domain._get_original_quantity_resource("cpu") == 2
    # Single task carrying the observed demand.
    (task_id,) = domain.task_ids
    assert domain.duration_dict[task_id][1] == 1
    assert domain.tasks_modes_rcpsp[task_id].get_resource_need("cpu") == 4


def test_aggregate_threshold_yields_real_rcpsp_domain_resource_sum_vs_limit():
    anomaly = _anomaly(
        relation_class="aggregate_threshold",
        kind="ResourceQuota",
        object_name="team-a-quota",
        namespace="team-a",
        field="requests.memory",
        observed="12288",
        expected="8192",
        detail="sum of Pod memory requests (12288Mi) exceeds quota (8192Mi)",
    )

    domain = phi(anomaly)

    assert isinstance(domain, RCPSP)
    assert domain.resource_names == ["requests.memory"]
    assert domain._get_original_quantity_resource("requests.memory") == 8192
    (task_id,) = domain.task_ids
    assert (
        domain.tasks_modes_rcpsp[task_id].get_resource_need("requests.memory")
        == 12288
    )


def test_unknown_relation_class_is_explicit_unrepresentable_not_a_guess():
    anomaly = _anomaly(relation_class="declared_vs_observed")
    object.__setattr__(anomaly, "relation_class", "made_up_relation_class")

    with pytest.raises(PhiUnrepresentableError) as excinfo:
        phi(anomaly)

    result = excinfo.value.result
    assert isinstance(result, PhiUnrepresentable)
    assert result.relation_class == "made_up_relation_class"
    assert "made_up_relation_class" in result.reason or "no encoder" in result.reason


def test_declared_vs_observed_missing_expected_is_unrepresentable():
    anomaly = _anomaly(relation_class="declared_vs_observed", expected=None)

    with pytest.raises(PhiUnrepresentableError) as excinfo:
        phi(anomaly)

    assert excinfo.value.result.relation_class == "declared_vs_observed"


def test_insufficient_capability_non_numeric_fields_are_unrepresentable():
    anomaly = _anomaly(
        relation_class="insufficient_capability",
        observed="not-a-number",
        expected="also-not-a-number",
    )

    with pytest.raises(PhiUnrepresentableError) as excinfo:
        phi(anomaly)

    assert excinfo.value.result.relation_class == "insufficient_capability"
