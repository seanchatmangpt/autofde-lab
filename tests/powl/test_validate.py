# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adversarial structural-validation tests for :mod:`skdecide.powl.validate`.

Every refusal ``validate_model`` can raise gets a model built specifically to
trigger it, and the *exact* refusal is asserted — not merely that a
``PowlError`` occurred.

Why ``_raw`` exists
-------------------
:mod:`skdecide.powl.algebra` refuses most malformed inputs at construction, so
several of these models cannot be built through the normal constructors.
:func:`_raw` allocates the frozen dataclass and writes its fields directly,
which is exactly the situation the validator exists for: a model that arrived
from a wire form or a future builder rather than from ``__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from skdecide.powl.algebra import (
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    End,
    OrderEdge,
    PartialOrder,
    Silent,
    Start,
)
from skdecide.powl.frequency import ONCE, ZERO_OR_MORE, Frequency
from skdecide.powl.refusals import PowlError, PowlRefusal
from skdecide.powl.validate import validate_model


def _raw(cls, **fields):
    """Allocate ``cls`` without running ``__post_init__`` and set fields directly."""
    obj = object.__new__(cls)
    for name, value in fields.items():
        object.__setattr__(obj, name, value)
    return obj


def _raw_po(children, order=frozenset(), frequency=ONCE, closure=None):
    return _raw(
        PartialOrder,
        children=tuple(children),
        order=frozenset(order),
        frequency=frequency,
        _closure=frozenset(order if closure is None else closure),
        _depth=2,
    )


def _raw_cg(children, edges=frozenset(), start=0, end=1, frequency=ONCE):
    return _raw(
        ChoiceGraph,
        children=tuple(children),
        edges=frozenset(edges),
        start=start,
        end=end,
        frequency=frequency,
        _depth=2,
    )


def _refusal(exc_info) -> PowlRefusal:
    return exc_info.value.refusal


A, B, C, D = Atom("a"), Atom("b"), Atom("c"), Atom("d")


# ── positives ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("leaf", [Start(), End(), Silent(), Atom("a")])
def test_leaves_are_valid(leaf):
    assert validate_model(leaf) is None


def test_wellformed_partial_order_accepted():
    node = PartialOrder((A, B, C), frozenset({OrderEdge(0, 1), OrderEdge(1, 2)}))
    assert validate_model(node) is None


def test_partial_order_built_from_closure_accepted():
    """Construction normalizes a closure input to the reduction, so it validates."""
    node = PartialOrder(
        (A, B, C), frozenset({OrderEdge(0, 1), OrderEdge(1, 2), OrderEdge(0, 2)})
    )
    assert node.order == frozenset({OrderEdge(0, 1), OrderEdge(1, 2)})
    assert validate_model(node) is None


def test_wellformed_choice_graph_accepted():
    node = ChoiceGraph((A, B), frozenset({ChoiceGraphEdge(0, 1)}), start=0, end=1)
    assert validate_model(node) is None


def test_cyclic_choice_graph_is_ACCEPTED():
    """A cycle in a choice graph is iteration, not a defect. Never refuse it.

    ``~/powlv2lsp`` rejects this shape; POWL 2.0 requires accepting it.
    """
    node = ChoiceGraph(
        (A, B, C, D),
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
    )
    assert validate_model(node) is None


def test_self_loop_in_choice_graph_is_ACCEPTED():
    node = ChoiceGraph(
        (A, B, C),
        frozenset(
            {
                ChoiceGraphEdge(0, 1),
                ChoiceGraphEdge(1, 1),  # <- self-loop == repeat this step
                ChoiceGraphEdge(1, 2),
            }
        ),
        start=0,
        end=2,
    )
    assert validate_model(node) is None


def test_nesting_at_max_depth_accepted():
    node = PartialOrder((A, B))  # depth 2
    for _ in range(6):
        node = PartialOrder((node, Atom("x")))  # -> depth 8
    assert node.depth == 8
    assert validate_model(node) is None


def test_recurses_into_children():
    """A defect buried in a grandchild is still found."""
    bad = _raw_cg((A, B, C), frozenset({ChoiceGraphEdge(0, 1)}), start=0, end=1)
    root = PartialOrder((PartialOrder((A, bad)), B))
    with pytest.raises(PowlError) as e:
        validate_model(root)
    assert _refusal(e) is PowlRefusal.CHOICE_GRAPH_DISCONNECTED


# ── arity ───────────────────────────────────────────────────────────────────


def test_partial_order_arity():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A,)))
    assert _refusal(e) is PowlRefusal.INVALID_PARTIAL_ORDER_ARITY


def test_choice_graph_arity():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_cg((A,)))
    assert _refusal(e) is PowlRefusal.INVALID_CHOICE_ARITY


# ── partial order relation laws ─────────────────────────────────────────────


def test_order_not_irreflexive():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B), {OrderEdge(0, 0)}))
    assert _refusal(e) is PowlRefusal.CYCLIC_PARTIAL_ORDER


def test_order_cyclic():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B, C), {OrderEdge(0, 1), OrderEdge(1, 2), OrderEdge(2, 0)}))
    assert _refusal(e) is PowlRefusal.CYCLIC_PARTIAL_ORDER


def test_order_not_transitively_reduced():
    """Stored order is the closure, not the reduction — refuse the wire form."""
    closure = {OrderEdge(0, 1), OrderEdge(1, 2), OrderEdge(0, 2)}
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B, C), closure))
    assert _refusal(e) is PowlRefusal.NOT_TRANSITIVELY_REDUCED


def test_closure_not_transitive():
    node = _raw_po(
        (A, B, C),
        order={OrderEdge(0, 1), OrderEdge(1, 2)},
        closure={OrderEdge(0, 1), OrderEdge(1, 2)},  # missing 0->2
    )
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.NOT_TRANSITIVELY_REDUCED


def test_closure_not_antisymmetric():
    node = _raw_po(
        (A, B),
        order=frozenset(),  # reduced and acyclic
        closure={OrderEdge(0, 1), OrderEdge(1, 0)},
    )
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.CYCLIC_PARTIAL_ORDER


def test_closure_not_irreflexive():
    node = _raw_po((A, B), order=frozenset(), closure={OrderEdge(1, 1)})
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.CYCLIC_PARTIAL_ORDER


# ── dangling references and edge types ──────────────────────────────────────


def test_dangling_order_edge():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B), {OrderEdge(0, 7)}))
    assert _refusal(e) is PowlRefusal.DANGLING_REFERENCE


def test_dangling_choice_graph_edge():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_cg((A, B), {ChoiceGraphEdge(0, 9)}))
    assert _refusal(e) is PowlRefusal.DANGLING_REFERENCE


def test_dangling_start_index():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_cg((A, B), frozenset(), start=5, end=1))
    assert _refusal(e) is PowlRefusal.DANGLING_REFERENCE


def test_dangling_end_index():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_cg((A, B), frozenset(), start=0, end=-1))
    assert _refusal(e) is PowlRefusal.DANGLING_REFERENCE


def test_edge_type_mismatch_in_partial_order():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B), {ChoiceGraphEdge(0, 1)}))
    assert _refusal(e) is PowlRefusal.EDGE_TYPE_MISMATCH


def test_edge_type_mismatch_in_choice_graph():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_cg((A, B), {OrderEdge(0, 1)}))
    assert _refusal(e) is PowlRefusal.EDGE_TYPE_MISMATCH


# ── choice graph boundary and connectivity ──────────────────────────────────


def test_start_has_incoming_edge():
    node = _raw_cg((A, B, C), {ChoiceGraphEdge(2, 0), ChoiceGraphEdge(0, 1)}, start=0, end=1)
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.MULTI_BOUNDARY_CHOICE_GRAPH


def test_end_has_outgoing_edge():
    node = _raw_cg((A, B, C), {ChoiceGraphEdge(0, 1), ChoiceGraphEdge(1, 2)}, start=0, end=1)
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.MULTI_BOUNDARY_CHOICE_GRAPH


def test_start_equals_end():
    node = _raw_cg((A, B), frozenset(), start=1, end=1)
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.MULTI_BOUNDARY_CHOICE_GRAPH


def test_node_unreachable_from_start():
    node = ChoiceGraph((A, B, C), frozenset({ChoiceGraphEdge(0, 1)}), start=0, end=1)
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.CHOICE_GRAPH_DISCONNECTED
    assert "not reachable from start" in e.value.detail


def test_node_does_not_co_reach_end():
    # index 2 is reachable from start but is a dead end that never reaches `end`.
    node = ChoiceGraph(
        (A, B, C),
        frozenset({ChoiceGraphEdge(0, 1), ChoiceGraphEdge(0, 2)}),
        start=0,
        end=1,
    )
    with pytest.raises(PowlError) as e:
        validate_model(node)
    assert _refusal(e) is PowlRefusal.CHOICE_GRAPH_DISCONNECTED
    assert "co-reach" in e.value.detail


# ── depth ───────────────────────────────────────────────────────────────────


def test_depth_exceeded():
    node = PartialOrder((A, B))  # depth 2
    for _ in range(6):
        node = PartialOrder((node, Atom("x")))  # -> depth 8 (legal)
    too_deep = _raw_po((node, Atom("y")))  # -> height 9
    with pytest.raises(PowlError) as e:
        validate_model(too_deep)
    assert _refusal(e) is PowlRefusal.DEPTH_EXCEEDED


# ── frequency ───────────────────────────────────────────────────────────────


def test_valid_frequencies_accepted():
    node = PartialOrder((A, B), frozenset(), frequency=ZERO_OR_MORE)
    assert validate_model(node) is None


def test_frequency_wrong_type():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B), frequency="often"))
    assert _refusal(e) is PowlRefusal.INVALID_FREQUENCY


def test_frequency_max_below_min():
    bad = _raw(Frequency, min=3, max=1)
    with pytest.raises(PowlError) as e:
        validate_model(_raw_cg((A, B), {ChoiceGraphEdge(0, 1)}, frequency=bad))
    assert _refusal(e) is PowlRefusal.INVALID_FREQUENCY


def test_frequency_negative_min():
    bad = _raw(Frequency, min=-1, max=None)
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, B), frequency=bad))
    assert _refusal(e) is PowlRefusal.INVALID_FREQUENCY


# ── prohibited node kinds ───────────────────────────────────────────────────


@dataclass(frozen=True)
class _Xor:
    """POWL 1.0's ``Xor`` — prohibited in POWL 2.0."""

    children: tuple = ()


def test_prohibited_node_kind():
    with pytest.raises(PowlError) as e:
        validate_model(_Xor((A, B)))
    assert _refusal(e) is PowlRefusal.PROHIBITED_NODE_KIND


def test_prohibited_node_kind_as_child():
    with pytest.raises(PowlError) as e:
        validate_model(_raw_po((A, _Xor((B, C)))))
    assert _refusal(e) is PowlRefusal.PROHIBITED_NODE_KIND
