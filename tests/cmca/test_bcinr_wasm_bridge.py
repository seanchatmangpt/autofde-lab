"""Chicago-style verification of the in-process WASM transport for bcinr-cmca.

Exercises the real wasmtime runtime over the real prebuilt
``wasm/artifacts/bcinr_cmca_wasm.wasm`` cdylib (no mocks): transport
determinism, bit-identical agreement with the vendored ``cmca_rank_cli``
subprocess transport, default-engine conservation through WASM alone, and
the typed-refusal laws (forced-but-absent transport refuses; unknown
transport value refuses; cardinality refuses before any transport runs).
"""

from __future__ import annotations

import json

import pytest

from autofde_lab.cmca import bcinr_bridge, bcinr_wasm
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    AllocationStanding,
    CandidateBranch,
    ResourceBudget,
)


def _candidates(n: int = 5) -> list[CandidateBranch]:
    return [
        CandidateBranch(
            branch_id=f"b{i}",
            operator_id="op",
            world_id="w",
            state_id=f"s{i}",
            option_entropy=1.0 + i * 0.7,
            historical_yield=0.2 + i * 0.1,
            estimated_cost=5.0 + i * 3.0,
        )
        for i in range(n)
    ]


requires_wasm = pytest.mark.skipif(
    not bcinr_wasm.AVAILABLE or bcinr_wasm.find_bcinr_wasm() is None,
    reason="wasmtime runtime or prebuilt bcinr_cmca_wasm.wasm artifact absent "
    "(uv sync --extra bcinr-wasm; build per wasm/README.md)",
)


def _vendored_cli() -> str | None:
    """The CLI binary only proves *same-source* agreement when it resolves to
    the repo-vendored build -- an upstream ``~/bcinr`` checkout may have
    drifted past ``VENDORED_BCINR_COMMIT``."""
    cli = bcinr_bridge.find_bcinr_cli()
    if cli and "vendor/bcinr" in cli:
        return cli
    return None


@requires_wasm
def test_wasm_transport_is_bit_identical_to_vendored_cli() -> None:
    """Same vendored commit, same Q16.16 arithmetic: the wasm and subprocess
    transports must produce bit-identical JSON for identical requests."""
    cli = _vendored_cli()
    if cli is None:
        pytest.skip(
            "cmca_rank_cli does not resolve to the vendored build; "
            "cross-source agreement is not asserted"
        )
    candidates = _candidates()
    canonical = sorted(candidates, key=lambda c: c.candidate_hash)
    request = {
        "candidates": [
            {"name": c.branch_id, "measures": bcinr_bridge.candidate_measures(c)}
            for c in canonical
        ]
    }
    wasm_payload = bcinr_wasm.call_rank(request)
    cli_payload = bcinr_bridge._call_cli(request, cli, 15.0)
    assert json.dumps(wasm_payload, sort_keys=True) == json.dumps(
        cli_payload, sort_keys=True
    )
    assert "error" not in wasm_payload


@requires_wasm
def test_wasm_transport_deterministic_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BCINR_CMCA_TRANSPORT", "wasm")
    candidates = _candidates()
    first = bcinr_bridge.rank_candidates(candidates)
    second = bcinr_bridge.rank_candidates(candidates)
    assert first == second
    assert first  # non-empty


@requires_wasm
def test_default_engine_end_to_end_through_wasm_conserves_prime_budget() -> None:
    """The default ``bcinr`` engine, served by the WASM transport, must
    conserve discrete budgets exactly as the CLI path does (Theorem-1-style
    floor conservation, now over the certified kernel's shares)."""
    allocator = MultifractalCascadeAllocator()  # engine="bcinr" default
    prime_ticks, prime_mem = 104729, 655363
    plan = allocator.allocate(
        plan_id="wasm_e2e",
        budget=ResourceBudget(
            total_ticks=prime_ticks,
            memory_bytes=prime_mem,
            max_verification_depth=6,
            consequence_risk_budget=0.5,
            concurrency_lanes=4,
        ),
        candidates=_candidates(),
    )
    total_ticks = sum(a.allocated_ticks for a in plan.allocations)
    total_mem = sum(a.allocated_memory_bytes for a in plan.allocations)
    admitted = [
        a for a in plan.allocations if a.standing == AllocationStanding.ADMITTED
    ]
    assert total_ticks <= prime_ticks
    assert total_mem <= prime_mem
    assert prime_ticks - total_ticks <= len(admitted)
    assert admitted, "anti-starvation: at least one admitted branch"
    assert sum(a.allocated_fraction for a in admitted) == pytest.approx(1.0, rel=1e-6)


@requires_wasm
def test_wasm_serves_rank_candidates_with_cli_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WASM-first independence: with no CLI binary resolvable at all, the
    default transport order still answers through WASM alone."""
    monkeypatch.setattr(bcinr_bridge, "find_bcinr_cli", lambda: None)
    candidates = _candidates()
    shares = bcinr_bridge.rank_candidates(candidates)
    assert set(shares) == {c.branch_id for c in candidates}
    assert sum(shares.values()) == pytest.approx(1.0, rel=1e-9)


def test_cardinality_refusal_precedes_any_transport() -> None:
    """N=8 is a property of the compiled allocator shape, not of a
    transport: 9 candidates must refuse without invoking either one."""
    with pytest.raises(bcinr_bridge.BcinrCardinalityRefusal):
        bcinr_bridge.rank_candidates(_candidates(9))


def test_unknown_transport_value_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BCINR_CMCA_TRANSPORT", "carrier-pigeon")
    with pytest.raises(bcinr_bridge.BcinrProtocolError, match="BCINR_CMCA_TRANSPORT"):
        bcinr_bridge.rank_candidates(_candidates())


@requires_wasm
def test_forced_wasm_with_missing_artifact_refuses_not_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forced-but-absent transport is a typed refusal, never a silent
    switch to the CLI."""
    monkeypatch.setenv("BCINR_CMCA_TRANSPORT", "wasm")
    monkeypatch.setenv("BCINR_CMCA_WASM", "/nonexistent/bcinr_cmca_wasm.wasm")
    with pytest.raises(bcinr_wasm.BcinrWasmModuleMissing):
        bcinr_bridge.rank_candidates(_candidates())
