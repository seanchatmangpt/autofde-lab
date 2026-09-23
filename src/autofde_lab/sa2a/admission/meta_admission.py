"""Meta-Admission Layer (RFC-SA2A-001 v26.9.16 §20, §58).

Constitutional Principle:
"Validators, rules, and shapes without standing cannot validate."

Enforces that any validator (SHACL shape, Datalog rule, SPARQL falsifier, etc.)
must possess an admitted receipt and valid cryptographic/ontological provenance
against the Root Manifest before it is permitted to participate in admission or validation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Union

from autofde_lab.sa2a.algebra import RefusalCause, Standing
from autofde_lab.sa2a.root_manifest import RootManifest


class ValidatorKind(str, Enum):
    """Types of validators subject to meta-admission (§20)."""

    SHACL_SHAPE = "SHACL_SHAPE"
    DATALOG_RULE = "DATALOG_RULE"
    SPARQL_FALSIFIER = "SPARQL_FALSIFIER"
    SHEX_SHAPE = "SHEX_SHAPE"
    N3_RULE = "N3_RULE"


@dataclass(frozen=True)
class ValidatorProvenance:
    """Provenance and attestation record for a validator artifact (§20, §58)."""

    validator_id: str
    kind: ValidatorKind
    digest: str
    source_root: str
    issuer_identity: str
    manifest_digest: str
    admitted_standing: Standing = Standing.ADMITTED
    receipt_hash: Optional[str] = None
    signature: Optional[str] = None


@dataclass(frozen=True)
class MetaAdmissionDecision:
    """Result of meta-admission evaluation for a validator."""

    admitted: bool
    standing: Standing
    refusal_cause: Optional[RefusalCause] = None
    reason: str = ""
    validator_id: Optional[str] = None


class MetaAdmissionRegistry:
    """Registry enforcing Meta-Admission Law (§20, §58).

    Guarantees that unadmitted, forged, or unanchored validators/rules/shapes
    cannot be loaded or invoked to judge candidate graphs.
    """

    def __init__(self, root_manifest: RootManifest) -> None:
        """Initialize registry anchored to an exact Root Manifest."""
        self._root_manifest = root_manifest
        self._root_manifest_digest = root_manifest.digest()
        self._registered_validators: Dict[str, ValidatorProvenance] = {}
        self._admitted_validators: Dict[str, ValidatorProvenance] = {}

    @property
    def root_manifest(self) -> RootManifest:
        return self._root_manifest

    @property
    def root_manifest_digest(self) -> str:
        return self._root_manifest_digest

    def admit_validator(
        self,
        validator_id: str,
        kind: Union[ValidatorKind, str],
        artifact_content: Union[str, bytes],
        source_root: str,
        issuer_identity: str,
        receipt_hash: Optional[str] = None,
        signature: Optional[str] = None,
        claimed_standing: Standing = Standing.ADMITTED,
    ) -> MetaAdmissionDecision:
        """Submit a validator for meta-admission against the Root Manifest.

        Checks:
        1. Content digest integrity.
        2. Source ontology/rule root is admitted by Root Manifest.
        3. Issuer identity is admitted by Root Manifest validator identities or manufacturer identities.
        4. Claimed standing is ADMITTED or higher, not a non-admissible standing.
        5. Valid receipt hash must be provided (no unreceipted authority / standing).
        """
        if isinstance(kind, str):
            try:
                kind = ValidatorKind(kind)
            except ValueError:
                return MetaAdmissionDecision(
                    admitted=False,
                    standing=Standing.REFUSED,
                    refusal_cause=RefusalCause.REFUSED_META_RIGOR,
                    reason=f"Unknown validator kind: {kind}",
                    validator_id=validator_id,
                )

        raw_bytes = (
            artifact_content.encode("utf-8")
            if isinstance(artifact_content, str)
            else artifact_content
        )
        content_digest = hashlib.sha256(raw_bytes).hexdigest()

        # 1. Check standing legality
        if claimed_standing != Standing.ADMITTED:
            return MetaAdmissionDecision(
                admitted=False,
                standing=Standing.REFUSED,
                refusal_cause=RefusalCause.REFUSED_META_RIGOR,
                reason=f"Validator cannot claim standing {claimed_standing.value} without formal admission",
                validator_id=validator_id,
            )

        # 2. Receipt requirement: validators without receipts cannot validate (§20, §58)
        if not receipt_hash or not receipt_hash.strip():
            return MetaAdmissionDecision(
                admitted=False,
                standing=Standing.REFUSED,
                refusal_cause=RefusalCause.REFUSED_RECEIPT,
                reason=f"Validator {validator_id} lacks required admission receipt",
                validator_id=validator_id,
            )

        # 3. Check source root against Root Manifest admitted ontology roots
        matched_root = any(
            source_root.startswith(root) or root in source_root
            for root in self._root_manifest.admitted_ontology_roots
        )
        if not matched_root:
            return MetaAdmissionDecision(
                admitted=False,
                standing=Standing.REFUSED,
                refusal_cause=RefusalCause.REFUSED_NAMESPACE,
                reason=f"Validator source root '{source_root}' not in Root Manifest admitted roots",
                validator_id=validator_id,
            )

        # 4. Check issuer identity against Root Manifest admitted validators / manufacturers
        admitted_authorities = set(
            self._root_manifest.admitted_validator_identities
        ) | set(self._root_manifest.manufacturer_identities)
        if issuer_identity not in admitted_authorities:
            return MetaAdmissionDecision(
                admitted=False,
                standing=Standing.REFUSED,
                refusal_cause=RefusalCause.REFUSED_IDENTITY,
                reason=f"Validator issuer '{issuer_identity}' is not an admitted validator or manufacturer in Root Manifest",
                validator_id=validator_id,
            )

        provenance = ValidatorProvenance(
            validator_id=validator_id,
            kind=kind,
            digest=content_digest,
            source_root=source_root,
            issuer_identity=issuer_identity,
            manifest_digest=self._root_manifest_digest,
            admitted_standing=claimed_standing,
            receipt_hash=receipt_hash,
            signature=signature,
        )

        self._registered_validators[validator_id] = provenance
        self._admitted_validators[validator_id] = provenance

        return MetaAdmissionDecision(
            admitted=True,
            standing=Standing.ADMITTED,
            reason=f"Validator {validator_id} successfully meta-admitted",
            validator_id=validator_id,
        )

    def is_admitted(self, validator_id: str) -> bool:
        """Check whether a validator has standing to validate."""
        return validator_id in self._admitted_validators

    def get_validator_provenance(
        self, validator_id: str
    ) -> Optional[ValidatorProvenance]:
        """Retrieve admitted validator provenance record."""
        return self._admitted_validators.get(validator_id)

    def assert_admitted(self, validator_id: str) -> None:
        """Assert that a validator is admitted, raising PermissionError if standing is lacking."""
        if not self.is_admitted(validator_id):
            raise PermissionError(
                f"Meta-admission failure: Validator '{validator_id}' lacks standing and cannot validate (§20, §58)"
            )
