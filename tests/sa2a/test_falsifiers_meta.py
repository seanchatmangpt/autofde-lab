"""Unit tests for SPARQL Falsifiers & Meta-Admission (RFC-SA2A-001 v26.9.16 §18, §20, §58, §61).

Tests:
1. SPARQL ASK Falsifiers Engine (§18, §61):
   - FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY triggers on non-observational actions lacking authority.
   - FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY does not trigger when authority requirement or authorization is present.
   - FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT triggers on DO actuation without receipt requirement.
   - FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT does not trigger when receipt requirement is declared.
   - FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN triggers when plan references capability not declared as Capability.
   - FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN does not trigger when capability is declared.
   - FALSIFIER_PROJECTION_AS_CANONICAL triggers when projection claims canonical standing or authority.
   - FALSIFIER_PROJECTION_AS_CANONICAL does not trigger on ordinary projections.
   - FALSIFIER_LLM_DIRECT_ADMITTED triggers on triples directly from LLM asserting ADMITTED standing.
   - FALSIFIER_LLM_DIRECT_ADMITTED does not trigger on non-LLM or candidate assertions.
   - FalsifierSuite evaluate: evaluates registered queries and returns list of triggered falsifiers.
   - Fail-closed behavior: invalid syntax or query execution errors fail closed.

2. Meta-Admission Layer (§20, §58):
   - "Validators/rules/shapes without standing cannot validate".
   - Unadmitted validator is refused and cannot validate (is_admitted is False, assert_admitted raises PermissionError).
   - Validator lacking receipt is refused (REFUSED_RECEIPT).
   - Validator from untrusted source root is refused (REFUSED_NAMESPACE).
   - Validator from untrusted issuer identity is refused (REFUSED_IDENTITY).
   - Validator with non-admissible standing claim is refused (REFUSED_META_RIGOR).
   - Fully admitted validator passes meta-admission and has standing to validate.
"""

from __future__ import annotations

import pytest
import rdflib

from autofde_lab.sa2a.admission.falsifiers import (
    FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
    FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT,
    FALSIFIER_LLM_DIRECT_ADMITTED,
    FALSIFIER_PROJECTION_AS_CANONICAL,
    FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN,
    FalsifierSuite,
)
from autofde_lab.sa2a.admission.meta_admission import (
    MetaAdmissionRegistry,
    ValidatorKind,
)
from autofde_lab.sa2a.algebra import RefusalCause, Standing
from autofde_lab.sa2a.root_manifest import RootManifest

# ==============================================================================
# 1. SPARQL ASK Falsifiers Engine Tests (§18, §61)
# ==============================================================================


class TestSparqlFalsifiers:
    """Test suite for the standard SPARQL ASK falsifiers."""

    def test_falsifier_consequence_without_authority_triggers(self):
        """Action with consequence class but no requiresAuthority must trigger falsification."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY",
            FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:act1 a afl:Actuation ;
            afl:consequenceClass "SYSTEMIC_REVERSIBLE" .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 1
        assert triggered[0].name == "FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY"

    def test_falsifier_consequence_with_authority_passes(self):
        """Action with consequence class AND explicit requiresAuthority or authorizedBy must NOT trigger."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY",
            FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:act1 a afl:Actuation ;
            afl:consequenceClass "SYSTEMIC_REVERSIBLE" ;
            afl:requiresAuthority <urn:auth:grant:123> .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 0

    def test_falsifier_consequence_observational_passes(self):
        """OBSERVATIONAL consequence class does not require authority."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY",
            FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:obs1 a afl:Actuation ;
            afl:consequenceClass "OBSERVATIONAL" .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 0

    def test_falsifier_do_without_receipt_requirement_triggers(self):
        """DO action without prepared receipt requirement must trigger falsification."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT",
            FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:actuation1 a afl:Actuation .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 1
        assert triggered[0].name == "FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT"

    def test_falsifier_do_with_receipt_requirement_passes(self):
        """DO action with prepared receipt requirement must NOT trigger."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT",
            FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:actuation1 a afl:Actuation ;
            afl:requiresReceipt <urn:receipt:schema:epoch> .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 0

    def test_falsifier_unknown_capability_in_plan_triggers(self):
        """Plan referencing undeclared capability must trigger falsification."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN",
            FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:plan1 a afl:PlanCandidate ;
            afl:requiresCapability <urn:cap:undeclared_tool> .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 1
        assert triggered[0].name == "FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN"

    def test_falsifier_unknown_capability_in_plan_passes_when_declared(self):
        """Plan referencing declared Capability passes without triggering."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN",
            FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:cap1 a afl:Capability .
        afl:plan1 a afl:PlanCandidate ;
            afl:requiresCapability afl:cap1 .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 0

    def test_falsifier_projection_as_canonical_triggers(self):
        """Projection claiming canonical authority must trigger falsification."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_PROJECTION_AS_CANONICAL",
            FALSIFIER_PROJECTION_AS_CANONICAL,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:view1 a afl:Projection ;
            afl:isCanonical true .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 1
        assert triggered[0].name == "FALSIFIER_PROJECTION_AS_CANONICAL"

    def test_falsifier_projection_as_canonical_passes_on_honest_projection(self):
        """Ordinary projection not claiming canonical authority does not trigger."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_PROJECTION_AS_CANONICAL",
            FALSIFIER_PROJECTION_AS_CANONICAL,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:view1 a afl:Projection ;
            afl:sourceEntity <urn:entity:canonical_1> .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 0

    def test_falsifier_llm_direct_admitted_triggers(self):
        """Triples originating directly from LLM asserting ADMITTED standing must trigger."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_LLM_DIRECT_ADMITTED",
            FALSIFIER_LLM_DIRECT_ADMITTED,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        afl:llm_bot a afl:LLM .
        afl:candidate1 afl:standing "ADMITTED" ;
            prov:wasAttributedTo afl:llm_bot .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 1
        assert triggered[0].name == "FALSIFIER_LLM_DIRECT_ADMITTED"

    def test_falsifier_llm_candidate_standing_passes(self):
        """Triples originating from LLM asserting CANDIDATE standing do not trigger."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register(
            "FALSIFIER_LLM_DIRECT_ADMITTED",
            FALSIFIER_LLM_DIRECT_ADMITTED,
        )

        turtle = """
        PREFIX afl: <urn:autofde-lab:>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        afl:llm_bot a afl:LLM .
        afl:candidate1 afl:standing "CANDIDATE" ;
            prov:wasAttributedTo afl:llm_bot .
        """
        triggered = suite.evaluate(turtle)
        assert len(triggered) == 0

    def test_falsifier_suite_default_registration_and_evaluation(self):
        """Default FalsifierSuite contains all 5 standard falsifiers and evaluates cleanly."""
        suite = FalsifierSuite(include_defaults=True)
        assert len(suite.registered_falsifiers) == 5
        assert "FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY" in suite.registered_falsifiers
        assert "FALSIFIER_DO_WITHOUT_RECEIPT_REQUIREMENT" in suite.registered_falsifiers
        assert "FALSIFIER_UNKNOWN_CAPABILITY_IN_PLAN" in suite.registered_falsifiers
        assert "FALSIFIER_PROJECTION_AS_CANONICAL" in suite.registered_falsifiers
        assert "FALSIFIER_LLM_DIRECT_ADMITTED" in suite.registered_falsifiers

        # Clean graph triggers 0 falsifiers
        clean_turtle = """
        PREFIX afl: <urn:autofde-lab:>
        afl:cap1 a afl:Capability .
        afl:act1 a afl:Actuation ;
            afl:consequenceClass "OBSERVATIONAL" ;
            afl:requiresReceipt <urn:rcpt:1> .
        """
        assert len(suite.evaluate(clean_turtle)) == 0

    def test_falsifier_suite_fail_closed_on_invalid_syntax(self):
        """Under fail_closed, malformed RDF syntax triggers a refusal/falsification violation."""
        suite = FalsifierSuite(include_defaults=True)
        malformed_turtle = "PREFIX NOT VALID TURTLE ::: ??? "
        triggered = suite.evaluate(malformed_turtle, fail_closed=True)
        assert len(triggered) >= 1
        assert triggered[0].name == "GRAPH_PARSE_FAILURE"

    def test_falsifier_suite_fail_closed_on_query_error(self):
        """Under fail_closed, a malfunctioning query fails closed (triggers violation)."""
        suite = FalsifierSuite(include_defaults=False)
        suite.register("BROKEN_QUERY", "ASK { INVALID SYNTAX ((( ")

        g = rdflib.Graph()
        g.add((rdflib.URIRef("urn:s"), rdflib.URIRef("urn:p"), rdflib.Literal(1)))

        triggered = suite.evaluate(g, fail_closed=True)
        assert len(triggered) == 1
        assert triggered[0].name == "BROKEN_QUERY"
        assert "fail-closed triggered" in triggered[0].description


# ==============================================================================
# 2. Meta-Admission Layer Tests (§20, §58)
# ==============================================================================


@pytest.fixture
def test_root_manifest() -> RootManifest:
    """Fixture providing a standard Root Manifest for test validation."""
    return RootManifest(
        admitted_ontology_roots=[
            "urn:autofde-lab:",
            "https://spec.autofde.org/sa2a#",
            "urn:skdecide:",
        ],
        semantic_profile_versions=["SA2A-PROFILE-v26.9.16"],
        canonicalization_algorithm="C14N-RDF-SHA256",
        manufacturer_identities=[
            "urn:manufacturer:chatman-prime",
            "urn:agent:autofde-lab",
        ],
        admitted_validator_identities=[
            "urn:validator:root-shacl",
            "urn:validator:meta-admission-court",
        ],
        authority_broker_identity="urn:authority:root-broker",
        brce_contract="urn:contract:brce-v1",
        receipt_law="CONSEQUENTIAL_DO_ZERO_UNRECEIPTED",
        cryptographic_algorithms=["SHA-256", "Ed25519"],
        version_policy="DUAL_READ_SINGLE_WRITE",
    )


class TestMetaAdmission:
    """Test suite for Meta-Admission registry and invariants."""

    def test_unadmitted_validator_cannot_validate(self, test_root_manifest):
        """A validator without standing cannot validate; assert_admitted raises PermissionError."""
        registry = MetaAdmissionRegistry(test_root_manifest)
        assert not registry.is_admitted("unadmitted-shape-1")

        with pytest.raises(PermissionError, match="lacks standing and cannot validate"):
            registry.assert_admitted("unadmitted-shape-1")

    def test_validator_without_receipt_is_refused(self, test_root_manifest):
        """A validator presented without an admission receipt must be refused (REFUSED_RECEIPT)."""
        registry = MetaAdmissionRegistry(test_root_manifest)
        decision = registry.admit_validator(
            validator_id="urn:shape:planning",
            kind=ValidatorKind.SHACL_SHAPE,
            artifact_content="<urn:s> <urn:p> <urn:o> .",
            source_root="urn:autofde-lab:shapes:planning",
            issuer_identity="urn:validator:root-shacl",
            receipt_hash=None,  # No receipt!
        )
        assert not decision.admitted
        assert decision.standing == Standing.REFUSED
        assert decision.refusal_cause == RefusalCause.REFUSED_RECEIPT
        assert not registry.is_admitted("urn:shape:planning")

    def test_validator_with_untrusted_source_root_is_refused(self, test_root_manifest):
        """A validator originating from an untrusted source root is refused (REFUSED_NAMESPACE)."""
        registry = MetaAdmissionRegistry(test_root_manifest)
        decision = registry.admit_validator(
            validator_id="urn:shape:rogue",
            kind=ValidatorKind.SHACL_SHAPE,
            artifact_content="<urn:s> <urn:p> <urn:o> .",
            source_root="http://untrusted-attacker.org/shapes",
            issuer_identity="urn:validator:root-shacl",
            receipt_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )
        assert not decision.admitted
        assert decision.standing == Standing.REFUSED
        assert decision.refusal_cause == RefusalCause.REFUSED_NAMESPACE
        assert not registry.is_admitted("urn:shape:rogue")

    def test_validator_with_untrusted_issuer_is_refused(self, test_root_manifest):
        """A validator signed/issued by an untrusted entity is refused (REFUSED_IDENTITY)."""
        registry = MetaAdmissionRegistry(test_root_manifest)
        decision = registry.admit_validator(
            validator_id="urn:shape:untrusted-issuer",
            kind=ValidatorKind.SPARQL_FALSIFIER,
            artifact_content="ASK { ?s ?p ?o }",
            source_root="urn:autofde-lab:falsifiers",
            issuer_identity="urn:agent:malicious-deputy",
            receipt_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )
        assert not decision.admitted
        assert decision.standing == Standing.REFUSED
        assert decision.refusal_cause == RefusalCause.REFUSED_IDENTITY
        assert not registry.is_admitted("urn:shape:untrusted-issuer")

    def test_validator_with_non_admissible_claimed_standing_is_refused(
        self, test_root_manifest
    ):
        """A validator claiming standing other than ADMITTED cannot validate."""
        registry = MetaAdmissionRegistry(test_root_manifest)
        decision = registry.admit_validator(
            validator_id="urn:shape:candidate-only",
            kind=ValidatorKind.DATALOG_RULE,
            artifact_content="reaches(?X, ?Y) :- edge(?X, ?Y) .",
            source_root="urn:autofde-lab:datalog",
            issuer_identity="urn:validator:root-shacl",
            receipt_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            claimed_standing=Standing.CANDIDATE,  # Unadmitted standing
        )
        assert not decision.admitted
        assert decision.standing == Standing.REFUSED
        assert decision.refusal_cause == RefusalCause.REFUSED_META_RIGOR
        assert not registry.is_admitted("urn:shape:candidate-only")

    def test_admitted_validator_passes_meta_admission(self, test_root_manifest):
        """A validator with complete valid provenance and receipt passes meta-admission."""
        registry = MetaAdmissionRegistry(test_root_manifest)
        shape_content = """
        PREFIX afl: <urn:autofde-lab:>
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        afl:TestShape a sh:NodeShape ;
            sh:targetClass afl:Actuation .
        """
        receipt_hash = (
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )

        decision = registry.admit_validator(
            validator_id="urn:shape:actuation-authority",
            kind=ValidatorKind.SHACL_SHAPE,
            artifact_content=shape_content,
            source_root="urn:autofde-lab:shapes:authority",
            issuer_identity="urn:validator:root-shacl",
            receipt_hash=receipt_hash,
            claimed_standing=Standing.ADMITTED,
        )

        assert decision.admitted
        assert decision.standing == Standing.ADMITTED
        assert registry.is_admitted("urn:shape:actuation-authority")

        # Provenance must be stored accurately
        prov = registry.get_validator_provenance("urn:shape:actuation-authority")
        assert prov is not None
        assert prov.validator_id == "urn:shape:actuation-authority"
        assert prov.kind == ValidatorKind.SHACL_SHAPE
        assert prov.receipt_hash == receipt_hash
        assert prov.manifest_digest == test_root_manifest.digest()

        # assert_admitted should not raise
        registry.assert_admitted("urn:shape:actuation-authority")
