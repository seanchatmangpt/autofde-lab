# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test Suite for Gate 1 Identity & Root Manifest Court (RFC-SA2A-002 v26.9.16).

Chicago Zero-Mock Standard:
- Real plant components, real disk I/O, genuine git repositories, real brokers.
- Strictly zero mocks: no `unittest.mock`, `Mock`, `MagicMock`, `patch`, or `monkeypatch`.
- Anti-oracle rule: deterministic cryptographic bindings, no golden trace fixtures.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.conformance.courts.identity_court import (
    CHI_ID_ARTIFACT_DIGEST,
    CHI_ID_COUNTERFEIT_TAG,
    CHI_ID_GIT_SHA,
    CHI_ID_ROOT_MANIFEST,
    SA2A_ENV_DIGEST_MISMATCH,
    SA2A_ENV_STANDING_ESCALATION,
    ArtifactDigestMismatchError,
    CounterfeitTagRefusalError,
    Gate1CourtReport,
    GitShaMismatchError,
    IdentityCourt,
    IdentityVerdict,
    RootManifestTamperError,
    StandingEscalationRefusalError,
    test_artifact_digest_mismatch_detection,
    test_counterfeit_tag_resolution_refusal,
    test_envelope_standing_escalation_refusal,
    test_git_sha_mismatch_detection,
    test_root_manifest_tamper_detection,
)
from autofde_lab.sa2a.construct.constructor import (
    ExecutableArtifact,
    TargetProfile,
)
from autofde_lab.sa2a.envelope import (
    ProvenanceRecord,
    SemanticEnvelope,
    SemanticGraph,
)
from autofde_lab.sa2a.root_manifest import RootManifest


def _init_real_git_repo(repo_dir: Path) -> str:
    """Initialize a genuine git repository on physical disk and create a real initial commit."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Chicago Test Agent"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "agent@autofde.org"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    dummy_file = repo_dir / "README.md"
    dummy_file.write_text("# AutoFDE Lab Real Git Tree\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial root commit"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip().lower()


def _make_sample_root_manifest() -> RootManifest:
    """Manufacture a real RootManifest instance."""
    return RootManifest(
        admitted_ontology_roots=[
            "https://autofde.org/ontology/core/v1",
            "https://airbus.com/ontology/flight/v2",
        ],
        semantic_profile_versions=["v26.9.16", "v26.9.15"],
        canonicalization_algorithm="C14N-JSON",
        manufacturer_identities=[
            "urn:manufacturer:autofde:core",
            "urn:manufacturer:airbus:certified",
        ],
        admitted_validator_identities=[
            "urn:validator:airbus:qa",
            "urn:validator:formal:audit",
        ],
        authority_broker_identity="urn:broker:authority:primary",
        brce_contract="BRCE-LEVEL4-STRICT",
        receipt_law="APPEND_ONLY_CRYPTOGRAPHIC_CHAIN",
        cryptographic_algorithms=["SHA-256", "ED25519"],
        version_policy="EXACT_PINNED",
    )


# =============================================================================
# 1. Git SHA Mismatch Detection (CHI-ID-GIT-SHA)
# =============================================================================


def test_git_sha_live_repo_match_passes(tmp_path: Path) -> None:
    """Verify that a genuine commit in a real git repository on disk matches successfully."""
    repo_dir = tmp_path / "real_git_repo"
    real_commit_sha = _init_real_git_repo(repo_dir)

    court = IdentityCourt()
    res = court.verify_git_sha(
        expected_sha=real_commit_sha,
        repo_path=repo_dir,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.verdict == IdentityVerdict.CONFORMANT
    assert res.rule_id == CHI_ID_GIT_SHA
    assert res.details["sha"] == real_commit_sha


def test_git_sha_live_repo_mismatch_detected_and_refused(tmp_path: Path) -> None:
    """Verify that an altered or forged Git commit SHA against a live repo raises GitShaMismatchError."""
    repo_dir = tmp_path / "real_git_repo"
    real_commit_sha = _init_real_git_repo(repo_dir)
    counterfeit_sha = "a" * 40

    court = IdentityCourt()
    with pytest.raises(GitShaMismatchError) as exc_info:
        court.verify_git_sha(
            expected_sha=counterfeit_sha,
            repo_path=repo_dir,
            fail_closed=True,
        )

    assert exc_info.value.rule_id == CHI_ID_GIT_SHA
    assert counterfeit_sha in str(exc_info.value)
    assert real_commit_sha in str(exc_info.value)


def test_git_sha_non_fail_closed_returns_verdict() -> None:
    """Verify non-throwing check returns NON_CONFORMANT result with details."""
    court = IdentityCourt()
    res = court.verify_git_sha(
        expected_sha="1111111111111111111111111111111111111111",
        actual_sha="2222222222222222222222222222222222222222",
        fail_closed=False,
    )
    assert res.passed is False
    assert res.verdict == IdentityVerdict.NON_CONFORMANT
    assert res.rule_id == CHI_ID_GIT_SHA
    assert res.error_message is not None


def test_git_sha_invalid_repo_path_raises(tmp_path: Path) -> None:
    """Verify pointing to a non-existent or non-git directory fails closed."""
    court = IdentityCourt()
    with pytest.raises(GitShaMismatchError):
        court.verify_git_sha(
            expected_sha="1111111111111111111111111111111111111111",
            repo_path=tmp_path / "non_existent_dir",
            fail_closed=True,
        )


# =============================================================================
# 2. Artifact Digest Mismatch Detection (CHI-ID-ARTIFACT-DIGEST)
# =============================================================================


def test_artifact_digest_real_disk_file_integrity(tmp_path: Path) -> None:
    """Verify artifact digest checking on a real file written to physical disk."""
    artifact_file = tmp_path / "projection_worker.py"
    code = "def execute_consequence():\n    return {'status': 'admitted'}\n"
    artifact_file.write_text(code, encoding="utf-8")
    expected_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()

    court = IdentityCourt()
    res = court.verify_artifact_digest(
        expected_digest=expected_digest,
        artifact=artifact_file,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.verdict == IdentityVerdict.CONFORMANT

    # Tamper with 1 byte on physical disk
    artifact_file.write_text(code + " ", encoding="utf-8")
    with pytest.raises(ArtifactDigestMismatchError) as exc_info:
        court.verify_artifact_digest(
            expected_digest=expected_digest,
            artifact=artifact_file,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == CHI_ID_ARTIFACT_DIGEST


def test_artifact_digest_executable_artifact_dataclass() -> None:
    """Verify ExecutableArtifact projection integrity check and corruption detection."""
    from autofde_lab.sa2a.construct.constructor import ConstructionReceipt

    code = "def run(): return 42"
    real_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    receipt = ConstructionReceipt.create(
        admitted_input_digest="inp-001",
        manufacturer_identity="urn:manufacturer:autofde:core",
        manufacturer_version="26.9.16",
        target_profile=TargetProfile.PYTHON_EPHEMERAL,
        output_artifact_digest=real_digest,
    )

    clean_artifact = ExecutableArtifact(
        source_code=code,
        target_profile=TargetProfile.PYTHON_EPHEMERAL,
        entrypoint="run",
        artifact_digest=real_digest,
        receipt=receipt,
    )

    court = IdentityCourt()
    res = court.verify_artifact_digest(
        expected_digest=real_digest,
        artifact=clean_artifact,
        fail_closed=True,
    )
    assert res.passed is True

    # Corrupt internal artifact digest
    bad_receipt = ConstructionReceipt.create(
        admitted_input_digest="inp-001",
        manufacturer_identity="urn:manufacturer:autofde:core",
        manufacturer_version="26.9.16",
        target_profile=TargetProfile.PYTHON_EPHEMERAL,
        output_artifact_digest="0" * 64,
    )
    corrupted_artifact = ExecutableArtifact(
        source_code=code,
        target_profile=TargetProfile.PYTHON_EPHEMERAL,
        entrypoint="run",
        artifact_digest="0" * 64,
        receipt=bad_receipt,
    )
    with pytest.raises(ArtifactDigestMismatchError):
        court.verify_artifact_digest(
            expected_digest=real_digest,
            artifact=corrupted_artifact,
            fail_closed=True,
        )


def test_artifact_digest_missing_file_raises(tmp_path: Path) -> None:
    """Verify attempting to verify a missing artifact file raises ArtifactDigestMismatchError."""
    court = IdentityCourt()
    with pytest.raises(ArtifactDigestMismatchError):
        court.verify_artifact_digest(
            expected_digest="a" * 64,
            artifact=tmp_path / "ghost_file.bin",
            fail_closed=True,
        )


# =============================================================================
# 3. Root Manifest Tamper Detection (CHI-ID-ROOT-MANIFEST)
# =============================================================================


def test_root_manifest_canonical_digest_matches() -> None:
    """Verify genuine root manifest canonical digest passes conformance check."""
    manifest = _make_sample_root_manifest()
    computed_digest = manifest.digest()

    court = IdentityCourt()
    res = court.verify_root_manifest(
        manifest=manifest,
        declared_digest=computed_digest,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.verdict == IdentityVerdict.CONFORMANT
    assert res.rule_id == CHI_ID_ROOT_MANIFEST


def test_root_manifest_tampered_field_detected() -> None:
    """Verify that tampering with any field in the RootManifest fails digest verification."""
    manifest = _make_sample_root_manifest()
    declared_digest = manifest.digest()

    # Adversary introduces unauthorized validator or modifies broker
    tampered_manifest = RootManifest(
        admitted_ontology_roots=manifest.admitted_ontology_roots,
        semantic_profile_versions=manifest.semantic_profile_versions,
        canonicalization_algorithm=manifest.canonicalization_algorithm,
        manufacturer_identities=manifest.manufacturer_identities,
        admitted_validator_identities=manifest.admitted_validator_identities,
        authority_broker_identity="urn:broker:adversary:fake",  # TAMPERED
        brce_contract=manifest.brce_contract,
        receipt_law=manifest.receipt_law,
        cryptographic_algorithms=manifest.cryptographic_algorithms,
        version_policy=manifest.version_policy,
    )

    court = IdentityCourt()
    with pytest.raises(RootManifestTamperError) as exc_info:
        court.verify_root_manifest(
            manifest=tampered_manifest,
            declared_digest=declared_digest,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == CHI_ID_ROOT_MANIFEST


def test_root_manifest_disk_file_tamper_detected(tmp_path: Path) -> None:
    """Verify that tampering with a serialized root manifest file on physical disk is detected."""
    manifest = _make_sample_root_manifest()
    manifest_path = tmp_path / "root_manifest.json"

    # Write canonical content to disk
    manifest_path.write_text(manifest.canonical_json(), encoding="utf-8")

    court = IdentityCourt()
    res = court.verify_root_manifest(
        manifest=manifest,
        manifest_file=manifest_path,
        fail_closed=True,
    )
    assert res.passed is True

    # Tamper with file on disk: inject unauthorized ontology root
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["admitted_ontology_roots"].append("https://malicious.org/ontology")
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(RootManifestTamperError):
        court.verify_root_manifest(
            manifest=manifest,
            manifest_file=manifest_path,
            fail_closed=True,
        )


def test_root_manifest_canonical_json_payload_tamper_detected() -> None:
    """Verify that tampering with canonical JSON representation is detected."""
    manifest = _make_sample_root_manifest()
    tampered_payload = manifest.canonical_json() + " "

    court = IdentityCourt()
    with pytest.raises(RootManifestTamperError):
        court.verify_root_manifest(
            manifest=manifest,
            canonical_json_payload=tampered_payload,
            fail_closed=True,
        )


# =============================================================================
# 4. Counterfeit Tag Resolution Refusal (CHI-ID-COUNTERFEIT-TAG)
# =============================================================================


def test_tag_resolution_admitted_tag_passes() -> None:
    """Verify registered tag in admitted namespace passes resolution."""
    admitted = {
        "urn:cap:flight:engine_cutoff": "Airbus Engine Cutoff Capability",
        "urn:cap:nav:autopilot_disengage": "Autopilot Disengage Capability",
    }
    allowed_ns = ["urn:cap:flight:", "urn:cap:nav:"]

    court = IdentityCourt()
    res = court.verify_tag_resolution(
        tag="urn:cap:flight:engine_cutoff",
        admitted_tags=admitted,
        allowed_namespaces=allowed_ns,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.verdict == IdentityVerdict.CONFORMANT
    assert res.rule_id == CHI_ID_COUNTERFEIT_TAG


def test_tag_resolution_counterfeit_tag_refused() -> None:
    """Verify that an unregistered tag claiming valid namespace is refused."""
    admitted = {"urn:cap:flight:engine_cutoff"}
    allowed_ns = ["urn:cap:flight:"]

    court = IdentityCourt()
    with pytest.raises(CounterfeitTagRefusalError) as exc_info:
        court.verify_tag_resolution(
            tag="urn:cap:flight:unauthorized_override",
            admitted_tags=admitted,
            allowed_namespaces=allowed_ns,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == CHI_ID_COUNTERFEIT_TAG


def test_tag_resolution_spoofed_namespace_refused() -> None:
    """Verify that a tag with a spoofed or unadmitted namespace is refused."""
    admitted = {"urn:cap:flight:engine_cutoff"}
    allowed_ns = ["urn:cap:flight:"]

    court = IdentityCourt()
    with pytest.raises(CounterfeitTagRefusalError) as exc_info:
        court.verify_tag_resolution(
            tag="urn:cap:adversary:privilege_escalation",
            admitted_tags=admitted,
            allowed_namespaces=allowed_ns,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == CHI_ID_COUNTERFEIT_TAG


def test_tag_resolution_empty_tag_refused() -> None:
    """Verify empty or whitespace-only tag is refused immediately."""
    court = IdentityCourt()
    with pytest.raises(CounterfeitTagRefusalError):
        court.verify_tag_resolution(
            tag="   ",
            admitted_tags={"urn:cap:test"},
            fail_closed=True,
        )


# =============================================================================
# 5. Semantic Envelope Standing Escalation Refusal (SA2A-ENV-STANDING-ESCALATION)
# =============================================================================


def test_envelope_unlawful_transition_jump_refused() -> None:
    """Verify that an envelope attempting an illegal standing transition jump is refused."""
    court = IdentityCourt()

    # CANDIDATE cannot jump directly to EXECUTED
    with pytest.raises(StandingEscalationRefusalError) as exc_info:
        court.verify_envelope_standing_escalation(
            envelope={
                "standing": Standing.EXECUTED.value,
                "provenance": {"issuer": "urn:agent:adversary"},
                "receipts": [{"receipt_id": "r1"}],
            },
            prior_standing=Standing.CANDIDATE,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == SA2A_ENV_STANDING_ESCALATION


def test_envelope_self_asserted_authorized_without_broker_grant_refused() -> None:
    """Verify that an envelope claiming AUTHORIZED without a real broker grant is refused."""
    broker = AuthorityBroker()
    # Broker holds no grants for urn:agent:rogue
    court = IdentityCourt()

    with pytest.raises(StandingEscalationRefusalError) as exc_info:
        court.verify_envelope_standing_escalation(
            envelope={
                "standing": Standing.AUTHORIZED.value,
                "provenance": {"issuer": "urn:agent:rogue"},
                "authorityRequirement": {
                    "requiredCapability": "urn:cap:power:grid",
                    "authorizedBy": "urn:broker:authority:primary",
                },
            },
            prior_standing=Standing.CONSTRUCTED,
            authority_broker=broker,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == SA2A_ENV_STANDING_ESCALATION
    assert "without valid grant in AuthorityBroker" in str(exc_info.value)


def test_envelope_authorized_with_genuine_broker_grant_passes() -> None:
    """Verify that an envelope claiming AUTHORIZED with a genuine registered grant passes."""
    actor_id = "urn:agent:authorized-controller"
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-001",
            subject_id=actor_id,
            action_iri="urn:action:quarantine",
            target_resource_iri="urn:cap:nodes",
        )
    )

    court = IdentityCourt()
    res = court.verify_envelope_standing_escalation(
        envelope={
            "standing": Standing.AUTHORIZED.value,
            "provenance": {"issuer": actor_id},
            "authorityRequirement": {
                "requiredCapability": "urn:cap:nodes",
                "authorizedBy": "urn:broker:authority:primary",
            },
        },
        prior_standing=Standing.CONSTRUCTED,
        authority_broker=broker,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.verdict == IdentityVerdict.CONFORMANT
    assert res.rule_id == SA2A_ENV_STANDING_ESCALATION


def test_envelope_executed_standing_without_receipts_refused() -> None:
    """Verify that self-asserting EXECUTED without receipts fails closed."""
    court = IdentityCourt()
    with pytest.raises(StandingEscalationRefusalError) as exc_info:
        court.verify_envelope_standing_escalation(
            envelope={
                "standing": Standing.EXECUTED.value,
                "provenance": {"issuer": "urn:agent:worker"},
                "receipts": [],  # NO RECEIPTS!
            },
            prior_standing=Standing.PREPARED,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == SA2A_ENV_STANDING_ESCALATION
    assert "cannot be asserted without verifiable execution receipts" in str(
        exc_info.value
    )


def test_envelope_executed_standing_with_receipts_passes() -> None:
    """Verify that asserting EXECUTED with genuine receipts passes."""
    court = IdentityCourt()
    res = court.verify_envelope_standing_escalation(
        envelope={
            "standing": Standing.EXECUTED.value,
            "provenance": {"issuer": "urn:agent:worker"},
            "receipts": [{"receipt_id": "rec-1", "hash": "abc"}],
        },
        prior_standing=Standing.PREPARED,
        fail_closed=True,
    )
    assert res.passed is True
    assert res.verdict == IdentityVerdict.CONFORMANT


def test_envelope_non_admissible_without_refusal_cause_rejected() -> None:
    """Verify that asserting REFUSED standing without refusalCause is rejected."""
    court = IdentityCourt()
    with pytest.raises(StandingEscalationRefusalError):
        court.verify_envelope_standing_escalation(
            envelope={
                "standing": Standing.REFUSED.value,
                "provenance": {"issuer": "urn:agent:worker"},
                "refusalCause": None,  # Missing refusalCause!
            },
            fail_closed=True,
        )


def test_envelope_pydantic_model_verification() -> None:
    """Verify SemanticEnvelope Pydantic model works cleanly with the court."""
    graph_content = (
        "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
    )
    graph_digest = hashlib.sha256(graph_content.encode("utf-8")).hexdigest()

    envelope = SemanticEnvelope(
        kind="INTENT",
        envelopeId="env-test-001",
        subjects=["urn:subject:system"],
        standing=Standing.CANDIDATE,
        provenance=ProvenanceRecord(
            issuer="urn:agent:intent-producer",
            timestamp="2026-09-16T12:00:00Z",
        ),
        graph=SemanticGraph(
            mediaType="text/turtle",
            digest=graph_digest,
            content=graph_content,
        ),
    )

    court = IdentityCourt()
    res_standing = court.verify_envelope_standing_escalation(
        envelope=envelope,
        prior_standing=Standing.CANDIDATE,
        fail_closed=True,
    )
    assert res_standing.passed is True

    res_digest = court.verify_envelope_digest(envelope=envelope, fail_closed=True)
    assert res_digest.passed is True
    assert res_digest.rule_id == SA2A_ENV_DIGEST_MISMATCH


# =============================================================================
# 6. Full Gate 1 Adjudication Adjudicator (Composite Suite)
# =============================================================================


def test_full_gate1_adjudication_all_conformant(tmp_path: Path) -> None:
    """Verify complete Gate 1 adjudication succeeds when all 5 identity checks pass."""
    repo_dir = tmp_path / "git_repo"
    real_git_sha = _init_real_git_repo(repo_dir)

    artifact_file = tmp_path / "artifact.py"
    code = "def action(): pass\n"
    artifact_file.write_text(code, encoding="utf-8")
    artifact_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()

    manifest = _make_sample_root_manifest()
    manifest_digest = manifest.digest()

    admitted_tags = {"urn:tag:autofde:production_safe": "desc"}
    allowed_namespaces = ["urn:tag:autofde:"]

    envelope = {
        "standing": Standing.CANDIDATE.value,
        "provenance": {"issuer": "urn:agent:planner"},
    }

    court = IdentityCourt()
    report: Gate1CourtReport = court.adjudicate_gate1(
        expected_git_sha=real_git_sha,
        repo_path=repo_dir,
        expected_artifact_digest=artifact_digest,
        artifact=artifact_file,
        manifest=manifest,
        declared_manifest_digest=manifest_digest,
        tag="urn:tag:autofde:production_safe",
        admitted_tags=admitted_tags,
        allowed_tag_namespaces=allowed_namespaces,
        envelope=envelope,
        prior_standing=Standing.CANDIDATE,
    )

    assert report.passed is True
    assert report.verdict == IdentityVerdict.CONFORMANT
    assert len(report.checks) == 5
    assert all(c.passed for c in report.checks)
    assert report.refusal_code is None
    assert len(report.report_digest) == 64  # Valid SHA-256


def test_full_gate1_adjudication_reports_refusal_on_tamper(tmp_path: Path) -> None:
    """Verify complete Gate 1 adjudication non-throwing report captures failures gracefully."""
    repo_dir = tmp_path / "git_repo"
    real_git_sha = _init_real_git_repo(repo_dir)

    artifact_file = tmp_path / "artifact.py"
    code = "def action(): pass\n"
    artifact_file.write_text(code, encoding="utf-8")
    artifact_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()

    manifest = _make_sample_root_manifest()

    court = IdentityCourt()
    report = court.adjudicate_gate1(
        expected_git_sha=real_git_sha,
        repo_path=repo_dir,
        expected_artifact_digest="0" * 64,  # FAKE DIGEST!
        artifact=artifact_file,
        manifest=manifest,
        declared_manifest_digest=manifest.digest(),
        tag="urn:tag:unadmitted:fake",  # COUNTERFEIT TAG!
        admitted_tags={"urn:tag:valid": "desc"},
        allowed_tag_namespaces=["urn:tag:valid:"],
        envelope={"standing": Standing.EXECUTED.value, "receipts": []},  # ESCALATION!
        prior_standing=Standing.CANDIDATE,
    )

    assert report.passed is False
    assert report.verdict == IdentityVerdict.REFUSED
    assert report.refusal_code is not None
    # Check that individual check failures are registered
    failed_rules = {c.rule_id for c in report.checks if not c.passed}
    assert CHI_ID_ARTIFACT_DIGEST in failed_rules
    assert CHI_ID_COUNTERFEIT_TAG in failed_rules
    assert SA2A_ENV_STANDING_ESCALATION in failed_rules


# =============================================================================
# 7. In-module Direct Test Runners Qualification
# =============================================================================


def test_in_module_test_helpers_execute_cleanly() -> None:
    """Verify that all standalone test functions in identity_court.py run and succeed."""
    court = IdentityCourt()
    test_git_sha_mismatch_detection(court)
    test_artifact_digest_mismatch_detection(court)
    test_root_manifest_tamper_detection(court)
    test_counterfeit_tag_resolution_refusal(court)
    test_envelope_standing_escalation_refusal(court)
