"""SHACL constraint validation layer (RFC-SA2A-001 §15).

Provides SHACL constraint validation for candidate RDF graphs using pyshacl,
returning structured validation reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Union
import pyshacl
import rdflib
from rdflib.namespace import RDF, SH


@dataclass(frozen=True)
class ShaclValidationReport:
    """Structured report returned by SHACL validation.

    Attributes:
        conforms: True if the candidate graph satisfied all constraints.
        violations: Tuple of human-readable violation descriptions.
        report_graph: Optional raw rdflib Graph containing the SHACL validation results.
        raw_text: Full validation report text output from pyshacl.
    """

    conforms: bool
    violations: tuple[str, ...]
    report_graph: Optional[rdflib.Graph] = None
    raw_text: str = ""


class ShaclValidator:
    """SHACL shape validator for candidate graphs.

    Wraps pyshacl to validate graph targets against SHACL shapes and extracts
    structured violation details.
    """

    def __init__(
        self,
        shapes: Union[str, bytes, rdflib.Graph],
        shapes_format: str = "turtle",
    ) -> None:
        """Initialize validator with SHACL shapes.

        Args:
            shapes: SHACL shapes provided as Turtle/RDF string, bytes, or parsed rdflib.Graph.
            shapes_format: Serialization format if shapes is a string/bytes (default: 'turtle').
        """
        if isinstance(shapes, rdflib.Graph):
            self.shapes_graph = shapes
        else:
            self.shapes_graph = rdflib.Graph()
            self.shapes_graph.parse(data=shapes, format=shapes_format)

    def validate(
        self,
        data_graph: Union[str, bytes, rdflib.Graph],
        data_format: str = "turtle",
        inference: Optional[str] = None,
        abort_on_first: bool = False,
        **kwargs,
    ) -> ShaclValidationReport:
        """Validate candidate RDF data against the configured SHACL shapes.

        Args:
            data_graph: Candidate graph as rdflib.Graph, or RDF string/bytes.
            data_format: Format if data_graph is str or bytes (default: 'turtle').
            inference: Optional inference mode (e.g. 'rdfs', 'owlrl', 'both', or None).
            abort_on_first: Abort validation on first detected failure.
            **kwargs: Extra arguments forwarded to `pyshacl.validate`.

        Returns:
            ShaclValidationReport with conformance boolean and violation messages.
        """
        if isinstance(data_graph, (str, bytes)):
            g = rdflib.Graph()
            g.parse(data=data_graph, format=data_format)
            target_graph = g
        else:
            target_graph = data_graph

        conforms, report_graph, report_text = pyshacl.validate(
            data_graph=target_graph,
            shacl_graph=self.shapes_graph,
            inference=inference,
            abort_on_first=abort_on_first,
            **kwargs,
        )

        violations_list: list[str] = []
        if not conforms and report_graph is not None:
            # Query the report graph for specific SHACL ValidationResults
            for result in report_graph.subjects(RDF.type, SH.ValidationResult):
                focus_node = report_graph.value(result, SH.focusNode)
                result_path = report_graph.value(result, SH.resultPath)
                result_message = report_graph.value(result, SH.resultMessage)
                source_shape = report_graph.value(result, SH.sourceShape)
                source_constraint = report_graph.value(result, SH.sourceConstraintComponent)

                parts = []
                if focus_node:
                    parts.append(f"FocusNode: {focus_node}")
                if result_path:
                    parts.append(f"Path: {result_path}")
                if result_message:
                    parts.append(f"Message: {result_message}")
                elif source_constraint:
                    parts.append(f"Constraint: {source_constraint}")
                elif source_shape:
                    parts.append(f"Shape: {source_shape}")

                v_str = " | ".join(parts) if parts else str(result)
                violations_list.append(v_str)

        # Fallback if no individual results found in graph but conforms is False
        if not conforms and not violations_list:
            cleaned_text = report_text.strip()
            if cleaned_text:
                violations_list.append(cleaned_text)
            else:
                violations_list.append("SHACL validation failed with unspecified violations.")

        return ShaclValidationReport(
            conforms=bool(conforms),
            violations=tuple(violations_list),
            report_graph=report_graph,
            raw_text=report_text,
        )
