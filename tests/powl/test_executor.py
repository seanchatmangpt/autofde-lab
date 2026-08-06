# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Bounded reference executor: enabling, bounded termination, replay, digest.

The headline property is the first test: a partial order with no precedence
enables *both* children at once. An executor that silently serialized
concurrency would still pass a trace-membership check, so it has to be pinned
directly.
"""

from __future__ import annotations

import random

import pytest

from skdecide.powl.algebra import (
    Atom,
    ChoiceGraph,
    ChoiceGraphEdge,
    NodeId,
    OrderEdge,
    PartialOrder,
    Silent,
)
from skdecide.powl.bounds import ExecutionBound
from skdecide.powl.frequency import Frequency
from skdecide.powl.executor import (
    INITIAL_MARKING,
    ChoiceRecord,
    DeadlockKind,
    Marking,
    ReplayDivergedError,
    classify_stall,
    enabled,
    fire,
    is_final,
    node_at,
    replay,
    trace_of,
)
from skdecide.powl.membership import explain, trace_in_language
from skdecide.powl.semantics import language
from skdecide.powl.normalize import canonical_form, model_digest
from skdecide.powl.refusals import PowlError, PowlRefusal


def _oe(a: int, b: int) -> OrderEdge:
    return OrderEdge(NodeId(a), NodeId(b))


def _ce(a: int, b: int) -> ChoiceGraphEdge:
    return ChoiceGraphEdge(NodeId(a), NodeId(b))


# ── enabling ────────────────────────────────────────────────────────────────


def test_unordered_partial_order_enables_both_children_initially():
    """Concurrency is preserved, not serialized. The headline property."""
    model = PartialOrder((Atom("a"), Atom("b")))
    assert enabled(model) == frozenset({(0,), (1,)})


def test_precedence_edge_enables_only_the_predecessor_then_the_successor():
    model = PartialOrder((Atom("a"), Atom("b")), frozenset({_oe(0, 1)}))
    assert enabled(model) == frozenset({(0,)})
    after = fire(model, INITIAL_MARKING, (0,))
    assert enabled(model, after) == frozenset({(1,)})
    assert not is_final(model, after)
    final = fire(model, after, (1,))
    assert enabled(model, final) == frozenset()
    assert is_final(model, final)


def test_indirect_precedence_is_read_from_the_closure_not_the_reduction():
    # a -> b -> c; the reduction drops a -> c, the closure keeps it.
    model = PartialOrder(
        (Atom("a"), Atom("b"), Atom("c")), frozenset({_oe(0, 1), _oe(1, 2)})
    )
    assert _oe(0, 2) not in model.order
    assert _oe(0, 2) in model.closure
    assert enabled(model) == frozenset({(0,)})


def test_firing_a_path_that_is_not_enabled_is_refused():
    model = PartialOrder((Atom("a"), Atom("b")), frozenset({_oe(0, 1)}))
    with pytest.raises(PowlError) as excinfo:
        fire(model, INITIAL_MARKING, (1,))
    assert excinfo.value.refusal is PowlRefusal.LANGUAGE_MISMATCH


def test_enabled_returns_a_set_and_the_executor_never_picks():
    """Two enabled steps stay two enabled steps; no tie-break is applied."""
    model = PartialOrder((Atom("a"), Atom("b"), Atom("c")))
    live = enabled(model)
    assert isinstance(live, frozenset)
    assert len(live) == 3
    # firing either one leaves the other two, in either order
    assert enabled(model, fire(model, INITIAL_MARKING, (2,))) == frozenset(
        {(0,), (1,)}
    )


# ── cyclic choice graph terminates structurally ─────────────────────────────


def _cyclic_model() -> ChoiceGraph:
    """start=0, end=1, cycle 0 -> 2 -> 3 -> 2, with an exit 2 -> 1."""
    return ChoiceGraph(
        (Silent(), Silent(), Atom("a"), Atom("b")),
        frozenset({_ce(0, 2), _ce(2, 3), _ce(3, 2), _ce(2, 1)}),
        start=0,
        end=1,
    )


def test_cyclic_choice_graph_terminates_and_reports_bound_exhausted():
    model = _cyclic_model()
    bound = ExecutionBound(max_node_visits=3)
    marking = INITIAL_MARKING
    for _ in range(200):  # guard: a hang would be a failure, not a timeout
        live = enabled(model, marking, bound)
        if not live:
            break
        # a policy that refuses to take the exit, to force the cap
        looping = sorted(p for p in live if p != (1,))
        marking = fire(model, marking, looping[0] if looping else sorted(live)[0], bound=bound)
    else:
        pytest.fail("cyclic choice graph did not terminate within 200 steps")

    assert not is_final(model, marking)
    assert classify_stall(model, marking, bound) is DeadlockKind.BOUND_EXHAUSTED
    assert classify_stall(model, marking, bound).value == "BLOCKED:BOUND_EXHAUSTED"


def test_cyclic_choice_graph_can_still_reach_its_end():
    model = _cyclic_model()
    bound = ExecutionBound(max_node_visits=3)
    m = fire(model, INITIAL_MARKING, (0,), bound=bound)
    m = fire(model, m, (2,), bound=bound)
    assert (1,) in enabled(model, m, bound)
    m = fire(model, m, (1,), bound=bound)
    assert is_final(model, m)


def test_visit_counts_are_carried_not_reset_across_re_entry():
    model = _cyclic_model()
    bound = ExecutionBound(max_node_visits=10)
    m = fire(model, INITIAL_MARKING, (0,), bound=bound)
    m = fire(model, m, (2,), bound=bound)
    assert dict(m.visits)[((), 2)] == 1
    m = fire(model, m, (3,), bound=bound)
    m = fire(model, m, (2,), bound=bound)
    assert dict(m.visits)[((), 2)] == 2, "re-entry must increment, never reset"


def test_a_choice_graph_with_no_way_forward_is_a_deadlock_not_a_bound():
    # node 2 has no outgoing edge and is not the end node.
    model = ChoiceGraph(
        (Silent(), Silent(), Atom("a")), frozenset({_ce(0, 2)}), start=0, end=1
    )
    m = fire(model, INITIAL_MARKING, (0,))
    m = fire(model, m, (2,))
    assert enabled(model, m) == frozenset()
    assert not is_final(model, m)
    assert classify_stall(model, m) is DeadlockKind.DEADLOCK


# ── replay ──────────────────────────────────────────────────────────────────


def _record_run(model, bound=ExecutionBound(), seed="run") -> tuple[list[ChoiceRecord], Marking]:
    rng = random.Random(seed)
    marking = INITIAL_MARKING
    records: list[ChoiceRecord] = []
    for step in range(200):
        live = enabled(model, marking, bound)
        if not live:
            break
        chosen = rng.choice(sorted(live))
        records.append(
            ChoiceRecord(
                step=step,
                path=chosen,
                enabled=tuple(sorted(live)),
                chosen=chosen,
                decided_by="test-policy",
            )
        )
        marking = fire(model, marking, chosen, bound=bound)
    return records, marking


def _mixed_model() -> PartialOrder:
    return PartialOrder(
        (
            Atom("a"),
            Atom("b"),
            PartialOrder((Atom("c"), Atom("d")), frozenset({_oe(0, 1)})),
        ),
        frozenset({_oe(0, 1)}),
    )


def test_replay_reproduces_the_identical_final_marking():
    model = _mixed_model()
    records, final = _record_run(model)
    assert records, "the run must have taken at least one step"
    assert replay(model, records) == final


def test_replay_with_a_tampered_choice_diverges():
    model = _mixed_model()
    records, _ = _record_run(model)
    # find a step where more than one path was enabled, and swap the pick
    for i, rec in enumerate(records):
        others = [p for p in rec.enabled if p != rec.chosen]
        if others:
            tampered = list(records)
            tampered[i] = ChoiceRecord(
                rec.step, others[0], rec.enabled, others[0], rec.decided_by
            )
            break
    else:
        pytest.fail("no branching step to tamper with")

    with pytest.raises(ReplayDivergedError) as excinfo:
        replay(model, tampered)
    assert excinfo.value.kind is DeadlockKind.REPLAY_DIVERGED
    assert excinfo.value.kind.value == "BLOCKED:REPLAY_DIVERGED"


def test_replay_with_a_tampered_enabled_set_diverges_even_if_the_pick_is_legal():
    """The record stores the full enabled set precisely so this is catchable."""
    model = _mixed_model()
    records, _ = _record_run(model)
    rec = records[0]
    tampered = [ChoiceRecord(rec.step, rec.path, (rec.chosen,), rec.chosen, "x")] + records[1:]
    if len(rec.enabled) == 1:
        pytest.skip("first step was not branching in this model")
    with pytest.raises(ReplayDivergedError):
        replay(model, tampered)


def test_replay_never_silently_repicks():
    model = PartialOrder((Atom("a"), Atom("b")), frozenset({_oe(0, 1)}))
    bogus = [ChoiceRecord(0, (1,), ((1,),), (1,), "bogus")]
    with pytest.raises(ReplayDivergedError):
        replay(model, bogus)


# ── cross-check against the independent membership implementation ───────────


@pytest.mark.parametrize("seed", [f"s{i}" for i in range(12)])
def test_every_executor_trace_is_in_the_language(seed):
    model = _mixed_model()
    records, final = _record_run(model, seed=seed)
    assert is_final(model, final)
    trace = trace_of(model, records)
    assert sorted(trace) == ["a", "b", "c", "d"]
    assert trace_in_language(model, trace), f"executor produced {trace!r}"


def _branching_choice_graph() -> ChoiceGraph:
    return ChoiceGraph(
        (Silent(), Silent(), Atom("x"), Atom("y")),
        frozenset({_ce(0, 2), _ce(0, 3), _ce(2, 1), _ce(3, 1)}),
        start=0,
        end=1,
    )


def test_cross_check_covers_a_choice_graph_too():
    model = _branching_choice_graph()
    seen = set()
    for seed in range(30):
        records, final = _record_run(model, seed=f"cg{seed}")
        assert is_final(model, final)
        trace = trace_of(model, records)
        assert trace_in_language(model, trace), f"executor produced {trace!r}"
        seen.add(trace)
    assert seen == {("x",), ("y",)}, "both branches must be reachable"


def test_membership_decides_a_choice_graph_nested_in_a_partial_order():
    """Positive cross-check over a nested choice graph.

    This test previously pinned a *gap*: ``membership.static_labels`` returns
    ``()`` for a :class:`~skdecide.powl.algebra.ChoiceGraph` (its length is
    branch-dependent), so an enclosing partial order's label multiset came out
    short and a genuinely-in-language trace was rejected. ``membership`` now
    enumerates the branch options (``membership.label_options``) and checks the
    partial order against each, so this is a real independent check of the
    executor's output rather than a recorded limitation.
    """
    model = PartialOrder((Atom("a"), _branching_choice_graph()), frozenset({_oe(0, 1)}))
    records, final = _record_run(model, seed="nested")
    assert is_final(model, final)
    trace = trace_of(model, records)
    assert trace[0] == "a" and trace[1] in {"x", "y"} and len(trace) == 2
    assert trace_in_language(model, trace), explain(model, trace)
    # and it still rejects: order reversed, and a branch the graph cannot emit
    assert not trace_in_language(model, tuple(reversed(trace)))
    assert not trace_in_language(model, ("a", "z"))


# ── digest / normalization ──────────────────────────────────────────────────


def test_model_digest_identical_for_closure_and_reduction_inputs():
    kids = (Atom("a"), Atom("b"), Atom("c"))
    reduced = PartialOrder(kids, frozenset({_oe(0, 1), _oe(1, 2)}))
    closed = PartialOrder(kids, frozenset({_oe(0, 1), _oe(1, 2), _oe(0, 2)}))
    assert model_digest(reduced) == model_digest(closed)
    assert len(model_digest(reduced)) == 64


def test_model_digest_identical_for_differently_ordered_children():
    forward = PartialOrder(
        (Atom("a"), Atom("b"), Atom("c")), frozenset({_oe(0, 1), _oe(1, 2)})
    )
    reversed_ = PartialOrder(
        (Atom("c"), Atom("b"), Atom("a")), frozenset({_oe(2, 1), _oe(1, 0)})
    )
    assert model_digest(forward) == model_digest(reversed_)


def test_model_digest_distinguishes_genuinely_different_orders():
    kids = (Atom("a"), Atom("b"), Atom("c"))
    assert model_digest(PartialOrder(kids, frozenset({_oe(0, 1)}))) != model_digest(
        PartialOrder(kids, frozenset({_oe(1, 0)}))
    )
    assert model_digest(PartialOrder(kids)) != model_digest(
        PartialOrder(kids, frozenset({_oe(0, 1)}))
    )


def test_canonical_form_is_idempotent_and_semantics_preserving():
    model = _mixed_model()
    once = canonical_form(model)
    assert model_digest(once) == model_digest(canonical_form(once))
    records, final = _record_run(once)
    assert is_final(once, final)
    assert trace_in_language(once, trace_of(once, records))


def test_marking_digest_material_is_sorted_not_set_ordered():
    model = PartialOrder((Atom("a"), Atom("b"), Atom("c")))
    m = INITIAL_MARKING
    for p in [(2,), (0,), (1,)]:
        m = fire(model, m, p)
    material = m.digest_material()
    assert material["completed_paths"] == sorted(material["completed_paths"])
    assert material["fires"] == 3


def test_node_at_addresses_nested_nodes_and_refuses_dangling_paths():
    model = _mixed_model()
    assert node_at(model, ()) is model
    assert node_at(model, (2, 1)) == Atom("d")
    with pytest.raises(PowlError) as excinfo:
        node_at(model, (0, 0))
    assert excinfo.value.refusal is PowlRefusal.DANGLING_REFERENCE


# ── repetition (Frequency) ──────────────────────────────────────────────────
#
# These pin the defect that no earlier test could see: nothing in this file ever
# fired a frequency-carrying model, so the executor could ignore ``frequency``
# entirely and still look correct. It declared a COMPLETE traversal whose trace
# was outside the model's own language, i.e. two components of this package
# contradicting each other.


def _greedy_run(model, bound=ExecutionBound(), seed="freq"):
    """Fire until nothing is enabled. Returns (marking, observable trace)."""
    rng = random.Random(seed)
    marking = INITIAL_MARKING
    trace: list[str] = []
    for _ in range(500):
        live = enabled(model, marking, bound)
        if not live:
            break
        chosen = rng.choice(sorted(live))
        node = node_at(model, chosen)
        if isinstance(node, Atom):
            trace.append(node.label)
        marking = fire(model, marking, chosen, bound=bound)
    return marking, tuple(trace)


def test_a_frequency_of_two_runs_two_rounds_not_one():
    """The exact reproducer. Before the fix: 2 fires, ``is_final`` True."""
    model = PartialOrder((Atom("a"), Atom("b")), frozenset(), frequency=Frequency(2, 2))
    marking, trace = _greedy_run(model)
    assert marking.fires == 4, f"expected two rounds of two atoms, got {trace!r}"
    assert is_final(model, marking)
    assert sorted(trace) == ["a", "a", "b", "b"]
    # and the minimum trace length really is 4 — a single round is not enough
    assert min(len(t) for t in _lang(model)) == 4


def test_a_frequency_of_two_is_not_final_after_one_round():
    model = PartialOrder((Atom("a"), Atom("b")), frozenset(), frequency=Frequency(2, 2))
    m = fire(model, INITIAL_MARKING, (0,))
    m = fire(model, m, (1,))
    assert not is_final(model, m), "one round of a (2, 2) composite is not complete"
    assert enabled(model, m), "the second round must still be offered"


def test_a_skippable_composite_is_final_with_zero_rounds():
    """``Frequency(0, 1)``: ``min=0`` must be reachable, i.e. final immediately."""
    model = PartialOrder((Atom("a"), Atom("b")), frozenset(), frequency=Frequency(0, 1))
    assert is_final(model, INITIAL_MARKING)
    # skippable is not the same as empty: the round may still be run...
    assert enabled(model, INITIAL_MARKING) == frozenset({(0,), (1,)})
    # ...and a half-run round is NOT final, or the trace ('a',) would pass
    half = fire(model, INITIAL_MARKING, (0,))
    assert not is_final(model, half)
    assert () in _lang(model) and ("a",) not in _lang(model)


def test_a_skippable_composite_nested_in_a_partial_order_may_be_skipped():
    inner = PartialOrder((Atom("c"), Atom("d")), frozenset(), frequency=Frequency(0, 1))
    model = PartialOrder((Atom("a"), inner), frozenset({_oe(0, 1)}))
    m = fire(model, INITIAL_MARKING, (0,))
    assert is_final(model, m), "the skippable child may contribute zero rounds"


def test_an_unbounded_frequency_terminates_structurally_not_by_raising():
    """``max=None`` is bounded by ``max_node_visits``, and runs out of enabled
    nodes rather than raising — the same rule that terminates a cyclic choice
    graph. Visit counters stay monotone (law 2)."""
    model = PartialOrder(
        (Atom("a"), Atom("b")), frozenset(), frequency=Frequency(1, None)
    )
    bound = ExecutionBound(max_node_visits=3)
    marking, trace = _greedy_run(model, bound=bound)
    assert marking.fires == 6, f"three rounds of two atoms, got {trace!r}"
    assert is_final(model, marking)
    assert enabled(model, marking, bound) == frozenset()


def test_the_executor_still_never_chooses_under_repetition():
    """Both children of an unordered repeating composite stay simultaneously
    enabled — repetition must not have serialized concurrency."""
    model = PartialOrder((Atom("a"), Atom("b")), frozenset(), frequency=Frequency(2, 2))
    m = fire(model, INITIAL_MARKING, (0,))
    m = fire(model, m, (1,))
    assert enabled(model, m) == frozenset({(0,), (1,)})


# ── the cross-check that would have caught this originally ──────────────────


def _lang(model, *, max_traces: int = 400, max_unrolls: int = 4):
    return language(model, max_traces=max_traces, max_unrolls=max_unrolls)


def _frequency_models():
    """Models whose completion the static membership checker cannot decide.

    ``membership.trace_in_language`` refuses a non-``ONCE`` frequency outright
    (``IRREDUCIBLE_PROJECTION``: its label multiset is not static), so the
    independent oracle for these is :mod:`skdecide.powl.semantics`, which is a
    different algorithm from the executor's and imports none of it.
    """
    return {
        "po-exactly-2": PartialOrder(
            (Atom("a"), Atom("b")), frozenset(), frequency=Frequency(2, 2)
        ),
        "po-ordered-exactly-2": PartialOrder(
            (Atom("a"), Atom("b")), frozenset({_oe(0, 1)}), frequency=Frequency(2, 2)
        ),
        "po-skippable": PartialOrder(
            (Atom("a"), Atom("b")), frozenset({_oe(0, 1)}), frequency=Frequency(0, 1)
        ),
        "po-1-to-3": PartialOrder(
            (Atom("a"), Atom("b")), frozenset({_oe(0, 1)}), frequency=Frequency(1, 3)
        ),
        "nested-repeat": PartialOrder(
            (
                Atom("a"),
                PartialOrder(
                    (Atom("c"), Atom("d")),
                    frozenset({_oe(0, 1)}),
                    frequency=Frequency(2, 2),
                ),
            ),
            frozenset({_oe(0, 1)}),
        ),
        "repeat-of-nested": PartialOrder(
            (
                Atom("a"),
                PartialOrder((Atom("c"), Atom("d")), frozenset({_oe(0, 1)})),
            ),
            frozenset({_oe(0, 1)}),
            frequency=Frequency(2, 2),
        ),
        "skippable-nested": PartialOrder(
            (
                Atom("a"),
                PartialOrder(
                    (Atom("c"), Atom("d")),
                    frozenset({_oe(0, 1)}),
                    frequency=Frequency(0, 1),
                ),
            ),
            frozenset({_oe(0, 1)}),
        ),
        "repeat-inside-a-choice-branch": ChoiceGraph(
            (
                Silent(),
                Silent(),
                PartialOrder(
                    (Atom("x"), Atom("y")),
                    frozenset({_oe(0, 1)}),
                    frequency=Frequency(2, 2),
                ),
                Atom("z"),
            ),
            frozenset({_ce(0, 2), _ce(0, 3), _ce(2, 1), _ce(3, 1)}),
            start=0,
            end=1,
        ),
        "choice-graph-twice": ChoiceGraph(
            (Silent(), Silent(), Atom("x"), Atom("y")),
            frozenset({_ce(0, 2), _ce(0, 3), _ce(2, 1), _ce(3, 1)}),
            start=0,
            end=1,
            frequency=Frequency(2, 2),
        ),
    }


@pytest.mark.parametrize("name", sorted(_frequency_models()))
@pytest.mark.parametrize("seed", [f"x{i}" for i in range(8)])
def test_every_final_frequency_trace_is_in_the_language(name, seed):
    """The invariant that was violated: a marking the executor calls FINAL must
    have an observable trace inside the model's own language.

    A general property over several frequency-carrying models, not one case —
    the reason no existing test caught the defect is that none of them fired a
    model carrying a frequency at all.
    """
    model = _frequency_models()[name]
    marking, trace = _greedy_run(model, seed=seed)
    assert is_final(model, marking), (
        f"{name}/{seed}: ran out of enabled nodes at a non-final marking, trace={trace!r}"
    )
    lang = _lang(model)
    assert trace in lang, (
        f"{name}/{seed}: executor called {trace!r} a COMPLETE traversal, but it is "
        f"not in the language of the model"
    )


@pytest.mark.parametrize("name", sorted(_frequency_models()))
def test_a_frequency_model_still_refuses_the_static_membership_check(name):
    """Pins *why* the cross-check above uses ``semantics`` and not ``membership``:
    the static checker declines rather than guessing. Recorded, not worked around."""
    model = _frequency_models()[name]
    with pytest.raises(PowlError) as excinfo:
        trace_in_language(model, ("a", "b"))
    assert excinfo.value.refusal is PowlRefusal.IRREDUCIBLE_PROJECTION
