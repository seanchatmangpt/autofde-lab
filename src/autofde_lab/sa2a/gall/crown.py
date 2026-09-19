"""GALL-005 UNKNOWN -> verified MachineExperience -> fresh KNOWN replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler

from .composition import GALLCompositionManifest
from .receipt_admission import AdmittedReceipt, admit_receipt


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class MachineExperienceArtifact:
    schema: str
    semantic_key: str
    deterministic_output: dict[str, Any]
    composition_digest: str
    rule_fingerprint: str
    source_receipts: tuple[str, ...]
    standing: str = "KNOWN"

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifact_digest"] = self.digest
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MachineExperienceArtifact":
        artifact = cls(
            schema=str(payload["schema"]),
            semantic_key=str(payload["semantic_key"]),
            deterministic_output=dict(payload["deterministic_output"]),
            composition_digest=str(payload["composition_digest"]),
            rule_fingerprint=str(payload["rule_fingerprint"]),
            source_receipts=tuple(str(x) for x in payload["source_receipts"]),
            standing=str(payload.get("standing", "KNOWN")),
        )
        claimed = payload.get("artifact_digest")
        if claimed is not None and claimed != artifact.digest:
            raise ValueError(
                f"MachineExperience digest mismatch: claimed {claimed}, observed {artifact.digest}"
            )
        return artifact


@dataclass(frozen=True, slots=True)
class GALLCrownResult:
    composition_digest: str
    admitted_receipts: tuple[str, ...]
    machine_experience_digest: str
    frontier_resolution_calls: int
    llm_allocations: int
    planner_invocations: int
    machine_experience_hits: int
    reflex_executions: int
    gate_11: str
    gate_12: str
    standing: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_cross_repo_subject(receipts: list[AdmittedReceipt]) -> None:
    # GALL-003 must name the same manufacturer subject that GALL-002 emitted.
    manufacturer = next(
        item.semantic_subject_digest
        for item in receipts
        if item.checkpoint == "GALL-002"
    )
    command_subject = next(
        item.semantic_subject_digest
        for item in receipts
        if item.checkpoint == "GALL-003"
    )
    if manufacturer != command_subject:
        raise ValueError(
            "GALL-002 manufacturer and GALL-003 semantic subject do not match"
        )

    # GALL-004 must explicitly consume the GALL-003 handoff digest.
    gall3 = next(item for item in receipts if item.checkpoint == "GALL-003")
    gall4 = next(item for item in receipts if item.checkpoint == "GALL-004")
    if gall4.payload.get("gall_003_receipt_digest") != gall3.payload.get("handoff_digest"):
        raise ValueError("GALL-004 does not bind the admitted GALL-003 handoff")


def compile_verified_experience(
    manifest: GALLCompositionManifest,
    *,
    deterministic_output: dict[str, Any],
) -> tuple[MachineExperienceArtifact, GALLCrownResult]:
    manifest.validate_shape()
    admitted = [admit_receipt(ref) for ref in manifest.receipts]
    _require_cross_repo_subject(admitted)

    compiler = MachineExperienceCompiler()
    compilation = compiler.compile_candidate_experience(
        receipt_id=manifest.digest,
        resolved_items=[
            (
                manifest.semantic_key,
                json.dumps(deterministic_output, sort_keys=True, separators=(",", ":")),
                None,
            )
        ],
    )
    rule = compiler.rules[manifest.semantic_key]

    artifact = MachineExperienceArtifact(
        schema="autofde.gall.machine-experience/v26.9.18",
        semantic_key=manifest.semantic_key,
        deterministic_output=deterministic_output,
        composition_digest=manifest.digest,
        rule_fingerprint=rule.fingerprint,
        source_receipts=tuple(
            item.receipt_digest for item in sorted(admitted, key=lambda x: x.checkpoint)
        ),
    )

    result = GALLCrownResult(
        composition_digest=manifest.digest,
        admitted_receipts=artifact.source_receipts,
        machine_experience_digest=artifact.digest,
        frontier_resolution_calls=1,
        llm_allocations=1,
        planner_invocations=1,
        machine_experience_hits=0,
        reflex_executions=0,
        gate_11="OPEN",
        gate_12="OPEN",
        standing="PARTIAL_ALIVE",
    )
    if compilation.compiled_rule_count != 1:
        raise AssertionError("MachineExperience compiler did not compile exactly one rule")
    return artifact, result


def run_known_replay(
    manifest: GALLCompositionManifest,
    artifact: MachineExperienceArtifact,
    *,
    semantic_key: str,
) -> tuple[dict[str, Any], GALLCrownResult]:
    manifest.validate_shape()
    if artifact.composition_digest != manifest.digest:
        raise ValueError("MachineExperience composition identity mismatch")
    if semantic_key != artifact.semantic_key:
        raise KeyError("semantic key is not qualified KNOWN for this artifact")

    # Positive reflex execution: returning the bound deterministic output is
    # the execution witness. No frontier resolver or planner is called here.
    output = dict(artifact.deterministic_output)
    result = GALLCrownResult(
        composition_digest=manifest.digest,
        admitted_receipts=artifact.source_receipts,
        machine_experience_digest=artifact.digest,
        frontier_resolution_calls=0,
        llm_allocations=0,
        planner_invocations=0,
        machine_experience_hits=1,
        reflex_executions=1,
        gate_11="OPEN",
        gate_12="PASS",
        standing="PARTIAL_ALIVE",
    )
    return output, result


def write_bundle(
    out_dir: str | Path,
    manifest: GALLCompositionManifest,
    artifact: MachineExperienceArtifact,
    episode_1: GALLCrownResult,
    episode_2: GALLCrownResult,
) -> None:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "gall-composition-manifest.json").write_text(
        json.dumps(manifest.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
    )
    (root / "machine-experience.json").write_text(
        json.dumps(artifact.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
    )
    (root / "episode-1-receipt.json").write_text(
        json.dumps(episode_1.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
    )
    (root / "episode-2-receipt.json").write_text(
        json.dumps(episode_2.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
    )
    crown = {
        "schema": "autofde.gall.crown/v26.9.18",
        "composition_digest": manifest.digest,
        "machine_experience_digest": artifact.digest,
        "gates_1_10": "DELEGATED_TO_ADMITTED_RECEIPTS",
        "gate_11": episode_2.gate_11,
        "gate_12": episode_2.gate_12,
        "cross_repo_standing": episode_2.standing,
    }
    crown["crown_receipt_digest"] = _digest(crown)
    (root / "gall-005-crown-receipt.json").write_text(
        json.dumps(crown, sort_keys=True, indent=2), encoding="utf-8"
    )
