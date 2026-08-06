from __future__ import annotations

import json
from pathlib import Path

import pytest

from skdecide.wasm import (
    ABI_VERSION,
    ArtifactUnavailable,
    ChatmanEcosystem,
    ComponentRegistry,
)
from skdecide.wasm._abi import RESPONSE_SCHEMA


class ReceiptBackend:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def invoke(self, artifact: Path, request: bytes) -> bytes:
        decoded = json.loads(request)
        self.requests.append(decoded)
        return json.dumps(
            {
                "schema": RESPONSE_SCHEMA,
                "status": "ALIVE",
                "output": {"operation": decoded["operation"]},
                "receipt": {
                    "subject": {
                        "component": decoded["component"],
                        "source_revision": decoded["source_revision"],
                    },
                    "artifact": artifact.name,
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


def test_default_registry_is_complete_and_exact_sha_pinned() -> None:
    registry = ComponentRegistry.default()
    assert len(registry) == 16
    assert {component.name for component in registry} == {
        "cargo-cicd",
        "ferroplan",
        "fgn",
        "ggen",
        "ggen-create",
        "ggen-legacy",
        "lsp-max",
        "mfact",
        "mfw",
        "mmdio",
        "mu-mcpp",
        "mu-truex",
        "powl",
        "star-toml",
        "wasm4pm",
        "wasm4pm-compat",
    }
    assert all(len(component.revision) == 40 for component in registry)
    assert all(component.artifact.endswith(".wasm") for component in registry)


def test_python_aliases_resolve_mu_and_powl(tmp_path: Path) -> None:
    ecosystem = ChatmanEcosystem(tmp_path, backend=ReceiptBackend())
    assert ecosystem.mcpp.descriptor.name == "mu-mcpp"
    assert ecosystem.truex.descriptor.name == "mu-truex"
    assert ecosystem.POWL.descriptor.name == "powl"


def test_missing_artifact_is_typed_blocker(tmp_path: Path) -> None:
    ecosystem = ChatmanEcosystem(tmp_path, backend=ReceiptBackend())
    with pytest.raises(ArtifactUnavailable, match="has not been manufactured"):
        ecosystem.ggen.invoke("render", {"graph": "urn:test"})


def test_receipt_bound_round_trip(tmp_path: Path) -> None:
    registry = ComponentRegistry.default()
    descriptor = registry.by_name("ggen")
    (tmp_path / descriptor.artifact).write_bytes(b"placeholder")
    backend = ReceiptBackend()
    ecosystem = ChatmanEcosystem(tmp_path, registry=registry, backend=backend)

    result = ecosystem.ggen.invoke(
        "render",
        {"graph": "urn:test"},
        authority={"actuation": "none"},
    )

    assert result.status == "ALIVE"
    assert result.output == {"operation": "render"}
    assert result.receipt["subject"]["source_revision"] == descriptor.revision
    assert backend.requests == [
        {
            "authority": {"actuation": "none"},
            "component": "ggen",
            "operation": "render",
            "payload": {"graph": "urn:test"},
            "schema": "chatman.ecosystem.invoke.v1",
            "source_revision": descriptor.revision,
        }
    ]


def test_inventory_reports_exact_artifact_availability(tmp_path: Path) -> None:
    registry = ComponentRegistry.default()
    first = next(iter(registry))
    (tmp_path / first.artifact).write_bytes(b"wasm")
    inventory = ChatmanEcosystem(tmp_path, registry=registry).inventory()
    by_name = {item["name"]: item for item in inventory}
    assert by_name[first.name]["available"] is True
    assert sum(bool(item["available"]) for item in inventory) == 1
    assert ABI_VERSION == "1.0.0"


def test_build_contract_is_deterministic(tmp_path: Path) -> None:
    from skdecide.wasm.build import emit_contract

    registry = ComponentRegistry.default()
    wit, manifest = emit_contract(tmp_path, registry)
    first = manifest.read_bytes()
    emit_contract(tmp_path, registry)
    assert manifest.read_bytes() == first
    assert wit.read_text().startswith("package chatman:ecosystem@1.0.0;")
    decoded = json.loads(first)
    assert decoded["component_count"] == 16


def test_receipt_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    class WrongReceiptBackend:
        def invoke(self, artifact: Path, request: bytes) -> bytes:
            decoded = json.loads(request)
            return json.dumps(
                {
                    "schema": RESPONSE_SCHEMA,
                    "status": "ALIVE",
                    "output": {},
                    "receipt": {
                        "subject": {
                            "component": "not-the-component",
                            "source_revision": decoded["source_revision"],
                        }
                    },
                }
            ).encode()

    descriptor = ComponentRegistry.default().by_name("ggen")
    (tmp_path / descriptor.artifact).write_bytes(b"placeholder")
    ecosystem = ChatmanEcosystem(tmp_path, backend=WrongReceiptBackend())
    from skdecide.wasm import AbiViolation

    with pytest.raises(AbiViolation, match="receipt-bound ABI"):
        ecosystem.ggen.invoke("render")
