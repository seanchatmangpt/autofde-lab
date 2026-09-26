"""KREX-shaped Region-Granular Intelligence benchmark tests."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.rgi import benchmark_trace, compare_runs, main

SUBJECT = "git:seanchatmangpt/autofde-lab@0123456789abcdef"
WORKLOAD = "sha256:fixed-command-stream"


def event(
    sequence: int,
    edge_id: str,
    *,
    executor: str = "MACHINE",
    route_state: str = "KNOWN",
    phase: str = "SELECT",
    duration_ms: float = 1.0,
    llm_tokens: int = 0,
    reasoning_class: str = "RC-EXAMPLE",
    receipt_id: str | None = None,
) -> dict:
    return {
        "sequence": sequence,
        "edge_id": edge_id,
        "reasoning_class": reasoning_class,
        "executor": executor,
        "route_state": route_state,
        "phase": phase,
        "duration_ms": duration_ms,
        "llm_tokens": llm_tokens,
        "receipt_id": receipt_id,
    }


def trace(
    mode: str,
    events: list[dict],
    *,
    wall: float = 10.0,
    universe: list[str] | None = None,
    ranking: list[str] | None = None,
    subject: str = SUBJECT,
    workload: str = WORKLOAD,
) -> dict:
    return {
        "schema": "autofde-lab.rgi-trace/1",
        "subject": subject,
        "workload_id": workload,
        "mode": mode,
        "run_wall_ms": wall,
        "edge_universe": universe or ["e1", "e2", "e3"],
        "ranking": ranking,
        "events": events,
    }


def fidelity(verdict: str = "PASS") -> dict:
    return {
        "subject": SUBJECT,
        "verdict": verdict,
        "verifier_set_id": "sha256:typed-fidelity-court",
        "receipt_id": "sha256:fidelity-receipt",
        "claim": "TYPED_OUTCOME_EQUIVALENT_FOR_EXACT_SUBJECT",
    }


def test_region_hybrid_measures_run_scoped_dependency_without_leakage() -> None:
    report = benchmark_trace(
        trace(
            "REGION_HYBRID",
            [
                event(0, "e1", phase="OBSERVE"),
                event(
                    1,
                    "e2",
                    executor="GENERAL_LLM",
                    route_state="UNKNOWN",
                    phase="CONSTRUCT",
                    duration_ms=6,
                    llm_tokens=40,
                    reasoning_class="RC-NOVEL",
                ),
                event(2, "e3", phase="VERIFY"),
            ],
        )
    )
    assert report["coverage"]["verdict"] == "PASS"
    assert report["metrics"]["llm_edge_executions"] == 1
    assert report["metrics"]["llm_dependency_ratio"] == {
        "value": 1 / 3,
        "scope": SUBJECT,
        "standing": "OBSERVED_RUN_SCOPE",
    }
    assert report["metrics"]["llm_leakage_count"] == 0
    assert report["retirement_frontier"] == {"RC-NOVEL": 1}
    assert report["metrics"]["llm_tokens"] == 40


def test_llm_on_known_edge_is_leakage_and_llm_do_is_separate_violation() -> None:
    report = benchmark_trace(
        trace(
            "REGION_HYBRID",
            [
                event(
                    0,
                    "e1",
                    executor="GENERAL_LLM",
                    route_state="KNOWN",
                    phase="SELECT",
                    llm_tokens=2,
                ),
                event(
                    1,
                    "e2",
                    executor="GENERAL_LLM",
                    route_state="UNKNOWN",
                    phase="DO",
                    llm_tokens=2,
                ),
                event(2, "e3", phase="VERIFY"),
            ],
        )
    )
    assert report["metrics"]["llm_leakage_count"] == 2
    assert report["metrics"]["llm_do_count"] == 1
    assert report["metrics"]["unreceipted_do_count"] == 1


def test_zero_llm_mode_passes_only_with_typed_fidelity_and_reports_ranking_noise() -> None:
    reference = trace(
        "LLM_NATIVE",
        [
            event(0, "e1", phase="OBSERVE"),
            event(
                1,
                "e2",
                executor="GENERAL_LLM",
                route_state="UNKNOWN",
                phase="SELECT",
                duration_ms=8,
                llm_tokens=100,
            ),
            event(2, "e3", phase="VERIFY"),
        ],
        wall=20,
        ranking=["a", "b", "c"],
    )
    candidate = trace(
        "ZERO_LLM",
        [
            event(0, "e1", phase="OBSERVE"),
            event(1, "e2", phase="SELECT"),
            event(2, "e3", phase="VERIFY"),
        ],
        wall=10,
        ranking=["a", "c", "b"],
    )
    result = compare_runs(
        reference,
        candidate,
        fidelity_receipt=fidelity(),
    )
    assert result["gate"] == "PASS"
    assert result["falsifiers"] == []
    assert result["candidate"]["metrics"]["zero_llm_observed"] is True
    assert result["delta"]["llm_tokens"] == -100
    assert result["delta"]["speedup"] == 2.0
    ranking = result["ranking_preservation"]
    assert ranking["standing"] == "OBSERVED"
    assert ranking["shared_candidates"] == 3
    assert ranking["pairs"] == 3
    assert ranking["flips"] == 1
    assert ranking["pairwise_flip_rate"] == pytest.approx(1 / 3)
    assert ranking["kendall_tau"] == pytest.approx(1 / 3)
    assert result["retirement"].startswith("UNCHANGED:")


def test_zero_llm_is_not_semantic_equivalence_without_fidelity_receipt() -> None:
    rows = [event(0, "e1"), event(1, "e2"), event(2, "e3")]
    result = compare_runs(
        trace("MACHINE_SERIAL", rows),
        trace("ZERO_LLM", rows),
    )
    assert result["gate"] == "COUNTEREXAMPLE"
    assert result["falsifiers"] == ["SEMANTIC_FIDELITY_NOT_PASS"]
    assert result["fidelity"]["verdict"] == "UNSUPPORTED"


def test_incomplete_edge_universe_does_not_invent_dependency_denominator() -> None:
    report = benchmark_trace(
        trace(
            "MACHINE_SERIAL",
            [event(0, "e1"), event(1, "e2")],
            universe=["e1", "e2", "e3"],
        )
    )
    assert report["coverage"]["verdict"] == "COUNTEREXAMPLE"
    assert report["coverage"]["missing"] == ["e3"]
    assert report["metrics"]["llm_dependency_ratio"]["value"].startswith(
        "UNREPRESENTABLE:"
    )


def test_compare_refuses_subject_or_workload_drift() -> None:
    rows = [event(0, "e1"), event(1, "e2"), event(2, "e3")]
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        compare_runs(
            trace("LLM_NATIVE", rows),
            trace(
                "ZERO_LLM",
                rows,
                subject="git:other/repo@sha",
            ),
            fidelity_receipt=fidelity(),
        )
    with pytest.raises(
        IECRefusal,
        match="REFUSED_WORKLOAD_MISMATCH",
    ):
        compare_runs(
            trace("LLM_NATIVE", rows),
            trace(
                "ZERO_LLM",
                rows,
                workload="sha256:different",
            ),
            fidelity_receipt=fidelity(),
        )


def test_machine_executor_cannot_hide_llm_tokens() -> None:
    with pytest.raises(
        IECRefusal,
        match="machine edge e1 reports 1 LLM tokens",
    ):
        benchmark_trace(
            trace(
                "MACHINE_SERIAL",
                [
                    event(0, "e1", llm_tokens=1),
                    event(1, "e2"),
                    event(2, "e3"),
                ],
            )
        )


def test_cli_gate_writes_deterministic_receipt(tmp_path) -> None:
    rows = [event(0, "e1"), event(1, "e2"), event(2, "e3")]
    ref_path = tmp_path / "reference.json"
    cand_path = tmp_path / "candidate.json"
    fidelity_path = tmp_path / "fidelity.json"
    out_path = tmp_path / "rgi.json"
    ref_path.write_text(
        json.dumps(trace("MACHINE_SERIAL", rows)),
        encoding="utf-8",
    )
    cand_path.write_text(
        json.dumps(trace("ZERO_LLM", rows)),
        encoding="utf-8",
    )
    fidelity_path.write_text(
        json.dumps(fidelity()),
        encoding="utf-8",
    )

    assert (
        main(
            [
                str(ref_path),
                str(cand_path),
                str(out_path),
                "--fidelity-receipt",
                str(fidelity_path),
                "--gate",
            ]
        )
        == 0
    )
    first = out_path.read_bytes()
    assert (
        main(
            [
                str(ref_path),
                str(cand_path),
                str(out_path),
                "--fidelity-receipt",
                str(fidelity_path),
            ]
        )
        == 0
    )
    assert out_path.read_bytes() == first
