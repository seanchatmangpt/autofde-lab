"""Unit tests for Semantic A2A Admission Pipeline (RFC-SA2A-001 v26.9.16 §13, §19, §62).

Tests complete end-to-end admission flow:
1. Valid graph admitted -> returns ADMITTED standing, canonical graph, digest, and AdmissionReceipt.
2. Malformed / failing graph refused with exact refusal code:
   - REFUSED_PARSE_FAILURE on unparseable graph syntax
   - REFUSED_IDENTITY / REFUSED_NAMESPACE on disallowed namespaces / IRIs
   - REFUSED_STRUCTURE on ShEx shape violations
   - REFUSED_SHACL on SHACL constraint violations
   - REFUSED_FALSIFIER when SPARQL falsifier query matches
   - REFUSED_PROVENANCE on missing or untrusted issuer / metadata
   - REFUSED_META_RIGOR on triple bounds violations
3. Fixpoint closure under Datalog & N3 derivation rules during admission.
4. Cryptographic binding and determinism of AdmissionReceipt.
"""

import pytest
from rdflib import Literal, Namespace
from rdflib.namespace import RDF

from autofde_lab.sa2a.admission import (
    REFUSED_FALSIFIER,
    REFUSED_IDENTITY,
    REFUSED_META_RIGOR,
    REFUSED_NAMESPACE,
    REFUSED_PARSE_FAILURE,
    REFUSED_PROVENANCE,
    REFUSED_SHACL,
    REFUSED_STRUCTURE,
    AdmissionPipeline,
    AdmissionReceipt,
    DatalogAtom,
    DatalogEngine,
    DatalogRule,
    IdentityPolicy,
    MetaAdmissionPolicy,
    N3ImplicationRule,
    N3RuleEngine,
    NodeKind,
    PredicateConstraint,
    ProvenancePolicy,
    ShaclValidator,
    ShexValidator,
    SparqlFalsifier,
    StructuralShape,
)
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.envelope import ProvenanceRecord, SemanticEnvelope, SemanticGraph

EX = Namespace("http://example.org/")


@pytest.fixture
def base_shacl_shapes():
    return """
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <http://example.org/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    ex:DeviceShape a sh:NodeShape ;
        sh:targetClass ex:Device ;
        sh:property [
            sh:path ex:deviceId ;
            sh:datatype xsd:string ;
            sh:minCount 1 ;
            sh:maxCount 1 ;
        ] ;
        sh:property [
            sh:path ex:status ;
            sh:datatype xsd:string ;
            sh:minCount 1 ;
        ] .
    """


@pytest.fixture
def base_shex_validator():
    device_shape = StructuralShape(
        name="DeviceStructuralShape",
        target_class=EX.Device,
        node_kind=NodeKind.IRI,
        required_types=(EX.Device,),
        predicates=(
            PredicateConstraint(
                predicate=EX.deviceId,
                min_count=1,
                max_count=1,
                node_kind=NodeKind.LITERAL,
            ),
            PredicateConstraint(
                predicate=EX.status,
                min_count=1,
                max_count=1,
                node_kind=NodeKind.LITERAL,
            ),
        ),
    )
    return ShexValidator([device_shape])


@pytest.fixture
def valid_candidate_turtle():
    return """
    @prefix ex: <http://example.org/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    ex:dev1 a ex:Device ;
        ex:deviceId "d-001" ;
        ex:status "ONLINE" .
    """


class TestAdmissionPipelineSuccess:
    def test_full_pipeline_admitted_success(
        self,
        base_shex_validator,
        base_shacl_shapes,
        valid_candidate_turtle,
    ):
        """Test happy path through all 10 stages resulting in Standing.ADMITTED."""
        # 1. Setup Datalog rule: online devices have high availability
        datalog = DatalogEngine(
            [
                DatalogRule(
                    head=DatalogAtom(EX.hasAvailability, "?D", Literal("HIGH")),
                    body=(
                        DatalogAtom(RDF.type, "?D", EX.Device),
                        DatalogAtom(EX.status, "?D", Literal("ONLINE")),
                    ),
                    name="online_high_availability",
                )
            ]
        )

        # 2. Setup N3 implication rule: high availability triggers candidate active lease
        n3 = N3RuleEngine(
            [
                N3ImplicationRule(
                    rule_id="lease_implication",
                    body_patterns=(("?D", EX.hasAvailability, Literal("HIGH")),),
                    head_patterns=(("?D", EX.activeLease, Literal("TRUE")),),
                )
            ]
        )

        # 3. SPARQL Falsifier: Falsify if any device has status ERROR
        falsifier = SparqlFalsifier(
            falsifier_id="no_error_devices",
            query="ASK { ?d <http://example.org/status> 'ERROR' }",
            description="Device in ERROR status cannot be admitted",
        )

        pipeline = AdmissionPipeline(
            identity_policy=IdentityPolicy(
                allowed_subject_namespaces=("http://example.org/",),
                allowed_predicate_namespaces=(
                    "http://example.org/",
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                ),
            ),
            shex_validator=base_shex_validator,
            shacl_validator=ShaclValidator(base_shacl_shapes),
            datalog_engine=datalog,
            n3_engine=n3,
            sparql_falsifiers=[falsifier],
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("agent-alpha", "agent-beta"),
                require_timestamp=True,
            ),
            meta_policy=MetaAdmissionPolicy(min_triples=1, max_triples=50),
        )

        provenance = {
            "issuer": "agent-alpha",
            "timestamp": "2026-09-16T00:00:00Z",
        }

        result = pipeline.admit(valid_candidate_turtle, provenance_record=provenance)

        # Assert standing and result invariants
        assert result.is_admitted is True
        assert result.standing == Standing.ADMITTED
        assert result.refusal_code is None
        assert result.reasons == ("CONFORMS_TO_SPEC",)
        assert result.graph is not None
        assert result.canonical_ntriples is not None
        assert result.digest is not None
        assert len(result.digest) == 64

        # Assert Datalog and N3 derived triples exist in admitted graph
        assert (EX.dev1, EX.hasAvailability, Literal("HIGH")) in result.graph
        assert (EX.dev1, EX.activeLease, Literal("TRUE")) in result.graph

        # Assert receipt properties
        receipt = result.receipt
        assert isinstance(receipt, AdmissionReceipt)
        assert receipt.standing == Standing.ADMITTED
        assert receipt.admitted_graph_digest == result.digest
        assert "PARSE" in receipt.stages_passed
        assert "IDENTITY_POLICY" in receipt.stages_passed
        assert "SHEX" in receipt.stages_passed
        assert "SHACL" in receipt.stages_passed
        assert "DATALOG_CLOSURE" in receipt.stages_passed
        assert "N3_DERIVATION" in receipt.stages_passed
        assert "SPARQL_FALSIFIERS" in receipt.stages_passed
        assert "PROVENANCE" in receipt.stages_passed
        assert "META_ADMISSION" in receipt.stages_passed
        assert receipt.metadata["issuer"] == "agent-alpha"

        # Canonical json and receipt hash verification
        canonical_json = receipt.canonical_json()
        assert len(receipt.receipt_hash) == 64
        assert "ADMITTED" in canonical_json

    def test_admit_semantic_envelope(self, base_shacl_shapes, valid_candidate_turtle):
        """Admission succeeds directly from a SemanticEnvelope model (§11)."""
        import hashlib

        digest = hashlib.sha256(valid_candidate_turtle.encode("utf-8")).hexdigest()

        envelope = SemanticEnvelope(
            envelopeId="env-12345",
            kind="PLAN",
            subjects=["http://example.org/dev1"],
            standing=Standing.CANDIDATE,
            provenance=ProvenanceRecord(
                issuer="agent-verified",
                timestamp="2026-09-16T01:00:00Z",
            ),
            graph=SemanticGraph(
                mediaType="turtle",
                digest=digest,
                content=valid_candidate_turtle,
            ),
        )

        pipeline = AdmissionPipeline(
            shacl_validator=ShaclValidator(base_shacl_shapes),
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("agent-verified",),
            ),
        )

        result = pipeline.admit(envelope)
        assert result.is_admitted is True
        assert result.standing == Standing.ADMITTED


class TestAdmissionPipelineFailClosedRefusals:
    def test_refuse_parse_failure(self):
        """Malformed syntax immediately triggers REFUSED_PARSE_FAILURE."""
        pipeline = AdmissionPipeline()
        malformed_turtle = "This is not turtle @@@@ !!!"

        result = pipeline.admit(malformed_turtle)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_PARSE_FAILURE
        assert any("parsing failed" in r.lower() for r in result.reasons)
        assert result.receipt.refusal_code == REFUSED_PARSE_FAILURE

    def test_refuse_identity_namespace(self):
        """Subject or predicate outside allowed namespaces triggers REFUSED_NAMESPACE."""
        pipeline = AdmissionPipeline(
            identity_policy=IdentityPolicy(
                allowed_subject_namespaces=("http://trusted.org/",),
            ),
            provenance_policy=ProvenancePolicy(
                require_issuer=False, require_timestamp=False
            ),
        )

        untrusted_ttl = """
        <http://untrusted.org/agentX> <http://example.org/says> "hello" .
        """
        result = pipeline.admit(untrusted_ttl)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_NAMESPACE
        assert any("Subject namespace not admitted" in r for r in result.reasons)

    def test_refuse_disallowed_iri(self):
        """Disallowed IRI triggers REFUSED_IDENTITY."""
        pipeline = AdmissionPipeline(
            identity_policy=IdentityPolicy(
                disallowed_iris=("http://example.org/forbidden",),
            ),
            provenance_policy=ProvenancePolicy(
                require_issuer=False, require_timestamp=False
            ),
        )

        ttl = """
        <http://example.org/safe> <http://example.org/linksTo> <http://example.org/forbidden> .
        """
        result = pipeline.admit(ttl)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_IDENTITY
        assert any("disallowed IRI" in r for r in result.reasons)

    def test_refuse_shex_structural_violation(self, base_shex_validator):
        """Missing required structural property in ShEx triggers REFUSED_STRUCTURE."""
        pipeline = AdmissionPipeline(
            shex_validator=base_shex_validator,
            provenance_policy=ProvenancePolicy(
                require_issuer=False, require_timestamp=False
            ),
        )

        # Missing ex:status
        ttl = """
        @prefix ex: <http://example.org/> .
        ex:dev2 a ex:Device ;
            ex:deviceId "d-002" .
        """
        result = pipeline.admit(ttl)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_STRUCTURE
        assert any("minCount violation" in r for r in result.reasons)

    def test_refuse_shacl_constraint_violation(self, base_shacl_shapes):
        """Violating datatype constraint in SHACL triggers REFUSED_SHACL."""
        pipeline = AdmissionPipeline(
            shacl_validator=ShaclValidator(base_shacl_shapes),
            provenance_policy=ProvenancePolicy(
                require_issuer=False, require_timestamp=False
            ),
        )

        # deviceId should be xsd:string, but integer provided
        ttl = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:dev3 a ex:Device ;
            ex:deviceId 12345 ;
            ex:status "ONLINE" .
        """
        result = pipeline.admit(ttl)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_SHACL
        assert len(result.reasons) > 0

    def test_refuse_sparql_falsifier(self, valid_candidate_turtle):
        """Graph matching a negative falsifier query triggers REFUSED_FALSIFIER."""
        falsifier = SparqlFalsifier(
            falsifier_id="no_online_in_quarantine",
            query="ASK { ?d <http://example.org/status> 'ONLINE' }",
            description="Online status forbidden in quarantine test environment",
        )

        pipeline = AdmissionPipeline(
            sparql_falsifiers=[falsifier],
            provenance_policy=ProvenancePolicy(
                require_issuer=False, require_timestamp=False
            ),
        )

        result = pipeline.admit(valid_candidate_turtle)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_FALSIFIER
        assert (
            "Online status forbidden in quarantine test environment" in result.reasons
        )

    def test_refuse_missing_provenance(self, valid_candidate_turtle):
        """Missing issuer/timestamp in provenance triggers REFUSED_PROVENANCE."""
        pipeline = AdmissionPipeline(
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                require_timestamp=True,
            )
        )

        result = pipeline.admit(valid_candidate_turtle, provenance_record={})
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_PROVENANCE
        assert "Missing required issuer in provenance" in result.reasons
        assert "Missing required timestamp in provenance" in result.reasons

    def test_refuse_untrusted_issuer(self, valid_candidate_turtle):
        """Untrusted issuer triggers REFUSED_PROVENANCE."""
        pipeline = AdmissionPipeline(
            provenance_policy=ProvenancePolicy(
                require_issuer=True,
                trusted_issuers=("root-ca", "admin-agent"),
                require_timestamp=False,
            )
        )

        result = pipeline.admit(
            valid_candidate_turtle, provenance_record={"issuer": "rogue-agent"}
        )
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_PROVENANCE
        assert "Issuer 'rogue-agent' not in trusted issuers list" in result.reasons

    def test_refuse_meta_admission_bounds(self):
        """Graph violating max_triples constraint triggers REFUSED_META_RIGOR."""
        pipeline = AdmissionPipeline(
            meta_policy=MetaAdmissionPolicy(min_triples=1, max_triples=2),
            provenance_policy=ProvenancePolicy(
                require_issuer=False, require_timestamp=False
            ),
        )

        ttl = """
        <http://ex.org/1> <http://ex.org/p> "a" .
        <http://ex.org/2> <http://ex.org/p> "b" .
        <http://ex.org/3> <http://ex.org/p> "c" .
        """
        result = pipeline.admit(ttl)
        assert result.is_admitted is False
        assert result.standing == Standing.REFUSED
        assert result.refusal_code == REFUSED_META_RIGOR
        assert any("exceeds maximum 2" in r for r in result.reasons)
