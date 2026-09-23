"""Admission & Shape Falsification Court for RFC-SA2A-002 v26.9.16.

Executable falsifiers implementing:
- CHI-ADM-*: Admission & Namespace Invariant Falsifiers
- SA2A-SHEX-*: Structural ShEx Shape Falsifiers
- SA2A-SHACL-*: Semantic SHACL Shape Falsifiers (e.g. unreceipted DO, missing authority)
- SA2A-SPARQL-*: SPARQL Invariant Falsifier Queries & Direct Canonical State Mutation Refusal

Conforms strictly to Chicago Zero-Mock Standard:
- Real plant components, real disk I/O, genuine brokers and boundaries.
- Zero unittest.mock / Mock / MagicMock / patch.
- Deterministic cryptographic digest bindings.
- Anti-Oracle Rule: No golden OCEL traces or snapshot oracles.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import rdflib
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, XSD

from autofde_lab.sa2a.admission.canonicalizer import (
    canonicalize_graph,
    compute_graph_digest,
)
from autofde_lab.sa2a.admission.falsifiers import (
    FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
    FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT,
    FALSIFIER_LLM_DIRECT_ADMITTED,
    FALSIFIER_PROJECTION_AS_CANONICAL,
    FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN,
    FalsifierSuite,
)
from autofde_lab.sa2a.admission.pipeline import (
    REFUSED_FALSIFIER,
    REFUSED_IDENTITY,
    REFUSED_META_RIGOR,
    REFUSED_NAMESPACE,
    REFUSED_PARSE_FAILURE,
    REFUSED_PROVENANCE,
    REFUSED_SHACL,
    REFUSED_STRUCTURE,
    AdmissionPipeline,
    IdentityPolicy,
    MetaAdmissionPolicy,
    ProvenancePolicy,
    SparqlFalsifier,
)
from autofde_lab.sa2a.admission.shacl_layer import ShaclValidator
from autofde_lab.sa2a.admission.shex_layer import (
    NodeKind,
    PredicateConstraint,
    ShexValidator,
    StructuralShape,
)
from autofde_lab.sa2a.algebra import Standing

# Common Namespaces
AFL = Namespace("urn:autofde-lab:")
SA2A = Namespace("https://spec.autofde.org/sa2a#")
EX = Namespace("http://example.org/")


class AdmissionFalsificationCode(str, Enum):
    """Enumeration of standard falsifier codes across court categories."""

    # CHI-ADM: Admission & Namespace Invariant Falsifiers
    CHI_ADM_UNADMITTED_SUBJECT_NS = "CHI-ADM-001"
    CHI_ADM_UNADMITTED_PREDICATE_NS = "CHI-ADM-002"
    CHI_ADM_FORBIDDEN_DISALLOWED_IRI = "CHI-ADM-003"
    CHI_ADM_PARSE_FAILURE_SYNTAX = "CHI-ADM-004"
    CHI_ADM_EMPTY_CANDIDATE_GRAPH = "CHI-ADM-005"
    CHI_ADM_MISSING_PROVENANCE_ISSUER = "CHI-ADM-006"
    CHI_ADM_UNTRUSTED_ISSUER = "CHI-ADM-007"

    # SA2A-SHEX: Structural Shape Falsifiers
    SA2A_SHEX_NODE_KIND_MISMATCH = "SA2A-SHEX-001"
    SA2A_SHEX_MISSING_REQUIRED_TYPE = "SA2A-SHEX-002"
    SA2A_SHEX_PREDICATE_MIN_COUNT = "SA2A-SHEX-003"
    SA2A_SHEX_PREDICATE_MAX_COUNT = "SA2A-SHEX-004"
    SA2A_SHEX_DATATYPE_MISMATCH = "SA2A-SHEX-005"
    SA2A_SHEX_CLOSED_SHAPE_UNPERMITTED_PREDICATE = "SA2A-SHEX-006"

    # SA2A-SHACL: Semantic SHACL Shape Falsifiers
    SA2A_SHACL_UNRECEIPTED_DO_ACTION = "SA2A-SHACL-001"
    SA2A_SHACL_MISSING_AUTHORITY_CONSEQUENCE = "SA2A-SHACL-002"
    SA2A_SHACL_UNDECLARED_CAPABILITY = "SA2A-SHACL-003"
    SA2A_SHACL_PROJECTION_CLAIMING_CANONICAL = "SA2A-SHACL-004"
    SA2A_SHACL_SEVERITY_RANGE_VIOLATION = "SA2A-SHACL-005"

    # SA2A-SPARQL: SPARQL Invariant Falsifiers & State Immutability
    SA2A_SPARQL_CONSEQUENCE_WITHOUT_AUTH = "SA2A-SPARQL-001"
    SA2A_SPARQL_DO_WITHOUT_RECEIPT = "SA2A-SPARQL-002"
    SA2A_SPARQL_UNKNOWN_CAPABILITY_PLAN = "SA2A-SPARQL-003"
    SA2A_SPARQL_PROJECTION_AS_CANONICAL = "SA2A-SPARQL-004"
    SA2A_SPARQL_LLM_DIRECT_ADMITTED = "SA2A-SPARQL-005"
    SA2A_SPARQL_DIRECT_STATE_UPDATE_REFUSAL = "SA2A-SPARQL-006"


class CanonicalStateDirectUpdateRefusedError(Exception):
    """Raised when an agent attempts a direct SPARQL update against canonical state."""


class CanonicalSemanticStore:
    """Canonical Semantic State store O* (§5, §27).

    Guarantees:
    - Canonical state can only be initialized via formal ADMITTED graph receipt.
    - Direct SPARQL UPDATE (INSERT DATA, DELETE DATA, DELETE/INSERT, CLEAR, DROP, etc.)
      is strictly refused and raises CanonicalStateDirectUpdateRefusedError.
    - Mutations must follow the BRCE Consequence Boundary under prepared receipts.
    """

    def __init__(self, initial_graph: Optional[Graph] = None) -> None:
        self._graph = Graph()
        if initial_graph is not None:
            for triple in initial_graph:
                self._graph.add(triple)
        self._canonical_nt = canonicalize_graph(self._graph)
        self._canonical_digest = compute_graph_digest(self._canonical_nt)

    @property
    def canonical_digest(self) -> str:
        """Deterministic digest of canonical state."""
        return self._canonical_digest

    @property
    def triple_count(self) -> int:
        """Total triples in canonical state."""
        return len(self._graph)

    def query(self, sparql_query: str) -> rdflib.query.Result:
        """Execute read-only SPARQL query against canonical state."""
        return self._graph.query(sparql_query)

    def update(self, sparql_update: str) -> None:
        """Attempt direct SPARQL UPDATE against canonical state.

        Direct SPARQL UPDATE against canonical state is strictly refused.
        Canonical state may only advance through formal admission of delta packages
        or verified BRCE postcondition observation.
        """
        clean_update = sparql_update.strip().upper()
        mutation_keywords = (
            "INSERT",
            "DELETE",
            "CLEAR",
            "DROP",
            "LOAD",
            "CREATE",
            "COPY",
            "MOVE",
            "ADD",
        )
        if any(kw in clean_update for kw in mutation_keywords):
            raise CanonicalStateDirectUpdateRefusedError(
                f"Direct SPARQL update against canonical state O* is strictly forbidden: {sparql_update.strip()[:60]}..."
            )
        raise CanonicalStateDirectUpdateRefusedError(
            "Direct update operations on canonical state are refused by specification (§27)."
        )

    def snapshot(self) -> Graph:
        """Return an immutable, isolated snapshot copy of the canonical graph."""
        g = Graph()
        for t in self._graph:
            g.add(t)
        return g


# Standard SHACL Shapes for RFC-SA2A-002 Conformance
STANDARD_CONFORMANCE_SHACL_SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix afl: <urn:autofde-lab:> .
@prefix sa2a: <https://spec.autofde.org/sa2a#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# SA2A-SHACL-001: DO actions require receipt specification
sa2a:DoActionShape
    a sh:NodeShape ;
    sh:targetClass afl:DoAction, sa2a:DoAction, afl:Actuation, sa2a:Actuation ;
    sh:property [
        sh:path afl:requiresReceipt ;
        sh:minCount 1 ;
        sh:message "DO action must specify afl:requiresReceipt" ;
    ] .

# SA2A-SHACL-002: Consequential actions require explicit authority declaration
sa2a:ConsequentialActionShape
    a sh:NodeShape ;
    sh:targetClass afl:ConsequentialAction, sa2a:ConsequentialAction ;
    sh:property [
        sh:path afl:requiresAuthority ;
        sh:minCount 1 ;
        sh:message "Consequential action requires explicit afl:requiresAuthority declaration" ;
    ] .

# SA2A-SHACL-003: Plans must bind declared capabilities
sa2a:PlanCapabilityShape
    a sh:NodeShape ;
    sh:targetClass afl:Plan, sa2a:Plan ;
    sh:property [
        sh:path afl:requiresCapability ;
        sh:minCount 1 ;
        sh:class afl:Capability ;
        sh:message "Plan must reference a valid afl:Capability resource" ;
    ] .

# SA2A-SHACL-004: Projections must not claim canonical status
sa2a:ProjectionNonCanonicalShape
    a sh:NodeShape ;
    sh:targetClass afl:Projection, sa2a:Projection ;
    sh:property [
        sh:path afl:isCanonical ;
        sh:maxCount 0 ;
        sh:message "Projection entities cannot assert afl:isCanonical" ;
    ] .

# SA2A-SHACL-005: Severity bounds constraint
sa2a:IncidentSeverityShape
    a sh:NodeShape ;
    sh:targetClass afl:Incident ;
    sh:property [
        sh:path afl:severity ;
        sh:in ("LOW" "MEDIUM" "HIGH" "CRITICAL") ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:message "Incident severity must be one of: LOW, MEDIUM, HIGH, CRITICAL" ;
    ] .
"""


# Standard ShEx Shapes for RFC-SA2A-002 Conformance
def create_standard_conformance_shex_validator() -> ShexValidator:
    """Construct reference ShexValidator with standard structural shapes."""
    # Shape 1: Action Shape
    action_shape = StructuralShape(
        name="ActionShape",
        target_class=AFL.Action,
        node_kind=NodeKind.IRI,
        required_types=(AFL.Action,),
        predicates=(
            PredicateConstraint(
                predicate=AFL.actionId,
                min_count=1,
                max_count=1,
                node_kind=NodeKind.LITERAL,
                datatype=XSD.string,
            ),
            PredicateConstraint(
                predicate=AFL.targetResource,
                min_count=1,
                max_count=1,
                node_kind=NodeKind.IRI,
            ),
        ),
        closed=False,
    )

    # Shape 2: Strict Closed Node Shape
    closed_node_shape = StructuralShape(
        name="ClosedClusterNodeShape",
        target_class=AFL.ClusterNode,
        node_kind=NodeKind.IRI,
        required_types=(AFL.ClusterNode,),
        predicates=(
            PredicateConstraint(
                predicate=AFL.nodeId,
                min_count=1,
                max_count=1,
                node_kind=NodeKind.LITERAL,
                datatype=XSD.string,
            ),
            PredicateConstraint(
                predicate=AFL.status,
                min_count=1,
                max_count=1,
                node_kind=NodeKind.LITERAL,
            ),
        ),
        closed=True,
        ignored_predicates=(RDF.type,),
    )

    return ShexValidator(shapes=(action_shape, closed_node_shape))


@dataclass(frozen=True)
class FalsificationVerdict:
    """Outcome of an admission or shape falsification trial."""

    falsifier_code: str
    attack_name: str
    expected_refusal_code: str
    actual_refusal_code: Optional[str]
    standing: Standing
    refused_before_consequence: bool
    details: Tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Falsifier trial passes if attack was refused with expected cause before consequence."""
        return (
            self.standing in (Standing.REFUSED, Standing.BLOCKED)
            and self.actual_refusal_code == self.expected_refusal_code
            and self.refused_before_consequence
        )


class AdmissionCourt:
    """Admission & Shape Falsification Court (CHI-ADM-*, SA2A-SHEX-*, SA2A-SHACL-*, SA2A-SPARQL-*).

    Coordinates and executes real adversarial attacks against:
    1. Unadmitted namespaces and ontology terms (CHI-ADM-*)
    2. Structural ShEx violations (SA2A-SHEX-*)
    3. Semantic SHACL shape violations (SA2A-SHACL-*)
    4. SPARQL invariant falsifier queries (SA2A-SPARQL-*)
    5. Direct SPARQL update refusal against canonical state (SA2A-SPARQL-006)
    """

    def __init__(
        self,
        *,
        allowed_subject_namespaces: Sequence[str] = (
            "http://example.org/admitted/",
            "urn:autofde-lab:",
        ),
        allowed_predicate_namespaces: Sequence[str] = (
            "http://example.org/vocab/",
            "urn:autofde-lab:",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "http://www.w3.org/2000/01/rdf-schema#",
            "http://www.w3.org/ns/prov#",
            "https://spec.autofde.org/sa2a#",
            "http://www.w3.org/ns/shacl#",
        ),
        disallowed_iris: Sequence[str] = ("http://malicious.org/forbidden/payload",),
        shex_validator: Optional[ShexValidator] = None,
        shacl_shapes_ttl: Optional[str] = None,
    ) -> None:
        self.identity_policy = IdentityPolicy(
            allowed_subject_namespaces=tuple(allowed_subject_namespaces),
            allowed_predicate_namespaces=tuple(allowed_predicate_namespaces),
            disallowed_iris=tuple(disallowed_iris),
        )
        self.shex_validator = (
            shex_validator or create_standard_conformance_shex_validator()
        )
        self.shacl_validator = ShaclValidator(
            shapes=shacl_shapes_ttl or STANDARD_CONFORMANCE_SHACL_SHAPES
        )
        self.falsifier_suite = FalsifierSuite(include_defaults=True)

        # Convert standard falsifiers to SparqlFalsifier instances for AdmissionPipeline
        sparql_falsifiers: List[SparqlFalsifier] = []
        for name in self.falsifier_suite.registered_falsifiers:
            fdef = self.falsifier_suite.get_falsifier(name)
            if fdef:
                sparql_falsifiers.append(
                    SparqlFalsifier(
                        falsifier_id=fdef.falsifier_id or name,
                        query=fdef.query,
                        description=fdef.description,
                    )
                )

        self.pipeline = AdmissionPipeline(
            identity_policy=self.identity_policy,
            shex_validator=self.shex_validator,
            shacl_validator=self.shacl_validator,
            sparql_falsifiers=sparql_falsifiers,
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=(
                    "urn:issuer:trusted-authority",
                    "urn:issuer:pipeline-admin",
                ),
                require_timestamp=True,
                require_signature=False,
            ),
            meta_policy=MetaAdmissionPolicy(
                min_triples=1,
                max_triples=5000,
            ),
        )

    # -------------------------------------------------------------------------
    # Category 1: CHI-ADM-* (Admission & Namespace Invariants)
    # -------------------------------------------------------------------------
    def falsify_unadmitted_subject_namespace(
        self, rogue_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """CHI-ADM-001: Attack with unadmitted subject IRI namespace."""
        res = self.pipeline.admit(rogue_ttl)
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.CHI_ADM_UNADMITTED_SUBJECT_NS.value,
            attack_name="Unadmitted Subject Namespace Ingress",
            expected_refusal_code=REFUSED_NAMESPACE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_unadmitted_predicate_namespace(
        self, rogue_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """CHI-ADM-002: Attack with unadmitted predicate / ontology property namespace."""
        res = self.pipeline.admit(rogue_ttl)
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.CHI_ADM_UNADMITTED_PREDICATE_NS.value,
            attack_name="Unadmitted Predicate Namespace Ingress",
            expected_refusal_code=REFUSED_NAMESPACE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_disallowed_iri(
        self, rogue_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """CHI-ADM-003: Attack using an explicitly blacklisted / forbidden IRI."""
        res = self.pipeline.admit(rogue_ttl)
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.CHI_ADM_FORBIDDEN_DISALLOWED_IRI.value,
            attack_name="Forbidden Disallowed IRI Injection",
            expected_refusal_code=REFUSED_IDENTITY,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_syntax_parse_failure(
        self, malformed_payload: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """CHI-ADM-004: Attack with unparseable corrupt RDF syntax."""
        res = self.pipeline.admit(malformed_payload)
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.CHI_ADM_PARSE_FAILURE_SYNTAX.value,
            attack_name="Syntax Malformed RDF Injection",
            expected_refusal_code=REFUSED_PARSE_FAILURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_empty_candidate_graph(
        self, empty_ttl: str = "", consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """CHI-ADM-005: Attack with an empty candidate graph violating meta-admission min_triples."""
        res = self.pipeline.admit(
            empty_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.CHI_ADM_EMPTY_CANDIDATE_GRAPH.value,
            attack_name="Empty Graph Candidate Ingress",
            expected_refusal_code=REFUSED_META_RIGOR,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_missing_provenance_issuer(
        self, valid_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """CHI-ADM-006: Attack with valid graph but missing provenance issuer."""
        res = self.pipeline.admit(valid_ttl, provenance_record={})
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.CHI_ADM_MISSING_PROVENANCE_ISSUER.value,
            attack_name="Missing Provenance Issuer Attestation",
            expected_refusal_code=REFUSED_PROVENANCE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    # -------------------------------------------------------------------------
    # Category 2: SA2A-SHEX-* (Structural ShEx Shape Falsifiers)
    # -------------------------------------------------------------------------
    def falsify_shex_node_kind(
        self, bnode_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHEX-001: Node kind mismatch (blank node where IRI required)."""
        res = self.pipeline.admit(
            bnode_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHEX_NODE_KIND_MISMATCH.value,
            attack_name="ShEx Node Kind Constraint Violation",
            expected_refusal_code=REFUSED_STRUCTURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shex_missing_required_type(
        self, missing_type_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHEX-002: Missing required rdf:type."""
        res = self.pipeline.admit(
            missing_type_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHEX_MISSING_REQUIRED_TYPE.value,
            attack_name="ShEx Missing Required Type Violation",
            expected_refusal_code=REFUSED_STRUCTURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shex_predicate_min_count(
        self, missing_pred_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHEX-003: Mandatory predicate omitted (minCount violation)."""
        res = self.pipeline.admit(
            missing_pred_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHEX_PREDICATE_MIN_COUNT.value,
            attack_name="ShEx Mandatory Predicate MinCount Violation",
            expected_refusal_code=REFUSED_STRUCTURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shex_predicate_max_count(
        self, excess_pred_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHEX-004: Excessive predicate occurrences (maxCount violation)."""
        res = self.pipeline.admit(
            excess_pred_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHEX_PREDICATE_MAX_COUNT.value,
            attack_name="ShEx Predicate MaxCount Violation",
            expected_refusal_code=REFUSED_STRUCTURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shex_datatype_mismatch(
        self, bad_datatype_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHEX-005: Datatype mismatch (integer instead of string)."""
        res = self.pipeline.admit(
            bad_datatype_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHEX_DATATYPE_MISMATCH.value,
            attack_name="ShEx Literal Datatype Mismatch",
            expected_refusal_code=REFUSED_STRUCTURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shex_closed_shape_violation(
        self, unpermitted_pred_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHEX-006: Unpermitted extra predicate injected into a closed shape."""
        res = self.pipeline.admit(
            unpermitted_pred_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHEX_CLOSED_SHAPE_UNPERMITTED_PREDICATE.value,
            attack_name="ShEx Closed Shape Extra Predicate Violation",
            expected_refusal_code=REFUSED_STRUCTURE,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    # -------------------------------------------------------------------------
    # Category 3: SA2A-SHACL-* (Semantic SHACL Shape Falsifiers)
    # -------------------------------------------------------------------------
    def falsify_shacl_unreceipted_do_action(
        self, unreceipted_do_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHACL-001: DO action candidate missing requiresReceipt constraint."""
        res = self.pipeline.admit(
            unreceipted_do_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHACL_UNRECEIPTED_DO_ACTION.value,
            attack_name="SHACL Unreceipted DO Action Violation",
            expected_refusal_code=REFUSED_SHACL,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shacl_missing_authority_consequence(
        self, missing_auth_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHACL-002: Consequential action missing requiresAuthority declaration."""
        res = self.pipeline.admit(
            missing_auth_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHACL_MISSING_AUTHORITY_CONSEQUENCE.value,
            attack_name="SHACL Consequential Action Missing Authority Violation",
            expected_refusal_code=REFUSED_SHACL,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shacl_undeclared_capability(
        self, plan_bad_cap_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHACL-003: Plan references a node that is not typed as afl:Capability."""
        res = self.pipeline.admit(
            plan_bad_cap_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHACL_UNDECLARED_CAPABILITY.value,
            attack_name="SHACL Plan Undeclared Capability Violation",
            expected_refusal_code=REFUSED_SHACL,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_shacl_projection_claiming_canonical(
        self, projection_canonical_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SHACL-004: Projection claiming canonical status via afl:isCanonical."""
        res = self.pipeline.admit(
            projection_canonical_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SHACL_PROJECTION_CLAIMING_CANONICAL.value,
            attack_name="SHACL Projection Claiming Canonical Status Violation",
            expected_refusal_code=REFUSED_SHACL,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    # -------------------------------------------------------------------------
    # Category 4: SA2A-SPARQL-* (SPARQL Invariant Falsifiers & Immutability)
    # -------------------------------------------------------------------------
    def falsify_sparql_consequence_without_authority(
        self, candidate_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SPARQL-001: SPARQL ASK falsifier detects consequence without authority."""
        pipeline = AdmissionPipeline(
            identity_policy=self.identity_policy,
            sparql_falsifiers=[
                SparqlFalsifier(
                    falsifier_id="FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY",
                    query=FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
                    description="Consequence without authority",
                )
            ],
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("urn:issuer:trusted-authority",),
                require_timestamp=True,
            ),
        )
        res = pipeline.admit(
            candidate_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SPARQL_CONSEQUENCE_WITHOUT_AUTH.value,
            attack_name="SPARQL Invariant Consequence Without Authority",
            expected_refusal_code=REFUSED_FALSIFIER,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_sparql_do_without_receipt(
        self, candidate_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SPARQL-002: SPARQL ASK falsifier detects DO action without prepared receipt."""
        pipeline = AdmissionPipeline(
            identity_policy=self.identity_policy,
            sparql_falsifiers=[
                SparqlFalsifier(
                    falsifier_id="FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT",
                    query=FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT,
                    description="DO action without receipt requirement",
                )
            ],
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("urn:issuer:trusted-authority",),
                require_timestamp=True,
            ),
        )
        res = pipeline.admit(
            candidate_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SPARQL_DO_WITHOUT_RECEIPT.value,
            attack_name="SPARQL Invariant DO Without Receipt",
            expected_refusal_code=REFUSED_FALSIFIER,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_sparql_unknown_capability_in_plan(
        self, candidate_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SPARQL-003: SPARQL ASK falsifier detects undeclared capability in plan candidate."""
        pipeline = AdmissionPipeline(
            identity_policy=self.identity_policy,
            sparql_falsifiers=[
                SparqlFalsifier(
                    falsifier_id="FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN",
                    query=FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN,
                    description="Plan references undeclared capability",
                )
            ],
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("urn:issuer:trusted-authority",),
                require_timestamp=True,
            ),
        )
        res = pipeline.admit(
            candidate_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SPARQL_UNKNOWN_CAPABILITY_PLAN.value,
            attack_name="SPARQL Invariant Unknown Capability in Plan",
            expected_refusal_code=REFUSED_FALSIFIER,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_sparql_projection_as_canonical(
        self, candidate_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SPARQL-004: SPARQL ASK falsifier detects projection claiming canonical authority."""
        pipeline = AdmissionPipeline(
            identity_policy=self.identity_policy,
            sparql_falsifiers=[
                SparqlFalsifier(
                    falsifier_id="FALSIFIER_PROJECTION_AS_CANONICAL",
                    query=FALSIFIER_PROJECTION_AS_CANONICAL,
                    description="Projection claiming canonical authority",
                )
            ],
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("urn:issuer:trusted-authority",),
                require_timestamp=True,
            ),
        )
        res = pipeline.admit(
            candidate_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SPARQL_PROJECTION_AS_CANONICAL.value,
            attack_name="SPARQL Invariant Projection As Canonical",
            expected_refusal_code=REFUSED_FALSIFIER,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_sparql_llm_direct_admitted(
        self, candidate_ttl: str, consequence_probe: Optional[Path] = None
    ) -> FalsificationVerdict:
        """SA2A-SPARQL-005: SPARQL ASK falsifier detects LLM asserting ADMITTED directly."""
        pipeline = AdmissionPipeline(
            identity_policy=self.identity_policy,
            sparql_falsifiers=[
                SparqlFalsifier(
                    falsifier_id="FALSIFIER_LLM_DIRECT_ADMITTED",
                    query=FALSIFIER_LLM_DIRECT_ADMITTED,
                    description="LLM asserting ADMITTED directly",
                )
            ],
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("urn:issuer:trusted-authority",),
                require_timestamp=True,
            ),
        )
        res = pipeline.admit(
            candidate_ttl,
            provenance_record={
                "issuer": "urn:issuer:trusted-authority",
                "timestamp": "2026-09-16T12:00:00Z",
            },
        )
        touched = consequence_probe.exists() if consequence_probe else False
        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SPARQL_LLM_DIRECT_ADMITTED.value,
            attack_name="SPARQL Invariant LLM Direct ADMITTED",
            expected_refusal_code=REFUSED_FALSIFIER,
            actual_refusal_code=res.refusal_code,
            standing=res.standing,
            refused_before_consequence=not touched,
            details=res.reasons,
        )

    def falsify_direct_sparql_update_refusal(
        self, canonical_store: CanonicalSemanticStore, sparql_update: str
    ) -> FalsificationVerdict:
        """SA2A-SPARQL-006: Direct SPARQL UPDATE against canonical state refusal."""
        digest_before = canonical_store.canonical_digest
        count_before = canonical_store.triple_count

        refused = False
        reasons = []
        try:
            canonical_store.update(sparql_update)
        except CanonicalStateDirectUpdateRefusedError as exc:
            refused = True
            reasons.append(str(exc))

        digest_after = canonical_store.canonical_digest
        count_after = canonical_store.triple_count
        unmutated = (digest_before == digest_after) and (count_before == count_after)

        return FalsificationVerdict(
            falsifier_code=AdmissionFalsificationCode.SA2A_SPARQL_DIRECT_STATE_UPDATE_REFUSAL.value,
            attack_name="Direct SPARQL Update Refusal on Canonical State",
            expected_refusal_code="REFUSED_CANONICAL_MUTATION",
            actual_refusal_code="REFUSED_CANONICAL_MUTATION" if refused else None,
            standing=Standing.REFUSED if refused else Standing.FAILED,
            refused_before_consequence=unmutated,
            details=tuple(reasons),
        )
