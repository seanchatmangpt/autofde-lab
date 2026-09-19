"""Immutable GALL-005 cross-repository composition identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_CHECKPOINTS = ("GALL-001", "GALL-002", "GALL-003", "GALL-004")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


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
class GALLCompositionManifest:
    schema: str
    receipts: tuple[ReceiptReference, ...]
    autofde_lab_sha: str
    planner_identity: str
    cmca_identity: str
    machine_experience_compiler_identity: str
    corpus_identity: str
    semantic_key: str

    @property
    def digest(self) -> str:
        payload = {
            "schema": self.schema,
            "receipts": [
                asdict(ref)
                for ref in sorted(self.receipts, key=lambda item: item.checkpoint)
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
        if len({ref.repository for ref in self.receipts}) != len(self.receipts):
            raise ValueError("each GALL checkpoint must be owned by a distinct repository")
        for ref in self.receipts:
            if not ref.repo_sha or not ref.receipt_digest.startswith("sha256:"):
                raise ValueError(f"invalid receipt reference: {ref}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipts": [asdict(ref) for ref in self.receipts],
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
        )
        manifest.validate_shape()
        claimed = payload.get("composition_digest")
        if claimed is not None and claimed != manifest.digest:
            raise ValueError(
                f"composition digest mismatch: claimed {claimed}, observed {manifest.digest}"
            )
        return manifest
