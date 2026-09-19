"""Portable GALL composition artifact for fresh deterministic consumers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from autofde_lab.sa2a.composition.exact_subject import ExactSubject

SCHEMA = "https://autofde.dev/gall/composition/v1"
REQUIRED_CHECKPOINTS = ("GALL-001", "GALL-002", "GALL-003", "GALL-004")


@dataclass(frozen=True, slots=True)
class GallArtifactError(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def build_portable_artifact(subject: ExactSubject, *, standing: str) -> dict[str, Any]:
    """Project one ExactSubject into a self-verifying, non-actuating artifact."""
    checkpoints = [
        {
            "checkpoint_id": c.checkpoint_id,
            "repository": c.repository,
            "exact_sha": c.exact_sha,
            "receipt_digest": c.receipt_digest if c.receipt_digest.startswith("sha256:") else "sha256:" + c.receipt_digest,
            "standing": c.standing,
            "evidence_class": c.evidence_class,
            "work_order_digest": c.work_order_digest,
        }
        for c in sorted(subject.checkpoints, key=lambda item: item.checkpoint_id)
    ]
    ids = {c['checkpoint_id'] for c in checkpoints}
    missing = [checkpoint for checkpoint in REQUIRED_CHECKPOINTS if checkpoint not in ids]
    if missing:
        raise GallArtifactError("REFUSED_MISSING_GALL_CHECKPOINT", f"missing {missing!r}")

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "release_id": subject.release_id,
        "composition_digest": subject.composition_digest,
        "work_order_digest": subject.work_order_digest,
        "standing": standing,
        "authority": "none",
        "checkpoints": checkpoints,
    }
    payload["artifact_digest"] = _sha256(payload)
    return payload


def verify_portable_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    """Verify integrity/shape without executing or re-actuating any producer."""
    payload = dict(value)
    recorded = str(payload.pop("artifact_digest", ""))
    if payload.get('schema') != SCHEMA:
        raise GallArtifactError("REFUSED_ARTIFACT_SCHEMA", "unsupported or missing schema")
    observed = _sha256(payload)
    if recorded != observed:
        raise GallArtifactError("REFUSED_ARTIFACT_DIGEST", f"expected {recorded!r}, observed {observed!r}")

    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list):
        raise GallArtifactError("REFUSED_ARTIFACT_SHAPE", "checkpoints must be a list")
    by_id: dict[str, Mapping[str, Any]] = {}
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping):
            raise GallArtifactError("REFUSED_ARTIFACT_SHAPE", "checkpoint must be an object")
        checkpoint_id = str(checkpoint.get("checkpoint_id", ""))
        if checkpoint_id in by_id:
            raise GallArtifactError("REFUSED_ARTIFACT_SHAPE", f"duplicate checkpoint {checkpoint_id!r}")
        by_id[checkpoint_id] = checkpoint
    missing = [checkpoint for checkpoint in REQUIRED_CHECKPOINTS if checkpoint not in by_id]
    if missing:
        raise GallArtifactError("REFUSED_MISSING_GALL_CHECKPOINT", f"missing {missing!r}")

    return {
        "schema": SCHEMA,
        "artifact_digest": recorded,
        "composition_digest": payload.get("composition_digest"),
        "work_order_digest": payload.get("work_order_digest"),
        "standing": payload.get("standing"),
        "authority": "none",
        "checkpoint_ids": tuple(REQUIRED_CHECKPOINTS),
    }
