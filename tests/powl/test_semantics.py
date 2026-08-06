# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the POWL 2.0 denotational semantics.

Every model here is small enough that its language is hand-computable, so the
assertions are on exact sets, never on cardinality alone.
"""

from __future__ import annotations

import pytest

from skdecide.powl import (
    ONCE,
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    Frequency,
    NodeId,
    OrderEdge,
    PartialOrder,
    PowlError,
    PowlRefusal,
    Silent,
    Start,
)
from skdecide.powl.semantics import enabled_labels, interleavings, language

A, B, C = Atom("a"), Atom("b"), Atom("c")


def lang(node, max_traces=1024, max_unrolls=3):
    return language(node, max_traces=max_traces, max_unrolls=max_unrolls)


def edge(i, j):
    return OrderEdge(NodeId(i), NodeId(j))


def cedge(i, j):
    return ChoiceGraphEdge(NodeId(i), NodeId(j))


# ── interleavings (Lean: Interleaves) ───────────────────────────────────────


def test_interleavings_matches_lean_nil_case():
    assert set(interleavings((), ())) == {()}


def test_interleavings_with_empty_operand_is_identity():
    assert set(interleavings(("a", "b"), ())) == {("a", "b")}
    assert set(interleavings((), ("a", "b"))) == {("a", "b")}


def test_interleavings_is_order_preserving_shuffle():
    assert set(interleavings(("a", "b"), ("c",))) == {
        ("a", "b", "c"),
        ("a", "c", "b"),
        ("c", "a", "b"),
    }
    # ("b", "a", "c") is absent: it violates a-before-b inside the left trace.


# ── leaves ──────────────────────────────────────────────────────────────────


def test_atom_denotes_singleton_trace():
    assert lang(A) == frozenset({("a",)})


def test_silent_and_start_denote_epsilon():
    assert lang(Silent()) == frozenset({()})
    assert lang(Start()) == frozenset({()})


# ── PartialOrder ────────────────────────────────────────────────────────────


def test_unordered_pair_gives_both_orders():
    po = PartialOrder((A, B))
    assert lang(po) == frozenset({("a", "b"), ("b", "a")})


def test_edge_a_before_b_gives_only_one_order():
    po = PartialOrder((A, B), frozenset({edge(0, 1)}))
    assert lang(po) == frozenset({("a", "b")})


def test_silent_child_contributes_nothing_to_the_trace():
    po = PartialOrder((A, Silent()), frozenset({edge(0, 1)}))
    assert lang(po) == frozenset({("a",)})


def test_three_atoms_with_one_edge():
    # a -> c, b unordered with both.
    po = PartialOrder((A, B, C), frozenset({edge(0, 2)}))
    assert lang(po) == frozenset(
        {("a", "b", "c"), ("a", "c", "b"), ("b", "a", "c")}
    )


def test_nested_partial_orders_interleave_symbol_by_symbol():
    # (a -> c) concurrent with b: b may land between a and c.
    inner = PartialOrder((A, C), frozenset({edge(0, 1)}))
    outer = PartialOrder((inner, B))
    assert lang(outer) == frozenset(
        {("a", "c", "b"), ("a", "b", "c"), ("b", "a", "c")}
    )


def test_partial_order_frequency_repeats_the_body():
    po = PartialOrder((A, B), frozenset({edge(0, 1)}), Frequency(0, 2))
    assert lang(po) == frozenset({(), ("a", "b"), ("a", "b", "a", "b")})


# ── ChoiceGraph ─────────────────────────────────────────────────────────────


def two_branch_choice() -> ChoiceGraph:
    """start -> {a, b} -> end; a hand-computable union."""
    return ChoiceGraph(
        (Silent(), Silent(), A, B),
        frozenset({cedge(0, 2), cedge(2, 1), cedge(0, 3), cedge(3, 1)}),
        start=0,
        end=1,
    )


def test_choice_graph_is_the_union_of_its_branches():
    assert lang(two_branch_choice()) == frozenset({("a",), ("b",)})


def test_cyclic_choice_graph_terminates_under_max_unrolls():
    # start -> a, a -> a (iteration), a -> end.
    cg = ChoiceGraph(
        (Silent(), Silent(), A),
        frozenset({cedge(0, 2), cedge(2, 2), cedge(2, 1)}),
        start=0,
        end=1,
        frequency=ONCE,
    )
    assert lang(cg, max_unrolls=1) == frozenset({("a",)})
    assert lang(cg, max_unrolls=3) == frozenset(
        {("a",), ("a", "a"), ("a", "a", "a")}
    )


def test_choice_graph_branches_of_different_lengths():
    inner = PartialOrder((A, B), frozenset({edge(0, 1)}))
    cg = ChoiceGraph(
        (Silent(), Silent(), inner, C),
        frozenset({cedge(0, 2), cedge(2, 1), cedge(0, 3), cedge(3, 1)}),
        start=0,
        end=1,
    )
    assert lang(cg) == frozenset({("a", "b"), ("c",)})


# ── bounds RAISE, never truncate ────────────────────────────────────────────


def test_exceeding_max_traces_raises_rather_than_truncating():
    po = PartialOrder((A, B, C))  # 6 linearizations
    assert len(lang(po)) == 6
    with pytest.raises(PowlError) as exc:
        lang(po, max_traces=3)
    assert exc.value.refusal is PowlRefusal.BOUND_EXHAUSTED


def test_cyclic_choice_graph_exceeding_max_traces_raises():
    cg = ChoiceGraph(
        (Silent(), Silent(), A),
        frozenset({cedge(0, 2), cedge(2, 2), cedge(2, 1)}),
        start=0,
        end=1,
    )
    with pytest.raises(PowlError) as exc:
        lang(cg, max_traces=2, max_unrolls=5)
    assert exc.value.refusal is PowlRefusal.BOUND_EXHAUSTED


def test_explicit_frequency_beyond_the_unroll_cap_raises():
    po = PartialOrder((A, B), frequency=Frequency(1, 9))
    with pytest.raises(PowlError) as exc:
        lang(po, max_unrolls=3)
    assert exc.value.refusal is PowlRefusal.BOUND_EXHAUSTED


def test_unbounded_frequency_is_capped_at_max_unrolls_not_refused():
    po = PartialOrder((A, Silent()), frozenset({edge(0, 1)}), Frequency(1, None))
    assert lang(po, max_unrolls=3) == frozenset(
        {("a",), ("a", "a"), ("a", "a", "a")}
    )


def test_nonsense_bounds_raise():
    with pytest.raises(PowlError) as exc:
        language(A, max_traces=0, max_unrolls=1)
    assert exc.value.refusal is PowlRefusal.BOUND_EXHAUSTED


# ── enabled_labels ──────────────────────────────────────────────────────────


def test_enabled_labels_of_leaves():
    assert enabled_labels(A) == frozenset({"a"})
    assert enabled_labels(Silent()) == frozenset()


def test_enabled_labels_respects_precedence():
    assert enabled_labels(PartialOrder((A, B))) == frozenset({"a", "b"})
    assert enabled_labels(
        PartialOrder((A, B), frozenset({edge(0, 1)}))
    ) == frozenset({"a"})


def test_enabled_labels_sees_through_a_nullable_predecessor():
    po = PartialOrder((Silent(), B), frozenset({edge(0, 1)}))
    assert enabled_labels(po) == frozenset({"b"})


def test_enabled_labels_of_a_choice_graph_is_the_union_of_branches():
    assert enabled_labels(two_branch_choice()) == frozenset({"a", "b"})


def test_enabled_labels_agrees_with_the_language_first_symbols():
    for node in (
        PartialOrder((A, B, C), frozenset({edge(0, 2)})),
        two_branch_choice(),
        PartialOrder((PartialOrder((A, C), frozenset({edge(0, 1)})), B)),
    ):
        first = frozenset(t[0] for t in lang(node) if t)
        assert enabled_labels(node) == first
