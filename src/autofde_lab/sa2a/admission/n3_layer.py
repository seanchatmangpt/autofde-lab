"""Admitted N3 derivation and graph implication layer (RFC-SA2A-001 §17).

Implements N3 implication rules over RDF graphs.
Derivations produced by this layer are strictly marked as candidates requiring
admitted standing, never possessing ambient authority or side-effecting DO.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import rdflib
from rdflib.term import Node

from autofde_lab.sa2a.admission.datalog_layer import (
    DatalogAtom,
    DatalogEngine,
    DatalogRule,
    Term,
    is_variable,
)

SA2A_NS = rdflib.Namespace("https://spec.autofde.org/sa2a#")


@dataclass(frozen=True)
class CandidateDerivation:
    """A derived graph candidate awaiting admission or standing (§17).

    CRITICAL INVARIANT: Candidate derivations NEVER possess ambient execution
    authority (A = μ(O*)), and NEVER side-effect execution DO. They are pure
    standing-requiring hypotheses.
    """

    subject: Node
    predicate: Node
    object: Node
    rule_id: str
    requires_standing: bool = True
    authority_verified: bool = False
    side_effect_do: bool = False

    def to_rdf_triple(self) -> Tuple[Node, Node, Node]:
        return (self.subject, self.predicate, self.object)


@dataclass(frozen=True)
class N3ImplicationRule:
    """N3 Implication Rule: { Body } => { Head } (§17).

    Under the safe profile:
    - Body is a set of graph triple patterns (binary relations).
    - Head is a set of implied triple patterns.
    - Range-restricted: Variables in Head must be bound by Body.
    - No ungrounded term synthesis.
    """

    rule_id: str
    body_patterns: Tuple[Tuple[Term, Term, Term], ...]
    head_patterns: Tuple[Tuple[Term, Term, Term], ...]
    description: str = ""

    def __post_init__(self):
        # Range restriction check: all variables in head must appear in body
        body_vars: Set[str] = set()
        for s, p, o in self.body_patterns:
            for term in (s, p, o):
                if is_variable(term):
                    body_vars.add(str(term))

        head_vars: Set[str] = set()
        for s, p, o in self.head_patterns:
            for term in (s, p, o):
                if is_variable(term):
                    head_vars.add(str(term))

        unbound = head_vars - body_vars
        if unbound:
            raise ValueError(
                f"Range-restriction violation in N3 rule '{self.rule_id}': "
                f"Head variable(s) {unbound} not bound in body (violates §17)."
            )

    def to_datalog_rules(self) -> List[DatalogRule]:
        """Convert N3 implication { Body } => { Head } into equivalent Datalog rules."""
        datalog_body = tuple(DatalogAtom(p, s, o) for s, p, o in self.body_patterns)
        rules = []
        for s, p, o in self.head_patterns:
            head_atom = DatalogAtom(p, s, o)
            rules.append(
                DatalogRule(
                    head=head_atom,
                    body=datalog_body,
                    name=f"{self.rule_id}_{head_atom}",
                )
            )
        return rules


class N3RuleEngine:
    """Admitted N3 derivation engine executing graph implication rules (§17).

    Executes admitted implication rules over graphs, marking derivations as candidates
    requiring standing, and ensuring zero side-effecting DO execution.
    """

    def __init__(
        self,
        rules: Optional[Sequence[N3ImplicationRule]] = None,
        max_iterations: int = 500,
    ):
        self.rules: List[N3ImplicationRule] = list(rules) if rules else []
        self.max_iterations = max_iterations

    def add_rule(self, rule: N3ImplicationRule) -> None:
        """Register an admitted N3 implication rule."""
        self.rules.append(rule)

    def apply_implications(
        self,
        graph: rdflib.Graph,
    ) -> Tuple[List[CandidateDerivation], rdflib.Graph, int]:
        """Execute admitted N3 implication rules over an RDF graph.

        Evaluates rules using least fixpoint semantics until convergence.
        Every newly derived triple is wrapped in a `CandidateDerivation` with:
          - requires_standing = True
          - authority_verified = False
          - side_effect_do = False (ZERO ambient actuation)

        Args:
            graph: Base admitted RDF graph.

        Returns:
            Tuple of (candidate_derivations, updated_graph, iteration_count).
        """
        # Convert all N3 rules to Datalog rules
        datalog_rules: List[DatalogRule] = []
        rule_map: Dict[str, str] = {}  # Map datalog rule string to N3 rule_id
        for r in self.rules:
            for dr in r.to_datalog_rules():
                datalog_rules.append(dr)
                rule_map[str(dr.head.predicate)] = r.rule_id

        # Run safe Datalog fixpoint
        datalog_engine = DatalogEngine(
            rules=datalog_rules, max_iterations=self.max_iterations
        )

        initial_triples = set(graph)
        result_graph, iterations = datalog_engine.execute_graph_fixpoint(graph)
        derived_triples = set(result_graph) - initial_triples

        # Annotate derivations as candidates requiring standing
        candidates: List[CandidateDerivation] = []
        for s, p, o in derived_triples:
            rule_id = rule_map.get(str(p), "n3_inferred")
            candidates.append(
                CandidateDerivation(
                    subject=s,
                    predicate=p,
                    object=o,
                    rule_id=rule_id,
                    requires_standing=True,
                    authority_verified=False,
                    side_effect_do=False,
                )
            )

        return candidates, result_graph, iterations
