"""Semantic frontier, Claude handoff, formal-evidence, and graph-delta tests."""

from __future__ import annotations

import pytest

from autofde_lab.iec.brce_reference import brce_reference_system
from autofde_lab.iec.claude_contract import ArchaeologyHypothesis, make_packet
from autofde_lab.iec.formal import (
    FormalCounterexampleTrace,
    FormalResult,
    FormalVerificationEvidence,
    make_tlc_intent,
)
from autofde_lab.iec.frontier import FrontierItem, FrontierPlanner, UnknownKind
from autofde_lab.iec.graph_ir import SemanticEdge, SemanticGraph, SemanticNode
from autofde_lab.iec.model import EvidenceKind
from autofde_lab.iec.semantic_diff import diff_graphs
from autofde_lab.iec.tla_projection import render_tla


def frontier_item(
    question: str,
    *,
    information: float,
    cost: float,
    recurrence: int = 1,
    mechanization: float = 0.0,
    risk: float = 0.0,
    dependencies: tuple[str, ...] = (),
) -> FrontierItem:
    return FrontierItem(
        kind=UnknownKind.EQUIVALENCE,
        question=question,
        subject_ids=("subject",),
        evidence_ids=("evidence",),
        expected_information_bits=information,
        expected_reasoning_units=cost,
        recurrence_count=recurrence,
        mechanization_potential=mechanization,
        consequence_risk=risk,
        dependencies=dependencies,
    )


def test_frontier_prioritizes_future_reasoning_elimination() -> None:
    one_off = frontier_item(
        "one-off curiosity",
        information=10,
        cost=10,
        recurrence=1,
        mechanization=0,
    )
    repeated = frontier_item(
        "repeated transform",
        information=4,
        cost=4,
        recurrence=20,
        mechanization=1.0,
    )
    plan = FrontierPlanner().plan(
        (one_off, repeated),
        budget_units=4,
    )
    assert plan.selected == (repeated,)
    assert plan.deferred == (one_off,)


def test_frontier_respects_dependency_and_budget() -> None:
    prerequisite = frontier_item(
        "resolve parser identity",
        information=1,
        cost=1,
    )
    dependent = frontier_item(
        "resolve semantic role",
        information=100,
        cost=2,
        dependencies=(prerequisite.item_id,),
    )
    plan = FrontierPlanner().plan(
        (dependent, prerequisite),
        budget_units=3,
    )
    assert plan.selected[0] == prerequisite
    assert dependent in plan.selected


def test_claude_packet_requires_exact_bounded_frontier() -> None:
    item = frontier_item("what is this protocol?", information=2, cost=1)
    packet = make_packet(
        exact_subject_ids=("sha:subject",),
        frontier_items=(item,),
        evidence_ids=("ev",),
    )
    assert packet.frontier_items == (item,)
    assert "preserve UNKNOWN" in packet.hard_constraints


def test_claude_hypothesis_cannot_self_admit_or_gain_authority() -> None:
    item = frontier_item("same protocol?", information=2, cost=1)
    packet = make_packet(
        exact_subject_ids=("subject",),
        frontier_items=(item,),
        evidence_ids=("ev",),
    )
    hypothesis = ArchaeologyHypothesis(
        packet_id=packet.packet_id,
        subject="a",
        predicate="sameProtocolCandidate",
        object="b",
        evidence_ids=("ev",),
        exclusions=("similarity is not equivalence",),
        falsifier="translation-validator finds different transition trace",
    )
    assert hypothesis.evidence_kind is EvidenceKind.INFERRED_CANDIDATE
    assert hypothesis.authority == "NONE"
    assert (
        hypothesis.as_semantic_claim().evidence_kind is EvidenceKind.INFERRED_CANDIDATE
    )

    with pytest.raises(ValueError, match="starts as INFERRED_CANDIDATE"):
        ArchaeologyHypothesis(
            packet_id=packet.packet_id,
            subject="a",
            predicate="same",
            object="b",
            evidence_ids=("ev",),
            exclusions=(),
            falsifier="x",
            evidence_kind=EvidenceKind.ADMITTED,
        )


def test_tlc_intent_is_exact_projection_bound_and_zero_authority() -> None:
    projection = render_tla(brce_reference_system())
    intent = make_tlc_intent(
        projection,
        tool_version="1.0",
        executable_digest="sha256:tool",
        module_path="BRCEReference.tla",
        config_path="BRCEReference.cfg",
    )
    assert intent.projection_id == projection.projection_id
    assert intent.tool_identity == "tlc2.TLC"
    assert intent.authority == "NONE"
    assert "BRCEReference.tla" in intent.argv


def test_formal_pass_requires_zero_exit_and_no_counterexample() -> None:
    projection = render_tla(brce_reference_system())
    intent = make_tlc_intent(
        projection,
        tool_version="1",
        executable_digest="sha256:tool",
        module_path="m.tla",
        config_path="m.cfg",
    )
    evidence = FormalVerificationEvidence(
        intent_id=intent.intent_id,
        projection_id=projection.projection_id,
        exit_code=0,
        result=FormalResult.PASS,
        properties_checked=("NoStandingWithoutReceipt",),
        stdout_digest="sha256:stdout",
        stderr_digest="sha256:stderr",
        states_generated=10,
        distinct_states=8,
    )
    assert evidence.result is FormalResult.PASS
    assert evidence.evidence_id

    with pytest.raises(ValueError, match="PASS requires exit code 0"):
        FormalVerificationEvidence(
            intent_id=intent.intent_id,
            projection_id=projection.projection_id,
            exit_code=1,
            result=FormalResult.PASS,
            properties_checked=("P",),
            stdout_digest="o",
            stderr_digest="e",
        )


def test_formal_counterexample_requires_durable_trace() -> None:
    trace = FormalCounterexampleTrace.from_states(
        "AtMostOneConsequence",
        ("state:0", "state:1", "state:2"),
    )
    evidence = FormalVerificationEvidence(
        intent_id="intent",
        projection_id="projection",
        exit_code=12,
        result=FormalResult.COUNTEREXAMPLE,
        properties_checked=("AtMostOneConsequence",),
        stdout_digest="out",
        stderr_digest="err",
        counterexample=trace,
    )
    assert evidence.counterexample is trace

    with pytest.raises(ValueError, match="requires trace"):
        FormalVerificationEvidence(
            intent_id="intent",
            projection_id="projection",
            exit_code=12,
            result=FormalResult.COUNTEREXAMPLE,
            properties_checked=("P",),
            stdout_digest="out",
            stderr_digest="err",
        )


def graph(version: int) -> SemanticGraph:
    a = SemanticNode.create(kind="Protocol", key="A")
    b = SemanticNode.create(kind="Verifier", key="B")
    nodes = [a, b]
    edges = [
        SemanticEdge.create(
            source=a.node_id,
            predicate="verifiedBy",
            target=b.node_id,
        )
    ]
    if version > 1:
        c = SemanticNode.create(kind="Receipt", key="C")
        nodes.append(c)
        edges.append(
            SemanticEdge.create(
                source=b.node_id,
                predicate="produces",
                target=c.node_id,
            )
        )
    return SemanticGraph.build(nodes, edges)


def test_semantic_diff_preserves_added_topology() -> None:
    base = graph(1)
    candidate = graph(2)
    delta = diff_graphs(base, candidate)
    assert not delta.empty
    assert len(delta.added_node_ids) == 1
    assert len(delta.added_edge_ids) == 1
    assert delta.removed_node_ids == ()


def test_semantic_diff_is_empty_for_reordered_same_graph() -> None:
    base = graph(1)
    candidate = SemanticGraph.build(reversed(base.nodes), reversed(base.edges))
    delta = diff_graphs(base, candidate)
    assert delta.empty
