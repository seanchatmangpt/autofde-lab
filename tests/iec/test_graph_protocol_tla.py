"""Graph, protocol, and TLA+ projection evidence tests for IEC."""

from __future__ import annotations

import pytest

from autofde_lab.iec.brce_reference import brce_reference_system
from autofde_lab.iec.graph_ir import SemanticEdge, SemanticGraph, SemanticNode
from autofde_lab.iec.graph_match import candidate_matches, fingerprints
from autofde_lab.iec.model import EvidenceKind
from autofde_lab.iec.protocol_ir import (
    Invariant,
    StateVariable,
    TransitionSystem,
    make_action,
)
from autofde_lab.iec.tla_projection import render_tla


def two_node_graph(prefix: str) -> SemanticGraph:
    source = SemanticNode.create(
        kind="Protocol",
        key=f"{prefix}:source",
        attributes={"role": "source"},
        evidence_ids=(f"{prefix}:ev-source",),
        evidence_kind=EvidenceKind.OBSERVED,
    )
    target = SemanticNode.create(
        kind="Verifier",
        key=f"{prefix}:target",
        attributes={"role": "verifier"},
        evidence_ids=(f"{prefix}:ev-target",),
        evidence_kind=EvidenceKind.OBSERVED,
    )
    edge = SemanticEdge.create(
        source=source.node_id,
        predicate="verifiedBy",
        target=target.node_id,
        evidence_ids=(f"{prefix}:edge",),
        evidence_kind=EvidenceKind.DERIVED_DETERMINISTIC,
    )
    return SemanticGraph.build((source, target), (edge,))


def test_semantic_graph_identity_ignores_input_order() -> None:
    graph = two_node_graph("a")
    reversed_graph = SemanticGraph.build(
        reversed(graph.nodes),
        reversed(graph.edges),
    )
    assert graph.graph_id == reversed_graph.graph_id


def test_semantic_graph_refuses_dangling_edge() -> None:
    node = SemanticNode.create(kind="A", key="a")
    edge = SemanticEdge.create(
        source=node.node_id,
        predicate="points",
        target="missing",
    )
    with pytest.raises(ValueError, match="dangling semantic edges"):
        SemanticGraph.build((node,), (edge,))


def test_reachability_is_graph_structural_evidence() -> None:
    graph = two_node_graph("a")
    source = next(node for node in graph.nodes if dict(node.attributes)["role"] == "source")
    target = next(node for node in graph.nodes if dict(node.attributes)["role"] == "verifier")
    reachable = graph.reachable(source.node_id)
    assert source.node_id in reachable
    assert target.node_id in reachable


def test_graph_fingerprint_matching_proposes_candidate_not_equivalence() -> None:
    left = two_node_graph("left")
    right = two_node_graph("right")
    matches = candidate_matches(left, right, rounds=2)
    assert len(matches) == 2
    assert all(match.required_verifier == "iec.translation-validation" for match in matches)
    assert {match.left_graph_id for match in matches} == {left.graph_id}
    assert {match.right_graph_id for match in matches} == {right.graph_id}


def test_graph_fingerprint_changes_when_structure_changes() -> None:
    graph = two_node_graph("a")
    baseline = {item.node_id: item.fingerprint for item in fingerprints(graph)}
    source = next(node for node in graph.nodes if dict(node.attributes)["role"] == "source")
    target = next(node for node in graph.nodes if dict(node.attributes)["role"] == "verifier")
    extra = SemanticEdge.create(
        source=target.node_id,
        predicate="references",
        target=source.node_id,
    )
    changed = SemanticGraph.build(graph.nodes, graph.edges + (extra,))
    changed_fp = {item.node_id: item.fingerprint for item in fingerprints(changed)}
    assert baseline != changed_fp


def test_transition_system_refuses_consequence_without_known_variable_reference() -> None:
    variable = StateVariable("phase", '"INIT"')
    bad_action = make_action(
        "Bad",
        guard="TRUE",
        updates={"unknown": "1"},
        consequence=True,
        authority_required=False,
    )
    with pytest.raises(ValueError, match="unknown variables"):
        TransitionSystem(
            name="BadSystem",
            variables=(variable,),
            actions=(bad_action,),
            invariants=(),
        )


def test_transition_system_surfaces_authority_gap_as_data() -> None:
    system = TransitionSystem(
        name="UnsafeSystem",
        variables=(
            StateVariable("phase", '"INIT"'),
            StateVariable("count", "0"),
        ),
        actions=(
            make_action(
                "UnsafeActuation",
                guard='phase = "INIT"',
                updates={"phase": '"DONE"', "count": "count + 1"},
                consequence=True,
                authority_required=False,
            ),
        ),
        invariants=(Invariant("Bound", "count <= 1"),),
    )
    assert system.authority_gaps() == ("UnsafeActuation",)


def test_brce_reference_has_no_declared_authority_gap() -> None:
    system = brce_reference_system()
    assert system.name == "BRCEReference"
    assert system.authority_gaps() == ()
    assert tuple(action.name for action in system.consequence_actions()) == ("Actuate",)


def test_tla_projection_is_deterministic_and_source_bound() -> None:
    system = brce_reference_system()
    first = render_tla(system)
    second = render_tla(system)
    assert first == second
    assert first.source_system_id == system.system_id
    assert first.projection_id == second.projection_id
    assert "---- MODULE BRCEReference ----" in first.tla
    assert "VARIABLES phase, authority, receipt, verified, standing, consequenceCount" in first.tla
    assert "Actuate ==" in first.tla
    assert "INVARIANT NoStandingWithoutReceipt" in first.cfg
    assert "PROPERTY AdmittedEventuallyTerminal" in first.cfg


def test_tla_projection_contains_zero_implicit_verification_claim() -> None:
    projection = render_tla(brce_reference_system())
    # A projection is text plus exact source identity. Model-check standing
    # requires a later SANY/TLC/TLAPS court; there is no result field here.
    assert not hasattr(projection, "passed")
    assert not hasattr(projection, "standing")
