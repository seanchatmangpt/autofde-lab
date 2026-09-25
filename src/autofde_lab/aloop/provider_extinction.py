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

__all__ = ["ExecutionSemantics", "ProviderExtinctionResult", "compare_provider_substitution"]

def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

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
        return "sha256:" + hashlib.sha256(_canonical(self.semantic_projection())).hexdigest()

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

def compare_provider_substitution(before: ExecutionSemantics, after: ExecutionSemantics) -> ProviderExtinctionResult:
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
