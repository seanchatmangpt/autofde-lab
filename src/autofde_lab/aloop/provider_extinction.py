# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Provider-extinction semantic court for autonomous-loop execution.

A provider is disposable capacity. Replacing it may change provider/run identity,
but it must not change admitted work, authority, exact subject, consequence,
or verification contract. The court is authority-free and never performs DO.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping

__all__ = [
    "ExecutionSemantics",
    "ProviderExtinctionResult",
    "ArtifactHandoff",
    "FailureInjection",
    "RecoveryQualification",
    "compare_provider_substitution",
    "qualify_fresh_job_recovery",
]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


@dataclass(frozen=True)
class ExecutionSemantics:
    """Provider-independent semantic identity plus provider-local observation."""

    workorder_digest: str
    command_digest: str
    candidate_digest: str
    exact_subject_sha: str
    authority_digest: str
    consequence_key: str
    verification_digest: str
    provider: str
    run_id: str

    def semantic_projection(self) -> Mapping[str, str]:
        value = asdict(self)
        value.pop("provider")
        value.pop("run_id")
        return value

    @property
    def semantic_digest(self) -> str:
        return (
            "sha256:"
            + hashlib.sha256(_canonical(self.semantic_projection())).hexdigest()
        )


@dataclass(frozen=True)
class ProviderExtinctionResult:
    qualified: bool
    before_provider: str
    after_provider: str
    before_semantic_digest: str
    after_semantic_digest: str
    changed_fields: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def verdict(self) -> str:
        return "QUALIFIED" if self.qualified else "NOT_QUALIFIED"


def compare_provider_substitution(
    before: ExecutionSemantics, after: ExecutionSemantics
) -> ProviderExtinctionResult:
    """Require provider replacement while conserving execution semantics."""
    left = before.semantic_projection()
    right = after.semantic_projection()
    changed = tuple(sorted(key for key in left if left[key] != right[key]))
    reasons: list[str] = []
    if before.provider == after.provider:
        reasons.append("PROVIDER_NOT_REPLACED")
    if before.run_id == after.run_id:
        reasons.append("RUN_ID_REUSED_ACROSS_PROVIDER_REPLACEMENT")
    if changed:
        reasons.extend(f"SEMANTIC_DRIFT:{field}" for field in changed)
    return ProviderExtinctionResult(
        qualified=not reasons,
        before_provider=before.provider,
        after_provider=after.provider,
        before_semantic_digest=before.semantic_digest,
        after_semantic_digest=after.semantic_digest,
        changed_fields=changed,
        reasons=tuple(reasons),
    )



@dataclass(frozen=True)
class ArtifactHandoff:
    """Content-addressed artifact handoff across provider/run boundaries.

    Locators are observations only. They are intentionally excluded from the
    content digest so a workstation path can never become artifact identity.
    """

    artifact_digest: str
    manifest_digest: str
    producer_digest: str
    source_provider: str
    source_run_id: str
    target_provider: str
    target_run_id: str
    source_locator: str | None = None
    target_locator: str | None = None

    def content_projection(self) -> Mapping[str, str]:
        return {
            "artifact_digest": self.artifact_digest,
            "manifest_digest": self.manifest_digest,
            "producer_digest": self.producer_digest,
        }

    @property
    def content_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            _canonical(self.content_projection())
        ).hexdigest()


@dataclass(frozen=True)
class FailureInjection:
    """Reusable, deterministic provider-loss stimulus."""

    injection_id: str
    kind: str
    failed_provider: str
    failed_run_id: str

    def __post_init__(self) -> None:
        if self.kind not in {"CRASH", "LEASE_LOSS", "PROVIDER_EXTINCTION"}:
            raise ValueError(f"unsupported failure injection kind {self.kind!r}")


@dataclass(frozen=True)
class RecoveryQualification:
    qualified: bool
    substitution: ProviderExtinctionResult
    handoff_content_digest: str
    injection_id: str
    reasons: tuple[str, ...]

    @property
    def verdict(self) -> str:
        return "QUALIFIED" if self.qualified else "NOT_QUALIFIED"


def _is_sha256(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    payload = value[7:]
    return len(payload) == 64 and all(
        ch in "0123456789abcdef" for ch in payload.lower()
    )


def qualify_fresh_job_recovery(
    before: ExecutionSemantics,
    after: ExecutionSemantics,
    *,
    handoff: ArtifactHandoff,
    failure: FailureInjection,
) -> RecoveryQualification:
    """Qualify provider-loss recovery with content-addressed fresh-job handoff.

    The function has no actuation edge. It only admits or rejects evidence that
    a fresh provider/run consumed the same candidate artifact under conserved
    work, authority, consequence, and verification semantics.
    """

    substitution = compare_provider_substitution(before, after)
    reasons = list(substitution.reasons)

    for name, value in handoff.content_projection().items():
        if not _is_sha256(value):
            reasons.append(f"INVALID_CONTENT_DIGEST:{name}")

    if failure.failed_provider != before.provider:
        reasons.append("FAILURE_PROVIDER_MISMATCH")
    if failure.failed_run_id != before.run_id:
        reasons.append("FAILURE_RUN_MISMATCH")

    if handoff.source_provider != before.provider:
        reasons.append("HANDOFF_SOURCE_PROVIDER_MISMATCH")
    if handoff.source_run_id != before.run_id:
        reasons.append("HANDOFF_SOURCE_RUN_MISMATCH")
    if handoff.target_provider != after.provider:
        reasons.append("HANDOFF_TARGET_PROVIDER_MISMATCH")
    if handoff.target_run_id != after.run_id:
        reasons.append("HANDOFF_TARGET_RUN_MISMATCH")

    if before.candidate_digest != handoff.artifact_digest:
        reasons.append("SOURCE_ARTIFACT_IDENTITY_MISMATCH")
    if after.candidate_digest != handoff.artifact_digest:
        reasons.append("TARGET_ARTIFACT_IDENTITY_MISMATCH")

    locators = (handoff.source_locator, handoff.target_locator)
    if any(
        locator is not None
        and locator in {
            handoff.artifact_digest,
            handoff.manifest_digest,
            handoff.producer_digest,
        }
        for locator in locators
    ):
        reasons.append("WORKSTATION_LOCATOR_USED_AS_IDENTITY")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return RecoveryQualification(
        qualified=not unique_reasons,
        substitution=substitution,
        handoff_content_digest=handoff.content_digest,
        injection_id=failure.injection_id,
        reasons=unique_reasons,
    )
