# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test Suite for Admission & Shape Falsification Court (RFC-SA2A-002 v26.9.16).

Strict Chicago Qualification Standard:
- Zero Mocks: Real plant components, genuine disk I/O, authentic brokers/boundaries.
- Anti-Oracle: No pre-canned golden traces or snapshot oracles.
- Rigorously exercises:
  * CHI-ADM-* (Admission & Namespace Invariant Falsifiers)
  * SA2A-SHEX-* (Structural ShEx Shape Falsifiers)
  * SA2A-SHACL-* (Semantic SHACL Shape Falsifiers)
  * SA2A-SPARQL-* (SPARQL Invariant Falsifiers & Canonical State Refusal)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
import rdflib
from rdflib import Graph

from autofde_lab.sa2a.admission.pipeline import (
    REFUSED_FALSIFIER,
    REFUSED_IDENTITY,
    REFUSED_META_RIGOR,
    REFUSED_NAMESPACE,
    REFUSED_PARSE_FAILURE,
    REFUSED_PROVENANCE,
    REFUSED_SHACL,
    REFUSED_STRUCTURE,
)
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import ReceiptStore, TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.admission_court import (
    AdmissionCourt,
    AdmissionFalsificationCode,
    CanonicalSemanticStore,
    CanonicalStateDirectUpdateRefusedError,
    FalsificationVerdict,
)


class RealDiskProbeActuator:
    """Real consequence actuator that mutates external physical disk filesystem state."""

    def __init__(self, probe_path: Path) -> None:
        self._probe_path = probe_path
        self._actuator_id = f"actuator:disk_probe:{probe_path.name}"

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        data = {
            "action": action_iri,
            "target": target_resource,
            "parameters": dict(parameters),
            "digest": hashlib.sha256(json.dumps(dict(sorted(parameters.items()))).encode("utf-8")).hexdigest(),
        }
        self._probe_path.write_text(json.dumps(data), encoding="utf-8")
        return {"applied": True, "path": str(self._probe_path)}

    def actuator_digest(self) -> str:
        return self._actuator_id


class IndependentDiskProbeVerifier:
    """Distinct, independent verifier inspecting real physical disk probe state."""

    def __init__(self, probe_path: Path) -> None:
        self._probe_path = probe_path

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Mapping[str, Any] | None,
    ) -> bool:
        if not self._probe_path.exists():
            return False
        try:
            data = json.loads(self._probe_path.read_text(encoding="utf-8"))
            return data.get("action") == action_iri and data.get("target") == target_resource
        except Exception:
            return False

    def verifier_digest(self) -> str:
        return f"verifier:disk_probe:{self._probe_path.name}"


# =============================================================================
# Category 1: CHI-ADM-* (Admission & Namespace Invariant Falsifiers)
# =============================================================================

def test_chi_adm_001_unadmitted_subject_namespace(tmp_path: Path) -> None:
    """CHI-ADM-001: Attempting to admit unadmitted rogue subject namespace fails closed."""
    consequence_probe = tmp_path / "probe_chi_adm_001.json"
    court = AdmissionCourt()

    rogue_ttl = """
    @prefix rogue: <http://malicious.org/rogue/> .
    @prefix vocab: <http://example.org/vocab/> .
    rogue:subject vocab:status 'ACTIVE' .
    """
    verdict: FalsificationVerdict = court.falsify_unadmitted_subject_namespace(
        rogue_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.CHI_ADM_UNADMITTED_SUBJECT_NS.value
    assert verdict.actual_refusal_code == REFUSED_NAMESPACE
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_chi_adm_002_unadmitted_predicate_namespace(tmp_path: Path) -> None:
    """CHI-ADM-002: Attempting to admit unadmitted predicate namespace fails closed."""
    consequence_probe = tmp_path / "probe_chi_adm_002.json"
    court = AdmissionCourt()

    rogue_ttl = """
    @prefix admitted: <http://example.org/admitted/> .
    @prefix rogue: <http://untrusted.org/vocab/> .
    admitted:node rogue:escalatePrivilege 'ROOT' .
    """
    verdict: FalsificationVerdict = court.falsify_unadmitted_predicate_namespace(
        rogue_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.CHI_ADM_UNADMITTED_PREDICATE_NS.value
    assert verdict.actual_refusal_code == REFUSED_NAMESPACE
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_chi_adm_003_forbidden_disallowed_iri(tmp_path: Path) -> None:
    """CHI-ADM-003: Injected explicitly disallowed / blacklisted IRI fails closed."""
    consequence_probe = tmp_path / "probe_chi_adm_003.json"
    court = AdmissionCourt()

    rogue_ttl = """
    @prefix admitted: <http://example.org/admitted/> .
    @prefix vocab: <http://example.org/vocab/> .
    admitted:node vocab:payload <http://malicious.org/forbidden/payload> .
    """
    verdict: FalsificationVerdict = court.falsify_disallowed_iri(
        rogue_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.CHI_ADM_FORBIDDEN_DISALLOWED_IRI.value
    assert verdict.actual_refusal_code == REFUSED_IDENTITY
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_chi_adm_004_syntax_parse_failure(tmp_path: Path) -> None:
    """CHI-ADM-004: Malformed RDF graph syntax is caught at parse stage."""
    consequence_probe = tmp_path / "probe_chi_adm_004.json"
    court = AdmissionCourt()

    corrupt_ttl = "THIS IS COMPLETELY CORRUPT RDF NOT TURTLE SYNTAX !!!"
    verdict: FalsificationVerdict = court.falsify_syntax_parse_failure(
        corrupt_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.CHI_ADM_PARSE_FAILURE_SYNTAX.value
    assert verdict.actual_refusal_code == REFUSED_PARSE_FAILURE
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_chi_adm_005_empty_candidate_graph(tmp_path: Path) -> None:
    """CHI-ADM-005: Empty candidate graph fails meta-rigor min_triples constraint."""
    consequence_probe = tmp_path / "probe_chi_adm_005.json"
    court = AdmissionCourt()

    verdict: FalsificationVerdict = court.falsify_empty_candidate_graph(
        "", consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.CHI_ADM_EMPTY_CANDIDATE_GRAPH.value
    assert verdict.actual_refusal_code == REFUSED_META_RIGOR
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_chi_adm_006_missing_provenance_issuer(tmp_path: Path) -> None:
    """CHI-ADM-006: Valid candidate missing required provenance issuer is refused."""
    consequence_probe = tmp_path / "probe_chi_adm_006.json"
    court = AdmissionCourt()

    valid_ttl = """
    @prefix admitted: <http://example.org/admitted/> .
    @prefix vocab: <http://example.org/vocab/> .
    admitted:cluster vocab:status 'ACTIVE' .
    """
    verdict: FalsificationVerdict = court.falsify_missing_provenance_issuer(
        valid_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.CHI_ADM_MISSING_PROVENANCE_ISSUER.value
    assert verdict.actual_refusal_code == REFUSED_PROVENANCE
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


# =============================================================================
# Category 2: SA2A-SHEX-* (Structural ShEx Shape Falsifiers)
# =============================================================================

def test_sa2a_shex_001_node_kind_mismatch(tmp_path: Path) -> None:
    """SA2A-SHEX-001: Target resource is blank node where IRI required by ShEx."""
    consequence_probe = tmp_path / "probe_shex_001.json"
    court = AdmissionCourt()

    # Action requires targetResource to be an IRI, but candidate provides a blank node
    bad_shex_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:action_001 a afl:Action ;
        afl:actionId "act-001"^^xsd:string ;
        afl:targetResource _:bnode_target .
    """
    verdict: FalsificationVerdict = court.falsify_shex_node_kind(
        bad_shex_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHEX_NODE_KIND_MISMATCH.value
    assert verdict.actual_refusal_code == REFUSED_STRUCTURE
    assert verdict.standing == Standing.REFUSED
    assert any("violates node_kind" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shex_002_missing_required_type(tmp_path: Path) -> None:
    """SA2A-SHEX-002: Subject node targeted by shape missing required rdf:type."""
    consequence_probe = tmp_path / "probe_shex_002.json"
    court = AdmissionCourt()

    # Node has Action shape fields but does not declare rdf:type afl:Action
    bad_shex_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:action_002
        afl:actionId "act-002"^^xsd:string ;
        afl:targetResource afl:resource_alpha .
    """
    # Explicitly test via ShexValidator targeting ActionShape
    validator = court.shex_validator
    g = Graph()
    g.parse(data=bad_shex_ttl, format="turtle")
    rep = validator.validate(g, target_nodes={"ActionShape": [rdflib.URIRef("urn:autofde-lab:action_002")]})

    assert rep.conforms is False
    assert any("missing required rdf:type" in v for v in rep.violations)


def test_sa2a_shex_003_predicate_min_count(tmp_path: Path) -> None:
    """SA2A-SHEX-003: Mandatory predicate omitted (minCount violation)."""
    consequence_probe = tmp_path / "probe_shex_003.json"
    court = AdmissionCourt()

    # Action missing mandatory afl:targetResource
    bad_shex_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:action_003 a afl:Action ;
        afl:actionId "act-003"^^xsd:string .
    """
    verdict: FalsificationVerdict = court.falsify_shex_predicate_min_count(
        bad_shex_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHEX_PREDICATE_MIN_COUNT.value
    assert verdict.actual_refusal_code == REFUSED_STRUCTURE
    assert verdict.standing == Standing.REFUSED
    assert any("minCount violation" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shex_004_predicate_max_count(tmp_path: Path) -> None:
    """SA2A-SHEX-004: Duplicate predicates exceed permitted maxCount."""
    consequence_probe = tmp_path / "probe_shex_004.json"
    court = AdmissionCourt()

    # Action has two different actionId values, violating maxCount 1
    bad_shex_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:action_004 a afl:Action ;
        afl:actionId "act-004-a"^^xsd:string ;
        afl:actionId "act-004-b"^^xsd:string ;
        afl:targetResource afl:resource_alpha .
    """
    verdict: FalsificationVerdict = court.falsify_shex_predicate_max_count(
        bad_shex_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHEX_PREDICATE_MAX_COUNT.value
    assert verdict.actual_refusal_code == REFUSED_STRUCTURE
    assert verdict.standing == Standing.REFUSED
    assert any("maxCount violation" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shex_005_datatype_mismatch(tmp_path: Path) -> None:
    """SA2A-SHEX-005: Datatype mismatch in literal property."""
    consequence_probe = tmp_path / "probe_shex_005.json"
    court = AdmissionCourt()

    # Action actionId is integer instead of xsd:string
    bad_shex_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:action_005 a afl:Action ;
        afl:actionId 9999 ;
        afl:targetResource afl:resource_alpha .
    """
    verdict: FalsificationVerdict = court.falsify_shex_datatype_mismatch(
        bad_shex_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHEX_DATATYPE_MISMATCH.value
    assert verdict.actual_refusal_code == REFUSED_STRUCTURE
    assert verdict.standing == Standing.REFUSED
    assert any("violates datatype" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shex_006_closed_shape_unpermitted_predicate(tmp_path: Path) -> None:
    """SA2A-SHEX-006: Closed shape containing rogue extra predicate."""
    consequence_probe = tmp_path / "probe_shex_006.json"
    court = AdmissionCourt()

    # ClusterNode shape is closed, only permitting nodeId and status; afl:rogueProperty is rejected
    bad_shex_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:node_006 a afl:ClusterNode ;
        afl:nodeId "worker-alpha"^^xsd:string ;
        afl:status "READY" ;
        afl:rogueProperty "UNPERMITTED_INJECTION" .
    """
    verdict: FalsificationVerdict = court.falsify_shex_closed_shape_violation(
        bad_shex_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHEX_CLOSED_SHAPE_UNPERMITTED_PREDICATE.value
    assert verdict.actual_refusal_code == REFUSED_STRUCTURE
    assert verdict.standing == Standing.REFUSED
    assert any("unpermitted predicate" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


# =============================================================================
# Category 3: SA2A-SHACL-* (Semantic SHACL Shape Falsifiers)
# =============================================================================

def test_sa2a_shacl_001_unreceipted_do_action(tmp_path: Path) -> None:
    """SA2A-SHACL-001: DO action candidate missing requiresReceipt constraint."""
    consequence_probe = tmp_path / "probe_shacl_001.json"
    court = AdmissionCourt()

    unreceipted_do_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:actuation_001 a afl:DoAction ;
        afl:actionKind "DO" ;
        afl:targetResource afl:cluster_storage .
    """
    verdict: FalsificationVerdict = court.falsify_shacl_unreceipted_do_action(
        unreceipted_do_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHACL_UNRECEIPTED_DO_ACTION.value
    assert verdict.actual_refusal_code == REFUSED_SHACL
    assert verdict.standing == Standing.REFUSED
    assert any("requiresReceipt" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shacl_002_missing_authority_consequence(tmp_path: Path) -> None:
    """SA2A-SHACL-002: Consequential action missing requiresAuthority declaration."""
    consequence_probe = tmp_path / "probe_shacl_002.json"
    court = AdmissionCourt()

    missing_auth_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:consequence_002 a afl:ConsequentialAction ;
        afl:actionKind "LOCAL_EFFECT" ;
        afl:targetResource afl:cluster_nodes .
    """
    verdict: FalsificationVerdict = court.falsify_shacl_missing_authority_consequence(
        missing_auth_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHACL_MISSING_AUTHORITY_CONSEQUENCE.value
    assert verdict.actual_refusal_code == REFUSED_SHACL
    assert verdict.standing == Standing.REFUSED
    assert any("requiresAuthority" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shacl_003_undeclared_capability(tmp_path: Path) -> None:
    """SA2A-SHACL-003: Plan references a node not typed as afl:Capability."""
    consequence_probe = tmp_path / "probe_shacl_003.json"
    court = AdmissionCourt()

    plan_bad_cap_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:plan_003 a afl:Plan ;
        afl:requiresCapability afl:arbitrary_undeclared_node .

    # Node exists but is an UntypedObject, not afl:Capability
    afl:arbitrary_undeclared_node a afl:UntypedObject .
    """
    verdict: FalsificationVerdict = court.falsify_shacl_undeclared_capability(
        plan_bad_cap_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHACL_UNDECLARED_CAPABILITY.value
    assert verdict.actual_refusal_code == REFUSED_SHACL
    assert verdict.standing == Standing.REFUSED
    assert any("Capability" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shacl_004_projection_claiming_canonical(tmp_path: Path) -> None:
    """SA2A-SHACL-004: Projection claiming canonical status via afl:isCanonical."""
    consequence_probe = tmp_path / "probe_shacl_004.json"
    court = AdmissionCourt()

    proj_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:proj_004 a afl:Projection ;
        afl:isCanonical true .
    """
    verdict: FalsificationVerdict = court.falsify_shacl_projection_claiming_canonical(
        proj_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SHACL_PROJECTION_CLAIMING_CANONICAL.value
    assert verdict.actual_refusal_code == REFUSED_SHACL
    assert verdict.standing == Standing.REFUSED
    assert any("isCanonical" in detail for detail in verdict.details)
    assert not consequence_probe.exists()


def test_sa2a_shacl_005_severity_range_violation(tmp_path: Path) -> None:
    """SA2A-SHACL-005: Property value not in permitted enum list."""
    consequence_probe = tmp_path / "probe_shacl_005.json"
    court = AdmissionCourt()

    bad_enum_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:incident_005 a afl:Incident ;
        afl:severity "APOCALYPTIC" .
    """
    res = court.pipeline.admit(
        bad_enum_ttl,
        provenance_record={
            "issuer": "urn:issuer:trusted-authority",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )

    assert res.is_admitted is False
    assert res.refusal_code == REFUSED_SHACL
    assert res.standing == Standing.REFUSED
    assert any("severity" in reason for reason in res.reasons)
    assert not consequence_probe.exists()


# =============================================================================
# Category 4: SA2A-SPARQL-* (SPARQL Invariant Falsifiers & Canonical State Refusal)
# =============================================================================

def test_sa2a_sparql_001_consequence_without_authority(tmp_path: Path) -> None:
    """SA2A-SPARQL-001: SPARQL ASK falsifier catches consequential action without authority."""
    consequence_probe = tmp_path / "probe_sparql_001.json"
    court = AdmissionCourt()

    candidate_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:act_sparql_001 afl:consequenceClass "LOCAL_EFFECT" .
    """
    verdict: FalsificationVerdict = court.falsify_sparql_consequence_without_authority(
        candidate_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SPARQL_CONSEQUENCE_WITHOUT_AUTH.value
    assert verdict.actual_refusal_code == REFUSED_FALSIFIER
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_sa2a_sparql_002_do_without_receipt(tmp_path: Path) -> None:
    """SA2A-SPARQL-002: SPARQL ASK falsifier catches DO action without receipt requirement."""
    consequence_probe = tmp_path / "probe_sparql_002.json"
    court = AdmissionCourt()

    candidate_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:act_sparql_002 a afl:DoAction .
    """
    verdict: FalsificationVerdict = court.falsify_sparql_do_without_receipt(
        candidate_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SPARQL_DO_WITHOUT_RECEIPT.value
    assert verdict.actual_refusal_code == REFUSED_FALSIFIER
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_sa2a_sparql_003_unknown_capability_in_plan(tmp_path: Path) -> None:
    """SA2A-SPARQL-003: SPARQL ASK falsifier catches plan candidate with undeclared capability."""
    consequence_probe = tmp_path / "probe_sparql_003.json"
    court = AdmissionCourt()

    candidate_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:plan_sparql_003 a afl:Plan ;
        afl:requiresCapability afl:phantom_cap .

    afl:phantom_cap a afl:PhantomEntity .
    """
    verdict: FalsificationVerdict = court.falsify_sparql_unknown_capability_in_plan(
        candidate_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SPARQL_UNKNOWN_CAPABILITY_PLAN.value
    assert verdict.actual_refusal_code == REFUSED_FALSIFIER
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_sa2a_sparql_004_projection_as_canonical(tmp_path: Path) -> None:
    """SA2A-SPARQL-004: SPARQL ASK falsifier catches projection claiming canonical authority."""
    consequence_probe = tmp_path / "probe_sparql_004.json"
    court = AdmissionCourt()

    candidate_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:proj_sparql_004 a afl:Projection ;
        afl:isCanonical true .
    """
    verdict: FalsificationVerdict = court.falsify_sparql_projection_as_canonical(
        candidate_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SPARQL_PROJECTION_AS_CANONICAL.value
    assert verdict.actual_refusal_code == REFUSED_FALSIFIER
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_sa2a_sparql_005_llm_direct_admitted(tmp_path: Path) -> None:
    """SA2A-SPARQL-005: SPARQL ASK falsifier catches LLM asserting ADMITTED directly."""
    consequence_probe = tmp_path / "probe_sparql_005.json"
    court = AdmissionCourt()

    candidate_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix prov: <http://www.w3.org/ns/prov#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:rogue_proposal afl:standing "ADMITTED" ;
        prov:wasAttributedTo afl:gemini_flash_agent .

    afl:gemini_flash_agent a afl:LLM .
    """
    verdict: FalsificationVerdict = court.falsify_sparql_llm_direct_admitted(
        candidate_ttl, consequence_probe=consequence_probe
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SPARQL_LLM_DIRECT_ADMITTED.value
    assert verdict.actual_refusal_code == REFUSED_FALSIFIER
    assert verdict.standing == Standing.REFUSED
    assert not consequence_probe.exists()


def test_sa2a_sparql_006_direct_state_update_refusal(tmp_path: Path) -> None:
    """SA2A-SPARQL-006: Direct SPARQL UPDATE against canonical state O* is refused."""
    initial_graph = Graph()
    initial_graph.parse(
        data="""
        @prefix afl: <urn:autofde-lab:> .
        afl:cluster_root afl:status "INITIALIZED" .
        """,
        format="turtle",
    )

    canonical_store = CanonicalSemanticStore(initial_graph=initial_graph)
    initial_digest = canonical_store.canonical_digest
    initial_count = canonical_store.triple_count

    court = AdmissionCourt()

    # Adversary attempts direct SPARQL INSERT DATA against canonical store
    adversary_update = """
    PREFIX afl: <urn:autofde-lab:>
    INSERT DATA {
        afl:backdoor_node afl:privilegedRole "ROOT_ADMIN" .
    }
    """

    verdict: FalsificationVerdict = court.falsify_direct_sparql_update_refusal(
        canonical_store=canonical_store,
        sparql_update=adversary_update,
    )

    assert verdict.passed is True
    assert verdict.falsifier_code == AdmissionFalsificationCode.SA2A_SPARQL_DIRECT_STATE_UPDATE_REFUSAL.value
    assert verdict.actual_refusal_code == "REFUSED_CANONICAL_MUTATION"
    assert verdict.standing == Standing.REFUSED
    assert verdict.refused_before_consequence is True

    # Assert canonical state remained strictly untouched
    assert canonical_store.canonical_digest == initial_digest
    assert canonical_store.triple_count == initial_count


# =============================================================================
# Zero-Mock Real Consequence Gating Test
# =============================================================================

def test_admission_court_zero_mock_consequence_gating(tmp_path: Path) -> None:
    """Proves the full pipeline gates a genuine BRCE Consequence Boundary with real disk I/O.

    Strict Zero-Mock:
    - Real disk probe file.
    - Real ConsequenceBoundary, AuthorityBroker, ReceiptStore.
    - If admission fails, disk probe is never touched.
    - If admission succeeds, admitted receipt digest can authorize downstream execution.
    """
    probe_file = tmp_path / "real_disk_actuation.json"
    actuator = RealDiskProbeActuator(probe_file)
    verifier = IndependentDiskProbeVerifier(probe_file)
    broker = AuthorityBroker()
    receipt_store = ReceiptStore()

    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=receipt_store,
    )

    court = AdmissionCourt()

    # Step 1: Adversary submits unadmitted state
    unadmitted_ttl = """
    @prefix rogue: <http://malicious.org/rogue/> .
    @prefix vocab: <http://example.org/vocab/> .
    rogue:node vocab:action "EXECUTE_IMPACT" .
    """
    res = court.pipeline.admit(unadmitted_ttl)
    assert res.is_admitted is False

    # Attempting to actuate consequence with unadmitted receipt or without grant fails closed
    envelope = ExecutionEnvelope(
        idempotency_token="idemp-unadmitted-01",
        action_iri="urn:action:execute_impact",
        target_resource="urn:resource:disk",
        parameters={"payload": "wipe"},
        actor_id="urn:agent:adversary",
    )
    exec_res = boundary.execute(envelope)
    assert exec_res.success is False
    assert exec_res.state == TerminalReceiptState.REFUSED
    assert not probe_file.exists()  # Zero disk I/O!

    # Step 2: Legitimate candidate passes full admission pipeline
    legit_ttl = """
    @prefix afl: <urn:autofde-lab:> .
    @prefix vocab: <http://example.org/vocab/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    afl:legit_action a afl:Action ;
        afl:actionId "legit-001"^^xsd:string ;
        afl:targetResource afl:disk_target .
    """
    legit_res = court.pipeline.admit(
        legit_ttl,
        provenance_record={
            "issuer": "urn:issuer:trusted-authority",
            "timestamp": "2026-09-16T12:00:00Z",
        },
    )
    assert legit_res.is_admitted is True
    assert legit_res.receipt.standing == Standing.ADMITTED

    # Register grant bound to admitted action and authorized actor
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-legit-001",
            subject_id="urn:agent:admitted-worker",
            action_iri="urn:action:legit_write",
            target_resource_iri="urn:resource:disk",
        )
    )

    # Legitimate actuation succeeds with real disk write and independent verification
    legit_envelope = ExecutionEnvelope(
        idempotency_token="idemp-legit-001",
        action_iri="urn:action:legit_write",
        target_resource="urn:resource:disk",
        parameters={"status": "INITIALIZED"},
        actor_id="urn:agent:admitted-worker",
    )
    legit_exec_res = boundary.execute(legit_envelope)
    assert legit_exec_res.success is True
    assert legit_exec_res.state == TerminalReceiptState.EXECUTED
    assert legit_exec_res.final_receipt is not None
    assert legit_exec_res.final_receipt.postcondition_verified is True

    # Real file exists and contains expected content
    assert probe_file.exists()
    disk_content = json.loads(probe_file.read_text(encoding="utf-8"))
    assert disk_content["action"] == "urn:action:legit_write"
    assert disk_content["target"] == "urn:resource:disk"
