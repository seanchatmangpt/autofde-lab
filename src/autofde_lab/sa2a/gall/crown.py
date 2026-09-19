"""GALL-005 UNKNOWN -> verified MachineExperience -> fresh KNOWN replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler

from .composition import GALLCompositionManifest
from .receipt_admission import (
    GALL004_TELEMETRY,
    LEARNED_CANDIDATE_CEILING,
    AdmittedEvidence,
    AdmittedReceipt,
    admit_evidence,
    admit_receipt,
)


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
    source_evidence: tuple[str, ...] = ()
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
            source_evidence=tuple(str(x) for x in payload.get("source_evidence", ())),
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
    admitted_evidence: tuple[str, ...]
    machine_experience_digest: str
    telemetry_valid: bool
    process_valid: bool
    postcondition_valid: bool
    learned_candidate_ceiling: str
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


def _by_checkpoint(receipts: list[AdmittedReceipt], checkpoint: str) -> AdmittedReceipt:
    return next(item for item in receipts if item.checkpoint == checkpoint)


def _require_cross_repo_subject(receipts: list[AdmittedReceipt]) -> None:
    gall1 = _by_checkpoint(receipts, "GALL-001")
    gall2 = _by_checkpoint(receipts, "GALL-002")
    gall3 = _by_checkpoint(receipts, "GALL-003")
    gall4 = _by_checkpoint(receipts, "GALL-004")

    if gall2.payload.get("gall_001_receipt_digest") != gall1.receipt_digest:
        raise ValueError("GALL-002 does not bind the admitted GALL-001 receipt digest")

    if gall2.semantic_subject_digest != gall3.semantic_subject_digest:
        raise ValueError("GALL-002 manufacturer and GALL-003 semantic subject do not match")
    semantic = gall3.payload["semantic_subject"]
    if semantic.get("graph_digest") != gall2.payload.get("graph_digest"):
        raise ValueError("GALL-002 graph and GALL-003 semantic graph do not match")
    if semantic.get("projection_digest") != gall2.payload.get("projection_digest"):
        raise ValueError("GALL-002 projection and GALL-003 semantic projection do not match")

    if gall4.payload.get("producer_sha") != gall3.repo_sha:
        raise ValueError("GALL-004 observer does not bind the exact admitted GALL-003 producer SHA")
    if gall4.payload.get("gall_003_receipt_digest") != gall3.payload.get("handoff_digest"):
        raise ValueError("GALL-004 does not bind the admitted GALL-003 handoff digest")
    if gall4.payload.get("capability_id") != gall3.payload.get("capability_id"):
        raise ValueError("GALL-004 capability identity does not match GALL-003")
    if gall4.payload.get("command_fingerprint") != gall3.payload.get("command_fingerprint"):
        raise ValueError("GALL-004 command fingerprint does not match GALL-003")


def _require_evidence_predicates(
    receipts: list[AdmittedReceipt], evidence: list[AdmittedEvidence]
) -> tuple[bool, bool, bool]:
    gall4 = _by_checkpoint(receipts, "GALL-004")
    process_valid = gall4.process_valid is True
    postcondition_valid = gall4.postcondition_valid is True

    telemetry = [item for item in evidence if item.evidence_class == GALL004_TELEMETRY]
    if len(telemetry) != 1:
        raise ValueError(
            "GALL-005 requires exactly one typed GALL-004 telemetry receipt; telemetry cannot be inferred from process/postcondition evidence"
        )
    telemetry_valid = telemetry[0].telemetry_valid is True

    if not telemetry_valid:
        raise ValueError("GALL-004 telemetry-valid predicate is not proven")
    if not process_valid:
        raise ValueError("GALL-004 process-valid predicate is not proven")
    if not postcondition_valid:
        raise ValueError("GALL-004 postcondition-valid predicate is not proven")
    return telemetry_valid, process_valid, postcondition_valid


def compile_verified_experience(
    manifest: GALLCompositionManifest,
    *,
    deterministic_output: dict[str, Any],
) -> tuple[MachineExperienceArtifact, GALLCrownResult]:
    manifest.validate_shape()
    admitted = [admit_receipt(ref) for ref in manifest.receipts]
    supporting = [admit_evidence(ref) for ref in manifest.evidence]
    _require_cross_repo_subject(admitted)
    telemetry_valid, process_valid, postcondition_valid = _require_evidence_predicates(
        admitted, supporting
    )

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
        source_evidence=tuple(
            item.receipt_digest for item in sorted(supporting, key=lambda x: x.evidence_class)
        ),
    )

    result = GALLCrownResult(
        composition_digest=manifest.digest,
        admitted_receipts=artifact.source_receipts,
        admitted_evidence=artifact.source_evidence,
        machine_experience_digest=artifact.digest,
        telemetry_valid=telemetry_valid,
        process_valid=process_valid,
        postcondition_valid=postcondition_valid,
        learned_candidate_ceiling=LEARNED_CANDIDATE_CEILING,
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

    expected_receipts = tuple(
        ref.receipt_digest for ref in sorted(manifest.receipts, key=lambda x: x.checkpoint)
    )
    expected_evidence = tuple(
        ref.receipt_digest for ref in sorted(manifest.evidence, key=lambda x: x.evidence_class)
    )
    if artifact.source_receipts != expected_receipts:
        raise ValueError("MachineExperience source receipt identities do not match manifest")
    if artifact.source_evidence != expected_evidence:
        raise ValueError("MachineExperience supporting evidence identities do not match manifest")

    output = dict(artifact.deterministic_output)
    result = GALLCrownResult(
        composition_digest=manifest.digest,
        admitted_receipts=artifact.source_receipts,
        admitted_evidence=artifact.source_evidence,
        machine_experience_digest=artifact.digest,
        telemetry_valid=True,
        process_valid=True,
        postcondition_valid=True,
        learned_candidate_ceiling=LEARNED_CANDIDATE_CEILING,
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



def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def write_compile_bundle(
    out_dir: str | Path,
    manifest: GALLCompositionManifest,
    artifact: MachineExperienceArtifact,
    episode_1: GALLCrownResult,
) -> None:
    """Persist Episode 1 only.

    Gate 12 is intentionally absent here. A compile process is not a fresh
    KNOWN replay process and therefore cannot mint the replay/crown receipt.
    """

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "gall-composition-manifest.json", manifest.to_dict())
    _write_json(root / "machine-experience.json", artifact.to_dict())
    _write_json(root / "episode-1-receipt.json", episode_1.to_dict())


def write_replay_bundle(
    out_dir: str | Path,
    manifest: GALLCompositionManifest,
    artifact: MachineExperienceArtifact,
    episode_2: GALLCrownResult,
) -> None:
    """Persist Gate-12 evidence from the separately invoked replay process."""

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "episode-2-receipt.json", episode_2.to_dict())
    crown = {
        "schema": "autofde.gall.crown/v26.9.18",
        "composition_digest": manifest.digest,
        "machine_experience_digest": artifact.digest,
        "telemetry_valid": episode_2.telemetry_valid,
        "process_valid": episode_2.process_valid,
        "postcondition_valid": episode_2.postcondition_valid,
        "learned_candidate_ceiling": episode_2.learned_candidate_ceiling,
        "gates_1_10": "DELEGATED_TO_TYPED_ADMITTED_RECEIPTS",
        "gate_11": episode_2.gate_11,
        "gate_12": episode_2.gate_12,
        "cross_repo_standing": episode_2.standing,
    }
    crown["crown_receipt_digest"] = _digest(crown)
    _write_json(root / "gall-005-crown-receipt.json", crown)

