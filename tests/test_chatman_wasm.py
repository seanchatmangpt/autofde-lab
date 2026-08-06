from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

import pytest

from skdecide.wasm import (
    ABI_VERSION,
    AbiViolation,
    ArtifactIntegrityError,
    ChatmanEcosystem,
    ComponentRegistry,
    DirectoryArtifactStore,
    EmbeddedArtifactStore,
    NodeBackend,
)
from skdecide.wasm._artifacts import ARTIFACTS
from skdecide.wasm.build import materialize, verify


def node_backend() -> NodeBackend:
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("Node.js is required for exact Wasm execution in this verifier")
    return NodeBackend(executable)


class BlockedBackend:
    name = "blocked-negative-fixture"

    def invoke(self, artifact: Any, request: bytes) -> bytes:
        decoded = json.loads(request)
        return json.dumps(
            {
                "schema": "chatman.ecosystem.response.v1",
                "status": "BLOCKED",
                "output": {"reason": "SHOULD_NOT_BE_ADMITTED"},
                "receipt": {
                    "schema": "chatman.ecosystem.receipt.v1",
                    "scope": "negative-fixture",
                    "subject": {
                        "component": decoded["component"],
                        "source_revision": decoded["source_revision"],
                    },
                    "standing": "BLOCKED",
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


def test_registry_is_complete_exact_and_artifact_bound() -> None:
    registry = ComponentRegistry.default()
    assert len(registry) == 16
    assert set(ARTIFACTS) == {component.name for component in registry}
    assert ABI_VERSION == "1.1.0"
    for component in registry:
        artifact = ARTIFACTS[component.name]
        data = artifact.bytes()
        assert component.revision and len(component.revision) == 40
        assert component.artifact_sha256 == hashlib.sha256(data).hexdigest()
        assert component.artifact_size == len(data)
        assert data.startswith(b"\x00asm\x01\x00\x00\x00")


def test_aliases_resolve_mu_and_powl() -> None:
    ecosystem = ChatmanEcosystem(backend=node_backend())
    assert ecosystem.mcpp.descriptor.name == "mu-mcpp"
    assert ecosystem.truex.descriptor.name == "mu-truex"
    assert ecosystem.POWL.descriptor.name == "powl"


def test_all_embedded_components_execute_self_test_alive() -> None:
    ecosystem = ChatmanEcosystem(backend=node_backend())
    results = ecosystem.self_test_all()
    assert len(results) == 16
    assert {result.status for result in results} == {"ALIVE"}
    assert ecosystem.missing_artifacts() == ()
    for result in results:
        assert result.receipt["scope"] == "federation-adapter"
        assert (
            result.receipt["artifact"]["sha256"]
            == result.component.artifact_sha256
        )
        assert result.receipt["host"]["backend"] == "node-webassembly"
        assert result.output["semantic_execution"] is False


def test_describe_and_admit_are_receipt_bound() -> None:
    ecosystem = ChatmanEcosystem(backend=node_backend())
    described = ecosystem.ggen.describe()
    admitted = ecosystem.ggen.admit({"graph": "urn:test"})
    assert described.status == "ALIVE"
    assert admitted.status == "ALIVE"
    assert admitted.receipt["subject"] == {
        "component": "ggen",
        "source_revision": ecosystem.ggen.descriptor.revision,
    }


def test_unadmitted_operation_is_typed_refusal() -> None:
    result = ChatmanEcosystem(backend=node_backend()).ggen.invoke("render")
    assert result.status == "REFUSED"
    assert result.output["reason"] == "OPERATION_NOT_ADMITTED"


def test_errc_rejects_blocked_guest_standing() -> None:
    ecosystem = ChatmanEcosystem(backend=BlockedBackend())
    with pytest.raises(AbiViolation, match="receipt-bound ABI"):
        ecosystem.ggen.invoke("self_test")


def test_materialized_inventory_is_deterministic_and_executable(
    tmp_path: Path,
) -> None:
    first = materialize(tmp_path)
    manifest_bytes = (tmp_path / "chatman-ecosystem.json").read_bytes()
    second = materialize(tmp_path)
    assert (tmp_path / "chatman-ecosystem.json").read_bytes() == manifest_bytes
    assert first == second
    report = verify(tmp_path)
    assert report["status"] == "ALIVE"
    assert report["component_count"] == 16
    assert {receipt["status"] for receipt in report["receipts"]} == {"ALIVE"}


def test_directory_store_refuses_artifact_drift(tmp_path: Path) -> None:
    materialize(tmp_path)
    descriptor = ComponentRegistry.default().by_name("ggen")
    (tmp_path / descriptor.artifact).write_bytes(b"not-wasm")
    store = DirectoryArtifactStore(tmp_path)
    with pytest.raises(ArtifactIntegrityError, match="digest mismatch"):
        store.load(descriptor)


def test_registry_manifest_has_no_blocked_or_partial_state() -> None:
    manifest = ComponentRegistry.default().as_manifest()
    encoded = json.dumps(manifest, sort_keys=True)
    assert "BLOCKED" not in encoded
    assert "PARTIAL_ALIVE" not in encoded
    assert manifest["component_count"] == 16
