r"""Constructor module for Semantic A2A (RFC-SA2A-001 v26.9.16).

Implements the Chatman construction relation:
    A = \mu(O*) (§5, §26)
    R = receipt(A)

Generates deterministic executable artifacts / projections from admitted semantics O*.
Includes ConstructionReceipt binding admitted input digest, manufacturer identity,
manufacturer version, target profile, and output artifact digest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


def compute_digest(data: str | bytes | Mapping[str, Any] | Sequence[Any]) -> str:
    """Compute canonical SHA-256 hex digest for arbitrary data."""
    if isinstance(data, bytes):
        payload = data
    elif isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    return hashlib.sha256(payload).hexdigest()


class TargetProfile(str, Enum):
    """Target execution profile for manufactured projections."""

    PYTHON_EPHEMERAL = "python_ephemeral"
    WASM_CORE = "wasm_core"
    BEAM_ATOMVM = "beam_atomvm"
    BASH_DISPATCH = "bash_dispatch"
    JSON_SCHEMA = "json_schema"


@dataclass(frozen=True, slots=True)
class AdmittedSemantics:
    """Admitted canonical semantic state O* (§5).

    Only semantics that have passed admission/conformance gating can constitute O*.
    """

    ontology_id: str
    canonical_triples: tuple[str, ...]
    semantic_version: str = "v26.9.16"
    provenance_hash: str = ""
    metadata: tuple[tuple[str, str], ...] = ()

    def canonical_digest(self) -> str:
        """Deterministic digest of the admitted semantics O*."""
        norm_triples = sorted(self.canonical_triples)
        norm_meta = sorted(self.metadata)
        repr_obj = {
            "ontology_id": self.ontology_id,
            "semantic_version": self.semantic_version,
            "provenance_hash": self.provenance_hash,
            "triples": norm_triples,
            "metadata": norm_meta,
        }
        return compute_digest(repr_obj)


@dataclass(frozen=True, slots=True)
class ConstructionReceipt:
    r"""Cryptographic receipt binding the construction relation A = \mu(O*).

    Binds:
      - admitted_input_digest: Digest of O*
      - manufacturer_identity: Identity of \mu manufacturer
      - manufacturer_version: Version of \mu manufacturer
      - target_profile: Target projection profile (TargetProfile)
      - output_artifact_digest: Digest of manufactured artifact A
      - receipt_id: Digest over all above parameters
    """

    admitted_input_digest: str
    manufacturer_identity: str
    manufacturer_version: str
    target_profile: TargetProfile
    output_artifact_digest: str
    receipt_id: str

    @classmethod
    def create(
        cls,
        *,
        admitted_input_digest: str,
        manufacturer_identity: str,
        manufacturer_version: str,
        target_profile: TargetProfile,
        output_artifact_digest: str,
    ) -> ConstructionReceipt:
        payload = {
            "admitted_input_digest": admitted_input_digest,
            "manufacturer_identity": manufacturer_identity,
            "manufacturer_version": manufacturer_version,
            "target_profile": target_profile.value,
            "output_artifact_digest": output_artifact_digest,
        }
        receipt_id = compute_digest(payload)
        return cls(
            admitted_input_digest=admitted_input_digest,
            manufacturer_identity=manufacturer_identity,
            manufacturer_version=manufacturer_version,
            target_profile=target_profile,
            output_artifact_digest=output_artifact_digest,
            receipt_id=receipt_id,
        )

    def verify(
        self, semantics: AdmittedSemantics, artifact: ExecutableArtifact
    ) -> bool:
        """Verify that this receipt strictly binds the given O* and manufactured artifact."""
        if self.admitted_input_digest != semantics.canonical_digest():
            return False
        if self.output_artifact_digest != artifact.artifact_digest:
            return False
        if self.target_profile != artifact.target_profile:
            return False
        expected_id = compute_digest(
            {
                "admitted_input_digest": self.admitted_input_digest,
                "manufacturer_identity": self.manufacturer_identity,
                "manufacturer_version": self.manufacturer_version,
                "target_profile": self.target_profile.value,
                "output_artifact_digest": self.output_artifact_digest,
            }
        )
        return self.receipt_id == expected_id


@dataclass(frozen=True, slots=True)
class ExecutableArtifact:
    """Manufactured executable projection A from O*.

    Generated code retains NO independent semantic authority.
    """

    target_profile: TargetProfile
    source_code: str
    entrypoint: str
    artifact_digest: str
    receipt: ConstructionReceipt
    metadata: tuple[tuple[str, str], ...] = ()


class ArtifactManufacturer:
    """Manufacturer \\mu implementing A = \\mu(O*) (§5, §26).

    Transforms admitted semantics O* into deterministic executable projections.
    """

    def __init__(
        self,
        *,
        manufacturer_identity: str = "urn:autofde:sa2a:constructor",
        manufacturer_version: str = "26.9.16",
    ) -> None:
        self.manufacturer_identity = manufacturer_identity
        self.manufacturer_version = manufacturer_version

    def manufacture(
        self,
        admitted: AdmittedSemantics,
        target_profile: TargetProfile = TargetProfile.PYTHON_EPHEMERAL,
        *,
        custom_renderer: Callable[[AdmittedSemantics], tuple[str, str]] | None = None,
    ) -> ExecutableArtifact:
        """Execute construction relation A = \\mu(O*).

        Generates deterministic source code and binds a ConstructionReceipt.
        """
        input_digest = admitted.canonical_digest()

        if custom_renderer is not None:
            source_code, entrypoint = custom_renderer(admitted)
        else:
            source_code, entrypoint = self._default_render(admitted, target_profile)

        output_digest = compute_digest(source_code)

        receipt = ConstructionReceipt.create(
            admitted_input_digest=input_digest,
            manufacturer_identity=self.manufacturer_identity,
            manufacturer_version=self.manufacturer_version,
            target_profile=target_profile,
            output_artifact_digest=output_digest,
        )

        return ExecutableArtifact(
            target_profile=target_profile,
            source_code=source_code,
            entrypoint=entrypoint,
            artifact_digest=output_digest,
            receipt=receipt,
            metadata=(
                ("ontology_id", admitted.ontology_id),
                ("semantic_version", admitted.semantic_version),
            ),
        )

    def _default_render(
        self, admitted: AdmittedSemantics, target: TargetProfile
    ) -> tuple[str, str]:
        triples_repr = json.dumps(sorted(admitted.canonical_triples), indent=4)
        input_digest = admitted.canonical_digest()

        if target == TargetProfile.PYTHON_EPHEMERAL:
            source = (
                f"# Ephemeral projection generated by {self.manufacturer_identity} v{self.manufacturer_version}\n"
                f"# Canonical Input Digest: {input_digest}\n"
                f"# Generated Code != Semantic Truth; canonical authority resides strictly in O*.\n\n"
                f"CANONICAL_TRIPLES = {triples_repr}\n"
                f'CANONICAL_INPUT_DIGEST = "{input_digest}"\n\n'
                f"def run(inputs=None):\n"
                f'    """Execute projection against inputs using canonical triple rules."""\n'
                f"    return {{\n"
                f"        'status': 'ALIVE',\n"
                f"        'digest': CANONICAL_INPUT_DIGEST,\n"
                f"        'triples_count': len(CANONICAL_TRIPLES),\n"
                f"        'inputs': inputs,\n"
                f"    }}\n"
            )
            return source, "run"

        elif target == TargetProfile.JSON_SCHEMA:
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": f"Ephemeral Schema from {admitted.ontology_id}",
                "type": "object",
                "properties": {
                    "admitted_digest": {"const": input_digest},
                    "triples": {
                        "type": "array",
                        "default": sorted(admitted.canonical_triples),
                    },
                },
                "required": ["admitted_digest"],
            }
            return json.dumps(schema, indent=2, sort_keys=True), "validate"

        elif target == TargetProfile.BASH_DISPATCH:
            source = (
                f"#!/usr/bin/env bash\n"
                f"# Ephemeral bash dispatch generated from {input_digest}\n"
                f"echo 'EXECUTING_EPHEMERAL_PROJECTION {input_digest}'\n"
            )
            return source, "main"

        elif target == TargetProfile.BEAM_ATOMVM:
            source = (
                f"%% Ephemeral AtomVM Erlang module\n"
                f"-module(ephemeral_projection).\n"
                f"-export([run/0, digest/0]).\n\n"
                f'digest() -> <<"{input_digest}">>.\n'
                f"run() -> {{alive, {len(admitted.canonical_triples)}}}.\n"
            )
            return source, "run"

        else:
            source = (
                f'// Projection for {target.value}\nconst DIGEST = "{input_digest}";\n'
            )
            return source, "default"
