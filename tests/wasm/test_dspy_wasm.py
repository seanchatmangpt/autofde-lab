from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autofde_lab.wasm.dspy import (
    DSPY_VERSION,
    DSPY_WASM_RECEIPT_SCHEMA,
    DSPY_WASM_SCHEMA,
    PYODIDE_VERSION,
    DSPyWasmProbe,
    DSPyWasmProtocolViolation,
    DSPyWasmResult,
)


def _payload(status: str = "ALIVE") -> dict[str, object]:
    blocker = None
    output: dict[str, object] = {
        "dspy_version": DSPY_VERSION,
        "module_output": "WASM",
        "module_type": "Prediction",
        "lm_calls": 1,
        "host_output": "WASM-HOST",
        "core_host_calls": 1,
        "provider_io": False,
        "capabilities": {
            "schema": "autofde.dspy-wasm.capabilities.v1",
            "capabilities": [
                {
                    "name": "module.predict",
                    "status": "ALIVE",
                    "phase": "execute",
                    "evidence": {"output": "WASM-HOST"},
                    "error": None,
                }
            ],
            "summary": {
                "total": 1,
                "alive": 1,
                "blocked": 0,
                "alive_names": ["module.predict"],
                "blocked_names": [],
            },
        },
        "authority": {"class": "candidate", "actuation": "none"},
    }
    if status != "ALIVE":
        blocker = {
            "code": "DSPY_DEPENDENCY_CLOSURE_UNAVAILABLE",
            "layer": "package-resolution",
            "detail": "no compatible wheel",
        }
        output = {}
    return {
        "schema": DSPY_WASM_SCHEMA,
        "status": status,
        "subject": {
            "dspy": DSPY_VERSION,
            "pyodide": PYODIDE_VERSION,
            "runtime": "node-pyodide",
            "profile": "autofde-core-no-provider-io-v1",
            "court": "full-capability-matrix",
        },
        "stages": [{"name": "dspy-module", "status": status}],
        "blocker": blocker,
        "output": output,
    }


def test_alive_receipt_is_subject_and_observation_bound() -> None:
    result = DSPyWasmResult.from_payload(
        _payload(), replay_command=("node", "probe.mjs")
    )
    receipt = result.receipt
    assert result.status == "ALIVE"
    assert receipt["schema"] == DSPY_WASM_RECEIPT_SCHEMA
    assert receipt["subject"]["dspy"] == DSPY_VERSION
    assert receipt["subject"]["pyodide"] == PYODIDE_VERSION
    assert receipt["authority"] == {"class": "candidate", "actuation": "none"}
    assert len(receipt["observation_sha256"]) == 64
    assert receipt["replay"]["command"] == ["node", "probe.mjs"]


def test_blocked_dependency_edge_preserves_typed_blocker() -> None:
    result = DSPyWasmResult.from_payload(
        _payload("BLOCKED"), replay_command=("node", "probe.mjs")
    )
    assert result.status == "BLOCKED"
    assert result.blocker is not None
    assert result.blocker["code"] == "DSPY_DEPENDENCY_CLOSURE_UNAVAILABLE"
    assert result.receipt["standing"] == "BLOCKED"


def test_subject_drift_is_refused() -> None:
    payload = _payload()
    payload["subject"] = {
        "dspy": "3.3.1",
        "pyodide": PYODIDE_VERSION,
        "runtime": "node-pyodide",
        "profile": "autofde-core-no-provider-io-v1",
        "court": "full-capability-matrix",
    }
    with pytest.raises(DSPyWasmProtocolViolation, match="DSPy subject drift"):
        DSPyWasmResult.from_payload(payload, replay_command=())


def test_alive_requires_observed_module_result() -> None:
    payload = _payload()
    payload["output"] = {"module_output": "not-wasm"}
    with pytest.raises(DSPyWasmProtocolViolation, match="requires observed"):
        DSPyWasmResult.from_payload(payload, replay_command=())


def test_missing_node_is_typed_unsupported(tmp_path: Path) -> None:
    script = tmp_path / "probe.mjs"
    script.write_text("// never executed\n", encoding="utf-8")
    result = DSPyWasmProbe(node="", script=script).run()
    assert result.status == "UNSUPPORTED"
    assert result.blocker is not None
    assert result.blocker["code"] == "NODE_UNAVAILABLE"


def test_real_node_pyodide_probe_when_dependency_is_materialized() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not available")

    script = DSPyWasmProbe.default_script()
    pyodide_package = script.parent / "node_modules" / "pyodide" / "package.json"
    if not pyodide_package.is_file():
        pytest.skip(
            "materialize wasm/dspy-wasm dependencies with npm install before real probe"
        )

    package = json.loads(pyodide_package.read_text(encoding="utf-8"))
    assert package["version"] == PYODIDE_VERSION

    result = DSPyWasmProbe(node=node, script=script).run()
    assert result.status in {"ALIVE", "BLOCKED"}
    if result.status == "ALIVE":
        assert result.output["module_output"] == "WASM"
        assert result.output["host_output"] == "WASM-HOST"
        assert result.output["core_host_calls"] == 1
        assert result.output["capabilities"]["summary"]["blocked"] == 0
        assert result.output["provider_io"] is False
        assert result.output["authority"] == {"class": "candidate", "actuation": "none"}
    else:
        assert result.blocker is not None
        assert result.blocker["code"] in {
            "DSPY_WASM_PROFILE_UNAVAILABLE",
            "DSPY_DEPENDENCY_CLOSURE_UNAVAILABLE",
            "DSPY_MODULE_EXECUTION_FAILED",
            "DSPY_CAPABILITY_MATRIX_INCOMPLETE",
            "DSPY_CAPABILITY_MATRIX_FAILED",
            "PYODIDE_START_FAILED",
        }
