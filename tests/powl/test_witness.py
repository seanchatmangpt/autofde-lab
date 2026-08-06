# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Deterministic sampling, honest counting, honest coverage statements."""

from __future__ import annotations

import math

from skdecide.powl.algebra import (
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    NodeId,
    OrderEdge,
    PartialOrder,
    Silent,
)
from skdecide.powl.membership import trace_in_language
from skdecide.powl.witness import (
    WitnessReport,
    count_linearizations,
    sample_linearizations,
)


def _diamond() -> PartialOrder:
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


# ── determinism ─────────────────────────────────────────────────────────────


def test_same_seed_gives_identical_sample_sequence():
    po = _diamond()
    a = list(sample_linearizations(po, samples=50, seed="witness-seed"))
    b = list(sample_linearizations(po, samples=50, seed="witness-seed"))
    assert a == b
    assert len(a) == 50


def test_different_seed_gives_a_different_sequence():
    po = _diamond()
    a = list(sample_linearizations(po, samples=50, seed="seed-one"))
    b = list(sample_linearizations(po, samples=50, seed="seed-two"))
    assert a != b


def test_every_sample_is_in_the_language():
    po = _diamond()
    for trace in sample_linearizations(po, samples=100, seed="cross-check"):
        assert trace_in_language(po, trace), trace


def test_sampling_reaches_both_diamond_linearizations():
    po = _diamond()
    seen = set(sample_linearizations(po, samples=100, seed="coverage"))
    assert seen == {("a", "b", "c", "d"), ("a", "c", "b", "d")}


def test_cyclic_choice_graph_samples_are_in_the_language():
    cg = ChoiceGraph(
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
    for trace in sample_linearizations(cg, samples=30, seed="cyclic"):
        assert trace_in_language(cg, trace), trace


# ── counting ────────────────────────────────────────────────────────────────


def test_exact_count_of_the_diamond():
    assert count_linearizations(_diamond()) == 2


def test_exact_count_of_an_unordered_partial_order_is_factorial():
    po = PartialOrder(children=tuple(Atom(c) for c in "abcd"))
    assert count_linearizations(po) == math.factorial(4)


def test_count_returns_none_past_the_exact_limit():
    po = PartialOrder(children=tuple(Atom(f"a{i}") for i in range(6)))
    assert count_linearizations(po, exact_limit=4) is None
    assert count_linearizations(po, exact_limit=10) == math.factorial(6)


def test_count_returns_none_for_a_choice_graph():
    cg = ChoiceGraph(
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
    assert count_linearizations(cg) is None


def test_count_returns_none_when_a_child_is_composite():
    inner = PartialOrder(children=(Atom("x"), Atom("y")))
    outer = PartialOrder(children=(Atom("a"), inner))
    assert count_linearizations(outer) is None


# ── coverage statement ──────────────────────────────────────────────────────


def test_coverage_statement_has_no_percentage_when_total_is_unknown():
    report = WitnessReport(
        samples=tuple(sample_linearizations(_diamond(), samples=100, seed="s")),
        seed="s",
        counterexamples=(),
        total_linearizations=None,
    )
    statement = report.coverage_statement()
    assert "%" not in statement
    assert "UNKNOWN" in statement
    assert "#P-complete" in statement
    assert statement == (
        "sampled 100 of an UNKNOWN total (counting is #P-complete); "
        "no counterexample found"
    )


def test_coverage_statement_with_a_known_total():
    report = WitnessReport(samples=(("a",),), seed="s", total_linearizations=2)
    assert report.coverage_statement() == (
        "sampled 1 of 2 total linearizations; no counterexample found"
    )


def test_coverage_statement_reports_counterexamples():
    report = WitnessReport(
        samples=(("a",), ("b",)),
        seed="s",
        counterexamples=(("b",),),
        total_linearizations=None,
    )
    statement = report.coverage_statement()
    assert "%" not in statement
    assert "1 counterexample(s) found" in statement
