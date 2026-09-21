"""Typed GALL-021..030 cross-repository process-intelligence composition."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

CHECKPOINT_REPOSITORIES = {
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
CHECKPOINT_CEILINGS = {
    "GALL-021": frozenset({"COMPUTE_ONLY", "COMPILE_COMPUTE", "QUERY_COMPUTE"}),
    "GALL-022": frozenset({"COMPUTE_ONLY", "COMPILE_COMPUTE", "QUERY_COMPUTE"}),
    "GALL-023": frozenset({"COMPUTE_ONLY", "COMPILE_COMPUTE", "QUERY_COMPUTE"}),
    "GALL-024": frozenset({"OBSERVE"}),
    "GALL-025": frozenset({"COMPARE"}),
    "GALL-026": frozenset({"ANALYZE"}),
    "GALL-027": frozenset({"OBSERVE_ACCOUNT"}),
    "GALL-028": frozenset({"RECOMMEND"}),
    "GALL-029": frozenset({"ADMIT_ONLY", "CANDIDATE"}),
    "GALL-030": frozenset({"AUTHORIZED_DO"}),
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
            if item.evidence_ceiling not in CHECKPOINT_CEILINGS[checkpoint]:
                raise ValueError(
                    f"{checkpoint} evidence ceiling {item.evidence_ceiling!r} exceeds its authority boundary"
                )

    def verify_exact_evidence(self, evidence: Mapping[str, bytes]) -> None:
        """Bind every manifest entry to independently hashed canonical evidence.

        Evidence is JSON and must name the exact checkpoint, repository, producer
        SHA, subject digest and authority ceiling represented by the manifest.
        GALL-030 additionally requires an explicit independent-authority witness
        and CommandBus-only route. Evidence is still evidence: this method does
        not execute a producer or manufacture cross-repository standing.
        """
        self.validate()
        by_id = {item.checkpoint: item for item in self.checkpoints}
        if set(evidence) != set(REQUIRED):
            raise ValueError("exact evidence requires one receipt for every GALL-021..030 checkpoint")

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
