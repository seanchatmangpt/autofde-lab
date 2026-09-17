"""Content-addressed Root Manifest definition (RFC-SA2A-001 v26.9.16 §21)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class RootManifest:
    """Content-addressed Root Manifest (§21).

    Establishes the cryptographic and ontological root of trust for an SA2A exchange.
    """

    admitted_ontology_roots: List[str]
    semantic_profile_versions: List[str]
    canonicalization_algorithm: str
    manufacturer_identities: List[str]
    admitted_validator_identities: List[str]
    authority_broker_identity: str
    brce_contract: str
    receipt_law: str
    cryptographic_algorithms: List[str]
    version_policy: str

    def canonical_json(self) -> str:
        """Produce deterministic canonical JSON representation (§21)."""
        data: Dict[str, Any] = {
            "admitted_ontology_roots": sorted(self.admitted_ontology_roots),
            "semantic_profile_versions": sorted(self.semantic_profile_versions),
            "canonicalization_algorithm": self.canonicalization_algorithm,
            "manufacturer_identities": sorted(self.manufacturer_identities),
            "admitted_validator_identities": sorted(self.admitted_validator_identities),
            "authority_broker_identity": self.authority_broker_identity,
            "brce_contract": self.brce_contract,
            "receipt_law": self.receipt_law,
            "cryptographic_algorithms": sorted(self.cryptographic_algorithms),
            "version_policy": self.version_policy,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def digest(self) -> str:
        """Compute SHA-256 digest of canonical root manifest JSON."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
