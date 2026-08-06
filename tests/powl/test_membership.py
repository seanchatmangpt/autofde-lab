# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Membership is decided independently of any executor."""

from __future__ import annotations

import pytest

from skdecide.powl.algebra import (
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    End,
    NodeId,
    OrderEdge,
    PartialOrder,
    Silent,
)
from skdecide.powl.frequency import ONE_OR_MORE
from skdecide.powl.membership import explain, static_labels, trace_in_language
from skdecide.powl.refusals import PowlError, PowlRefusal


def _diamond() -> PartialOrder:
    """a -> b, a -> c, b -> d, c -> d."""
    return PartialOrder(
        children=(Atom("a"), Atom("b"), Atom("c"), Atom("d")),
        order=frozenset(
            {
                OrderEdge(NodeId(0), NodeId(1)),
                OrderEdge(NodeId(0), NodeId(2)),
                OrderEdge(NodeId(1), NodeId(3)),
                OrderEdge(NodeId(2), NodeId(3)),
            }
        ),
    )


def test_membership_module_does_not_import_the_executor():
    import skdecide.powl.membership as m

    src = open(m.__file__).read()
    import_lines = [
        line
        for line in src.splitlines()
        if line.startswith(("import ", "from ")) or line.lstrip().startswith(("import ", "from "))
    ]
    assert import_lines  # guard against a vacuous pass
    assert not [line for line in import_lines if "executor" in line]
    # and the loaded module object never grew the dependency either
    assert not any(
        "executor" in name for name in vars(m) if not name.startswith("__")
    )


# ── accept ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "trace", [("a", "b", "c", "d"), ("a", "c", "b", "d")]
)
def test_accepts_valid_linearizations(trace):
    po = _diamond()
    assert trace_in_language(po, trace) is True
    assert explain(po, trace).startswith("accepted")


# ── reject ──────────────────────────────────────────────────────────────────


def test_rejects_precedence_violation():
    po = _diamond()
    bad = ("b", "a", "c", "d")  # b before a violates a -> b
    assert trace_in_language(po, bad) is False
    reason = explain(po, bad)
    assert reason.startswith("rejected")
    assert "precedence violated" in reason


def test_rejects_missing_occurrence():
    po = _diamond()
    bad = ("a", "b", "c")  # d missing
    assert trace_in_language(po, bad) is False
    reason = explain(po, bad)
    assert "missing occurrence" in reason
    assert "'d'" in reason


def test_rejects_duplicate_occurrence():
    po = _diamond()
    bad = ("a", "b", "b", "c", "d")
    assert trace_in_language(po, bad) is False
    reason = explain(po, bad)
    assert "duplicate occurrence" in reason


def test_transitive_precedence_is_enforced_via_the_closure():
    po = _diamond()
    # a -> d only holds in the closure (reduction has a->b->d, a->c->d)
    assert trace_in_language(po, ("b", "c", "d", "a")) is False


# ── leaves ──────────────────────────────────────────────────────────────────


def test_atom_and_silent():
    assert trace_in_language(Atom("x"), ("x",)) is True
    assert trace_in_language(Atom("x"), ()) is False
    assert trace_in_language(Silent(), ()) is True
    assert trace_in_language(End(), ("x",)) is False


def test_silent_child_carries_no_label():
    po = PartialOrder(
        children=(Atom("a"), Silent(), Atom("b")),
        order=frozenset({OrderEdge(NodeId(0), NodeId(2))}),
    )
    assert static_labels(po) == ("a", "b")
    assert trace_in_language(po, ("a", "b")) is True
    assert trace_in_language(po, ("b", "a")) is False


# ── choice graph ────────────────────────────────────────────────────────────


def _cyclic_choice() -> ChoiceGraph:
    """s -> body -> body (loop) and body -> e; boundary nodes are silent."""
    return ChoiceGraph(
        children=(Silent(), Silent(), Atom("w")),
        edges=frozenset(
            {
                ChoiceGraphEdge(NodeId(0), NodeId(2)),
                ChoiceGraphEdge(NodeId(2), NodeId(2)),
                ChoiceGraphEdge(NodeId(2), NodeId(1)),
            }
        ),
        start=0,
        end=1,
    )


def test_cyclic_choice_graph_accepts_iteration():
    cg = _cyclic_choice()
    assert trace_in_language(cg, ("w",)) is True
    assert trace_in_language(cg, ("w", "w", "w")) is True
    assert trace_in_language(cg, ()) is False
    assert trace_in_language(cg, ("w", "z")) is False
    assert "no start->end walk" in explain(cg, ())


def test_choice_graph_branches():
    cg = ChoiceGraph(
        children=(Silent(), Silent(), Atom("p"), Atom("q")),
        edges=frozenset(
            {
                ChoiceGraphEdge(NodeId(0), NodeId(2)),
                ChoiceGraphEdge(NodeId(0), NodeId(3)),
                ChoiceGraphEdge(NodeId(2), NodeId(1)),
                ChoiceGraphEdge(NodeId(3), NodeId(1)),
            }
        ),
        start=0,
        end=1,
    )
    assert trace_in_language(cg, ("p",)) is True
    assert trace_in_language(cg, ("q",)) is True
    assert trace_in_language(cg, ("p", "q")) is False


# ── nesting and refusals ────────────────────────────────────────────────────


def test_nested_partial_order_recursion():
    inner = PartialOrder(
        children=(Atom("b1"), Atom("b2")),
        order=frozenset({OrderEdge(NodeId(0), NodeId(1))}),
    )
    outer = PartialOrder(
        children=(Atom("a"), inner),
        order=frozenset({OrderEdge(NodeId(0), NodeId(1))}),
    )
    assert trace_in_language(outer, ("a", "b1", "b2")) is True
    assert trace_in_language(outer, ("a", "b2", "b1")) is False
    assert "child 1" in explain(outer, ("a", "b2", "b1"))


def test_non_once_frequency_refuses_rather_than_guessing():
    po = PartialOrder(
        children=(Atom("a"), Atom("b")),
        order=frozenset({OrderEdge(NodeId(0), NodeId(1))}),
        frequency=ONE_OR_MORE,
    )
    with pytest.raises(PowlError) as exc:
        trace_in_language(po, ("a", "b"))
    assert exc.value.refusal is PowlRefusal.IRREDUCIBLE_PROJECTION
