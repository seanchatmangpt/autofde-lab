"""Typed identities for provenance-bound collective-skill evaluation courts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_CONTENT_DIGEST = re.compile(r"^(?:sha256|blake3):[0-9a-f]{64}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")

ProbeKind = Literal["oracle", "noop", "mutation"]


def _require_text(name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} is required")


def _require_sha(name: str, value: str) -> None:
    if not _GIT_SHA.fullmatch(value):
        raise ValueError(f"{name} must be an exact 40-hex git SHA")


def _require_digest(name: str, value: str) -> None:
    if not _CONTENT_DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be a sha256: or blake3: content digest")


@dataclass(frozen=True, slots=True)
class MarketplacePackRef:
    repository: str
    commit_sha: str
    pack_name: str
    pack_version: str
    pack_source_digest: str

    def validate(self) -> None:
        _require_text("marketplace.repository", self.repository)
        _require_sha("marketplace.commit_sha", self.commit_sha)
        _require_text("marketplace.pack_name", self.pack_name)
        if not _SEMVER.fullmatch(self.pack_version):
            raise ValueError("marketplace.pack_version must be x.y.z SemVer")
        _require_digest("marketplace.pack_source_digest", self.pack_source_digest)

    @property
    def identity(self) -> str:
        return (
            f"{self.repository}@{self.commit_sha}:{self.pack_name}@{self.pack_version}"
        )


@dataclass(frozen=True, slots=True)
class SkillSource:
    source_id: str
    source_kind: str
    provenance_uri: str
    source_digest: str

    def validate(self) -> None:
        _require_text("source.source_id", self.source_id)
        _require_text("source.source_kind", self.source_kind)
        _require_text("source.provenance_uri", self.provenance_uri)
        _require_digest("source.source_digest", self.source_digest)


@dataclass(frozen=True, slots=True)
class SjiraWorkOrderRef:
    identity: str
    repository: str
    base_sha: str
    evidence_ceiling: str
    authority_ceiling: str

    def validate(self) -> None:
        _require_text("work_order.identity", self.identity)
        _require_text("work_order.repository", self.repository)
        _require_sha("work_order.base_sha", self.base_sha)
        _require_text("work_order.evidence_ceiling", self.evidence_ceiling)
        _require_text("work_order.authority_ceiling", self.authority_ceiling)


@dataclass(frozen=True, slots=True)
class ProbeObservation:
    probe_id: str
    kind: ProbeKind
    observed_success: bool
    evidence_digest: str

    def validate(self) -> None:
        _require_text("probe.probe_id", self.probe_id)
        if self.kind not in {"oracle", "noop", "mutation"}:
            raise ValueError(f"unsupported probe kind: {self.kind!r}")
        _require_digest("probe.evidence_digest", self.evidence_digest)


@dataclass(frozen=True, slots=True)
class CourtSpec:
    court_id: str
    semantic_class_id: str
    source: SkillSource
    marketplace: MarketplacePackRef
    work_order: SjiraWorkOrderRef
    exact_subject_sha: str
    oracle: ProbeObservation
    noop: ProbeObservation
    mutations: tuple[ProbeObservation, ...]

    def validate(self) -> None:
        _require_text("court_id", self.court_id)
        _require_text("semantic_class_id", self.semantic_class_id)
        _require_sha("exact_subject_sha", self.exact_subject_sha)
        self.source.validate()
        self.marketplace.validate()
        self.work_order.validate()
        self.oracle.validate()
        self.noop.validate()
        if self.oracle.kind != "oracle":
            raise ValueError("oracle observation must have kind=oracle")
        if self.noop.kind != "noop":
            raise ValueError("noop observation must have kind=noop")
        if not self.mutations:
            raise ValueError("at least one mutation probe is required")
        for mutation in self.mutations:
            mutation.validate()
            if mutation.kind != "mutation":
                raise ValueError("mutation observations must have kind=mutation")
        probe_ids = [self.oracle.probe_id, self.noop.probe_id]
        probe_ids.extend(item.probe_id for item in self.mutations)
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("probe identities must be unique")

    @property
    def digest(self) -> str:
        self.validate()
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CourtAdmissionReceipt:
    receipt_id: str
    court_digest: str
    admitted: bool
    standing: Literal["ADMITTED", "REFUSED"]
    reasons: tuple[str, ...]
    authority: Literal["none"] = "none"

    @property
    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
