"""Wire-schema drift tests for delegation admission contracts."""

from __future__ import annotations

import json
from pathlib import Path

from autofde_lab.iec.crowns.delegation_admission import REQUIRED_FIELDS, SCHEMA
from autofde_lab.iec.crowns.delegation_admission_batch import BATCH_SCHEMA
from autofde_lab.iec.crowns.delegation_admission_history import HISTORY_SCHEMA

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "iec"


def load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_wire_schema_constants_match_runtime_contracts() -> None:
    artifact = load("delegation-admission-artifact-v1.schema.json")
    batch = load("delegation-admission-batch-v1.schema.json")
    history = load("delegation-admission-history-v1.schema.json")

    assert artifact["properties"]["schema"]["const"] == SCHEMA
    assert batch["properties"]["schema"]["const"] == BATCH_SCHEMA
    assert history["properties"]["schema"]["const"] == HISTORY_SCHEMA


def test_artifact_schema_required_evidence_matches_runtime_fields() -> None:
    artifact = load("delegation-admission-artifact-v1.schema.json")
    defs = artifact["$defs"]
    for obligation, runtime_fields in REQUIRED_FIELDS.items():
        required = set(defs[obligation]["required"])
        assert {"subject", "verdict", "scope_units"} <= required
        assert set(runtime_fields) <= required

    assert "independent" in defs["verify"]["required"]


def test_relative_schema_references_resolve_to_committed_files() -> None:
    batch = load("delegation-admission-batch-v1.schema.json")
    history = load("delegation-admission-history-v1.schema.json")
    refs = [
        batch["properties"]["cases"]["items"]["$ref"],
        history["properties"]["snapshots"]["items"]["properties"]["artifact"]["$ref"],
    ]
    for relative in refs:
        assert (SCHEMAS / relative).is_file()


def test_batch_and_history_refuse_vacuous_empty_collections_at_schema_level() -> None:
    batch = load("delegation-admission-batch-v1.schema.json")
    history = load("delegation-admission-history-v1.schema.json")
    assert batch["properties"]["cases"]["minItems"] == 1
    assert history["properties"]["snapshots"]["minItems"] == 1
