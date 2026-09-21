"""Pydantic models for Semantic Envelope (RFC-SA2A-001 v26.9.16 §11)."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autofde_lab.sa2a.algebra import RefusalCause, Standing


class SemanticGraph(BaseModel):
    """Encapsulated RDF/OWL/SHACL or structured semantic graph (§11)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mediaType: str = Field(
        ...,
        description="MIME/media type of the graph payload, e.g. text/turtle, application/ld+json",
    )
    digest: str = Field(
        ...,
        description="Hex-encoded SHA-256 digest of content",
    )
    content: str = Field(
        ...,
        description="Raw serialized graph content",
    )

    @model_validator(mode="after")
    def verify_digest(self) -> SemanticGraph:
        expected = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.digest.lower() != expected.lower():
            raise ValueError(
                f"Graph digest mismatch: declared {self.digest} != computed {expected}"
            )
        return self


class ProvenanceRecord(BaseModel):
    """Provenance and attestation metadata (§11)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issuer: str = Field(..., description="Identity of issuer/agent generating envelope")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    signature: Optional[str] = Field(
        None, description="Cryptographic signature over envelope body"
    )
    parentEnvelopeId: Optional[str] = Field(
        None, description="ID of predecessor envelope if any"
    )


class AuthorityRequirement(BaseModel):
    """Authority requirement specification (§11)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requiredCapability: str = Field(..., description="Capability URI or name required")
    minStanding: Standing = Field(
        default=Standing.AUTHORIZED,
        description="Minimum standing level required to execute",
    )
    authorizedBy: Optional[str] = Field(
        None,
        description="Identity of the authority broker providing warrant",
    )


class EnvelopeBounds(BaseModel):
    """Resource, horizon, or consequence bounds (§11)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maxComputeMs: Optional[int] = Field(
        None, description="Max compute milliseconds allowed"
    )
    maxTokens: Optional[int] = Field(None, description="Max tokens allowed")
    maxSteps: Optional[int] = Field(None, description="Max interaction steps allowed")
    falsifierGuards: List[str] = Field(
        default_factory=list, description="Falsifier assertions"
    )


class SemanticEnvelope(BaseModel):
    """Semantic Envelope representing a formal message/payload in SA2A (§11).

    Standing cannot be self-asserted past CANDIDATE by unverified issuers without proof.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str = Field(
        default="SA2A-PROFILE-v26.9.16",
        description="Profile specification version",
    )
    kind: str = Field(
        ..., description="Envelope kind e.g. INTENT, PLAN, WARRANT, RECEIPT, ATT_PROOF"
    )
    envelopeId: str = Field(
        ..., description="Unique content-addressed or UUID envelope identifier"
    )
    subjects: List[str] = Field(
        ..., description="URIs or identifiers of primary subjects"
    )
    standing: Standing = Field(
        default=Standing.CANDIDATE,
        description="Current standing of this envelope",
    )
    refusalCause: Optional[RefusalCause] = Field(
        None,
        description="Refusal cause if standing is REFUSED, BLOCKED, or UNSUPPORTED",
    )
    semanticBasis: List[str] = Field(
        default_factory=list,
        description="Ontology or SHACL schema URIs supporting this envelope",
    )
    graph: Optional[SemanticGraph] = Field(
        None,
        description="Embedded semantic graph payload",
    )
    provenance: ProvenanceRecord = Field(
        ...,
        description="Provenance of envelope creation and authorship",
    )
    consequenceClass: str = Field(
        default="OBSERVATIONAL",
        description="Consequence classification (OBSERVATIONAL, LOCAL_EFFECT, SYSTEMIC_REVERSIBLE, IRREVERSIBLE)",
    )
    authorityRequirement: Optional[AuthorityRequirement] = Field(
        None,
        description="Authority requirements if consequence is non-observational",
    )
    bounds: Optional[EnvelopeBounds] = Field(
        None,
        description="Execution or resource bounds",
    )
    receipts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Receipt hashes or embedded receipts verifying lifecycle execution",
    )

    @model_validator(mode="after")
    def validate_non_self_assertion_of_standing(self) -> SemanticEnvelope:
        """Enforce §11 non-self-assertion: an envelope cannot self-assert standing past CANDIDATE

        unless supported by explicit authority or receipts.
        Specifically:
        - EXECUTED or RECEIPTED requires at least one receipt in `receipts`.
        - AUTHORIZED requires `authorityRequirement.authorizedBy` to be present.
        - Standing cannot be set to non-admissible without specifying refusalCause.
        """
        # Non-admissible check
        if self.standing in {Standing.REFUSED, Standing.BLOCKED, Standing.UNSUPPORTED}:
            if not self.refusalCause:
                raise ValueError(
                    f"Envelope with standing {self.standing.value} must declare refusalCause (§11, §42)"
                )

        # Self-assertion guards
        if self.standing in {Standing.EXECUTED, Standing.RECEIPTED, Standing.ATTESTED}:
            if not self.receipts:
                raise ValueError(
                    f"Standing {self.standing.value} cannot be self-asserted without receipts (§11)"
                )

        if self.standing in {Standing.AUTHORIZED, Standing.PREPARED}:
            if (
                not self.authorityRequirement
                or not self.authorityRequirement.authorizedBy
            ):
                raise ValueError(
                    f"Standing {self.standing.value} requires authorizedBy in authorityRequirement (§11)"
                )

        return self
