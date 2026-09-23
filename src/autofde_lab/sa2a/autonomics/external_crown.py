"""GALL-032 external process autonomics composition evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping

_REQUIRED = tuple(f"GALL-{index:03d}" for index in range(1, 32))


@dataclass(frozen=True, slots=True)
class ExternalAutonomicsManifest:
    receipts: Mapping[str, str]
    disturbance_class: str
    process_subject_digest: str
    authority_policy_digest: str
    runtime_identity: str

    def validate(self) -> None:
        missing = [
            checkpoint for checkpoint in _REQUIRED if checkpoint not in self.receipts
        ]
        if missing:
            raise ValueError(f"BLOCKED(missing predecessor receipts: {missing})")
        for checkpoint, digest in self.receipts.items():
            if checkpoint in _REQUIRED and not (
                isinstance(digest, str) and digest.startswith(("sha256:", "blake3:"))
            ):
                raise ValueError(f"invalid predecessor digest for {checkpoint}")

    @property
    def digest(self) -> str:
        self.validate()
        payload = {
            "receipts": dict(sorted(self.receipts.items())),
            "disturbance_class": self.disturbance_class,
            "process_subject_digest": self.process_subject_digest,
            "authority_policy_digest": self.authority_policy_digest,
            "runtime_identity": self.runtime_identity,
        }
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )


@dataclass(frozen=True, slots=True)
class ExternalCrownEvidence:
    manifest_digest: str
    episode_1_disturbance_observed: bool
    episode_1_independent_postcondition: bool
    machine_experience_digest: str | None
    episode_2_fresh_process: bool
    episode_2_frontier_calls: int
    episode_2_llm_allocations: int
    episode_2_planner_calls: int
    episode_2_reflex_executions: int
    episode_2_fresh_authority_receipt: str | None
    episode_2_independent_postcondition: bool

    def qualify_for_affidavit(self) -> dict[str, object]:
        if not self.episode_1_disturbance_observed:
            raise RuntimeError("BLOCKED(episode-1 disturbance not observed)")
        if not self.episode_1_independent_postcondition:
            raise RuntimeError("BLOCKED(episode-1 independent postcondition)")
        if self.machine_experience_digest is None:
            raise RuntimeError("BLOCKED(MachineExperience not compiled)")
        if not self.episode_2_fresh_process:
            raise RuntimeError("REFUSED(episode-2 reuses episode-1 process state)")
        if self.episode_2_frontier_calls != 0 or self.episode_2_llm_allocations != 0:
            raise RuntimeError(
                "REFUSED(KNOWN recurrence repurchased exploratory cognition)"
            )
        if self.episode_2_planner_calls != 0:
            raise RuntimeError("REFUSED(KNOWN reflex still invokes equivalent planner)")
        if self.episode_2_reflex_executions < 1:
            raise RuntimeError("REFUSED(zero-inference-vacuous-no-execution)")
        if self.episode_2_fresh_authority_receipt is None:
            raise RuntimeError("REFUSED(reused-or-missing-authority)")
        if not self.episode_2_independent_postcondition:
            raise RuntimeError("BLOCKED(episode-2 independent postcondition)")
        payload = asdict(self)
        return {
            "schema": "autofde.external-autonomics-evidence/v26.9.18",
            "standing": "EVIDENCE_READY_FOR_AFFIDAVIT",
            "authority": "none",
            "evidence": payload,
        }
