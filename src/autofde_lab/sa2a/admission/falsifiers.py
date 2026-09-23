"""SPARQL ASK Falsifiers Engine (RFC-SA2A-001 v26.9.16 §18, §61).

Provides an extensible SPARQL ASK query-based falsification engine to test candidate
semantic graphs against constitutional invariants and refusal constraints.

Standard falsifiers:
- FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY: ASK for action with consequence class but no requiresAuthority/authorizedBy.
- FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT: ASK for DO action without prepared receipt requirement.
- FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN: ASK for plan referencing undeclared capability.
- FALSIFIER_PROJECTION_AS_CANONICAL: ASK for projection claiming canonical authority.
- FALSIFIER_LLM_DIRECT_ADMITTED: ASK for triples originating directly from LLM asserting ADMITTED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from rdflib import Graph

# Standard SPARQL prefixes commonly used across autofde-lab and SA2A
STANDARD_PREFIXES = """
PREFIX afl: <urn:autofde-lab:>
PREFIX sa2a: <https://spec.autofde.org/sa2a#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX odrl: <http://www.w3.org/ns/odrl/2/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

# §18 Standard Falsifier Queries

# 1. Action with consequence class but no authority requirement or authorization
FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY = (
    STANDARD_PREFIXES
    + """
ASK {
    {
        ?action afl:consequenceClass ?cc .
        FILTER(?cc != "OBSERVATIONAL" && str(?cc) != "OBSERVATIONAL")
        FILTER NOT EXISTS { ?action afl:requiresAuthority ?auth }
        FILTER NOT EXISTS { ?action afl:authorizedBy ?auth }
        FILTER NOT EXISTS { ?action sa2a:requiresAuthority ?auth }
        FILTER NOT EXISTS { ?action sa2a:authorizedBy ?auth }
    }
    UNION
    {
        ?action sa2a:consequenceClass ?cc .
        FILTER(?cc != "OBSERVATIONAL" && str(?cc) != "OBSERVATIONAL")
        FILTER NOT EXISTS { ?action afl:requiresAuthority ?auth }
        FILTER NOT EXISTS { ?action afl:authorizedBy ?auth }
        FILTER NOT EXISTS { ?action sa2a:requiresAuthority ?auth }
        FILTER NOT EXISTS { ?action sa2a:authorizedBy ?auth }
    }
}
"""
)

# 2. DO action without prepared receipt requirement
FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT = (
    STANDARD_PREFIXES
    + """
ASK {
    {
        ?action a ?type .
        FILTER(?type IN (afl:Actuation, afl:DoAction, sa2a:Actuation, sa2a:DoAction))
        FILTER NOT EXISTS { ?action afl:requiresReceipt ?rcpt }
        FILTER NOT EXISTS { ?action sa2a:requiresReceipt ?rcpt }
        FILTER NOT EXISTS { ?action afl:receiptRequirement ?rcpt }
        FILTER NOT EXISTS { ?action sa2a:receiptRequirement ?rcpt }
    }
    UNION
    {
        ?action afl:actionKind "DO" .
        FILTER NOT EXISTS { ?action afl:requiresReceipt ?rcpt }
        FILTER NOT EXISTS { ?action sa2a:requiresReceipt ?rcpt }
        FILTER NOT EXISTS { ?action afl:receiptRequirement ?rcpt }
        FILTER NOT EXISTS { ?action sa2a:receiptRequirement ?rcpt }
    }
    UNION
    {
        ?action sa2a:actionKind "DO" .
        FILTER NOT EXISTS { ?action afl:requiresReceipt ?rcpt }
        FILTER NOT EXISTS { ?action sa2a:requiresReceipt ?rcpt }
        FILTER NOT EXISTS { ?action afl:receiptRequirement ?rcpt }
        FILTER NOT EXISTS { ?action sa2a:receiptRequirement ?rcpt }
    }
}
"""
)

# 3. Plan referencing undeclared capability
FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN = (
    STANDARD_PREFIXES
    + """
ASK {
    {
        ?plan a ?planType .
        FILTER(?planType IN (afl:Plan, afl:PlanCandidate, sa2a:Plan, sa2a:PlanCandidate))
        ?plan ?usesCap ?cap .
        FILTER(?usesCap IN (afl:requiresCapability, afl:usesCapability, sa2a:requiresCapability, sa2a:usesCapability))
        FILTER NOT EXISTS { ?cap a ?capType . FILTER(?capType IN (afl:Capability, sa2a:Capability)) }
    }
    UNION
    {
        ?plan ?hasStep ?step .
        FILTER(?hasStep IN (afl:hasStep, sa2a:hasStep))
        ?step ?usesCap ?cap .
        FILTER(?usesCap IN (afl:requiresCapability, afl:usesCapability, sa2a:requiresCapability, sa2a:usesCapability))
        FILTER NOT EXISTS { ?cap a ?capType . FILTER(?capType IN (afl:Capability, sa2a:Capability)) }
    }
}
"""
)

# 4. Projection claiming canonical authority
FALSIFIER_PROJECTION_AS_CANONICAL = (
    STANDARD_PREFIXES
    + """
ASK {
    {
        ?entity a ?projType .
        FILTER(?projType IN (afl:Projection, sa2a:Projection, afl:View, sa2a:View))
        {
            ?entity afl:isCanonical true .
        }
        UNION
        {
            ?entity sa2a:isCanonical true .
        }
        UNION
        {
            ?entity afl:claimsCanonicalAuthority true .
        }
        UNION
        {
            ?entity sa2a:claimsCanonicalAuthority true .
        }
        UNION
        {
            ?entity a afl:CanonicalAuthority .
        }
        UNION
        {
            ?entity a sa2a:CanonicalAuthority .
        }
    }
    UNION
    {
        ?entity afl:isProjection true .
        {
            ?entity afl:isCanonical true .
        }
        UNION
        {
            ?entity sa2a:isCanonical true .
        }
        UNION
        {
            ?entity afl:claimsCanonicalAuthority true .
        }
        UNION
        {
            ?entity sa2a:claimsCanonicalAuthority true .
        }
        UNION
        {
            ?entity a afl:CanonicalAuthority .
        }
        UNION
        {
            ?entity a sa2a:CanonicalAuthority .
        }
    }
    UNION
    {
        ?entity sa2a:isProjection true .
        {
            ?entity afl:isCanonical true .
        }
        UNION
        {
            ?entity sa2a:isCanonical true .
        }
        UNION
        {
            ?entity afl:claimsCanonicalAuthority true .
        }
        UNION
        {
            ?entity sa2a:claimsCanonicalAuthority true .
        }
        UNION
        {
            ?entity a afl:CanonicalAuthority .
        }
        UNION
        {
            ?entity a sa2a:CanonicalAuthority .
        }
    }
}
"""
)

# 5. Triples originating directly from LLM asserting ADMITTED
FALSIFIER_LLM_DIRECT_ADMITTED = (
    STANDARD_PREFIXES
    + """
ASK {
    {
        ?triple prov:wasAttributedTo ?agent .
        ?agent a ?llmType .
        FILTER(?llmType IN (afl:LLM, afl:LLMAgent, sa2a:LLM, sa2a:LLMAgent))
        {
            ?subject afl:standing "ADMITTED" .
        }
        UNION
        {
            ?subject sa2a:standing "ADMITTED" .
        }
        UNION
        {
            ?subject afl:hasStanding afl:ADMITTED .
        }
        UNION
        {
            ?subject sa2a:hasStanding sa2a:ADMITTED .
        }
    }
    UNION
    {
        ?subject afl:standing "ADMITTED" ;
                 prov:wasAttributedTo ?agent .
        ?agent a ?llmType .
        FILTER(?llmType IN (afl:LLM, afl:LLMAgent, sa2a:LLM, sa2a:LLMAgent))
    }
    UNION
    {
        ?subject sa2a:standing "ADMITTED" ;
                 prov:wasAttributedTo ?agent .
        ?agent a ?llmType .
        FILTER(?llmType IN (afl:LLM, afl:LLMAgent, sa2a:LLM, sa2a:LLMAgent))
    }
    UNION
    {
        ?subject afl:hasStanding afl:ADMITTED ;
                 prov:wasAttributedTo ?agent .
        ?agent a ?llmType .
        FILTER(?llmType IN (afl:LLM, afl:LLMAgent, sa2a:LLM, sa2a:LLMAgent))
    }
    UNION
    {
        ?subject sa2a:hasStanding sa2a:ADMITTED ;
                 prov:wasAttributedTo ?agent .
        ?agent a ?llmType .
        FILTER(?llmType IN (afl:LLM, afl:LLMAgent, sa2a:LLM, sa2a:LLMAgent))
    }
}
"""
)


@dataclass(frozen=True)
class FalsifierDefinition:
    """A registered SPARQL ASK falsifier query specification."""

    name: str
    query: str
    description: str = ""
    falsifier_id: Optional[str] = None


@dataclass(frozen=True)
class TriggeredFalsifier:
    """Record of a triggered falsifier (§18, §61)."""

    name: str
    description: str
    falsifier_id: Optional[str] = None
    query: str = ""


class FalsifierSuite:
    """SPARQL ASK Falsifier Suite (§18, §61).

    Evaluates RDF graphs against a set of registered SPARQL ASK queries.
    In accordance with the fail-closed calculus:
    - If an ASK query returns True, the falsifier condition is present (invalidation triggered).
    - If a query raises a syntax or execution error, it fails closed (triggered/refused).
    """

    def __init__(self, include_defaults: bool = True) -> None:
        """Initialize falsifier suite, optionally registering standard default falsifiers."""
        self._falsifiers: Dict[str, FalsifierDefinition] = {}
        if include_defaults:
            self.register_default_falsifiers()

    def register_default_falsifiers(self) -> None:
        """Register the standard SA2A §18 falsifiers."""
        self.register(
            name="FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY",
            query=FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
            description="Consequential action without required authority declaration or authorization grant.",
            falsifier_id="urn:sa2a:falsifier:consequence-without-authority",
        )
        self.register(
            name="FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT",
            query=FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT,
            description="DO action without prepared receipt requirement.",
            falsifier_id="urn:sa2a:falsifier:do-without-receipt-requirement",
        )
        self.register(
            name="FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN",
            query=FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN,
            description="Plan candidate references undeclared or unknown capability.",
            falsifier_id="urn:sa2a:falsifier:unknown-capability-in-plan",
        )
        self.register(
            name="FALSIFIER_PROJECTION_AS_CANONICAL",
            query=FALSIFIER_PROJECTION_AS_CANONICAL,
            description="Derived projection claiming canonical authority.",
            falsifier_id="urn:sa2a:falsifier:projection-as-canonical",
        )
        self.register(
            name="FALSIFIER_LLM_DIRECT_ADMITTED",
            query=FALSIFIER_LLM_DIRECT_ADMITTED,
            description="Triples originating directly from LLM asserting ADMITTED standing without admission court.",
            falsifier_id="urn:sa2a:falsifier:llm-direct-admitted",
        )

    def register(
        self,
        name: str,
        query: str,
        description: str = "",
        falsifier_id: Optional[str] = None,
    ) -> None:
        """Register a new SPARQL ASK falsifier query."""
        if not name:
            raise ValueError("Falsifier name cannot be empty")
        if not query or not query.strip():
            raise ValueError(f"Falsifier '{name}' query cannot be empty")
        self._falsifiers[name] = FalsifierDefinition(
            name=name,
            query=query,
            description=description,
            falsifier_id=falsifier_id or f"urn:sa2a:falsifier:{name.lower()}",
        )

    def unregister(self, name: str) -> bool:
        """Remove a registered falsifier by name. Returns True if removed."""
        return self._falsifiers.pop(name, None) is not None

    def get_falsifier(self, name: str) -> Optional[FalsifierDefinition]:
        """Retrieve a registered falsifier by name."""
        return self._falsifiers.get(name)

    @property
    def registered_falsifiers(self) -> List[str]:
        """Return list of all registered falsifier names."""
        return list(self._falsifiers.keys())

    def evaluate(
        self,
        graph: Union[Graph, str, bytes],
        graph_format: str = "turtle",
        fail_closed: bool = True,
    ) -> List[TriggeredFalsifier]:
        """Evaluate graph against all registered SPARQL ASK falsifiers.

        Args:
            graph: rdflib.Graph or serialized RDF string/bytes.
            graph_format: Format if graph is string or bytes (default: 'turtle').
            fail_closed: If True (default), query parse or execution errors trigger
                         as falsification violations.

        Returns:
            List of TriggeredFalsifier instances for every query that returned True
            (or errored under fail_closed).
        """
        if isinstance(graph, Graph):
            rdf_graph = graph
        else:
            rdf_graph = Graph()
            try:
                rdf_graph.parse(data=graph, format=graph_format)
            except Exception as e:
                if fail_closed:
                    return [
                        TriggeredFalsifier(
                            name="GRAPH_PARSE_FAILURE",
                            description=f"Candidate graph failed parsing: {e}",
                            falsifier_id="urn:sa2a:falsifier:parse-failure",
                        )
                    ]
                raise

        triggered: List[TriggeredFalsifier] = []
        for name, fdef in self._falsifiers.items():
            try:
                qres = rdf_graph.query(fdef.query)
                # rdflib Result for ASK queries provides `askAnswer` boolean
                is_triggered = bool(getattr(qres, "askAnswer", False))
                if is_triggered:
                    triggered.append(
                        TriggeredFalsifier(
                            name=fdef.name,
                            description=fdef.description,
                            falsifier_id=fdef.falsifier_id,
                            query=fdef.query,
                        )
                    )
            except Exception as exc:
                if fail_closed:
                    triggered.append(
                        TriggeredFalsifier(
                            name=fdef.name,
                            description=f"Falsifier execution failed (fail-closed triggered): {exc}",
                            falsifier_id=fdef.falsifier_id,
                            query=fdef.query,
                        )
                    )
                else:
                    raise

        return triggered
