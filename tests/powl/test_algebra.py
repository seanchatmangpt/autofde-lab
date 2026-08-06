# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the POWL 2.0 type foundation."""

from __future__ import annotations

import pytest

from skdecide.powl import (
    DEFAULT_BOUND,
    MAX_POWL_DEPTH,
    ONE_OR_MORE,
    OPTIONAL,
    ZERO_OR_MORE,
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    End,
    ExecutionBound,
    Frequency,
    OrderEdge,
    PartialOrder,
    PowlError,
    PowlRefusal,
    Silent,
    Start,
    activity_sha256,
    node_depth,
    node_id,
    transitive_closure,
    transitive_reduction,
)


def E(*pairs: tuple[int, int]) -> frozenset[OrderEdge]:
    return frozenset(OrderEdge(a, b) for a, b in pairs)


def atoms(n: int) -> tuple[Atom, ...]:
    return tuple(Atom(f"a{i}") for i in range(n))


# ── adversarial negatives ───────────────────────────────────────────────────


def test_partial_order_rejects_single_child():
    with pytest.raises(PowlError) as exc:
        PartialOrder(atoms(1))
    assert exc.value.refusal is PowlRefusal.INVALID_PARTIAL_ORDER_ARITY


def test_choice_graph_rejects_single_child():
    with pytest.raises(PowlError) as exc:
        ChoiceGraph(atoms(1))
    assert exc.value.refusal is PowlRefusal.INVALID_CHOICE_ARITY


@pytest.mark.parametrize(
    "edges", [E((0, 1), (1, 0)), E((0, 0)), E((0, 1), (1, 2), (2, 0))]
)
def test_partial_order_rejects_cycles(edges):
    with pytest.raises(PowlError) as exc:
        PartialOrder(atoms(3), edges)
    assert exc.value.refusal is PowlRefusal.CYCLIC_PARTIAL_ORDER


def test_partial_order_rejects_dangling_index():
    with pytest.raises(PowlError) as exc:
        PartialOrder(atoms(2), E((0, 5)))
    assert exc.value.refusal is PowlRefusal.DANGLING_REFERENCE


def test_choice_graph_start_with_incoming_edge_is_refused():
    with pytest.raises(PowlError) as exc:
        ChoiceGraph(
            atoms(3),
            frozenset({ChoiceGraphEdge(0, 2), ChoiceGraphEdge(2, 0)}),
            start=0,
            end=1,
        )
    assert exc.value.refusal is PowlRefusal.MULTI_BOUNDARY_CHOICE_GRAPH


def test_choice_graph_end_with_outgoing_edge_is_refused():
    with pytest.raises(PowlError) as exc:
        ChoiceGraph(
            atoms(3),
            frozenset({ChoiceGraphEdge(0, 1), ChoiceGraphEdge(1, 2)}),
            start=0,
            end=1,
        )
    assert exc.value.refusal is PowlRefusal.MULTI_BOUNDARY_CHOICE_GRAPH


def test_cyclic_choice_graph_is_accepted():
    """POWL 2.0 expresses iteration as a cycle; it must never be refused."""
    cg = ChoiceGraph(
        atoms(4),
        frozenset(
            {
                ChoiceGraphEdge(0, 1),
                ChoiceGraphEdge(1, 2),
                ChoiceGraphEdge(2, 1),  # <- the cycle
                ChoiceGraphEdge(2, 3),
            }
        ),
        start=0,
        end=3,
        frequency=ZERO_OR_MORE,
    )
    assert ChoiceGraphEdge(2, 1) in cg.edges
    assert node_depth(cg) == 2


def test_depth_nine_is_refused():
    node = PartialOrder(atoms(2))  # depth 2
    for _ in range(MAX_POWL_DEPTH - 2):
        node = PartialOrder((node, Atom("x")))
    assert node_depth(node) == MAX_POWL_DEPTH
    with pytest.raises(PowlError) as exc:
        PartialOrder((node, Atom("x")))
    assert exc.value.refusal is PowlRefusal.DEPTH_EXCEEDED


def test_order_edge_rejected_where_choice_graph_edge_required():
    with pytest.raises(PowlError) as exc:
        ChoiceGraph(atoms(2), frozenset({OrderEdge(0, 1)}), start=0, end=1)
    assert exc.value.refusal is PowlRefusal.EDGE_TYPE_MISMATCH


def test_choice_graph_edge_rejected_where_order_edge_required():
    with pytest.raises(PowlError) as exc:
        PartialOrder(atoms(2), frozenset({ChoiceGraphEdge(0, 1)}))
    assert exc.value.refusal is PowlRefusal.EDGE_TYPE_MISMATCH


def test_bare_tuple_is_not_an_edge():
    with pytest.raises(PowlError) as exc:
        PartialOrder(atoms(2), frozenset({(0, 1)}))
    assert exc.value.refusal is PowlRefusal.EDGE_TYPE_MISMATCH


def test_edge_types_are_not_interchangeable_by_value():
    assert OrderEdge(0, 1) != ChoiceGraphEdge(0, 1)
    assert OrderEdge(0, 1) != (0, 1)


def test_frequency_min_greater_than_max_is_refused():
    with pytest.raises(PowlError) as exc:
        Frequency(min=3, max=2)
    assert exc.value.refusal is PowlRefusal.INVALID_FREQUENCY


def test_frequency_negative_min_is_refused():
    with pytest.raises(PowlError) as exc:
        Frequency(min=-1)
    assert exc.value.refusal is PowlRefusal.INVALID_FREQUENCY


# ── frequency positives ─────────────────────────────────────────────────────


def test_frequency_semantics():
    assert Frequency().allows(1) and not Frequency().allows(0)
    assert OPTIONAL.is_skippable and not OPTIONAL.is_repeatable
    assert ONE_OR_MORE.is_unbounded and ONE_OR_MORE.is_repeatable
    assert ZERO_OR_MORE.is_skippable and ZERO_OR_MORE.allows(9999)
    assert not ZERO_OR_MORE.allows(-1)


# ── closure / reduction algebra ─────────────────────────────────────────────

DAGS = [
    (3, E((0, 1), (1, 2))),
    (4, E((0, 1), (0, 2), (1, 3), (2, 3))),
    (5, E((0, 1), (1, 2), (2, 3), (3, 4), (0, 4))),
    (6, E((0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (0, 5))),
    (4, frozenset()),
    (5, E((4, 0), (0, 3), (3, 1))),
]


@pytest.mark.parametrize("n,edges", DAGS)
def test_reduce_close_idempotence(n, edges):
    red = transitive_reduction(edges, n)
    assert transitive_reduction(transitive_closure(edges, n), n) == red
    assert transitive_reduction(red, n) == red
    assert transitive_closure(red, n) == transitive_closure(edges, n)


def test_reduction_drops_the_shortcut():
    assert transitive_reduction(E((0, 1), (1, 2), (0, 2)), 3) == E((0, 1), (1, 2))
    assert transitive_closure(E((0, 1), (1, 2)), 3) == E((0, 1), (1, 2), (0, 2))


@pytest.mark.parametrize("n,edges", DAGS)
def test_partial_order_normalizes_input_to_reduction(n, edges):
    children = atoms(n)
    from_closure = PartialOrder(children, transitive_closure(edges, n))
    from_reduction = PartialOrder(children, transitive_reduction(edges, n))
    from_raw = PartialOrder(children, edges)
    assert from_closure == from_reduction == from_raw
    assert hash(from_closure) == hash(from_reduction) == hash(from_raw)
    assert from_closure.order == transitive_reduction(edges, n)
    assert from_closure.closure == transitive_closure(edges, n)


def test_closure_is_computed_once_and_cached():
    po = PartialOrder(atoms(4), E((0, 1), (1, 2), (2, 3)))
    assert po.closure is po.closure  # same object, not recomputed
    assert len(po.closure) == 6
    assert len(po.order) == 3


def test_partial_order_is_hashable_and_value_equal():
    a = PartialOrder(atoms(3), E((0, 1)))
    b = PartialOrder(atoms(3), E((0, 1)))
    assert a is not b and a == b
    assert len({a, b}) == 1


def test_atom_with_dict_bindings_is_hashable_and_value_equal():
    a = Atom("pay", bindings={"amount": 3, "cur": "EUR"})
    b = Atom("pay", bindings={"cur": "EUR", "amount": 3})
    assert a == b and hash(a) == hash(b)
    assert Atom("pay") != a


def test_leaf_nodes_are_value_equal():
    assert Start() == Start() and End() == End() and Silent() == Silent()
    assert Start() != End()


# ── identity ────────────────────────────────────────────────────────────────


def test_node_id_stable_across_differently_ordered_edge_inputs():
    n = 4
    edges = E((0, 1), (0, 2), (1, 3), (2, 3))
    a = PartialOrder(atoms(n), frozenset(sorted(edges)))
    b = PartialOrder(atoms(n), frozenset(sorted(edges, reverse=True)))
    c = PartialOrder(atoms(n), transitive_closure(edges, n))
    assert node_id(a) == node_id(b) == node_id(c)


def test_node_id_ignores_the_closure_and_tracks_the_reduction():
    shortcut = PartialOrder(atoms(3), E((0, 1), (1, 2), (0, 2)))
    plain = PartialOrder(atoms(3), E((0, 1), (1, 2)))
    assert node_id(shortcut) == node_id(plain)
    assert node_id(plain) != node_id(PartialOrder(atoms(3), E((0, 1))))


def test_node_id_is_sensitive_to_frequency_and_labels():
    base = PartialOrder(atoms(2))
    assert node_id(base) != node_id(PartialOrder(atoms(2), frequency=ZERO_OR_MORE))
    assert node_id(base) != node_id(PartialOrder((Atom("z"), Atom("a1"))))


def test_node_id_is_recursive_merkle():
    inner = PartialOrder(atoms(2))
    outer = PartialOrder((inner, Atom("t")), E((0, 1)))
    assert node_id(outer) != node_id(inner)
    from skdecide.powl import node_structure

    assert node_structure(outer)["children"][0] == node_id(inner)


def test_activity_sha256_covers_label_and_bindings():
    assert activity_sha256(Atom("a")) == activity_sha256(Atom("a"))
    assert activity_sha256(Atom("a")) != activity_sha256(Atom("b"))
    assert activity_sha256(Atom("a", bindings={"k": 1})) != activity_sha256(Atom("a"))
    assert len(activity_sha256(Atom("a"))) == 64


def test_activity_sha256_rejects_non_atom():
    with pytest.raises(PowlError) as exc:
        activity_sha256(Silent())
    assert exc.value.refusal is PowlRefusal.PROHIBITED_NODE_KIND


# ── bounds ──────────────────────────────────────────────────────────────────


def test_execution_bound_digest():
    assert DEFAULT_BOUND.sha256() == ExecutionBound().sha256()
    assert len(DEFAULT_BOUND.sha256()) == 64
    assert ExecutionBound(1, 2, 3).sha256() != DEFAULT_BOUND.sha256()
