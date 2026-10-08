"""Bind bounded DSPy-WASM execution into Region-Granular Intelligence traces.

Runtime compatibility is not semantic fidelity. This bridge keeps those claims
separate: a DSPyWasmResult proves the bounded executor reached ALIVE with no
ambient provider I/O or actuation; an independent semantic witness binds the
same RGI edge to expected/observed output digests. Only their conjunction can
manufacture an RGI fidelity PASS receipt.

Provider/runtime/replay identity may change without changing the semantic
edge_id, workload_id, or exact workload subject.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from autofde_lab.wasm.dspy import DSPyWasmResult

from .model import IECRefusal, Verdict, content_id
from .rgi import TRACE_SCHEMA

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_NON_DO_PHASES = frozenset({"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"})
_ROUTE_STATES = frozenset({"KNOWN", "ADMITTED"})


@dataclass(frozen=True, slots=True)
class DSPyWasmSemanticWitness:
    """Independent semantic evidence for one RGI edge execution."""

    subject: str
    workload_id: str
    edge_id: str
    reasoning_class: str
    expected_output_digest: str
    observed_output_digest: str
    verifier_set_id: str
    verifier_receipt_digest: str
    duration_ms: float
    phase: str = "CONSTRUCT"
    route_state: str = "KNOWN"
    sequence: int = 0

    def __post_init__(self) -> None:
        for field in ("subject", "workload_id", "edge_id", "reasoning_class", "verifier_set_id"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"{field} must be non-empty")
        for field in (
            "expected_output_digest",
            "observed_output_digest",
            "verifier_receipt_digest",
        ):
            if not _SHA256.fullmatch(str(getattr(self, field))):
                raise ValueError(f"{field} must be sha256:<64-hex>")
        if self.phase not in _NON_DO_PHASES:
            raise ValueError("DSPy-WASM candidate execution cannot claim DO phase")
        if self.route_state not in _ROUTE_STATES:
            raise ValueError("route_state must be KNOWN or ADMITTED")
        if (
            isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, (int, float))
            or self.duration_ms < 0
        ):
            raise ValueError("duration_ms must be a non-negative number")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError("sequence must be a non-negative integer")


def _runtime_receipt_id(result: DSPyWasmResult) -> str:
    return content_id(result.receipt)


def _admit_runtime(result: DSPyWasmResult) -> None:
    if result.status != "ALIVE":
        code = result.blocker.get("code") if result.blocker else "NOT_ALIVE"
        raise IECRefusal(
            "REFUSED_DSPY_WASM_RUNTIME_NOT_ALIVE",
            f"bounded executor standing={result.status} blocker={code}",
        )

    receipt = result.receipt
    authority = receipt.get("authority")
    if not isinstance(authority, dict) or authority.get("actuation") != "none":
        raise IECRefusal(
            "REFUSED_DSPY_WASM_AUTHORITY_DRIFT",
            "bounded executor receipt must preserve actuation=none",
        )
    if result.output.get("provider_io") is not False:
        raise IECRefusal(
            "REFUSED_DSPY_WASM_PROVIDER_IO",
            "bounded executor must preserve provider_io=false",
        )


def bind_dspy_wasm_to_rgi(
    result: DSPyWasmResult,
    witness: DSPyWasmSemanticWitness,
) -> dict[str, Any]:
    """Manufacture a machine trace plus fidelity receipt for one semantic edge."""

    _admit_runtime(result)

    runtime_receipt_id = _runtime_receipt_id(result)
    fidelity_verdict = (
        Verdict.PASS
        if witness.expected_output_digest == witness.observed_output_digest
        else Verdict.COUNTEREXAMPLE
    )

    fidelity_payload = {
        "schema": "autofde-lab.rgi-fidelity-receipt/1",
        "subject": witness.subject,
        "edge_id": witness.edge_id,
        "workload_id": witness.workload_id,
        "verdict": fidelity_verdict.value,
        "verifier_set_id": witness.verifier_set_id,
        "verifier_receipt_digest": witness.verifier_receipt_digest,
        "expected_output_digest": witness.expected_output_digest,
        "observed_output_digest": witness.observed_output_digest,
        "runtime_receipt_id": runtime_receipt_id,
        "claim": (
            "SEMANTIC_OUTPUT_DIGEST_EQUAL"
            if fidelity_verdict is Verdict.PASS
            else "SEMANTIC_OUTPUT_DIGEST_MISMATCH"
        ),
        "authority": "NONE",
    }
    fidelity_receipt = {
        **fidelity_payload,
        "receipt_id": content_id(fidelity_payload),
    }

    trace = {
        "schema": TRACE_SCHEMA,
        "subject": witness.subject,
        "workload_id": witness.workload_id,
        "mode": "MACHINE_SERIAL",
        "run_wall_ms": float(witness.duration_ms),
        "edge_universe": [witness.edge_id],
        "events": [
            {
                "sequence": witness.sequence,
                "edge_id": witness.edge_id,
                "reasoning_class": witness.reasoning_class,
                "executor": "MACHINE",
                "route_state": witness.route_state,
                "phase": witness.phase,
                "duration_ms": float(witness.duration_ms),
                "llm_tokens": 0,
                "receipt_id": runtime_receipt_id,
            }
        ],
        "ranking": None,
    }

    binding_payload = {
        "schema": "autofde-lab.rgi-dspy-wasm-binding/1",
        "semantic": {
            "subject": witness.subject,
            "workload_id": witness.workload_id,
            "edge_id": witness.edge_id,
            "reasoning_class": witness.reasoning_class,
        },
        "executor": {
            "class": "DSPY_WASM",
            "runtime_subject": dict(result.subject),
            "runtime_receipt_id": runtime_receipt_id,
        },
        "fidelity_receipt_id": fidelity_receipt["receipt_id"],
        "authority": "NONE",
        "actuation": "none",
        "retirement": "UNCHANGED:IEC-C3-OWNS-RETIREMENT",
    }
    binding_receipt = {
        **binding_payload,
        "receipt_id": content_id(binding_payload),
    }

    return {
        "trace": trace,
        "fidelity_receipt": fidelity_receipt,
        "binding_receipt": binding_receipt,
        "witness": asdict(witness),
    }
