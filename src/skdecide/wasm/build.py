"""Deterministic build planner for the Chatman ecosystem Wasm federation.

The builder never treats a command plan as a successful artifact.  It validates
exact source identities, emits the canonical WIT and registry, and can run a
source-owned adapter only when that repository provides one.  This prevents a
central wrapper from silently inventing semantics for heterogeneous libraries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from ._abi import WIT
from ._model import ComponentDescriptor, canonical_json_bytes
from ._registry import ComponentRegistry

ADAPTER_PATH = Path(".chatman/wasm-build.py")


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _source_head(source: Path) -> str:
    result = _run(["git", "rev-parse", "HEAD"], cwd=source)
    if result.returncode != 0:
        raise RuntimeError(f"cannot resolve source identity for {source}: {result.stdout}")
    return result.stdout.strip()


def _adapter_command(
    component: ComponentDescriptor,
    source: Path,
    artifact: Path,
    wit: Path,
) -> list[str]:
    adapter = source / ADAPTER_PATH
    if not adapter.is_file():
        raise FileNotFoundError(
            f"{component.name}: source-owned adapter missing at {ADAPTER_PATH}"
        )
    return [
        sys.executable,
        str(adapter),
        "--source-revision",
        component.revision,
        "--wit",
        str(wit),
        "--output",
        str(artifact),
    ]


def emit_contract(output: Path, registry: ComponentRegistry) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    wit_path = output / "chatman-ecosystem.wit"
    manifest_path = output / "chatman-ecosystem.json"
    wit_path.write_text(WIT, encoding="utf-8")
    manifest_path.write_bytes(canonical_json_bytes(registry.as_manifest()) + b"\n")
    return wit_path, manifest_path


def build_component(
    component: ComponentDescriptor,
    *,
    source_root: Path,
    output: Path,
    wit: Path,
) -> dict[str, Any]:
    source = source_root / component.repository_name
    artifact = output / component.artifact
    receipt: dict[str, Any] = {
        "schema": "chatman.ecosystem.build-receipt.v1",
        "subject": component.as_dict(),
        "source_path": str(source),
        "artifact_path": str(artifact),
        "changed": False,
        "status": "UNKNOWN",
    }
    if not source.is_dir():
        receipt.update(status="BLOCKED", reason="SOURCE_NOT_MATERIALIZED")
        return receipt
    try:
        observed_head = _source_head(source)
    except RuntimeError as exc:
        receipt.update(status="BLOCKED", reason="SOURCE_IDENTITY_UNKNOWN", detail=str(exc))
        return receipt
    receipt["observed_source_revision"] = observed_head
    if observed_head != component.revision:
        receipt.update(status="REFUSED", reason="SOURCE_REVISION_MISMATCH")
        return receipt
    try:
        command = _adapter_command(component, source, artifact, wit)
    except FileNotFoundError as exc:
        receipt.update(status="BLOCKED", reason="SOURCE_ADAPTER_MISSING", detail=str(exc))
        return receipt
    receipt["command"] = command
    result = _run(command, cwd=source)
    receipt["exit_code"] = result.returncode
    receipt["output"] = result.stdout
    if result.returncode != 0:
        receipt.update(status="BUILD_BROKEN", reason="ADAPTER_FAILED")
        return receipt
    if not artifact.is_file():
        receipt.update(status="BUILD_BROKEN", reason="ARTIFACT_NOT_PRODUCED")
        return receipt
    artifact_bytes = artifact.read_bytes()
    receipt.update(
        status="PARTIAL_ALIVE",
        changed=True,
        artifact_size=len(artifact_bytes),
        artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
        reason="ARTIFACT_BUILT_INVOKE_NOT_REPLAYED",
    )
    return receipt


def build_all(
    source_root: Path,
    output: Path,
    *,
    selected: set[str] | None = None,
) -> dict[str, Any]:
    registry = ComponentRegistry.default()
    wit, manifest = emit_contract(output, registry)
    receipts = []
    for component in registry:
        if selected and component.name not in selected:
            continue
        receipts.append(
            build_component(
                component,
                source_root=source_root,
                output=output,
                wit=wit,
            )
        )
    report = {
        "schema": "chatman.ecosystem.build-report.v1",
        "manifest": str(manifest),
        "wit": str(wit),
        "receipts": receipts,
    }
    report_path = output / "build-report.json"
    report_path.write_bytes(canonical_json_bytes(report) + b"\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(".chatman/sources"))
    parser.add_argument("--output", type=Path, default=Path("build/chatman-wasm"))
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--emit-contract", action="store_true")
    args = parser.parse_args(argv)

    registry = ComponentRegistry.default()
    if args.emit_contract:
        emit_contract(args.output, registry)
        return 0

    selected = set(args.component) or None
    if selected:
        unknown = selected.difference(component.name for component in registry)
        if unknown:
            parser.error(f"unknown components: {', '.join(sorted(unknown))}")
    report = build_all(args.source_root, args.output, selected=selected)
    failed = {
        receipt["status"]
        for receipt in report["receipts"]
        if receipt["status"] not in {"ALIVE", "PARTIAL_ALIVE"}
    }
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
