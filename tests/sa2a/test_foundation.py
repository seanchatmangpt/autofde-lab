"""Unit tests for SA2A Foundation & Algebra (RFC-SA2A-001 v26.9.16)."""

import hashlib
import pytest
from pydantic import ValidationError

from autofde_lab.sa2a.algebra import (
    Standing,
    RefusalCause,
    can_transition,
    validate_transition,
    validate_refusal,
    is_terminal,
    is_admissible,
)
from autofde_lab.sa2a.envelope import (
    SemanticEnvelope,
    SemanticGraph,
    ProvenanceRecord,
    AuthorityRequirement,
    EnvelopeBounds,
)
from autofde_lab.sa2a.root_manifest import RootManifest


def test_standing_enum_members():
    expected_standings = {
        "CANDIDATE",
        "ADMITTED",
        "SELECTED",
        "CONSTRUCTED",
        "AUTHORIZED",
        "PREPARED",
        "EXECUTED",
        "RECEIPTED",
        "ATTESTED",
        "REFUSED",
        "BLOCKED",
        "UNKNOWN",
        "UNSUPPORTED",
        "FAILED",
    }
    actual_standings = {s.value for s in Standing}
    assert expected_standings == actual_standings


def test_refusal_cause_enum_members():
    expected_refusals = {
        "REFUSED_IDENTITY",
        "REFUSED_NAMESPACE",
        "REFUSED_STRUCTURE",
        "REFUSED_SHACL",
        "REFUSED_RULE",
        "REFUSED_FALSIFIER",
        "REFUSED_PROVENANCE",
        "REFUSED_PROFILE",
        "REFUSED_PLAN",
        "REFUSED_CAPABILITY",
        "REFUSED_AUTHORITY",
        "REFUSED_CONSEQUENCE",
        "REFUSED_RECEIPT",
        "REFUSED_BOUNDS",
        "REFUSED_META_RIGOR",
        "BLOCKED_UNKNOWN",
        "BLOCKED_RESOURCE",
        "UNSUPPORTED_PROFILE",
    }
    actual_refusals = {r.value for r in RefusalCause}
    assert expected_refusals == actual_refusals


def test_standing_transitions_and_validation():
    # Lawful progression: CANDIDATE -> ADMITTED -> SELECTED
    assert can_transition(Standing.CANDIDATE, Standing.ADMITTED)
    assert can_transition(Standing.ADMITTED, Standing.SELECTED)
    assert can_transition(Standing.SELECTED, Standing.CONSTRUCTED)
    assert can_transition(Standing.CONSTRUCTED, Standing.AUTHORIZED)
    assert can_transition(Standing.AUTHORIZED, Standing.PREPARED)
    assert can_transition(Standing.PREPARED, Standing.EXECUTED)
    assert can_transition(Standing.EXECUTED, Standing.RECEIPTED)
    assert can_transition(Standing.RECEIPTED, Standing.ATTESTED)

    validate_transition(Standing.CANDIDATE, Standing.ADMITTED)

    # Unlawful progression: CANDIDATE directly to EXECUTED
    assert not can_transition(Standing.CANDIDATE, Standing.EXECUTED)
    with pytest.raises(ValueError, match="Unlawful standing transition"):
        validate_transition(Standing.CANDIDATE, Standing.EXECUTED)

    # Self-transition is allowed
    assert can_transition(Standing.ADMITTED, Standing.ADMITTED)

    # Terminal state transition checks
    assert is_terminal(Standing.ATTESTED)
    assert is_terminal(Standing.REFUSED)
    assert not is_terminal(Standing.ADMITTED)

    # Admissibility checks
    assert is_admissible(Standing.CANDIDATE)
    assert is_admissible(Standing.ADMITTED)
    assert not is_admissible(Standing.REFUSED)
    assert not is_admissible(Standing.BLOCKED)


def test_refusal_validation():
    validate_refusal(Standing.REFUSED, RefusalCause.REFUSED_SHACL)
    validate_refusal(Standing.BLOCKED, RefusalCause.BLOCKED_RESOURCE)
    validate_refusal(Standing.UNSUPPORTED, RefusalCause.UNSUPPORTED_PROFILE)

    # Missing refusal cause
    with pytest.raises(ValueError, match="requires a specific RefusalCause"):
        validate_refusal(Standing.REFUSED, None)

    # Mismatched refusal prefix
    with pytest.raises(ValueError, match="requires a BLOCKED_\\* cause"):
        validate_refusal(Standing.BLOCKED, RefusalCause.REFUSED_SHACL)


def test_semantic_envelope_valid_candidate():
    content = "<urn:s> <urn:p> <urn:o> ."
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    graph = SemanticGraph(
        mediaType="text/turtle",
        digest=digest,
        content=content,
    )
    prov = ProvenanceRecord(
        issuer="agent://agent-1",
        timestamp="2026-09-16T00:00:00Z",
    )
    envelope = SemanticEnvelope(
        kind="INTENT",
        envelopeId="env-123",
        subjects=["urn:subject:1"],
        provenance=prov,
        graph=graph,
    )
    assert envelope.profile == "SA2A-PROFILE-v26.9.16"
    assert envelope.standing == Standing.CANDIDATE
    assert envelope.graph.digest == digest


def test_semantic_graph_digest_mismatch():
    with pytest.raises(ValidationError, match="Graph digest mismatch"):
        SemanticGraph(
            mediaType="text/turtle",
            digest="invalid_digest_hex",
            content="content",
        )


def test_semantic_envelope_non_self_assertion_of_standing():
    prov = ProvenanceRecord(
        issuer="agent://agent-1",
        timestamp="2026-09-16T00:00:00Z",
    )

    # Cannot self-assert EXECUTED without receipts
    with pytest.raises(ValidationError, match="cannot be self-asserted without receipts"):
        SemanticEnvelope(
            kind="ACTION",
            envelopeId="env-executed-without-receipt",
            subjects=["urn:subject:1"],
            standing=Standing.EXECUTED,
            provenance=prov,
        )

    # Cannot assert REFUSED without refusalCause
    with pytest.raises(ValidationError, match="must declare refusalCause"):
        SemanticEnvelope(
            kind="ACTION",
            envelopeId="env-refused-no-cause",
            subjects=["urn:subject:1"],
            standing=Standing.REFUSED,
            provenance=prov,
        )

    # Cannot assert AUTHORIZED without authorizedBy in authorityRequirement
    with pytest.raises(ValidationError, match="requires authorizedBy in authorityRequirement"):
        SemanticEnvelope(
            kind="ACTION",
            envelopeId="env-authorized-no-broker",
            subjects=["urn:subject:1"],
            standing=Standing.AUTHORIZED,
            provenance=prov,
            authorityRequirement=AuthorityRequirement(
                requiredCapability="urn:cap:execute",
            ),
        )

    # Valid EXECUTED envelope with receipt
    valid_executed = SemanticEnvelope(
        kind="ACTION",
        envelopeId="env-executed-ok",
        subjects=["urn:subject:1"],
        standing=Standing.EXECUTED,
        provenance=prov,
        receipts=[{"receiptId": "rec-1", "hash": "abc"}],
    )
    assert valid_executed.standing == Standing.EXECUTED


def test_root_manifest_canonicalization_and_digest():
    manifest = RootManifest(
        admitted_ontology_roots=["urn:onto:b", "urn:onto:a"],
        semantic_profile_versions=["v26.9.16"],
        canonicalization_algorithm="CANONICAL_JSON_SHA256",
        manufacturer_identities=["mfg://agent-1"],
        admitted_validator_identities=["val://validator-2", "val://validator-1"],
        authority_broker_identity="auth://broker-1",
        brce_contract="brce://contract-v1",
        receipt_law="RECEIPT_LAW_STRICT_V1",
        cryptographic_algorithms=["SHA-256", "ED25519"],
        version_policy="EXACT_MATCH",
    )

    digest = manifest.digest()
    assert isinstance(digest, str)
    assert len(digest) == 64

    # Immutability check
    with pytest.raises(Exception):
        manifest.authority_broker_identity = "auth://tampered"

    # Determinism check (independent of input order in lists)
    manifest_reordered = RootManifest(
        admitted_ontology_roots=["urn:onto:a", "urn:onto:b"],
        semantic_profile_versions=["v26.9.16"],
        canonicalization_algorithm="CANONICAL_JSON_SHA256",
        manufacturer_identities=["mfg://agent-1"],
        admitted_validator_identities=["val://validator-1", "val://validator-2"],
        authority_broker_identity="auth://broker-1",
        brce_contract="brce://contract-v1",
        receipt_law="RECEIPT_LAW_STRICT_V1",
        cryptographic_algorithms=["ED25519", "SHA-256"],
        version_policy="EXACT_MATCH",
    )
    assert manifest.digest() == manifest_reordered.digest()
