"""Fail-closed admission of GALL-001..004 raw receipt artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .composition import ReceiptReference

EXPECTED_REPOSITORIES = {
    "GALL-001": "seanchatmangpt/ggen",
    "GALL-002": "seanchatmangpt/ggen_igniter",
    "GALL-003": "seanchatmangpt/ash_a2a",
    "GALL-004": "seanchatmangpt/beam4pm",
}


@dataclass(frozen=True, slots=True)
class AdmittedReceipt:
    checkpoint: str
    repository: str
    repo_sha: str
    receipt_digest: str
    standing: str
    semantic_subject_digest: str | None
    payload: dict[str, Any]


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{field} must be sha256:<64hex>, got {value!r}")
    int(value[7:], 16)
    return value


def _checkpoint_001(payload: dict[str, Any]) -> tuple[str, str | None]:
    if payload.get("standing") != "ALIVE":
        raise ValueError("GALL-001 requires standing ALIVE")
    replay = payload.get("replay")
    if not isinstance(replay, dict) or replay.get("status") != "PASS":
        raise ValueError("GALL-001 requires observed replay.status=PASS")
    subject = payload.get("subject")
    if not isinstance(subject, dict):
        raise ValueError("GALL-001 subject missing")
    pack_digest = _require_sha256(subject.get("pack_digest"), "subject.pack_digest")
    return "ALIVE", pack_digest


def _checkpoint_002(payload: dict[str, Any]) -> tuple[str, str | None]:
    standing = payload.get("standing")
    if standing != "ALIVE":
        raise ValueError("GALL-002 requires standing ALIVE")
    manufacturer = _require_sha256(
        payload.get("manufacturer_digest"), "manufacturer_digest"
    )
    _require_sha256(payload.get("projection_digest"), "projection_digest")
    return "ALIVE", manufacturer


def _checkpoint_003(payload: dict[str, Any]) -> tuple[str, str | None]:
    standing = payload.get("standing")
    if standing not in {"ALIVE", "PARTIAL_ALIVE"}:
        raise ValueError("GALL-003 standing must be ALIVE or PARTIAL_ALIVE")
    _require_sha256(payload.get("handoff_digest"), "handoff_digest")
    semantic = payload.get("semantic_subject")
    if not isinstance(semantic, dict):
        raise ValueError("GALL-003 semantic_subject missing")
    subject_digest = _require_sha256(
        semantic.get("manufacturer_digest"), "semantic_subject.manufacturer_digest"
    )
    if payload.get("consequence") not in {"change", "external_do"}:
        raise ValueError("GALL-003 receipt is not consequence-bearing")
    return str(standing), subject_digest


def _checkpoint_004(payload: dict[str, Any]) -> tuple[str, str | None]:
    if payload.get("standing") != "ALIVE":
        raise ValueError("GALL-004 requires independent observer standing ALIVE")
    source = payload.get("post_state_source")
    if source in {None, "actuator_reply", "command_bus_reply"}:
        raise ValueError("GALL-004 post-state is not independent")
    if payload.get("occurrence_count") != 1:
        raise ValueError("GALL-004 requires exactly one observed consequence")
    _require_sha256(payload.get("observer_receipt_digest"), "observer_receipt_digest")
    subject = payload.get("semantic_subject_digest")
    if subject is not None:
        _require_sha256(subject, "semantic_subject_digest")
    return "ALIVE", subject


_VALIDATORS = {
    "GALL-001": _checkpoint_001,
    "GALL-002": _checkpoint_002,
    "GALL-003": _checkpoint_003,
    "GALL-004": _checkpoint_004,
}


def admit_receipt(reference: ReceiptReference) -> AdmittedReceipt:
    expected_repo = EXPECTED_REPOSITORIES.get(reference.checkpoint)
    if expected_repo is None:
        raise ValueError(f"unsupported checkpoint {reference.checkpoint}")
    if reference.repository != expected_repo:
        raise ValueError(
            f"{reference.checkpoint} repository mismatch: "
            f"expected {expected_repo}, got {reference.repository}"
        )

    raw = Path(reference.path).read_bytes()
    observed_digest = _digest(raw)
    if observed_digest != reference.receipt_digest:
        raise ValueError(
            f"{reference.checkpoint} receipt digest mismatch: "
            f"expected {reference.receipt_digest}, got {observed_digest}"
        )

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{reference.checkpoint} receipt must be a JSON object")

    standing, semantic_subject_digest = _VALIDATORS[reference.checkpoint](payload)
    return AdmittedReceipt(
        checkpoint=reference.checkpoint,
        repository=reference.repository,
        repo_sha=reference.repo_sha,
        receipt_digest=reference.receipt_digest,
        standing=standing,
        semantic_subject_digest=semantic_subject_digest,
        payload=payload,
    )
