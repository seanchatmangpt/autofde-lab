"""Typed, fail-closed admission of the repository-native GALL evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .composition import EvidenceReference, ReceiptReference

EXPECTED_REPOSITORIES = {
    "GALL-001": "seanchatmangpt/ggen",
    "GALL-002": "seanchatmangpt/ggen_igniter",
    "GALL-003": "seanchatmangpt/ash_a2a",
    "GALL-004": "seanchatmangpt/beam4pm",
}

GALL004_TELEMETRY = "GALL-004-TELEMETRY"
LEARNED_CANDIDATE_CEILING = "CANDIDATE"

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_BINDING_DIGEST = re.compile(r"^(?:sha256|hmac-sha256):[0-9a-f]{64}$")
_RAW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class AdmittedReceipt:
    checkpoint: str
    repository: str
    repo_sha: str
    receipt_digest: str
    standing: str
    semantic_subject_digest: str | None
    telemetry_valid: bool | None
    process_valid: bool | None
    postcondition_valid: bool | None
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AdmittedEvidence:
    evidence_class: str
    repository: str
    repo_sha: str
    receipt_digest: str
    standing: str
    telemetry_valid: bool | None
    process_valid: bool | None
    postcondition_valid: bool | None
    payload: dict[str, Any]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _digest_value(value: Any) -> str:
    return _digest(_canonical(value))


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be sha256:<64hex>, got {value!r}")
    return value


def _require_binding_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _BINDING_DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be sha256: or hmac-sha256:<64hex>, got {value!r}")
    return value


def _require_raw_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _RAW_SHA256.fullmatch(value):
        raise ValueError(f"{field} must be 64 lowercase hex characters, got {value!r}")
    return value


def _require_git_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _GIT_SHA.fullmatch(value):
        raise ValueError(f"{field} must be an exact 40-hex git SHA, got {value!r}")
    return value


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _load_and_bind(path: str, expected_digest: str, label: str) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    observed_digest = _digest(raw)
    if observed_digest != expected_digest:
        raise ValueError(
            f"{label} receipt digest mismatch: expected {expected_digest}, got {observed_digest}"
        )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} receipt must be a JSON object")
    return payload


def _checkpoint_001(payload: dict[str, Any], reference: ReceiptReference) -> AdmittedReceipt:
    if payload.get("schema") != "https://ggen.dev/receipt/pack/v1":
        raise ValueError("GALL-001 requires the ggen portable receipt schema")
    if payload.get("spec") != "RFC-GPACK-001-v26.9.17":
        raise ValueError("GALL-001 requires RFC-GPACK-001-v26.9.17")
    if payload.get("standing") != "ALIVE":
        raise ValueError("GALL-001 requires standing ALIVE")

    replay = _require_mapping(payload.get("replay"), "replay")
    if replay.get("status") != "PASS":
        raise ValueError("GALL-001 requires clean replay.status=PASS")
    _require_sha256(replay.get("source_receipt_sha256"), "replay.source_receipt_sha256")
    _require_sha256(replay.get("replayed_receipt_sha256"), "replay.replayed_receipt_sha256")
    if replay.get("court") != "ggen-engine::replay::verify_project_replay":
        raise ValueError("GALL-001 replay court identity mismatch")

    subject = _require_mapping(payload.get("subject"), "subject")
    pack = _require_nonempty_string(subject.get("pack"), "subject.pack")
    version = _require_nonempty_string(subject.get("version"), "subject.version")
    pack_digest = _require_sha256(subject.get("pack_digest"), "subject.pack_digest")

    composition = _require_mapping(payload.get("composition"), "composition")
    resolved = composition.get("resolved_packs")
    if not isinstance(resolved, list) or not resolved:
        raise ValueError("GALL-001 composition.resolved_packs must be non-empty")
    resolved_identities: set[tuple[str, str, str]] = set()
    for index, item in enumerate(resolved):
        item = _require_mapping(item, f"composition.resolved_packs[{index}]")
        resolved_identities.add(
            (
                _require_nonempty_string(item.get("name"), f"resolved_packs[{index}].name"),
                _require_nonempty_string(item.get("version"), f"resolved_packs[{index}].version"),
                _require_sha256(item.get("digest"), f"resolved_packs[{index}].digest"),
            )
        )
    if (pack, version, pack_digest) not in resolved_identities:
        raise ValueError("GALL-001 subject is not bound into the resolved pack composition")
    if len(resolved_identities) != 1:
        raise ValueError(
            "GALL-001 current portable receipt selects subject via packs.first(); "
            "multi-pack composition is ambiguous without an explicit subject-selection proof"
        )

    graph = _require_mapping(payload.get("graph"), "graph")
    _require_nonempty_string(graph.get("canonical_digest"), "graph.canonical_digest")

    admission = _require_mapping(payload.get("admission"), "admission")
    attempted = admission.get("gates_attempted")
    refusals = admission.get("refusals")
    if not isinstance(attempted, list):
        raise ValueError("GALL-001 admission.gates_attempted must be a list")
    if refusals != []:
        raise ValueError("GALL-001 admitted receipt must have no gate refusals")

    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("GALL-001 dependencies must be a list")
    for index, item in enumerate(dependencies):
        item = _require_mapping(item, f"dependencies[{index}]")
        _require_nonempty_string(item.get("name"), f"dependencies[{index}].name")
        _require_nonempty_string(item.get("version"), f"dependencies[{index}].version")
        _require_sha256(item.get("digest"), f"dependencies[{index}].digest")
        if not isinstance(item.get("scope"), list):
            raise ValueError(f"dependencies[{index}].scope must be a list")

    consequences = payload.get("consequences")
    if not isinstance(consequences, list) or not consequences:
        raise ValueError("GALL-001 requires at least one manufactured consequence")
    for index, item in enumerate(consequences):
        item = _require_mapping(item, f"consequences[{index}]")
        _require_nonempty_string(item.get("target"), f"consequences[{index}].target")
        if item.get("operation") not in {"MANAGED_WRITE", "MANAGED_INJECT"}:
            raise ValueError(f"consequences[{index}].operation is not a ggen managed consequence")
        _require_raw_sha256(item.get("sha256"), f"consequences[{index}].sha256")

    return AdmittedReceipt(
        checkpoint=reference.checkpoint,
        repository=reference.repository,
        repo_sha=reference.repo_sha,
        receipt_digest=reference.receipt_digest,
        standing="ALIVE",
        semantic_subject_digest=pack_digest,
        telemetry_valid=None,
        process_valid=None,
        postcondition_valid=None,
        payload=payload,
    )


def _checkpoint_002(payload: dict[str, Any], reference: ReceiptReference) -> AdmittedReceipt:
    # GgenIgniter's checkpoint contract defines this exact handoff rather than
    # a generic envelope. It is derived from the durable GgenIgniter.Receipt
    # plus ProjectManufacturer identity and therefore keeps both identities.
    if str(payload.get("standing", "")).upper() != "ALIVE":
        raise ValueError("GALL-002 requires standing ALIVE")
    if payload.get("repo_sha") != reference.repo_sha:
        raise ValueError("GALL-002 handoff repo_sha does not match the exact referenced producer")

    graph_digest = _require_sha256(payload.get("graph_digest"), "graph_digest")
    manufacturer = _require_sha256(payload.get("manufacturer_digest"), "manufacturer_digest")
    projection = _require_sha256(payload.get("projection_digest"), "projection_digest")
    post_run = _require_sha256(payload.get("post_run_hash"), "post_run_hash")
    if projection != post_run:
        raise ValueError("GALL-002 projection_digest must equal the durable receipt post_run_hash")
    _require_sha256(payload.get("attestation_digest"), "attestation_digest")
    _require_sha256(payload.get("mix_lock_digest"), "mix_lock_digest")
    _require_sha256(payload.get("gall_001_receipt_digest"), "gall_001_receipt_digest")

    _require_mapping(payload.get("manifest_identity"), "manifest_identity")
    _require_nonempty_string(payload.get("profile"), "profile")
    tasks = payload.get("generator_tasks")
    if not isinstance(tasks, list) or not tasks or not all(isinstance(x, str) and x for x in tasks):
        raise ValueError("GALL-002 generator_tasks must be a non-empty string list")
    _require_mapping(payload.get("toolchain"), "toolchain")
    files = payload.get("generated_files")
    if not isinstance(files, list) or not files:
        raise ValueError("GALL-002 generated_files must be non-empty")
    if payload.get("regeneration") != "PASS":
        raise ValueError("GALL-002 requires deterministic regeneration=PASS")

    _ = graph_digest
    return AdmittedReceipt(
        checkpoint=reference.checkpoint,
        repository=reference.repository,
        repo_sha=reference.repo_sha,
        receipt_digest=reference.receipt_digest,
        standing="ALIVE",
        semantic_subject_digest=manufacturer,
        telemetry_valid=None,
        process_valid=None,
        postcondition_valid=None,
        payload=payload,
    )


def _checkpoint_003(payload: dict[str, Any], reference: ReceiptReference) -> AdmittedReceipt:
    # This is AshA2A.Gall.CommandReceipt serialized to JSON, not a generic
    # {standing, handoff_digest} composition object.
    receipt_standing = str(payload.get("receipt_standing", "")).lower()
    if receipt_standing != "durable":
        raise ValueError("GALL-003 requires receipt_standing=durable from the repository-native receipt store contract")
    terminal = str(payload.get("terminal_status", "")).lower()
    if terminal not in {"executed", "reconciled"}:
        raise ValueError("GALL-003 compilation requires executed or reconciled consequence evidence")
    consequence = str(payload.get("consequence", "")).lower().lstrip(":")
    if consequence not in {"change", "external_do"}:
        raise ValueError("GALL-003 receipt is not consequence-bearing")

    semantic = _require_mapping(payload.get("semantic_subject"), "semantic_subject")
    _require_sha256(semantic.get("graph_digest"), "semantic_subject.graph_digest")
    _require_sha256(semantic.get("projection_digest"), "semantic_subject.projection_digest")
    manufacturer = _require_sha256(
        semantic.get("manufacturer_digest"), "semantic_subject.manufacturer_digest"
    )
    if payload.get("manufacturer_subject_digest") != manufacturer:
        raise ValueError("GALL-003 manufacturer_subject_digest disagrees with semantic_subject")

    _require_nonempty_string(payload.get("receipt_id"), "receipt_id")
    _require_nonempty_string(payload.get("command_id"), "command_id")
    _require_nonempty_string(payload.get("capability_id"), "capability_id")
    _require_sha256(payload.get("command_fingerprint"), "command_fingerprint")
    _require_sha256(payload.get("authority_grant_digest"), "authority_grant_digest")
    _require_nonempty_string(payload.get("idempotency_key"), "idempotency_key")
    _require_binding_digest(payload.get("binding_digest"), "binding_digest")
    _require_sha256(payload.get("handoff_digest"), "handoff_digest")

    return AdmittedReceipt(
        checkpoint=reference.checkpoint,
        repository=reference.repository,
        repo_sha=reference.repo_sha,
        receipt_digest=reference.receipt_digest,
        standing="ALIVE",
        semantic_subject_digest=manufacturer,
        telemetry_valid=None,
        process_valid=None,
        postcondition_valid=None,
        payload=payload,
    )


def _checkpoint_004(payload: dict[str, Any], reference: ReceiptReference) -> AdmittedReceipt:
    if payload.get("schema") != "beam4pm.gall.observer/v26.9.18":
        raise ValueError("GALL-004 requires the beam4pm independent observer receipt schema")
    if payload.get("standing") != "ALIVE":
        raise ValueError("GALL-004 requires independent observer standing ALIVE")
    if payload.get("authority") != "none":
        raise ValueError("GALL-004 observer must not carry authority")

    _require_git_sha(payload.get("producer_sha"), "producer_sha")
    _require_sha256(payload.get("gall_003_receipt_digest"), "gall_003_receipt_digest")
    _require_sha256(payload.get("work_order_digest"), "work_order_digest")
    semantic_subject = _require_sha256(
        payload.get("semantic_subject_digest"), "semantic_subject_digest"
    )
    _require_nonempty_string(payload.get("capability_id"), "capability_id")
    _require_sha256(payload.get("command_fingerprint"), "command_fingerprint")
    _require_nonempty_string(payload.get("independent_observer_id"), "independent_observer_id")
    _require_sha256(payload.get("post_state_digest"), "post_state_digest")
    _require_sha256(payload.get("ocel_digest"), "ocel_digest")
    _require_sha256(payload.get("observer_receipt_digest"), "observer_receipt_digest")

    source = payload.get("post_state_source")
    if source in {None, "actuator_reply", "command_bus_reply"}:
        raise ValueError("GALL-004 post-state is not independent")
    if payload.get("occurrence_count") != 1:
        raise ValueError("GALL-004 requires exactly one independently observed consequence")

    witnesses = payload.get("ordering_witnesses")
    required_witnesses = {
        ("receipt_prepared", "do_attempted"),
        ("do_attempted", "post_state_observed"),
    }
    if not isinstance(witnesses, list):
        raise ValueError("GALL-004 ordering_witnesses must be a list")
    observed_witnesses = {
        (item.get("before"), item.get("after"))
        for item in witnesses
        if isinstance(item, dict)
    }
    if not required_witnesses.issubset(observed_witnesses):
        raise ValueError("GALL-004 is missing required prepared/DO/post-state ordering witnesses")

    required_falsifiers = {
        "actuator_self_report_only",
        "identity_mismatch",
        "missing_prepared_event",
        "double_consequence",
    }
    falsifiers = payload.get("falsifiers_attempted")
    if not isinstance(falsifiers, list) or not required_falsifiers.issubset(set(falsifiers)):
        raise ValueError("GALL-004 observer receipt is missing required falsifier witnesses")

    return AdmittedReceipt(
        checkpoint=reference.checkpoint,
        repository=reference.repository,
        repo_sha=reference.repo_sha,
        receipt_digest=reference.receipt_digest,
        standing="ALIVE",
        semantic_subject_digest=semantic_subject,
        telemetry_valid=None,
        process_valid=True,
        postcondition_valid=True,
        payload=payload,
    )


_VALIDATORS = {
    "GALL-001": _checkpoint_001,
    "GALL-002": _checkpoint_002,
    "GALL-003": _checkpoint_003,
    "GALL-004": _checkpoint_004,
}


def _gall004_telemetry(payload: dict[str, Any], reference: EvidenceReference) -> AdmittedEvidence:
    if reference.repository != "seanchatmangpt/beam4pm":
        raise ValueError("GALL-004 telemetry evidence must come from seanchatmangpt/beam4pm")
    if payload.get("schema") != "beam4pm.gall.weaver-court/v26.9.18":
        raise ValueError("GALL-004 telemetry requires the beam4pm Weaver court schema")
    if payload.get("standing") != "PARTIAL_ALIVE":
        raise ValueError("GALL-004 Weaver qualification receipt requires PARTIAL_ALIVE standing")
    if payload.get("authority") != "none":
        raise ValueError("GALL-004 Weaver evidence must not carry authority")
    if "0.26.1" not in str(payload.get("weaver_version", "")):
        raise ValueError("GALL-004 telemetry requires exact Weaver v0.26.1 identity")
    _require_sha256(payload.get("registry_manifest_digest"), "registry_manifest_digest")
    _require_sha256(payload.get("registry_definition_digest"), "registry_definition_digest")
    _require_sha256(payload.get("live_check_report_digest"), "live_check_report_digest")
    if payload.get("otlp_round_trip") is not True:
        raise ValueError("GALL-004 telemetry requires an observed OTLP round trip")
    if payload.get("negative_unknown_authority_attribute_refused") is not True:
        raise ValueError("GALL-004 telemetry requires the authority-secret negative falsifier")

    claimed = _require_sha256(payload.get("receipt_digest"), "receipt_digest")
    body = dict(payload)
    body.pop("receipt_digest")
    observed = _digest_value(body)
    if claimed != observed:
        raise ValueError(
            f"GALL-004 Weaver receipt self-digest mismatch: expected {claimed}, got {observed}"
        )

    return AdmittedEvidence(
        evidence_class=reference.evidence_class,
        repository=reference.repository,
        repo_sha=reference.repo_sha,
        receipt_digest=reference.receipt_digest,
        standing="PARTIAL_ALIVE",
        telemetry_valid=True,
        process_valid=None,
        postcondition_valid=None,
        payload=payload,
    )


def admit_receipt(reference: ReceiptReference) -> AdmittedReceipt:
    expected_repo = EXPECTED_REPOSITORIES.get(reference.checkpoint)
    if expected_repo is None:
        raise ValueError(f"unsupported checkpoint {reference.checkpoint}")
    if reference.repository != expected_repo:
        raise ValueError(
            f"{reference.checkpoint} repository mismatch: expected {expected_repo}, got {reference.repository}"
        )
    _require_git_sha(reference.repo_sha, f"{reference.checkpoint}.repo_sha")
    _require_sha256(reference.receipt_digest, f"{reference.checkpoint}.receipt_digest")
    payload = _load_and_bind(reference.path, reference.receipt_digest, reference.checkpoint)

    # Learned/model output is never a substitute for a GALL receipt. This is
    # the composition-side fence corresponding to Standing.CANDIDATE in #159.
    if str(payload.get("standing", "")).upper() == LEARNED_CANDIDATE_CEILING or payload.get(
        "authorizes_actuation"
    ) is True:
        raise ValueError("learned GNN/ONNX evidence remains CANDIDATE and cannot satisfy GALL admission")

    return _VALIDATORS[reference.checkpoint](payload, reference)


def admit_evidence(reference: EvidenceReference) -> AdmittedEvidence:
    _require_git_sha(reference.repo_sha, f"{reference.evidence_class}.repo_sha")
    _require_sha256(reference.receipt_digest, f"{reference.evidence_class}.receipt_digest")
    payload = _load_and_bind(reference.path, reference.receipt_digest, reference.evidence_class)
    if str(payload.get("standing", "")).upper() == LEARNED_CANDIDATE_CEILING or payload.get(
        "authorizes_actuation"
    ) is True:
        raise ValueError("learned GNN/ONNX evidence remains CANDIDATE and cannot satisfy GALL admission")
    if reference.evidence_class == GALL004_TELEMETRY:
        return _gall004_telemetry(payload, reference)
    raise ValueError(f"unsupported supporting evidence class {reference.evidence_class}")
