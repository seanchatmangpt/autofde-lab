"""Safe Finite Datalog Profile for Semantic A2A (RFC-SA2A-001 §16).

Implements deterministic least-fixpoint closure over finite domains.
Enforces:
- Function-free terms (constants and variables only).
- Range-restriction: Every variable occurring in the rule head must also occur
  in at least one positive body atom.
- Finite-domain rules of form Head(X, Y) :- Body1(X, Z), Body2(Z, Y).
- Finite termination with no unbounded term invention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import rdflib
from rdflib.term import Literal, Node, URIRef

# Type aliases for Datalog terms and atoms
Term = Union[
    Node, str
]  # Can be an rdflib Node (URIRef, BNode, Literal) or variable / constant string


def is_variable(term: Term) -> bool:
    """Check if a term represents a Datalog variable.

    A term is considered a variable if:
    1. It is a string starting with '?' or uppercase letter (standard Datalog convention).
    2. Or rdflib.Variable if rdflib Variable is used.
    """
    if isinstance(term, rdflib.Variable):
        return True
    if isinstance(term, str):
        if term.startswith("?"):
            return True
    return False


@dataclass(frozen=True)
class DatalogAtom:
    """An atom in a Datalog rule: Predicate(arg0, arg1, ...).

    For RDF / binary relations, predicate is the relation/property IRI,
    and arguments are typically (subject, object) or (arg0, arg1).
    """

    predicate: Term
    args: Tuple[Term, ...]

    def __init__(self, predicate: Term, *args: Term):
        object.__setattr__(self, "predicate", predicate)
        object.__setattr__(self, "args", tuple(args))

    @property
    def variables(self) -> Set[str]:
        """Set of variable names appearing in this atom."""
        vars_found = set()
        if is_variable(self.predicate):
            vars_found.add(str(self.predicate))
        for arg in self.args:
            if is_variable(arg):
                vars_found.add(str(arg))
        return vars_found

    @property
    def is_ground(self) -> bool:
        """True if the atom contains no variables."""
        return len(self.variables) == 0

    def apply_binding(self, binding: Dict[str, Node]) -> DatalogAtom:
        """Substitute variables according to the provided binding."""
        new_pred = (
            binding.get(str(self.predicate), self.predicate)
            if is_variable(self.predicate)
            else self.predicate
        )
        new_args = tuple(
            binding.get(str(arg), arg) if is_variable(arg) else arg for arg in self.args
        )
        return DatalogAtom(new_pred, *new_args)

    def to_rdf_triple(self) -> Optional[Tuple[Node, Node, Node]]:
        """Convert a binary ground atom Pred(S, O) to an RDF triple (S, Pred, O)."""
        if len(self.args) == 2:
            s, o = self.args[0], self.args[1]
            p = self.predicate
            # Coerce strings to URIRef/Literal if needed
            s_node = s if isinstance(s, Node) else URIRef(s)
            p_node = p if isinstance(p, Node) else URIRef(p)
            o_node = (
                o
                if isinstance(o, Node)
                else (URIRef(o) if str(o).startswith("http") else Literal(o))
            )
            return (s_node, p_node, o_node)
        return None

    @classmethod
    def from_rdf_triple(cls, triple: Tuple[Node, Node, Node]) -> DatalogAtom:
        """Create a binary atom Pred(S, O) from an RDF triple (S, P, O)."""
        s, p, o = triple
        return cls(p, s, o)

    def __str__(self) -> str:
        args_str = ", ".join(str(a) for a in self.args)
        return f"{self.predicate}({args_str})"


@dataclass(frozen=True)
class DatalogRule:
    """A range-restricted, function-free Datalog rule.

    Head :- Body1, Body2, ..., BodyN.
    """

    head: DatalogAtom
    body: Tuple[DatalogAtom, ...]
    name: Optional[str] = None

    def __post_init__(self):
        # Range-restriction check (§16): Every variable in Head must appear in Body
        head_vars = self.head.variables
        body_vars: Set[str] = set()
        for b in self.body:
            body_vars.update(b.variables)

        unbound = head_vars - body_vars
        if unbound:
            raise ValueError(
                f"Range-restriction violation in rule {self.name or str(self)}: "
                f"Head variable(s) {unbound} do not appear in body (violates §16)."
            )

    def __str__(self) -> str:
        body_str = ", ".join(str(b) for b in self.body)
        return f"{self.head} :- {body_str}."


class DatalogEngine:
    """Safe Finite Datalog engine executing deterministic least-fixpoint closure (§16).

    Guarantees:
    1. Function-free: No complex functor terms, ensuring finite Herbrand universe.
    2. Range-restricted: Head vars ⊆ Body vars, ensuring no new term invention.
    3. Monotonic bottom-up $T_P$ operator execution until $F_{n+1} = F_n$.
    4. Deterministic termination within finite iterations bounded by $|Domain|^{arity}$.
    """

    def __init__(
        self, rules: Optional[Sequence[DatalogRule]] = None, max_iterations: int = 1000
    ):
        self.rules: List[DatalogRule] = list(rules) if rules else []
        self.max_iterations = max_iterations

    def add_rule(self, rule: DatalogRule) -> None:
        """Add a Datalog rule after verifying safety invariants."""
        self.rules.append(rule)

    def execute_fixpoint(
        self,
        initial_facts: Iterable[DatalogAtom],
    ) -> Tuple[Set[DatalogAtom], int]:
        """Execute deterministic least-fixpoint computation until convergence ($F_{n+1} = F_n$).

        Args:
            initial_facts: Set of ground atoms (base database EDB).

        Returns:
            Tuple of (converged_facts, num_iterations).

        Raises:
            RuntimeError: If max_iterations is reached without reaching fixpoint.
        """
        facts: Set[DatalogAtom] = {f for f in initial_facts if f.is_ground}
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            new_derived_this_round: Set[DatalogAtom] = set()

            # Apply immediate consequence operator T_P
            for rule in self.rules:
                derived = self._evaluate_rule(rule, facts)
                new_derived_this_round.update(derived)

            prev_count = len(facts)
            facts.update(new_derived_this_round)

            # Check convergence: F_{n+1} == F_n
            if len(facts) == prev_count:
                # Least fixpoint reached
                return facts, iteration

        raise RuntimeError(
            f"Datalog engine failed to reach fixpoint within {self.max_iterations} iterations. "
            "Safety invariant check violated or infinite recursion detected."
        )

    def execute_graph_fixpoint(
        self,
        graph: rdflib.Graph,
    ) -> Tuple[rdflib.Graph, int]:
        """Execute least-fixpoint closure over an RDF graph.

        Loads RDF triples as EDB binary atoms, evaluates fixpoint,
        and returns a new graph containing both original and derived triples.
        """
        initial_facts = [DatalogAtom.from_rdf_triple((s, p, o)) for s, p, o in graph]

        closed_facts, iters = self.execute_fixpoint(initial_facts)

        out_graph = rdflib.Graph()
        for triple in graph:
            out_graph.add(triple)

        for fact in closed_facts:
            triple = fact.to_rdf_triple()
            if triple:
                out_graph.add(triple)

        return out_graph, iters

    def _evaluate_rule(
        self,
        rule: DatalogRule,
        facts: Set[DatalogAtom],
    ) -> Set[DatalogAtom]:
        """Evaluate a single rule against current facts using conjunctive pattern matching."""
        derived = set()

        # Build index by predicate for faster joining
        pred_index: Dict[Term, List[DatalogAtom]] = {}
        for f in facts:
            pred_index.setdefault(f.predicate, []).append(f)

        bindings = self._match_body(rule.body, 0, {}, pred_index)
        for b in bindings:
            head_inst = rule.head.apply_binding(b)
            if head_inst.is_ground and head_inst not in facts:
                derived.add(head_inst)

        return derived

    def _match_body(
        self,
        body: Tuple[DatalogAtom, ...],
        body_idx: int,
        current_binding: Dict[str, Node],
        pred_index: Dict[Term, List[DatalogAtom]],
    ) -> List[Dict[str, Node]]:
        """Backtracking conjunctive matching for rule body atoms."""
        if body_idx >= len(body):
            return [dict(current_binding)]

        target_atom = body[body_idx]
        candidates = pred_index.get(target_atom.predicate, [])
        results = []

        for cand in candidates:
            if len(cand.args) != len(target_atom.args):
                continue

            compatible = True
            new_binding = dict(current_binding)

            for pattern_arg, cand_val in zip(target_atom.args, cand.args):
                if is_variable(pattern_arg):
                    var_name = str(pattern_arg)
                    if var_name in new_binding:
                        if new_binding[var_name] != cand_val:
                            compatible = False
                            break
                    else:
                        new_binding[var_name] = cand_val  # bind
                else:
                    # Constant match
                    if pattern_arg != cand_val:
                        compatible = False
                        break

            if compatible:
                sub_results = self._match_body(
                    body, body_idx + 1, new_binding, pred_index
                )
                results.extend(sub_results)

        return results
