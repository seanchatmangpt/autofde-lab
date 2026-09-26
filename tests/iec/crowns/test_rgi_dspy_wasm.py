from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.rgi import TRACE_SCHEMA, benchmark_trace, compare_runs
from autofde_lab.iec.crowns.rgi_dspy_wasm import (
    DSPyWasmSemanticWitness,
    bind_dspy_wasm_to_rgi,
)
from autofde_lab.wasm.dspy import (
    DSPY_VERSION,
    DSPY_WASM_SCHEMA,
    PYODIDE_VERSION,
    DSPyWasmResult,
)


D1 = "sha256:" + "1" * 64
D2 = "sha256:" + "2" * 64
D3 = "sha256:" + "3" * 64


def alive_result(*, replay_command: tuple[str, ...] = ("node", "probe.mjs")) -> DSPyWasmResult:
    return DSPyWasmResult.from_payload(
        {
            "schema": DSPY_WASM_SCHEMA,
            "status": "ALIVE",
            "subject": {
                "dspy": DSPY_VERSION,
                "pyodide": PYODIDE_VERSION,
                "runtime": "node-pyodide",
                "profile": "autofde-core-no-provider-io-v1",
                "court": "full-capability-matrix",
            },
            "stages": [],
            "blocker": None,
            "output": {
                "module_output": "WASM",
                "host_output": "WASM-HOST",
                "core_host_calls": 1,
                "capabilities": {
                    "summary": {"blocked": 0, "alive": 2, "total": 2}
                },
                "provider_io": False,
                "authority": {"class": "candidate", "actuation": "none"},
            },
        },
        replay_command=replay_command,
    )


def blocked_result() -> DSPyWasmResult:
    return DSPyWasmResult.from_payload(
        {
            "schema": DSPY_WASM_SCHEMA,
            "status": "BLOCKED",
            "subject": {
                "dspy": DSPY_VERSION,
                "pyodide": PYODIDE_VERSION,
                "runtime": "node-pyodide",
                "profile": "autofde-core-no-provider-io-v1",
                "court": "full-capability-matrix",
            },
            "stages": [],
            "blocker": {"code": "NODE_TIMEOUT", "detail": "timeout", "layer": "host"},
            "output": {},
        },
        replay_command=("node", "probe.mjs"),
    )


def witness(**overrides: object) -> DSPyWasmSemanticWitness:
    values: dict[str, object] = {
        "subject": "seanchatmangpt/autofde-lab@exact-workload",
        "workload_id": "workload:retirement-edge-1",
        "edge_id": "edge:dspy:ticket-triage",
        "reasoning_class": "classification",
        "expected_output_digest": D1,
        "observed_output_digest": D1,
        "verifier_set_id": "verifier-set:semantic-output-v1",
        "verifier_receipt_digest": D2,
        "duration_ms": 4.0,
    }
    values.update(overrides)
    return DSPyWasmSemanticWitness(**values)  # type: ignore[arg-type]


def reference_trace() -> dict[str, object]:
    return {
        "schema": TRACE_SCHEMA,
        "subject": "seanchatmangpt/autofde-lab@exact-workload",
        "workload_id": "workload:retirement-edge-1",
        "mode": "LLM_NATIVE",
        "run_wall_ms": 10.0,
        "edge_universe": ["edge:dspy:ticket-triage"],
        "events": [
            {
                "sequence": 0,
                "edge_id": "edge:dspy:ticket-triage",
                "reasoning_class": "classification",
                "executor": "GENERAL_LLM",
                "route_state": "UNKNOWN",
                "phase": "CONSTRUCT",
                "duration_ms": 10.0,
                "llm_tokens": 100,
                "receipt_id": "receipt:reference",
            }
        ],
        "ranking": None,
    }


def test_alive_dspy_wasm_manufactures_machine_rgi_trace_and_fidelity_receipt() -> None:
    binding = bind_dspy_wasm_to_rgi(alive_result(), witness())

    trace = binding["trace"]
    event = trace["events"][0]

    assert trace["mode"] == "MACHINE_SERIAL"
    assert trace["edge_universe"] == ["edge:dspy:ticket-triage"]
    assert event["edge_id"] == "edge:dspy:ticket-triage"
    assert event["executor"] == "MACHINE"
    assert event["llm_tokens"] == 0
    assert event["phase"] == "CONSTRUCT"

    fidelity = binding["fidelity_receipt"]
    assert fidelity["verdict"] == "PASS"
    assert fidelity["authority"] == "NONE"
    assert fidelity["expected_output_digest"] == fidelity["observed_output_digest"]

    receipt = binding["binding_receipt"]
    assert receipt["authority"] == "NONE"
    assert receipt["actuation"] == "none"
    assert receipt["retirement"] == "UNCHANGED:IEC-C3-OWNS-RETIREMENT"


def test_bridge_output_is_directly_admitted_by_rgi_comparison() -> None:
    binding = bind_dspy_wasm_to_rgi(alive_result(), witness())
    comparison = compare_runs(
        reference_trace(),
        binding["trace"],
        fidelity_receipt=binding["fidelity_receipt"],
    )

    assert comparison["gate"] == "PASS"
    assert comparison["candidate"]["metrics"]["zero_llm_observed"] is True
    assert comparison["candidate"]["metrics"]["llm_tokens"] == 0
    assert comparison["retirement"].startswith("UNCHANGED:")


def test_semantic_digest_mismatch_remains_counterexample_not_machine_success() -> None:
    binding = bind_dspy_wasm_to_rgi(
        alive_result(),
        witness(observed_output_digest=D3),
    )

    assert binding["fidelity_receipt"]["verdict"] == "COUNTEREXAMPLE"
    comparison = compare_runs(
        reference_trace(),
        binding["trace"],
        fidelity_receipt=binding["fidelity_receipt"],
    )
    assert comparison["gate"] == "COUNTEREXAMPLE"
    assert "SEMANTIC_FIDELITY_NOT_PASS" in comparison["falsifiers"]


def test_runtime_failure_refuses_binding_before_rgi_trace_manufacture() -> None:
    with pytest.raises(IECRefusal) as error:
        bind_dspy_wasm_to_rgi(blocked_result(), witness())

    assert error.value.code == "REFUSED_DSPY_WASM_RUNTIME_NOT_ALIVE"


def test_witness_refuses_do_and_malformed_numeric_fields() -> None:
    with pytest.raises(ValueError, match="cannot claim DO"):
        witness(phase="DO")
    with pytest.raises(ValueError, match="non-negative number"):
        witness(duration_ms="4")
    with pytest.raises(ValueError, match="non-negative integer"):
        witness(sequence=1.5)


def test_runtime_replay_identity_can_change_without_changing_semantic_edge_identity() -> None:
    left = bind_dspy_wasm_to_rgi(
        alive_result(replay_command=("node", "probe-a.mjs")),
        witness(),
    )
    right = bind_dspy_wasm_to_rgi(
        alive_result(replay_command=("node", "probe-b.mjs")),
        witness(),
    )

    assert left["binding_receipt"]["executor"]["runtime_receipt_id"] != right["binding_receipt"]["executor"]["runtime_receipt_id"]
    assert benchmark_trace(left["trace"])["edge_universe_id"] == benchmark_trace(right["trace"])["edge_universe_id"]
    assert left["binding_receipt"]["semantic"] == right["binding_receipt"]["semantic"]
