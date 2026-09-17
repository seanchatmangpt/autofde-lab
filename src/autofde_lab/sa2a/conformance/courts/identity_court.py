"""Gate 1 Identity & Root Manifest Court (RFC-SA2A-002 v26.9.16 §10, §21, §41).

Chicago Zero-Mock Standard:
- Real plant components, real disk I/O, genuine git repositories, real brokers.
- Strictly zero mocks (no unittest.mock, Mock, MagicMock, patch, or monkeypatch).
- Non-oracle verification with deterministic cryptographic digests.

Enforces:
- CHI-ID-GIT-SHA: Exact Git commit SHA binding and mismatch detection.
- CHI-ID-ARTIFACT-DIGEST: Code projection/artifact content-addressed digest integrity.
- CHI-ID-ROOT-MANIFEST: Root manifest tamper detection and canonical digest verification.
- CHI-ID-COUNTERFEIT-TAG: Refusal of counterfeit, forged, or unadmitted semantic tags.
- SA2A-ENV-STANDING-ESCALATION: Refusal of unauthorized semantic envelope standing escalation.
- SA2A-ENV-DIGEST-MISMATCH: Detection of semantic graph/envelope payload corruption.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from autofde_lab.sa2a.algebra import (
    LAWFUL_TRANSITIONS,
    RefusalCause,
    Standing,
    can_transition,
)
from autofde_lab.sa2a.authority.broker import AuthorityBroker, ConsequenceRequest
from autofde_lab.sa2a.construct.constructor import ExecutableArtifact
from autofde_lab.sa2a.envelope import SemanticEnvelope, SemanticGraph
from autofde_lab.sa2a.root_manifest import RootManifest

# Formal Rule Identifiers (RFC-SA2A-002 Gate 1)
CHI_ID_GIT_SHA: str = "CHI-ID-GIT-SHA"
CHI_ID_ARTIFACT_DIGEST: str = "CHI-ID-ARTIFACT-DIGEST"
CHI_ID_ROOT_MANIFEST: str = "CHI-ID-ROOT-MANIFEST"
CHI_ID_COUNTERFEIT_TAG: str = "CHI-ID-COUNTERFEIT-TAG"
SA2A_ENV_STANDING_ESCALATION: str = "SA2A-ENV-STANDING-ESCALATION"
SA2A_ENV_DIGEST_MISMATCH: str = "SA2A-ENV-DIGEST-MISMATCH"


class IdentityVerdict(str, Enum):
    """Court adjudication verdicts for Gate 1 Identity & Manifest."""

    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"
    REFUSED = "REFUSED"


class IdentityCourtError(Exception):
    """Base exception for Gate 1 Identity & Root Manifest Court violations."""

    def __init__(self, rule_id: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(f"[{rule_id}] {message}")
        self.rule_id = rule_id
        self.message = message
        self.details = details or {}


class GitShaMismatchError(IdentityCourtError):
    """Raised when Git SHA binding fails or differs from repo/expected commit (CHI-ID-GIT-SHA)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(CHI_ID_GIT_SHA, message, details)


class ArtifactDigestMismatchError(IdentityCourtError):
    """Raised when an executable artifact's digest fails cryptographic match (CHI-ID-ARTIFACT-DIGEST)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(CHI_ID_ARTIFACT_DIGEST, message, details)


class RootManifestTamperError(IdentityCourtError):
    """Raised when a root manifest has been modified or its canonical digest is corrupted (CHI-ID-ROOT-MANIFEST)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(CHI_ID_ROOT_MANIFEST, message, details)


class CounterfeitTagRefusalError(IdentityCourtError):
    """Raised when a counterfeit, unregistered, or spoofed semantic tag is presented (CHI-ID-COUNTERFEIT-TAG)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(CHI_ID_COUNTERFEIT_TAG, message, details)


class StandingEscalationRefusalError(IdentityCourtError):
    """Raised when an envelope attempts unlawful or ungrounded standing escalation (SA2A-ENV-STANDING-ESCALATION)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(SA2A_ENV_STANDING_ESCALATION, message, details)


class EnvelopeDigestMismatchError(IdentityCourtError):
    """Raised when an envelope's declared digest or graph content is corrupted (SA2A-ENV-DIGEST-MISMATCH)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(SA2A_ENV_DIGEST_MISMATCH, message, details)


@dataclass(frozen=True, slots=True)
class IdentityCheckResult:
    """Individual rule verification outcome."""

    rule_id: str
    passed: bool
    verdict: IdentityVerdict
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Gate1CourtReport:
    """Comprehensive adjudication report for Gate 1 Identity & Root Manifest Court."""

    court_id: str
    verdict: IdentityVerdict
    passed: bool
    checks: Tuple[IdentityCheckResult, ...]
    refusal_code: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def report_digest(self) -> str:
        payload = {
            "court_id": self.court_id,
            "verdict": self.verdict.value,
            "passed": self.passed,
            "refusal_code": self.refusal_code,
            "checks": [
                {
                    "rule_id": c.rule_id,
                    "passed": c.passed,
                    "verdict": c.verdict.value,
                    "error_message": c.error_message,
                }
                for c in self.checks
            ],
            "timestamp": self.timestamp,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


class IdentityCourt:
    """Gate 1 Identity & Root Manifest Conformance Court.

    Strictly adheres to Chicago Zero-Mock Standard:
    - Real git repository operations and tree commit resolutions.
    - Real disk I/O and cryptographic SHA-256 calculation.
    - Real AuthorityBroker evaluation.
    - Fail-closed defense.
    """

    def __init__(self, court_id: str = "court:gate1:identity-root-manifest") -> None:
        self.court_id = court_id

    @staticmethod
    def resolve_git_sha(repo_path: Union[Path, str]) -> str:
        """Resolve actual HEAD commit SHA from a real git repository on disk.

        Exercises real subprocess execution against the genuine git binary.
        """
        path = Path(repo_path).resolve()
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(path),
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip().lower()
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise GitShaMismatchError(
                f"Failed to resolve git SHA from repository at {path}: {exc}",
                {"repo_path": str(path)},
            ) from exc

    def verify_git_sha(
        self,
        expected_sha: str,
        actual_sha: Optional[str] = None,
        repo_path: Optional[Union[Path, str]] = None,
        fail_closed: bool = True,
    ) -> IdentityCheckResult:
        """Verify Git commit SHA match (CHI-ID-GIT-SHA).

        If repo_path is provided, resolves HEAD SHA directly from the live git repository on disk.
        """
        resolved_actual: str
        if actual_sha is not None:
            resolved_actual = actual_sha.strip().lower()
        elif repo_path is not None:
            resolved_actual = self.resolve_git_sha(repo_path)
        else:
            raise ValueError("Must provide either actual_sha or repo_path for Git SHA verification")

        expected_norm = expected_sha.strip().lower()
        passed = (resolved_actual == expected_norm)

        if not passed:
            err_msg = (
                f"Git SHA mismatch: declared {expected_norm} != actual repository SHA {resolved_actual}"
            )
            if fail_closed:
                raise GitShaMismatchError(
                    err_msg,
                    {"expected_sha": expected_norm, "actual_sha": resolved_actual},
                )
            return IdentityCheckResult(
                rule_id=CHI_ID_GIT_SHA,
                passed=False,
                verdict=IdentityVerdict.NON_CONFORMANT,
                error_message=err_msg,
                details={"expected_sha": expected_norm, "actual_sha": resolved_actual},
            )

        return IdentityCheckResult(
            rule_id=CHI_ID_GIT_SHA,
            passed=True,
            verdict=IdentityVerdict.CONFORMANT,
            details={"sha": resolved_actual},
        )

    def verify_artifact_digest(
        self,
        expected_digest: str,
        artifact: Union[ExecutableArtifact, Path, str, bytes],
        fail_closed: bool = True,
    ) -> IdentityCheckResult:
        """Verify content-addressed digest of an executable projection or file (CHI-ID-ARTIFACT-DIGEST)."""
        actual_digest: str
        if isinstance(artifact, ExecutableArtifact):
            # Calculate SHA-256 over raw artifact code and compare against declared artifact_digest
            computed_from_code = hashlib.sha256(artifact.source_code.encode("utf-8")).hexdigest()
            if artifact.artifact_digest.lower() != computed_from_code.lower():
                err_msg = (
                    f"ExecutableArtifact internal digest corrupt: "
                    f"declared {artifact.artifact_digest} != computed {computed_from_code}"
                )
                if fail_closed:
                    raise ArtifactDigestMismatchError(err_msg)
                return IdentityCheckResult(
                    rule_id=CHI_ID_ARTIFACT_DIGEST,
                    passed=False,
                    verdict=IdentityVerdict.NON_CONFORMANT,
                    error_message=err_msg,
                )
            actual_digest = computed_from_code
        elif isinstance(artifact, Path):
            if not artifact.exists():
                err_msg = f"Artifact file does not exist on disk: {artifact}"
                if fail_closed:
                    raise ArtifactDigestMismatchError(err_msg)
                return IdentityCheckResult(
                    rule_id=CHI_ID_ARTIFACT_DIGEST,
                    passed=False,
                    verdict=IdentityVerdict.NON_CONFORMANT,
                    error_message=err_msg,
                )
            actual_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        elif isinstance(artifact, str):
            actual_digest = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
        elif isinstance(artifact, bytes):
            actual_digest = hashlib.sha256(artifact).hexdigest()
        else:
            raise TypeError(f"Unsupported artifact type: {type(artifact)}")

        expected_norm = expected_digest.strip().lower()
        passed = (actual_digest.lower() == expected_norm)

        if not passed:
            err_msg = (
                f"Artifact digest mismatch: declared {expected_norm} != computed {actual_digest}"
            )
            if fail_closed:
                raise ArtifactDigestMismatchError(
                    err_msg,
                    {"expected_digest": expected_norm, "actual_digest": actual_digest},
                )
            return IdentityCheckResult(
                rule_id=CHI_ID_ARTIFACT_DIGEST,
                passed=False,
                verdict=IdentityVerdict.NON_CONFORMANT,
                error_message=err_msg,
                details={"expected_digest": expected_norm, "actual_digest": actual_digest},
            )

        return IdentityCheckResult(
            rule_id=CHI_ID_ARTIFACT_DIGEST,
            passed=True,
            verdict=IdentityVerdict.CONFORMANT,
            details={"digest": actual_digest},
        )

    def verify_root_manifest(
        self,
        manifest: RootManifest,
        declared_digest: Optional[str] = None,
        canonical_json_payload: Optional[str] = None,
        manifest_file: Optional[Union[Path, str]] = None,
        fail_closed: bool = True,
    ) -> IdentityCheckResult:
        """Verify root manifest cryptographic integrity and tamper detection (CHI-ID-ROOT-MANIFEST).

        Detects:
        - Modification of any manifest fields.
        - Canonical JSON serialization divergences.
        - Disk file tampering.
        """
        computed_digest = manifest.digest().lower()

        # 1. Check against declared digest if provided
        if declared_digest is not None:
            declared_norm = declared_digest.strip().lower()
            if computed_digest != declared_norm:
                err_msg = (
                    f"Root manifest tamper detected: declared digest {declared_norm} "
                    f"!= computed canonical digest {computed_digest}"
                )
                if fail_closed:
                    raise RootManifestTamperError(
                        err_msg,
                        {"declared": declared_norm, "computed": computed_digest},
                    )
                return IdentityCheckResult(
                    rule_id=CHI_ID_ROOT_MANIFEST,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                    details={"declared": declared_norm, "computed": computed_digest},
                )

        # 2. Check canonical JSON payload if provided
        if canonical_json_payload is not None:
            expected_json = manifest.canonical_json()
            if canonical_json_payload != expected_json:
                err_msg = (
                    "Root manifest canonical JSON tamper detected: "
                    "serialized payload does not match canonical deterministic form"
                )
                if fail_closed:
                    raise RootManifestTamperError(err_msg)
                return IdentityCheckResult(
                    rule_id=CHI_ID_ROOT_MANIFEST,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )

        # 3. Check real disk manifest file if provided
        if manifest_file is not None:
            file_path = Path(manifest_file).resolve()
            if not file_path.exists():
                err_msg = f"Root manifest file missing from disk: {file_path}"
                if fail_closed:
                    raise RootManifestTamperError(err_msg)
                return IdentityCheckResult(
                    rule_id=CHI_ID_ROOT_MANIFEST,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )
            content = file_path.read_text(encoding="utf-8")
            file_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            # Also verify JSON deserialization against manifest
            try:
                disk_data = json.loads(content)
                disk_manifest = RootManifest(
                    admitted_ontology_roots=disk_data["admitted_ontology_roots"],
                    semantic_profile_versions=disk_data["semantic_profile_versions"],
                    canonicalization_algorithm=disk_data["canonicalization_algorithm"],
                    manufacturer_identities=disk_data["manufacturer_identities"],
                    admitted_validator_identities=disk_data["admitted_validator_identities"],
                    authority_broker_identity=disk_data["authority_broker_identity"],
                    brce_contract=disk_data["brce_contract"],
                    receipt_law=disk_data["receipt_law"],
                    cryptographic_algorithms=disk_data["cryptographic_algorithms"],
                    version_policy=disk_data["version_policy"],
                )
                if disk_manifest.digest() != computed_digest:
                    err_msg = (
                        f"Root manifest file on disk tampered: disk digest {disk_manifest.digest()} "
                        f"!= memory manifest digest {computed_digest}"
                    )
                    if fail_closed:
                        raise RootManifestTamperError(err_msg)
                    return IdentityCheckResult(
                        rule_id=CHI_ID_ROOT_MANIFEST,
                        passed=False,
                        verdict=IdentityVerdict.REFUSED,
                        error_message=err_msg,
                    )
            except Exception as exc:
                err_msg = f"Failed to parse or validate root manifest from disk: {exc}"
                if fail_closed:
                    raise RootManifestTamperError(err_msg) from exc
                return IdentityCheckResult(
                    rule_id=CHI_ID_ROOT_MANIFEST,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )

        return IdentityCheckResult(
            rule_id=CHI_ID_ROOT_MANIFEST,
            passed=True,
            verdict=IdentityVerdict.CONFORMANT,
            details={"manifest_digest": computed_digest},
        )

    def verify_tag_resolution(
        self,
        tag: str,
        admitted_tags: Union[Iterable[str], Mapping[str, Any]],
        allowed_namespaces: Optional[Sequence[str]] = None,
        fail_closed: bool = True,
    ) -> IdentityCheckResult:
        """Verify tag resolution and strictly refuse counterfeit or forged tags (CHI-ID-COUNTERFEIT-TAG).

        Rejects:
        - Unregistered tags not found in admitted_tags.
        - Counterfeit / spoofed namespace prefixes (e.g. counterfeit urn/tag claiming official namespaces).
        - Malformed or blank tags.
        """
        tag_str = str(tag).strip()
        if not tag_str:
            err_msg = "Refusal: Empty or whitespace-only tag is counterfeit/invalid"
            if fail_closed:
                raise CounterfeitTagRefusalError(err_msg)
            return IdentityCheckResult(
                rule_id=CHI_ID_COUNTERFEIT_TAG,
                passed=False,
                verdict=IdentityVerdict.REFUSED,
                error_message=err_msg,
            )

        # Namespace check
        if allowed_namespaces is not None:
            if not any(tag_str.startswith(ns) for ns in allowed_namespaces):
                err_msg = (
                    f"Refusal: Counterfeit tag '{tag_str}' does not match any admitted namespace: "
                    f"{list(allowed_namespaces)}"
                )
                if fail_closed:
                    raise CounterfeitTagRefusalError(err_msg, {"tag": tag_str})
                return IdentityCheckResult(
                    rule_id=CHI_ID_COUNTERFEIT_TAG,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                    details={"tag": tag_str},
                )

        # Admitted tags membership check
        admitted_set = set(admitted_tags.keys()) if isinstance(admitted_tags, Mapping) else set(admitted_tags)
        if tag_str not in admitted_set:
            err_msg = f"Refusal: Counterfeit or unadmitted tag '{tag_str}' rejected by identity court"
            if fail_closed:
                raise CounterfeitTagRefusalError(err_msg, {"tag": tag_str})
            return IdentityCheckResult(
                rule_id=CHI_ID_COUNTERFEIT_TAG,
                passed=False,
                verdict=IdentityVerdict.REFUSED,
                error_message=err_msg,
                details={"tag": tag_str},
            )

        return IdentityCheckResult(
            rule_id=CHI_ID_COUNTERFEIT_TAG,
            passed=True,
            verdict=IdentityVerdict.CONFORMANT,
            details={"resolved_tag": tag_str},
        )

    def verify_envelope_standing_escalation(
        self,
        envelope: Union[SemanticEnvelope, Mapping[str, Any]],
        prior_standing: Optional[Standing] = None,
        authority_broker: Optional[AuthorityBroker] = None,
        fail_closed: bool = True,
    ) -> IdentityCheckResult:
        """Verify that an envelope does not perform an unlawful standing escalation (SA2A-ENV-STANDING-ESCALATION).

        Checks:
        1. Standing transition path validity under RFC-SA2A-001 §41 LAWFUL_TRANSITIONS.
        2. Prevention of self-asserted standing beyond CANDIDATE without supporting warrants/receipts.
        3. Prevention of AUTHORIZED standing if authority_broker does not hold a corresponding grant.
        4. Prevention of EXECUTED or RECEIPTED standing without receipts.
        """
        # Extract standing
        current_standing: Standing
        raw_standing = envelope.standing if isinstance(envelope, SemanticEnvelope) else envelope.get("standing")
        try:
            current_standing = Standing(raw_standing)
        except (ValueError, KeyError) as exc:
            err_msg = f"Invalid standing value '{raw_standing}' in envelope"
            if fail_closed:
                raise StandingEscalationRefusalError(err_msg) from exc
            return IdentityCheckResult(
                rule_id=SA2A_ENV_STANDING_ESCALATION,
                passed=False,
                verdict=IdentityVerdict.REFUSED,
                error_message=err_msg,
            )

        # 1. Check state transition law from prior standing
        if prior_standing is not None and prior_standing != current_standing:
            if not can_transition(prior_standing, current_standing):
                err_msg = (
                    f"Unlawful standing transition: escalation from {prior_standing.value} "
                    f"to {current_standing.value} is forbidden by standing algebra §41"
                )
                if fail_closed:
                    raise StandingEscalationRefusalError(
                        err_msg,
                        {"prior_standing": prior_standing.value, "target_standing": current_standing.value},
                    )
                return IdentityCheckResult(
                    rule_id=SA2A_ENV_STANDING_ESCALATION,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                    details={"prior_standing": prior_standing.value, "target_standing": current_standing.value},
                )

        # Extract attributes whether Pydantic or Mapping
        if isinstance(envelope, SemanticEnvelope):
            receipts = envelope.receipts
            auth_req = envelope.authorityRequirement
            actor_id = envelope.provenance.issuer
            refusal_cause = envelope.refusalCause
        else:
            receipts = envelope.get("receipts", [])
            auth_req_dict = envelope.get("authorityRequirement")
            auth_req = None
            if auth_req_dict:
                from autofde_lab.sa2a.envelope import AuthorityRequirement
                auth_req = AuthorityRequirement(**auth_req_dict)
            prov_dict = envelope.get("provenance", {})
            actor_id = prov_dict.get("issuer", "urn:agent:unknown")
            refusal_cause = envelope.get("refusalCause")

        # 2. Refusal check: non-admissible standings must declare refusal cause
        if current_standing in {Standing.REFUSED, Standing.BLOCKED, Standing.UNSUPPORTED}:
            if not refusal_cause:
                err_msg = f"Non-admissible standing {current_standing.value} lacks required refusalCause"
                if fail_closed:
                    raise StandingEscalationRefusalError(err_msg)
                return IdentityCheckResult(
                    rule_id=SA2A_ENV_STANDING_ESCALATION,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )

        # 3. Terminal/Executed standing requires receipts
        if current_standing in {Standing.EXECUTED, Standing.RECEIPTED, Standing.ATTESTED}:
            if not receipts:
                err_msg = (
                    f"Self-assertion refusal: Standing {current_standing.value} cannot be asserted "
                    f"without verifiable execution receipts (§11)"
                )
                if fail_closed:
                    raise StandingEscalationRefusalError(err_msg)
                return IdentityCheckResult(
                    rule_id=SA2A_ENV_STANDING_ESCALATION,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )

        # 4. Authorized/Prepared standing requires broker verification
        if current_standing in {Standing.AUTHORIZED, Standing.PREPARED}:
            if not auth_req or not auth_req.authorizedBy:
                err_msg = (
                    f"Standing escalation refusal: Standing {current_standing.value} requires "
                    f"an explicit authorityRequirement.authorizedBy warrant"
                )
                if fail_closed:
                    raise StandingEscalationRefusalError(err_msg)
                return IdentityCheckResult(
                    rule_id=SA2A_ENV_STANDING_ESCALATION,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )

            # If real AuthorityBroker provided, verify grant exists for this subject
            if authority_broker is not None:
                # Check if any registered grant covers this actor (subject_id match).
                # AuthorityBroker.evaluate() requires exact action+resource match, but here
                # we only need to know if the broker holds ANY grant for the declared actor.
                # Access internal _grants (same package, same layer) for the subject check.
                has_grant = any(
                    g.subject_id == actor_id
                    for g in getattr(authority_broker, "_grants", {}).values()
                )
                if not has_grant:
                    err_msg = (
                        f"Standing escalation refusal: Actor '{actor_id}' self-asserted "
                        f"{current_standing.value} without valid grant in AuthorityBroker"
                    )
                    if fail_closed:
                        raise StandingEscalationRefusalError(
                            err_msg,
                            {"actor_id": actor_id, "standing": current_standing.value},
                        )
                    return IdentityCheckResult(
                        rule_id=SA2A_ENV_STANDING_ESCALATION,
                        passed=False,
                        verdict=IdentityVerdict.REFUSED,
                        error_message=err_msg,
                        details={"actor_id": actor_id, "standing": current_standing.value},
                    )

        return IdentityCheckResult(
            rule_id=SA2A_ENV_STANDING_ESCALATION,
            passed=True,
            verdict=IdentityVerdict.CONFORMANT,
            details={"standing": current_standing.value},
        )

    def verify_envelope_digest(
        self,
        envelope: SemanticEnvelope,
        fail_closed: bool = True,
    ) -> IdentityCheckResult:
        """Verify semantic graph digest integrity within envelope (SA2A-ENV-DIGEST-MISMATCH)."""
        if envelope.graph is not None:
            computed_graph_digest = hashlib.sha256(envelope.graph.content.encode("utf-8")).hexdigest()
            if envelope.graph.digest.lower() != computed_graph_digest.lower():
                err_msg = (
                    f"Envelope graph payload tamper: declared digest {envelope.graph.digest} "
                    f"!= computed {computed_graph_digest}"
                )
                if fail_closed:
                    raise EnvelopeDigestMismatchError(err_msg)
                return IdentityCheckResult(
                    rule_id=SA2A_ENV_DIGEST_MISMATCH,
                    passed=False,
                    verdict=IdentityVerdict.REFUSED,
                    error_message=err_msg,
                )

        return IdentityCheckResult(
            rule_id=SA2A_ENV_DIGEST_MISMATCH,
            passed=True,
            verdict=IdentityVerdict.CONFORMANT,
            details={"envelope_id": envelope.envelopeId},
        )

    def adjudicate_gate1(
        self,
        *,
        expected_git_sha: str,
        actual_git_sha: Optional[str] = None,
        repo_path: Optional[Union[Path, str]] = None,
        expected_artifact_digest: str,
        artifact: Union[ExecutableArtifact, Path, str, bytes],
        manifest: RootManifest,
        declared_manifest_digest: Optional[str] = None,
        tag: str,
        admitted_tags: Union[Iterable[str], Mapping[str, Any]],
        allowed_tag_namespaces: Optional[Sequence[str]] = None,
        envelope: Union[SemanticEnvelope, Mapping[str, Any]],
        prior_standing: Optional[Standing] = None,
        authority_broker: Optional[AuthorityBroker] = None,
    ) -> Gate1CourtReport:
        """Adjudicate complete Gate 1 Identity & Root Manifest verification suite.

        Non-throwing aggregator: collects verdicts across all 5 mandatory checks.
        Returns a canonical Gate1CourtReport with cryptographic digest binding.
        """
        checks: List[IdentityCheckResult] = []

        # 1. Git SHA
        checks.append(
            self.verify_git_sha(
                expected_sha=expected_git_sha,
                actual_sha=actual_git_sha,
                repo_path=repo_path,
                fail_closed=False,
            )
        )

        # 2. Artifact Digest
        checks.append(
            self.verify_artifact_digest(
                expected_digest=expected_artifact_digest,
                artifact=artifact,
                fail_closed=False,
            )
        )

        # 3. Root Manifest
        checks.append(
            self.verify_root_manifest(
                manifest=manifest,
                declared_digest=declared_manifest_digest,
                fail_closed=False,
            )
        )

        # 4. Tag Resolution
        checks.append(
            self.verify_tag_resolution(
                tag=tag,
                admitted_tags=admitted_tags,
                allowed_namespaces=allowed_tag_namespaces,
                fail_closed=False,
            )
        )

        # 5. Envelope Standing Escalation
        checks.append(
            self.verify_envelope_standing_escalation(
                envelope=envelope,
                prior_standing=prior_standing,
                authority_broker=authority_broker,
                fail_closed=False,
            )
        )

        all_passed = all(c.passed for c in checks)
        first_refusal = next((c.error_message for c in checks if not c.passed), None)

        verdict = IdentityVerdict.CONFORMANT if all_passed else IdentityVerdict.REFUSED

        return Gate1CourtReport(
            court_id=self.court_id,
            verdict=verdict,
            passed=all_passed,
            checks=tuple(checks),
            refusal_code=first_refusal,
        )


# Backward-compatible alias
Gate1IdentityCourt = IdentityCourt


# =============================================================================
# In-module Test Procedures (Directly executable for court qualification)
# =============================================================================

def test_git_sha_mismatch_detection(court: Optional[IdentityCourt] = None) -> None:
    """Implement test for Git SHA mismatch detection (CHI-ID-GIT-SHA)."""
    c = court or IdentityCourt()
    # 1. Mismatch must raise GitShaMismatchError under fail-closed
    mismatched = False
    try:
        c.verify_git_sha(
            expected_sha="4b825dc642cb6eb9a060e54bf8d69288fbee4904",
            actual_sha="0000000000000000000000000000000000000000",
            fail_closed=True,
        )
    except GitShaMismatchError:
        mismatched = True
    assert mismatched, "Failed to detect Git SHA mismatch under fail-closed"

    # 2. Non-fail-closed check returns failed check result
    res = c.verify_git_sha(
        expected_sha="4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        actual_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        fail_closed=False,
    )
    assert not res.passed
    assert res.verdict == IdentityVerdict.NON_CONFORMANT
    assert res.rule_id == CHI_ID_GIT_SHA


def test_artifact_digest_mismatch_detection(court: Optional[IdentityCourt] = None) -> None:
    """Implement test for Artifact digest mismatch detection (CHI-ID-ARTIFACT-DIGEST)."""
    c = court or IdentityCourt()
    content = "print('admitted safe operation')"
    real_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    counterfeit_digest = "f" * 64

    # 1. Fail closed on altered digest
    mismatched = False
    try:
        c.verify_artifact_digest(
            expected_digest=counterfeit_digest,
            artifact=content,
            fail_closed=True,
        )
    except ArtifactDigestMismatchError:
        mismatched = True
    assert mismatched, "Failed to detect artifact digest mismatch under fail-closed"

    # 2. Success on matching digest
    res = c.verify_artifact_digest(
        expected_digest=real_digest,
        artifact=content,
        fail_closed=True,
    )
    assert res.passed
    assert res.verdict == IdentityVerdict.CONFORMANT


def test_root_manifest_tamper_detection(court: Optional[IdentityCourt] = None) -> None:
    """Implement test for Root manifest tamper detection (CHI-ID-ROOT-MANIFEST)."""
    c = court or IdentityCourt()
    manifest = RootManifest(
        admitted_ontology_roots=["https://autofde.org/ontology/v1"],
        semantic_profile_versions=["v26.9.16"],
        canonicalization_algorithm="C14N-JSON",
        manufacturer_identities=["urn:manufacturer:autofde:core"],
        admitted_validator_identities=["urn:validator:airbus:qa"],
        authority_broker_identity="urn:broker:authority:primary",
        brce_contract="BRCE-LEVEL4-STRICT",
        receipt_law="APPEND_ONLY_CRYPTOGRAPHIC_CHAIN",
        cryptographic_algorithms=["SHA-256"],
        version_policy="EXACT_PINNED",
    )
    valid_digest = manifest.digest()
    tampered_digest = "0" * 64

    # Tamper detection
    tamper_detected = False
    try:
        c.verify_root_manifest(
            manifest=manifest,
            declared_digest=tampered_digest,
            fail_closed=True,
        )
    except RootManifestTamperError:
        tamper_detected = True
    assert tamper_detected, "Failed to detect root manifest tampering"

    # Valid check
    res = c.verify_root_manifest(
        manifest=manifest,
        declared_digest=valid_digest,
        fail_closed=True,
    )
    assert res.passed
    assert res.verdict == IdentityVerdict.CONFORMANT


def test_counterfeit_tag_resolution_refusal(court: Optional[IdentityCourt] = None) -> None:
    """Implement test for Counterfeit tag resolution refusal (CHI-ID-COUNTERFEIT-TAG)."""
    c = court or IdentityCourt()
    admitted = {"urn:tag:autofde:safe_consequence", "urn:tag:airbus:navigation"}
    allowed_ns = ["urn:tag:autofde:", "urn:tag:airbus:"]

    # 1. Unadmitted tag in allowed namespace
    refused = False
    try:
        c.verify_tag_resolution(
            tag="urn:tag:autofde:counterfeit_injection",
            admitted_tags=admitted,
            allowed_namespaces=allowed_ns,
            fail_closed=True,
        )
    except CounterfeitTagRefusalError:
        refused = True
    assert refused, "Failed to refuse counterfeit tag in admitted namespace"

    # 2. Tag in spoofed unadmitted namespace
    spoofed = False
    try:
        c.verify_tag_resolution(
            tag="urn:tag:adversary:malicious_root",
            admitted_tags=admitted,
            allowed_namespaces=allowed_ns,
            fail_closed=True,
        )
    except CounterfeitTagRefusalError:
        spoofed = True
    assert spoofed, "Failed to refuse tag in unadmitted namespace"


def test_envelope_standing_escalation_refusal(court: Optional[IdentityCourt] = None) -> None:
    """Implement test for Semantic envelope standing escalation refusal (SA2A-ENV-STANDING-ESCALATION)."""
    c = court or IdentityCourt()

    # 1. Unlawful transition jump: CANDIDATE -> EXECUTED without receipts
    refused_jump = False
    try:
        c.verify_envelope_standing_escalation(
            envelope={
                "standing": Standing.EXECUTED.value,
                "provenance": {"issuer": "urn:agent:adversary"},
                "receipts": [],
            },
            prior_standing=Standing.CANDIDATE,
            fail_closed=True,
        )
    except StandingEscalationRefusalError:
        refused_jump = True
    assert refused_jump, "Failed to refuse unlawful transition jump from CANDIDATE to EXECUTED"

    # 2. Self-asserted AUTHORIZED standing without valid broker grant
    broker = AuthorityBroker()
    refused_escalation = False
    try:
        c.verify_envelope_standing_escalation(
            envelope={
                "standing": Standing.AUTHORIZED.value,
                "provenance": {"issuer": "urn:agent:adversary"},
                "authorityRequirement": {
                    "requiredCapability": "urn:cap:system",
                    "authorizedBy": "urn:broker:authority:primary",
                },
            },
            prior_standing=Standing.CONSTRUCTED,
            authority_broker=broker,
            fail_closed=True,
        )
    except StandingEscalationRefusalError:
        refused_escalation = True
    assert refused_escalation, "Failed to refuse self-asserted AUTHORIZED without broker grant"
