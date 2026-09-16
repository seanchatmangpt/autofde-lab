"""Structural membership and shape validator (RFC-SA2A-001 §14).

Provides ShEx-style structural shape verification on RDF graphs, validating
node kinds, required RDF types, mandatory predicates, cardinality constraints,
and value constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Sequence, Union
import rdflib
from rdflib.namespace import RDF


class NodeKind(str, Enum):
    """Permitted RDF node kinds."""

    IRI = "iri"
    BNODE = "bnode"
    LITERAL = "literal"
    NON_LITERAL = "non_literal"
    ANY = "any"


@dataclass(frozen=True)
class PredicateConstraint:
    """Constraint on a property path / predicate from a subject node.

    Attributes:
        predicate: The property URI.
        min_count: Minimum occurrences of the predicate on the subject.
        max_count: Maximum occurrences (None for unbounded).
        node_kind: Expected node kind for the object.
        datatype: Optional expected literal datatype URI.
        allowed_values: Optional set of permitted object values.
        value_shape_name: Optional shape name the object must satisfy.
    """

    predicate: rdflib.URIRef
    min_count: int = 1
    max_count: Optional[int] = None
    node_kind: NodeKind = NodeKind.ANY
    datatype: Optional[rdflib.URIRef] = None
    allowed_values: Optional[tuple[Union[rdflib.URIRef, rdflib.Literal], ...]] = None
    value_shape_name: Optional[str] = None


@dataclass(frozen=True)
class StructuralShape:
    """Shape specification defining structural constraints for nodes.

    Attributes:
        name: Name or URI of the shape.
        target_class: Optional rdf:type target that triggers validation on matching nodes.
        node_kind: Permitted node kind for matching nodes.
        required_types: Set of rdf:type URIs that the node must instantiate.
        predicates: Tuple of property/predicate constraints that the node must satisfy.
        closed: If True, extra predicates not specified in constraints are disallowed.
        ignored_predicates: Predicates excluded when checking closed shapes (e.g. rdf:type).
    """

    name: str
    target_class: Optional[rdflib.URIRef] = None
    node_kind: NodeKind = NodeKind.ANY
    required_types: tuple[rdflib.URIRef, ...] = ()
    predicates: tuple[PredicateConstraint, ...] = ()
    closed: bool = False
    ignored_predicates: tuple[rdflib.URIRef, ...] = (RDF.type,)


@dataclass(frozen=True)
class ShexValidationReport:
    """Structured report returned by ShEx / structural shape validation.

    Attributes:
        conforms: True if all targeted nodes satisfy shape requirements.
        violations: Tuple of human-readable violation descriptions.
    """

    conforms: bool
    violations: tuple[str, ...]


def _check_node_kind(node: rdflib.term.Identifier, kind: NodeKind) -> bool:
    if kind == NodeKind.ANY:
        return True
    if kind == NodeKind.IRI:
        return isinstance(node, rdflib.URIRef)
    if kind == NodeKind.BNODE:
        return isinstance(node, rdflib.BNode)
    if kind == NodeKind.LITERAL:
        return isinstance(node, rdflib.Literal)
    if kind == NodeKind.NON_LITERAL:
        return isinstance(node, (rdflib.URIRef, rdflib.BNode))
    return True


class ShexValidator:
    """Structural membership and shape validator.

    Validates candidate RDF graphs against a collection of StructuralShape rules.
    """

    def __init__(self, shapes: Sequence[StructuralShape] = ()) -> None:
        self.shapes_by_name: dict[str, StructuralShape] = {
            s.name: s for s in shapes
        }

    def add_shape(self, shape: StructuralShape) -> None:
        """Register a structural shape."""
        self.shapes_by_name[shape.name] = shape

    def validate_node(
        self,
        graph: rdflib.Graph,
        node: rdflib.term.Identifier,
        shape: StructuralShape,
    ) -> list[str]:
        """Validate a single node against a specific shape."""
        violations: list[str] = []

        # 1. Check node kind
        if not _check_node_kind(node, shape.node_kind):
            violations.append(
                f"Node <{node}> violates node_kind requirement: expected {shape.node_kind.value}"
            )

        # 2. Check required types
        node_types = set(graph.objects(node, RDF.type))
        for req_type in shape.required_types:
            if req_type not in node_types:
                violations.append(
                    f"Node <{node}> missing required rdf:type: <{req_type}>"
                )

        # 3. Check property constraints
        allowed_preds = set(p.predicate for p in shape.predicates)
        for pc in shape.predicates:
            objects = list(graph.objects(node, pc.predicate))
            count = len(objects)

            if count < pc.min_count:
                violations.append(
                    f"Node <{node}> predicate <{pc.predicate}> minCount violation: "
                    f"found {count}, required >= {pc.min_count}"
                )
            if pc.max_count is not None and count > pc.max_count:
                violations.append(
                    f"Node <{node}> predicate <{pc.predicate}> maxCount violation: "
                    f"found {count}, allowed <= {pc.max_count}"
                )

            for obj in objects:
                if not _check_node_kind(obj, pc.node_kind):
                    violations.append(
                        f"Node <{node}> object <{obj}> for <{pc.predicate}> violates node_kind: "
                        f"expected {pc.node_kind.value}"
                    )
                if pc.datatype is not None:
                    if not isinstance(obj, rdflib.Literal) or obj.datatype != pc.datatype:
                        violations.append(
                            f"Node <{node}> object <{obj}> for <{pc.predicate}> violates datatype: "
                            f"expected {pc.datatype}, found {getattr(obj, 'datatype', None)}"
                        )
                if pc.allowed_values is not None:
                    if obj not in pc.allowed_values:
                        violations.append(
                            f"Node <{node}> object <{obj}> for <{pc.predicate}> not in allowed values"
                        )
                if pc.value_shape_name is not None and pc.value_shape_name in self.shapes_by_name:
                    sub_violations = self.validate_node(
                        graph, obj, self.shapes_by_name[pc.value_shape_name]
                    )
                    violations.extend(sub_violations)

        # 4. Check closed shape constraints
        if shape.closed:
            all_preds = set(graph.predicates(node, None))
            ignored = set(shape.ignored_predicates)
            extra = all_preds - allowed_preds - ignored
            for ep in extra:
                violations.append(
                    f"Node <{node}> contains unpermitted predicate <{ep}> in closed shape '{shape.name}'"
                )

        return violations

    def validate(
        self,
        graph: Union[str, bytes, rdflib.Graph],
        graph_format: str = "turtle",
        target_nodes: Optional[dict[str, Sequence[rdflib.term.Identifier]]] = None,
    ) -> ShexValidationReport:
        """Validate candidate RDF data against registered shapes.

        Args:
            graph: Graph instance, or RDF string/bytes.
            graph_format: Format if graph is str/bytes.
            target_nodes: Optional explicit mapping of shape name -> sequence of nodes to validate.
                          If omitted, shapes with `target_class` automatically target matching nodes.

        Returns:
            ShexValidationReport with conformance status and violation list.
        """
        if isinstance(graph, (str, bytes)):
            g = rdflib.Graph()
            g.parse(data=graph, format=graph_format)
            target_graph = g
        else:
            target_graph = graph

        all_violations: list[str] = []

        # Validate explicit node targets
        if target_nodes:
            for shape_name, nodes in target_nodes.items():
                if shape_name not in self.shapes_by_name:
                    all_violations.append(f"Referenced shape '{shape_name}' not defined in validator.")
                    continue
                shape = self.shapes_by_name[shape_name]
                for node in nodes:
                    all_violations.extend(self.validate_node(target_graph, node, shape))

        # Validate shapes with target_class
        for shape in self.shapes_by_name.values():
            if shape.target_class:
                matching_nodes = list(target_graph.subjects(RDF.type, shape.target_class))
                for node in matching_nodes:
                    all_violations.extend(self.validate_node(target_graph, node, shape))

        return ShexValidationReport(
            conforms=(len(all_violations) == 0),
            violations=tuple(all_violations),
        )
