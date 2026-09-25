"""Bounded DSPy-on-Pyodide WebAssembly compatibility court.

This module does not claim that DSPy is generally WASM-compatible. It executes a
small, replayable court in a Node-hosted Pyodide runtime and returns typed standing
for the exact pinned subject.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DSPY_WASM_SCHEMA = "autofde.dspy-wasm.probe.v1"
DSPY_WASM_RECEIPT_SCHEMA = "autofde.dspy-wasm.receipt.v1"
DSPY_VERSION = "3.4.0"
PYODIDE_VERSION = "314.0.7"
_ALLOWED_STANDING = frozenset({"ALIVE", "BLOCKED", "UNSUPPORTED"})


class DSPyWasmError(RuntimeError):
    """Base class for host-side DSPy WASM court failures."""


class DSPyWasmProtocolViolation(DSPyWasmError):
    """The guest returned an envelope that cannot support a standing claim."""


@dataclass(frozen=True, slots=True)
class DSPyWasmResult:
    """Observed result for the exact DSPy/Pyodide subject."""

    status: str
    subject: Mapping[str, Any]
    stages: tuple[Mapping[str, Any], ...]
    blocker: Mapping[str, Any] | None
    output: Mapping[str, Any]
    observation: Mapping[str, Any]
    replay_command: tuple[str, ...]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        replay_command: tuple[str, ...],
    ) -> "DSPyWasmResult":
        if payload.get("schema") != DSPY_WASM_SCHEMA:
            raise DSPyWasmProtocolViolation("unexpected DSPy WASM probe schema")

        status = payload.get("status")
        if status not in _ALLOWED_STANDING:
            raise DSPyWasmProtocolViolation(f"invalid standing: {status!r}")

        subject = payload.get("subject")
        if not isinstance(subject, Mapping):
            raise DSPyWasmProtocolViolation("probe subject must be an object")
        if subject.get("dspy") != DSPY_VERSION:
            raise DSPyWasmProtocolViolation(
                f"DSPy subject drift: expected {DSPY_VERSION}, observed {subject.get('dspy')!r}"
            )
        if subject.get("pyodide") != PYODIDE_VERSION:
            raise DSPyWasmProtocolViolation(
                "Pyodide subject drift: "
                f"expected {PYODIDE_VERSION}, observed {subject.get('pyodide')!r}"
            )

        stages = payload.get("stages", [])
        if not isinstance(stages, list) or not all(
            isinstance(stage, Mapping) for stage in stages
        ):
            raise DSPyWasmProtocolViolation("probe stages must be a list of objects")

        blocker = payload.get("blocker")
        if blocker is not None and not isinstance(blocker, Mapping):
            raise DSPyWasmProtocolViolation("probe blocker must be an object or null")

        output = payload.get("output", {})
        if not isinstance(output, Mapping):
            raise DSPyWasmProtocolViolation("probe output must be an object")

        if status == "ALIVE":
            if output.get("module_output") != "WASM":
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires observed deterministic dspy.Module output 'WASM'"
                )
            if output.get("host_output") != "WASM-HOST":
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires observed DSPy custom-engine host output 'WASM-HOST'"
                )
            if output.get("core_host_calls") != 1:
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires exactly one core host-engine handshake"
                )
            capabilities = output.get("capabilities")
            if not isinstance(capabilities, Mapping):
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires a capability matrix"
                )
            summary = capabilities.get("summary")
            if not isinstance(summary, Mapping):
                raise DSPyWasmProtocolViolation(
                    "ALIVE capability matrix requires a summary"
                )
            if summary.get("blocked") != 0:
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires zero blocked capabilities"
                )
            if summary.get("alive") != summary.get("total"):
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires every capability row to be alive"
                )
            if output.get("provider_io") is not False:
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires provider_io=false"
                )
            authority = output.get("authority")
            if not isinstance(authority, Mapping) or authority.get("actuation") != "none":
                raise DSPyWasmProtocolViolation(
                    "ALIVE requires zero-actuation authority"
                )
            if blocker is not None:
                raise DSPyWasmProtocolViolation("ALIVE result cannot carry a blocker")
        elif blocker is None:
            raise DSPyWasmProtocolViolation(
                f"{status} result requires a typed blocker"
            )

        return cls(
            status=status,
            subject=dict(subject),
            stages=tuple(dict(stage) for stage in stages),
            blocker=dict(blocker) if blocker is not None else None,
            output=dict(output),
            observation=dict(payload),
            replay_command=replay_command,
        )

    @property
    def receipt(self) -> dict[str, Any]:
        canonical = json.dumps(
            self.observation,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return {
            "schema": DSPY_WASM_RECEIPT_SCHEMA,
            "standing": self.status,
            "subject": dict(self.subject),
            "authority": {"class": "candidate", "actuation": "none"},
            "observation_sha256": hashlib.sha256(canonical).hexdigest(),
            "replay": {"command": list(self.replay_command)},
            "blocker": dict(self.blocker) if self.blocker is not None else None,
        }


class DSPyWasmProbe:
    """Run the isolated Node/Pyodide DSPy compatibility court."""

    def __init__(
        self,
        *,
        node: str | None = None,
        script: str | Path | None = None,
        timeout: float = 120.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.node = (shutil.which("node") or "") if node is None else node
        self.script = Path(script) if script is not None else self.default_script()
        self.timeout = timeout

    @staticmethod
    def repository_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @classmethod
    def default_script(cls) -> Path:
        return cls.repository_root() / "wasm" / "dspy-wasm" / "probe.mjs"

    def run(self) -> DSPyWasmResult:
        if not self.node:
            return self._host_blocker(
                status="UNSUPPORTED",
                code="NODE_UNAVAILABLE",
                detail="Node.js is required for the Pyodide host runtime",
            )
        if not self.script.is_file():
            return self._host_blocker(
                status="UNSUPPORTED",
                code="PROBE_SCRIPT_MISSING",
                detail=str(self.script),
            )

        command = (self.node, str(self.script))
        try:
            completed = subprocess.run(
                command,
                cwd=self.script.parent,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._host_blocker(
                status="BLOCKED",
                code="NODE_TIMEOUT",
                detail=f"probe exceeded {self.timeout:g}s",
                replay_command=command,
            )
        except OSError as exc:
            return self._host_blocker(
                status="UNSUPPORTED",
                code="NODE_EXECUTION_UNAVAILABLE",
                detail=str(exc),
                replay_command=command,
            )

        if completed.returncode != 0:
            return self._host_blocker(
                status="BLOCKED",
                code="NODE_RUNTIME_FAILURE",
                detail=completed.stderr.strip() or f"exit={completed.returncode}",
                replay_command=command,
            )

        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise DSPyWasmProtocolViolation(
                f"probe must emit exactly one JSON envelope, observed {len(lines)} lines"
            )
        try:
            payload = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise DSPyWasmProtocolViolation("probe emitted invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise DSPyWasmProtocolViolation("probe envelope must be an object")
        return DSPyWasmResult.from_payload(payload, replay_command=command)

    @staticmethod
    def _host_blocker(
        *,
        status: str,
        code: str,
        detail: str,
        replay_command: tuple[str, ...] = (),
    ) -> DSPyWasmResult:
        payload = {
            "schema": DSPY_WASM_SCHEMA,
            "status": status,
            "subject": {
                "dspy": DSPY_VERSION,
                "pyodide": PYODIDE_VERSION,
                "runtime": "node-pyodide",
                "profile": "autofde-core-no-provider-io-v1",
                "court": "full-capability-matrix",
            },
            "stages": [],
            "blocker": {"code": code, "detail": detail, "layer": "host"},
            "output": {},
        }
        return DSPyWasmResult.from_payload(
            payload, replay_command=replay_command
        )
