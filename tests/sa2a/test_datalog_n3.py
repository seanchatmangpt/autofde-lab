"""Unit tests for Safe Finite Datalog (§16) and Admitted N3 Engine (§17)."""

import pytest
import rdflib
from rdflib import Namespace

from autofde_lab.sa2a.admission.datalog_layer import (
    DatalogAtom,
    DatalogEngine,
    DatalogRule,
)
from autofde_lab.sa2a.admission.n3_layer import (
    N3ImplicationRule,
    N3RuleEngine,
)

EX = Namespace("http://example.org/")


def test_datalog_range_restriction_guard():
    """Verify that rules violating range-restriction raise ValueError (§16)."""
    # Head has variable ?Y that does not appear in body
    with pytest.raises(ValueError, match="Range-restriction violation"):
        DatalogRule(
            head=DatalogAtom("reaches", "?X", "?Y"),
            body=(DatalogAtom("edge", "?X", "node_a"),),
            name="unsafe_rule",
        )


def test_datalog_deterministic_least_fixpoint_transitive_reachability():
    """Test deterministic least-fixpoint closure over transitive reachability.

    Graph: a -> b -> c -> d
    Base rule: Reaches(X, Y) :- Edge(X, Y)
    Transitive rule: Reaches(X, Y) :- Reaches(X, Z), Edge(Z, Y)
    """
    engine = DatalogEngine()

    # Rule 1: reaches(X, Y) :- edge(X, Y)
    rule_base = DatalogRule(
        head=DatalogAtom("reaches", "?X", "?Y"),
        body=(DatalogAtom("edge", "?X", "?Y"),),
        name="reach_base",
    )

    # Rule 2: reaches(X, Y) :- reaches(X, Z), edge(Z, Y)
    rule_trans = DatalogRule(
        head=DatalogAtom("reaches", "?X", "?Y"),
        body=(
            DatalogAtom("reaches", "?X", "?Z"),
            DatalogAtom("edge", "?Z", "?Y"),
        ),
        name="reach_transitive",
    )

    engine.add_rule(rule_base)
    engine.add_rule(rule_trans)

    # Base edges: a->b, b->c, c->d
    initial_facts = [
        DatalogAtom("edge", "a", "b"),
        DatalogAtom("edge", "b", "c"),
        DatalogAtom("edge", "c", "d"),
    ]

    facts, iterations = engine.execute_fixpoint(initial_facts)

    # Check termination
    assert iterations >= 3
    assert (
        len(facts) == 3 + 6
    )  # 3 edges + 6 reachability pairs (ab, bc, cd, ac, bd, ad)

    expected_pairs = {
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
        ("a", "c"),
        ("b", "d"),
        ("a", "d"),
    }

    derived_reach = {(f.args[0], f.args[1]) for f in facts if f.predicate == "reaches"}

    assert derived_reach == expected_pairs


def test_datalog_rdf_graph_fixpoint():
    """Test executing Datalog least-fixpoint directly over an rdflib.Graph."""
    g = rdflib.Graph()
    parent_of = EX["parentOf"]
    ancestor_of = EX["ancestorOf"]

    # Facts: Alice parent of Bob, Bob parent of Charlie
    g.add((EX["Alice"], parent_of, EX["Bob"]))
    g.add((EX["Bob"], parent_of, EX["Charlie"]))

    # ancestorOf(X, Y) :- parentOf(X, Y)
    r1 = DatalogRule(
        head=DatalogAtom(ancestor_of, "?X", "?Y"),
        body=(DatalogAtom(parent_of, "?X", "?Y"),),
    )
    # ancestorOf(X, Y) :- ancestorOf(X, Z), parentOf(Z, Y)
    r2 = DatalogRule(
        head=DatalogAtom(ancestor_of, "?X", "?Y"),
        body=(DatalogAtom(ancestor_of, "?X", "?Z"), DatalogAtom(parent_of, "?Z", "?Y")),
    )

    engine = DatalogEngine([r1, r2])
    closed_graph, iters = engine.execute_graph_fixpoint(g)

    assert (EX["Alice"], ancestor_of, EX["Bob"]) in closed_graph
    assert (EX["Bob"], ancestor_of, EX["Charlie"]) in closed_graph
    assert (EX["Alice"], ancestor_of, EX["Charlie"]) in closed_graph
    assert len(closed_graph) == 5  # 2 parentOf + 3 ancestorOf


def test_datalog_cyclic_graph_termination():
    """Test that a cyclic graph terminates cleanly without infinite loops."""
    engine = DatalogEngine()
    engine.add_rule(
        DatalogRule(
            head=DatalogAtom("reaches", "?X", "?Y"),
            body=(DatalogAtom("edge", "?X", "?Y"),),
        )
    )
    engine.add_rule(
        DatalogRule(
            head=DatalogAtom("reaches", "?X", "?Y"),
            body=(DatalogAtom("reaches", "?X", "?Z"), DatalogAtom("edge", "?Z", "?Y")),
        )
    )

    # Cycle: a -> b -> a
    cyclic_edges = [
        DatalogAtom("edge", "a", "b"),
        DatalogAtom("edge", "b", "a"),
    ]

    facts, iters = engine.execute_fixpoint(cyclic_edges)
    assert iters <= 5
    # Should include: edge(a, b), edge(b, a), reaches(a, b), reaches(b, a), reaches(a, a), reaches(b, b)
    reach_facts = {f for f in facts if f.predicate == "reaches"}
    assert len(reach_facts) == 4


def test_n3_rule_engine_standing_and_zero_do():
    """Test N3RuleEngine ensures derived facts require standing and zero DO side effects (§17)."""
    # Rule: { ?agent ex:hasRole ex:Admin } => { ?agent ex:hasPermission ex:Write }
    n3_rule = N3ImplicationRule(
        rule_id="role_permission_rule",
        body_patterns=(("?A", EX["hasRole"], EX["Admin"]),),
        head_patterns=(("?A", EX["hasPermission"], EX["Write"]),),
        description="Admin grants write permission candidate",
    )

    engine = N3RuleEngine([n3_rule])

    g = rdflib.Graph()
    g.add((EX["Agent42"], EX["hasRole"], EX["Admin"]))

    candidates, result_graph, iterations = engine.apply_implications(g)

    # Assert derived triple is present in result graph
    assert (EX["Agent42"], EX["hasPermission"], EX["Write"]) in result_graph

    # Assert candidate derivation invariants (§17)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.subject == EX["Agent42"]
    assert cand.predicate == EX["hasPermission"]
    assert cand.object == EX["Write"]
    assert cand.requires_standing is True  # Must require admitted standing
    assert cand.authority_verified is False
    assert cand.side_effect_do is False  # Zero ambient DO execution authority


def test_n3_range_restriction_guard():
    """Verify N3 range restriction guard raises error on unbound head variables."""
    with pytest.raises(ValueError, match="Range-restriction violation"):
        N3ImplicationRule(
            rule_id="invalid_n3",
            body_patterns=(("?A", EX["hasRole"], EX["Admin"]),),
            head_patterns=(("?A", EX["grantsTo"], "?UnboundTarget"),),
        )
