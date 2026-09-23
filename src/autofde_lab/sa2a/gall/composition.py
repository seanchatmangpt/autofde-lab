"""Immutable GALL-005 cross-repository composition identity."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_CHECKPOINTS = ("GALL-001", "GALL-002", "GALL-003", "GALL-004")
REQUIRED_REPOSITORIES = {
    "GALL-001": "seanchatmangpt/ggen",
    "GALL-002": "seanchatmangpt/ggen_igniter",
    "GALL-003": "seanchatmangpt/ash_a2a",
    "GALL-004": "seanchatmangpt/beam4pm",
}
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _validate_reference_identity(
    *, label: str, repository: str, repo_sha: str, digest: str
) -> None:
    if not repository:
        raise ValueError(f"{label} repository is required")
    if not _GIT_SHA.fullmatch(repo_sha):
        raise ValueError(f"{label} repo_sha must be an exact 40-hex commit SHA")
    if not _SHA256.fullmatch(digest):
        raise ValueError(f"{label} digest must be sha256:<64hex>")


@dataclass(frozen=True, slots=True)
class ReceiptReference:
    checkpoint: str
    repository: str
    repo_sha: str
    path: str
    receipt_digest: str

    @classmethod
    def from_path(
        cls,
        *,
        checkpoint: str,
        repository: str,
        repo_sha: str,
        path: str | Path,
    ) -> "ReceiptReference":
        raw = Path(path).read_bytes()
        return cls(
            checkpoint=checkpoint,
            repository=repository,
            repo_sha=repo_sha,
            path=str(path),
            receipt_digest=_sha256(raw),
        )


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Exact supporting evidence that is not itself a GALL checkpoint receipt.

    GALL-004 intentionally has more than one proposition. Its independent
    observer receipt proves process/postcondition evidence, while the stacked
    Weaver court proves telemetry semantics. Keeping the latter here prevents
    those predicates from being collapsed into one checkpoint boolean.
    """

    evidence_class: str
    repository: str
    repo_sha: str
    path: str
    receipt_digest: str

    @classmethod
    def from_path(
        cls,
        *,
        evidence_class: str,
        repository: str,
        repo_sha: str,
        path: str | Path,
    ) -> "EvidenceReference":
        raw = Path(path).read_bytes()
        return cls(
            evidence_class=evidence_class,
            repository=repository,
            repo_sha=repo_sha,
            path=str(path),
            receipt_digest=_sha256(raw),
        )


@dataclass(frozen=True, slots=True)
class GALLCompositionManifest:
    schema: str
    receipts: tuple[ReceiptReference, ...]
    autofde_lab_sha: str
    planner_identity: str
    cmca_identity: str
    machine_experience_compiler_identity: str
    corpus_identity: str
    semantic_key: str
    evidence: tuple[EvidenceReference, ...] = ()

    @property
    def digest(self) -> str:
        payload = {
            "schema": self.schema,
            "receipts": [
                asdict(ref)
                for ref in sorted(self.receipts, key=lambda item: item.checkpoint)
            ],
            "evidence": [
                asdict(ref)
                for ref in sorted(self.evidence, key=lambda item: item.evidence_class)
            ],
            "autofde_lab_sha": self.autofde_lab_sha,
            "planner_identity": self.planner_identity,
            "cmca_identity": self.cmca_identity,
            "machine_experience_compiler_identity": self.machine_experience_compiler_identity,
            "corpus_identity": self.corpus_identity,
            "semantic_key": self.semantic_key,
        }
        return _sha256(_canonical(payload))

    def validate_shape(self) -> None:
        checkpoints = tuple(
            ref.checkpoint
            for ref in sorted(self.receipts, key=lambda item: item.checkpoint)
        )
        if checkpoints != REQUIRED_CHECKPOINTS:
            raise ValueError(
                f"composition requires exactly {REQUIRED_CHECKPOINTS}, got {checkpoints}"
            )

        for ref in self.receipts:
            expected_repo = REQUIRED_REPOSITORIES[ref.checkpoint]
            if ref.repository != expected_repo:
                raise ValueError(
                    f"{ref.checkpoint} repository mismatch: expected {expected_repo}, got {ref.repository}"
                )
            _validate_reference_identity(
                label=ref.checkpoint,
                repository=ref.repository,
                repo_sha=ref.repo_sha,
                digest=ref.receipt_digest,
            )

        evidence_classes = [item.evidence_class for item in self.evidence]
        if len(evidence_classes) != len(set(evidence_classes)):
            raise ValueError("supporting evidence classes must be unique")
        for item in self.evidence:
            _validate_reference_identity(
                label=item.evidence_class,
                repository=item.repository,
                repo_sha=item.repo_sha,
                digest=item.receipt_digest,
            )

        if not _GIT_SHA.fullmatch(self.autofde_lab_sha):
            raise ValueError("autofde_lab_sha must be an exact 40-hex commit SHA")
        if not _SHA256.fullmatch(self.corpus_identity):
            raise ValueError("corpus_identity must be sha256:<64hex>")
        for field, value in (
            ("planner_identity", self.planner_identity),
            ("cmca_identity", self.cmca_identity),
            (
                "machine_experience_compiler_identity",
                self.machine_experience_compiler_identity,
            ),
            ("semantic_key", self.semantic_key),
        ):
            if not value:
                raise ValueError(f"{field} is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipts": [asdict(ref) for ref in self.receipts],
            "evidence": [asdict(ref) for ref in self.evidence],
            "autofde_lab_sha": self.autofde_lab_sha,
            "planner_identity": self.planner_identity,
            "cmca_identity": self.cmca_identity,
            "machine_experience_compiler_identity": self.machine_experience_compiler_identity,
            "corpus_identity": self.corpus_identity,
            "semantic_key": self.semantic_key,
            "composition_digest": self.digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GALLCompositionManifest":
        manifest = cls(
            schema=str(payload["schema"]),
            receipts=tuple(
                ReceiptReference(
                    checkpoint=str(item["checkpoint"]),
                    repository=str(item["repository"]),
                    repo_sha=str(item["repo_sha"]),
                    path=str(item["path"]),
                    receipt_digest=str(item["receipt_digest"]),
                )
                for item in payload["receipts"]
            ),
            autofde_lab_sha=str(payload["autofde_lab_sha"]),
            planner_identity=str(payload["planner_identity"]),
            cmca_identity=str(payload["cmca_identity"]),
            machine_experience_compiler_identity=str(
                payload["machine_experience_compiler_identity"]
            ),
            corpus_identity=str(payload["corpus_identity"]),
            semantic_key=str(payload["semantic_key"]),
            evidence=tuple(
                EvidenceReference(
                    evidence_class=str(item["evidence_class"]),
                    repository=str(item["repository"]),
                    repo_sha=str(item["repo_sha"]),
                    path=str(item["path"]),
                    receipt_digest=str(item["receipt_digest"]),
                )
                for item in payload.get("evidence", ())
            ),
        )
        manifest.validate_shape()
        claimed = payload.get("composition_digest")
        if claimed is not None and claimed != manifest.digest:
            raise ValueError(
                f"composition digest mismatch: claimed {claimed}, observed {manifest.digest}"
            )
        return manifest
