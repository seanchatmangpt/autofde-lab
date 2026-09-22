"""Typed GALL-021..030 cross-repository process-intelligence composition."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

CHECKPOINT_REPOSITORIES = {
    "GALL-015": "seanchatmangpt/ex4pm",
    "GALL-016": "seanchatmangpt/ex4pm",
    "GALL-017": "seanchatmangpt/ex4pm",
    "GALL-018": "seanchatmangpt/ex4pm",
    "GALL-019": "seanchatmangpt/ex4pm",
    "GALL-020": "seanchatmangpt/ex4pm",
    "GALL-021": "seanchatmangpt/wasm4pm",
    "GALL-022": "seanchatmangpt/wasm4pm",
    "GALL-023": "seanchatmangpt/wasm4pm",
    "GALL-024": "seanchatmangpt/beam4pm",
    "GALL-025": "seanchatmangpt/beam4pm",
    "GALL-026": "seanchatmangpt/beam4pm",
    "GALL-027": "seanchatmangpt/beam4pm",
    "GALL-028": "seanchatmangpt/beam4pm",
    "GALL-029": "seanchatmangpt/ash_a2a",
    "GALL-030": "seanchatmangpt/ash_a2a",
}
REQUIRED = tuple(CHECKPOINT_REPOSITORIES)
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^(?:sha256|blake3):[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ProcessCheckpointReference:
    checkpoint: str
    repository: str
    repo_sha: str
    evidence_digest: str
    subject_digest: str
    evidence_ceiling: str


@dataclass(frozen=True, slots=True)
class ProcessSpine:
    schema: str
    checkpoints: tuple[ProcessCheckpointReference, ...]

    def validate(self) -> None:
        by_id = {item.checkpoint: item for item in self.checkpoints}
        if tuple(sorted(by_id)) != tuple(sorted(REQUIRED)):
            raise ValueError(f"process spine requires exactly {REQUIRED}")
        if len(by_id) != len(self.checkpoints):
            raise ValueError("process spine checkpoint identities must be unique")

        for checkpoint in REQUIRED:
            item = by_id[checkpoint]
            expected_repo = CHECKPOINT_REPOSITORIES[checkpoint]
            if item.repository != expected_repo:
                raise ValueError(
                    f"{checkpoint} repository mismatch: expected {expected_repo}, got {item.repository}"
                )
            if not _GIT_SHA.fullmatch(item.repo_sha):
                raise ValueError(f"{checkpoint} repo_sha must be exact 40-hex")
            if not _DIGEST.fullmatch(item.evidence_digest):
                raise ValueError(f"{checkpoint} evidence_digest must be content-addressed")
            if not _DIGEST.fullmatch(item.subject_digest):
                raise ValueError(f"{checkpoint} subject_digest must be content-addressed")
            if not item.evidence_ceiling:
                raise ValueError(f"{checkpoint} evidence_ceiling is required")

        # Authority conservation: reference/process-compute checkpoints cannot claim DO.
        exact_ex4pm_ceilings = {
            "GALL-015": "REFERENCE_CORPUS",
            "GALL-016": "COMPILE_COMPUTE",
            "GALL-017": "QUERY_COMPUTE",
            "GALL-018": "DISCOVERY_CANDIDATE",
            "GALL-019": "PREDICTION_CANDIDATE",
            "GALL-020": "COMPUTE_ONLY",
        }
        for checkpoint, ceiling in exact_ex4pm_ceilings.items():
            if by_id[checkpoint].evidence_ceiling != ceiling:
                raise ValueError(
                    f"{checkpoint} evidence ceiling must be {ceiling}, "
                    f"got {by_id[checkpoint].evidence_ceiling}"
                )

        for checkpoint in ("GALL-021", "GALL-022", "GALL-023"):
            if by_id[checkpoint].evidence_ceiling not in {"COMPUTE_ONLY", "COMPILE_COMPUTE", "QUERY_COMPUTE"}:
                raise ValueError(f"{checkpoint} exceeded portable compute authority ceiling")
        for checkpoint in ("GALL-024", "GALL-025", "GALL-026", "GALL-027", "GALL-028"):
            if by_id[checkpoint].evidence_ceiling in {"DO", "AUTHORIZED_DO"}:
                raise ValueError(f"{checkpoint} observer evidence cannot grant DO")
        if by_id["GALL-029"].evidence_ceiling not in {"ADMIT_ONLY", "CANDIDATE"}:
            raise ValueError("GALL-029 must remain candidate admission only")
        if by_id["GALL-030"].evidence_ceiling != "AUTHORIZED_DO":
            raise ValueError("GALL-030 is the sole bounded DO checkpoint in this spine")

    def verify_exact_evidence(self, evidence: Mapping[str, bytes]) -> None:
        """Bind every manifest entry to independently hashed canonical evidence.

        Evidence is JSON and must name the exact checkpoint, repository, producer
        SHA, subject digest and authority ceiling represented by the manifest.
        GALL-030 additionally requires an explicit independent-authority witness
        and CommandBus-only route. Evidence is still evidence: this method does
        not execute a producer or manufacture cross-repository standing.
        (Carried over from gall/integrate-021-030-process-spine: strictly
        additive evidence binding on top of this spine's authority model.)
        """
        self.validate()
        by_id = {item.checkpoint: item for item in self.checkpoints}
        if set(evidence) != set(REQUIRED):
            raise ValueError("exact evidence requires one receipt for every GALL-015..030 checkpoint")

        for checkpoint in REQUIRED:
            item = by_id[checkpoint]
            raw = evidence[checkpoint]
            actual = "sha256:" + hashlib.sha256(raw).hexdigest()
            if item.evidence_digest != actual:
                raise ValueError(f"{checkpoint} evidence digest mismatch")

            try:
                receipt = json.loads(raw)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"{checkpoint} evidence must be JSON") from exc
            expected = {
                "checkpoint": checkpoint,
                "repository": item.repository,
                "repo_sha": item.repo_sha,
                "subject_digest": item.subject_digest,
                "evidence_ceiling": item.evidence_ceiling,
            }
            for field, value in expected.items():
                if receipt.get(field) != value:
                    raise ValueError(f"{checkpoint} evidence {field} mismatch")

            if checkpoint != "GALL-030":
                if receipt.get("authority", "NONE") != "NONE":
                    raise ValueError(f"{checkpoint} evidence cannot manufacture authority")
            else:
                if receipt.get("authority_source") != "INDEPENDENT":
                    raise ValueError("GALL-030 requires independently supplied authority")
                if receipt.get("do_route") != "AshA2A.CommandBus":
                    raise ValueError("GALL-030 DO must route only through AshA2A.CommandBus")

    @property
    def digest(self) -> str:
        self.validate()
        payload: dict[str, Any] = {
            "schema": self.schema,
            "checkpoints": [
                asdict(item) for item in sorted(self.checkpoints, key=lambda item: item.checkpoint)
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()
