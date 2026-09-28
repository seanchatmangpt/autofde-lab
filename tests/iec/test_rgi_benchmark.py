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


def test_edge_universe_identity_is_set_stable_across_orderings() -> None:
    rows = [event(0, "e1"), event(1, "e2"), event(2, "e3")]
    reference = trace(
        "MACHINE_SERIAL",
        rows,
        universe=["e1", "e2", "e3"],
    )
    candidate = trace(
        "ZERO_LLM",
        rows,
        universe=["e3", "e1", "e2"],
    )
    result = compare_runs(reference, candidate, fidelity_receipt=fidelity())
    assert result["gate"] == "PASS"
    assert (
        result["reference"]["edge_universe_id"]
        == result["candidate"]["edge_universe_id"]
    )


def test_v2_trace_requires_exact_producer_and_canonical_universe_binding() -> None:
    rows = [event(0, "e1"), event(1, "e2"), event(2, "e3")]
    base = trace("ZERO_LLM", rows, universe=["e3", "e1", "e2"])
    universe_id = benchmark_trace(base)["edge_universe_id"]
    v2 = {
        **base,
        "schema": "autofde-lab.rgi-trace/2",
        "producer_digest": "sha256:" + "a" * 64,
        "edge_universe_id": universe_id,
    }
    report = benchmark_trace(v2)
    assert report["trace_schema"] == "autofde-lab.rgi-trace/2"
    assert report["producer_digest"] == "sha256:" + "a" * 64

    missing_producer = dict(v2)
    missing_producer.pop("producer_digest")
    with pytest.raises(IECRefusal, match="v2 trace requires producer_digest"):
        benchmark_trace(missing_producer)

    forged_universe = dict(v2)
    forged_universe["edge_universe_id"] = "sha256:" + "f" * 64
    with pytest.raises(IECRefusal, match="edge_universe_id does not match"):
        benchmark_trace(forged_universe)


def test_retirement_standing_is_evidence_bound_not_inferred_from_zero_llm() -> None:
    rows = [event(0, "e1"), event(1, "e2"), event(2, "e3")]
    reference = trace("MACHINE_SERIAL", rows)
    base_candidate = trace("ZERO_LLM", rows)
    universe_id = benchmark_trace(base_candidate)["edge_universe_id"]
    producer = "sha256:" + "b" * 64
    candidate = {
        **base_candidate,
        "schema": "autofde-lab.rgi-trace/2",
        "producer_digest": producer,
        "edge_universe_id": universe_id,
    }

    observed_only = compare_runs(
        reference,
        candidate,
        fidelity_receipt=fidelity(),
    )
    assert observed_only["retirement_standing"]["standing"] == (
        "OBSERVED_MACHINE_ONLY"
    )

    retired = compare_runs(
        reference,
        candidate,
        fidelity_receipt=fidelity(),
        retirement_receipt={
            "subject": SUBJECT,
            "workload_id": WORKLOAD,
            "verdict": "PASS",
            "standing": "RETIRED_FROM_LLM",
            "ledger_entry_id": "iec-c3:rc-example",
            "verifier_set_id": "court:iec-c3:v26.9.25",
            "evidence_digest": "sha256:" + "c" * 64,
            "producer_digest": producer,
        },
    )
    assert retired["retirement_standing"] == {
        "standing": "RETIRED_FROM_LLM",
        "ledger_entry_id": "iec-c3:rc-example",
        "verifier_set_id": "court:iec-c3:v26.9.25",
        "evidence_digest": "sha256:" + "c" * 64,
        "producer_digest": producer,
    }


def test_machine_only_mode_emits_typed_mode_falsifiers() -> None:
    report = benchmark_trace(
        trace(
            "ZERO_LLM",
            [
                event(
                    0,
                    "e1",
                    executor="GENERAL_LLM",
                    route_state="KNOWN",
                    phase="DO",
                    llm_tokens=3,
                ),
                event(1, "e2"),
                event(2, "e3"),
            ],
        )
    )
    assert report["mode_falsifiers"] == [
        "GENERAL_LLM_OUTSIDE_UNKNOWN_REGION",
        "GENERAL_LLM_IN_DO",
        "UNRECEIPTED_DO",
        "GENERAL_LLM_PRESENT_IN_NON_LLM_MODE",
    ]


def test_dspy_wasm_is_bounded_candidate_executor_not_retirement_endpoint() -> None:
    rows = [
        event(0, "e1", executor="DSPY_WASM", route_state="KNOWN"),
        event(1, "e2", executor="DSPY_WASM", route_state="KNOWN"),
        event(2, "e3", executor="MACHINE", route_state="ADMITTED"),
    ]
    reference = trace("MACHINE_SERIAL", [event(0, "e1"), event(1, "e2"), event(2, "e3")])
    candidate = trace("DSPY_WASM_CANDIDATE", rows)
    report = benchmark_trace(candidate)
    assert report["metrics"]["llm_edge_executions"] == 0
    assert report["metrics"]["dspy_wasm_edge_executions"] == 2
    assert report["metrics"]["machine_edge_executions"] == 1
    assert report["metrics"]["zero_general_llm_observed"] is True
    assert report["metrics"]["machine_only_observed"] is False
    assert report["mode_falsifiers"] == []

    comparison = compare_runs(
        reference,
        candidate,
        fidelity_receipt=fidelity(),
    )
    assert comparison["retirement_standing"]["standing"] == (
        "OBSERVED_BOUNDED_NON_LLM_ONLY"
    )


def test_dspy_wasm_cannot_be_promoted_to_retired_by_receipt_alone() -> None:
    rows = [
        event(0, "e1", executor="DSPY_WASM", route_state="KNOWN"),
        event(1, "e2", executor="MACHINE", route_state="ADMITTED"),
        event(2, "e3", executor="MACHINE", route_state="ADMITTED"),
    ]
    reference = trace("MACHINE_SERIAL", [event(0, "e1"), event(1, "e2"), event(2, "e3")])
    base = trace("DSPY_WASM_CANDIDATE", rows)
    universe_id = benchmark_trace(base)["edge_universe_id"]
    producer = "sha256:" + "d" * 64
    candidate = {
        **base,
        "schema": "autofde-lab.rgi-trace/2",
        "producer_digest": producer,
        "edge_universe_id": universe_id,
    }
    result = compare_runs(
        reference,
        candidate,
        fidelity_receipt=fidelity(),
        retirement_receipt={
            "subject": SUBJECT,
            "workload_id": WORKLOAD,
            "verdict": "PASS",
            "standing": "RETIRED_FROM_LLM",
            "ledger_entry_id": "iec-c3:attempt",
            "verifier_set_id": "court:iec-c3:v26.9.25",
            "evidence_digest": "sha256:" + "e" * 64,
            "producer_digest": producer,
        },
    )
    assert result["retirement_standing"]["standing"] == "COUNTEREXAMPLE"
    assert "MACHINE-only" in result["retirement_standing"]["reason"]


def test_machine_mode_refuses_bounded_executor_residue() -> None:
    report = benchmark_trace(
        trace(
            "MACHINE_SERIAL",
            [
                event(0, "e1", executor="DSPY_WASM"),
                event(1, "e2"),
                event(2, "e3"),
            ],
        )
    )
    assert report["mode_falsifiers"] == [
        "BOUNDED_EXECUTOR_PRESENT_IN_MACHINE_MODE"
    ]
