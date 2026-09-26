"""Region-Granular Intelligence (RGI) benchmark for non-LLM execution.

KREX-shaped protocol: keep an exact workload fixed, vary execution strategy,
measure throughput and fidelity together, and never infer semantic preservation
from speed or from the absence of an LLM call.

RGI consumes observed semantic-edge traces. It does not execute subjects and it
does not retire reasoning classes. Retirement remains owned by IEC-C3.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import IECRefusal, Verdict, canonical_json, content_id

__all__ = [
    "BENCHMARK_SCHEMA",
    "TRACE_SCHEMA",
    "TRACE_SCHEMA_V2",
    "EdgeExecution",
    "benchmark_trace",
    "compare_runs",
    "main",
]

TRACE_SCHEMA = "autofde-lab.rgi-trace/1"
TRACE_SCHEMA_V2 = "autofde-lab.rgi-trace/2"
SUPPORTED_TRACE_SCHEMAS = frozenset({TRACE_SCHEMA, TRACE_SCHEMA_V2})
BENCHMARK_SCHEMA = "autofde-lab.rgi-benchmark/1"

MODES = {"LLM_NATIVE", "MACHINE_SERIAL", "REGION_HYBRID", "ZERO_LLM"}
EXECUTORS = {"GENERAL_LLM", "MACHINE"}
ROUTE_STATES = {"UNKNOWN", "KNOWN", "ADMITTED"}
PHASES = {"OBSERVE", "SELECT", "CONSTRUCT", "DO", "VERIFY"}
LLM_ALLOWED_PHASES = {"OBSERVE", "SELECT", "CONSTRUCT"}


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _nonnegative_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IECRefusal("REFUSED_INVALID_RGI_TRACE", f"{name} must be numeric")
    value = float(value)
    if value < 0:
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE", f"{name} must be non-negative"
        )
    return value


def _validate_sha256_digest(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE", f"{name} must be a sha256 digest"
        )
    digest = value.strip().lower()
    payload = digest.removeprefix("sha256:")
    if (
        not digest.startswith("sha256:")
        or len(payload) != 64
        or any(ch not in "0123456789abcdef" for ch in payload)
    ):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            f"{name} must be sha256:<64 lowercase hex>",
        )
    return digest


def _edge_universe_identity(universe: Sequence[str]) -> str:
    """Order-independent identity for the semantic edge set."""
    return content_id(sorted(universe))


@dataclass(frozen=True)
class EdgeExecution:
    sequence: int
    edge_id: str
    reasoning_class: str
    executor: str
    route_state: str
    phase: str
    duration_ms: float
    llm_tokens: int
    receipt_id: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "EdgeExecution":
        sequence = row.get("sequence")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 0
        ):
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE",
                "event sequence must be a non-negative integer",
            )
        edge_id = str(row.get("edge_id", "")).strip()
        if not edge_id:
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE", "event edge_id is empty"
            )
        reasoning_class = (
            str(row.get("reasoning_class", "UNKNOWN")).strip() or "UNKNOWN"
        )
        executor = str(row.get("executor", ""))
        route_state = str(row.get("route_state", ""))
        phase = str(row.get("phase", ""))
        if executor not in EXECUTORS:
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE", f"unknown executor {executor!r}"
            )
        if route_state not in ROUTE_STATES:
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE",
                f"unknown route_state {route_state!r}",
            )
        if phase not in PHASES:
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE", f"unknown phase {phase!r}"
            )
        duration_ms = _nonnegative_number(
            row.get("duration_ms", 0), "duration_ms"
        )
        llm_tokens = row.get("llm_tokens", 0)
        if (
            isinstance(llm_tokens, bool)
            or not isinstance(llm_tokens, int)
            or llm_tokens < 0
        ):
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE",
                "llm_tokens must be a non-negative integer",
            )
        if executor == "MACHINE" and llm_tokens:
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE",
                f"machine edge {edge_id} reports {llm_tokens} LLM tokens",
            )
        receipt = row.get("receipt_id")
        receipt_id = None if receipt is None else str(receipt).strip() or None
        return cls(
            sequence=sequence,
            edge_id=edge_id,
            reasoning_class=reasoning_class,
            executor=executor,
            route_state=route_state,
            phase=phase,
            duration_ms=duration_ms,
            llm_tokens=llm_tokens,
            receipt_id=receipt_id,
        )

    @property
    def llm_leakage(self) -> bool:
        if self.executor != "GENERAL_LLM":
            return False
        return (
            self.route_state != "UNKNOWN"
            or self.phase not in LLM_ALLOWED_PHASES
        )

    @property
    def llm_do(self) -> bool:
        return self.executor == "GENERAL_LLM" and self.phase == "DO"

    @property
    def unreceipted_do(self) -> bool:
        return self.phase == "DO" and self.receipt_id is None


def _parse_trace(
    document: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[EdgeExecution, ...]]:
    trace_schema = str(document.get("schema", ""))
    if trace_schema not in SUPPORTED_TRACE_SCHEMAS:
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "schema must be one of "
            f"{sorted(SUPPORTED_TRACE_SCHEMAS)!r}, got {trace_schema!r}",
        )
    subject = str(document.get("subject", "")).strip()
    workload_id = str(document.get("workload_id", "")).strip()
    mode = str(document.get("mode", ""))
    if not subject or not workload_id:
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "subject and workload_id are required",
        )
    if mode not in MODES:
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE", f"unknown mode {mode!r}"
        )
    run_wall_ms = _nonnegative_number(
        document.get("run_wall_ms", 0), "run_wall_ms"
    )

    producer_digest: str | None = None
    if document.get("producer_digest") is not None:
        producer_digest = _validate_sha256_digest(
            document.get("producer_digest"), "producer_digest"
        )
    if trace_schema == TRACE_SCHEMA_V2 and producer_digest is None:
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "v2 trace requires producer_digest",
        )

    universe_raw = document.get("edge_universe", ())
    if not isinstance(universe_raw, list):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE", "edge_universe must be a list"
        )
    universe = tuple(sorted(str(edge).strip() for edge in universe_raw))
    if (
        any(not edge for edge in universe)
        or len(universe) != len(set(universe))
    ):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "edge_universe must contain unique non-empty ids",
        )
    edge_universe_id = _edge_universe_identity(universe)
    declared_universe_id = document.get("edge_universe_id")
    if trace_schema == TRACE_SCHEMA_V2 and declared_universe_id != edge_universe_id:
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "edge_universe_id does not match the canonical edge set",
        )
    if (
        trace_schema != TRACE_SCHEMA_V2
        and declared_universe_id is not None
        and declared_universe_id != edge_universe_id
    ):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "edge_universe_id does not match the canonical edge set",
        )

    rows = document.get("events")
    if not isinstance(rows, list):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE", "events must be a list"
        )
    events = tuple(
        sorted(
            (EdgeExecution.from_mapping(row) for row in rows),
            key=lambda event: event.sequence,
        )
    )
    sequences = [event.sequence for event in events]
    if len(sequences) != len(set(sequences)):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "event sequence values must be unique",
        )
    if sequences and sequences != list(
        range(sequences[0], sequences[0] + len(sequences))
    ):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            "event sequence must be contiguous",
        )

    ranking_raw = document.get("ranking")
    ranking: tuple[str, ...] | None = None
    if ranking_raw is not None:
        if not isinstance(ranking_raw, list):
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE", "ranking must be a list"
            )
        ranking = tuple(str(value) for value in ranking_raw)
        if len(ranking) != len(set(ranking)):
            raise IECRefusal(
                "REFUSED_INVALID_RGI_TRACE",
                "ranking contains duplicates",
            )

    return (
        {
            "trace_schema": trace_schema,
            "subject": subject,
            "workload_id": workload_id,
            "mode": mode,
            "run_wall_ms": run_wall_ms,
            "producer_digest": producer_digest,
            "edge_universe": universe,
            "edge_universe_id": edge_universe_id,
            "ranking": ranking,
        },
        events,
    )


def _coverage(
    universe: Sequence[str], events: Sequence[EdgeExecution]
) -> dict[str, Any]:
    if not universe:
        return {
            "verdict": Verdict.UNSUPPORTED.value,
            "detail": "no run-scoped edge_universe observation",
            "missing": [],
            "outside": [],
        }
    declared = set(universe)
    observed = {event.edge_id for event in events}
    missing = sorted(declared - observed)
    outside = sorted(observed - declared)
    verdict = (
        Verdict.PASS
        if not missing and not outside
        else Verdict.COUNTEREXAMPLE
    )
    return {
        "verdict": verdict.value,
        "detail": (
            f"observed all {len(declared)} declared run-scoped edges"
            if verdict is Verdict.PASS
            else "observed trace does not equal the declared run-scoped edge universe"
        ),
        "missing": missing,
        "outside": outside,
    }


def _mode_falsifiers(
    mode: str, events: Sequence[EdgeExecution]
) -> list[str]:
    llm_events = [event for event in events if event.executor == "GENERAL_LLM"]
    failures: list[str] = []
    if any(event.llm_leakage for event in llm_events):
        failures.append("GENERAL_LLM_OUTSIDE_UNKNOWN_REGION")
    if any(event.llm_do for event in llm_events):
        failures.append("GENERAL_LLM_IN_DO")
    if any(event.unreceipted_do for event in events):
        failures.append("UNRECEIPTED_DO")
    if mode in {"MACHINE_SERIAL", "ZERO_LLM"} and llm_events:
        failures.append("LLM_PRESENT_IN_ZERO_LLM_MODE")
    return failures


def benchmark_trace(document: Mapping[str, Any]) -> dict[str, Any]:
    """Measure one execution mode without turning observation into retirement."""
    header, events = _parse_trace(document)
    coverage = _coverage(header["edge_universe"], events)
    total_duration = sum(event.duration_ms for event in events)
    llm_events = [
        event for event in events if event.executor == "GENERAL_LLM"
    ]
    machine_events = [
        event for event in events if event.executor == "MACHINE"
    ]
    leakage = [event for event in llm_events if event.llm_leakage]
    llm_do = [event for event in llm_events if event.llm_do]
    unreceipted_do = [
        event for event in events if event.unreceipted_do
    ]
    universe = set(header["edge_universe"])
    llm_unique = {event.edge_id for event in llm_events}
    observed_unique = {event.edge_id for event in events}

    dependency = (
        {
            "value": _ratio(len(llm_unique), len(universe)),
            "scope": header["subject"],
            "standing": "OBSERVED_RUN_SCOPE",
        }
        if coverage["verdict"] == Verdict.PASS.value
        else {
            "value": "UNREPRESENTABLE:NO_COMPLETE_RUN_EDGE_UNIVERSE",
            "scope": header["subject"],
            "standing": "UNKNOWN",
        }
    )

    metrics = {
        "edge_executions": len(events),
        "declared_reachable_edges": len(universe),
        "observed_unique_edges": len(observed_unique),
        "llm_edge_executions": len(llm_events),
        "machine_edge_executions": len(machine_events),
        "machine_closed_fraction": _ratio(
            len(machine_events), len(events)
        ),
        "observed_llm_execution_fraction": _ratio(
            len(llm_events), len(events)
        ),
        "llm_dependency_ratio": dependency,
        "llm_wall_fraction": _ratio(
            sum(event.duration_ms for event in llm_events),
            total_duration,
        ),
        "llm_tokens": sum(event.llm_tokens for event in llm_events),
        "llm_leakage_count": len(leakage),
        "llm_leakage_ratio": _ratio(
            len(leakage), len(llm_events)
        ),
        "llm_do_count": len(llm_do),
        "unreceipted_do_count": len(unreceipted_do),
        "throughput_edges_per_second": (
            None
            if header["run_wall_ms"] == 0
            else 1000.0 * len(events) / header["run_wall_ms"]
        ),
        "zero_llm_observed": not llm_events,
    }
    report = {
        "schema": "autofde-lab.rgi-run-report/2",
        "trace_schema": header["trace_schema"],
        "subject": header["subject"],
        "workload_id": header["workload_id"],
        "producer_digest": header["producer_digest"],
        "mode": header["mode"],
        "run_wall_ms": header["run_wall_ms"],
        "edge_universe_id": header["edge_universe_id"],
        "coverage": coverage,
        "metrics": metrics,
        "leakage": [
            {
                "sequence": event.sequence,
                "edge_id": event.edge_id,
                "reasoning_class": event.reasoning_class,
                "route_state": event.route_state,
                "phase": event.phase,
            }
            for event in leakage
        ],
        "mode_falsifiers": _mode_falsifiers(header["mode"], events),
        "retirement_frontier": dict(
            sorted(
                Counter(
                    event.reasoning_class
                    for event in llm_events
                ).items()
            )
        ),
        "ranking": (
            list(header["ranking"])
            if header["ranking"] is not None
            else None
        ),
        "claim_ceiling": (
            "run-scoped execution observation; zero LLM is not "
            "RETIRED_FROM_LLM; retirement requires the IEC-C3 ledger"
        ),
    }
    report["id"] = content_id(report)
    return report


def _ranking_comparison(
    left: Sequence[str] | None,
    right: Sequence[str] | None,
) -> dict[str, Any]:
    if left is None or right is None:
        return {
            "standing": "UNKNOWN",
            "reason": "ranking absent from one or both runs",
        }
    common = sorted(set(left) & set(right))
    if len(common) < 2:
        return {
            "standing": "UNSUPPORTED",
            "reason": "fewer than two shared candidates",
        }
    left_pos = {
        value: index for index, value in enumerate(left)
    }
    right_pos = {
        value: index for index, value in enumerate(right)
    }
    pairs = 0
    flips = 0
    for index, first in enumerate(common):
        for second in common[index + 1 :]:
            pairs += 1
            if (
                left_pos[first] < left_pos[second]
            ) != (
                right_pos[first] < right_pos[second]
            ):
                flips += 1
    flip_rate = _ratio(flips, pairs)
    return {
        "standing": "OBSERVED",
        "shared_candidates": len(common),
        "pairs": pairs,
        "flips": flips,
        "pairwise_flip_rate": flip_rate,
        "kendall_tau": 1.0 - 2.0 * flip_rate,
    }


def _fidelity(
    receipt: Mapping[str, Any] | None,
    subject: str,
) -> dict[str, Any]:
    if receipt is None:
        return {
            "verdict": Verdict.UNSUPPORTED.value,
            "detail": "no typed fidelity court receipt supplied",
        }
    if receipt.get("subject") != subject:
        raise IECRefusal(
            "REFUSED_AMBIGUOUS_AUTHORITY",
            f"fidelity receipt is about "
            f"{receipt.get('subject')!r}, not {subject!r}",
        )
    if (
        not receipt.get("verifier_set_id")
        or not receipt.get("receipt_id")
    ):
        raise IECRefusal(
            "REFUSED_UNBOUNDED_EQUIVALENCE",
            "fidelity receipt must name verifier_set_id and receipt_id",
        )
    verdict = str(
        receipt.get(
            "verdict", Verdict.UNSUPPORTED.value
        )
    )
    if verdict not in {value.value for value in Verdict}:
        raise IECRefusal(
            "REFUSED_UNBOUNDED_EQUIVALENCE",
            f"unknown fidelity verdict {verdict!r}",
        )
    return {
        "verdict": verdict,
        "receipt_id": receipt["receipt_id"],
        "verifier_set_id": receipt["verifier_set_id"],
        "claim": receipt.get("claim", "NOT_VALIDATED"),
    }


def _retirement_standing(
    receipt: Mapping[str, Any] | None,
    *,
    subject: str,
    workload_id: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if receipt is None:
        return {
            "standing": (
                "OBSERVED_ZERO_LLM_ONLY"
                if candidate["metrics"]["zero_llm_observed"]
                else "LLM_OBSERVED"
            ),
            "reason": (
                "zero observed LLM calls are execution evidence, not "
                "RETIRED_FROM_LLM standing"
            ),
        }
    if receipt.get("subject") != subject:
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            "retirement receipt subject does not match benchmark subject",
        )
    if receipt.get("workload_id") != workload_id:
        raise IECRefusal(
            "REFUSED_WORKLOAD_MISMATCH",
            "retirement receipt workload does not match benchmark workload",
        )
    required = (
        "ledger_entry_id",
        "verifier_set_id",
        "evidence_digest",
        "producer_digest",
    )
    missing = [name for name in required if not receipt.get(name)]
    if missing:
        raise IECRefusal(
            "REFUSED_INVALID_RETIREMENT_RECEIPT",
            f"retirement receipt missing {missing!r}",
        )
    evidence_digest = _validate_sha256_digest(
        receipt["evidence_digest"], "retirement.evidence_digest"
    )
    producer_digest = _validate_sha256_digest(
        receipt["producer_digest"], "retirement.producer_digest"
    )
    candidate_producer = candidate.get("producer_digest")
    if candidate_producer is None:
        return {
            "standing": "UNSUPPORTED",
            "reason": "candidate trace does not bind a producer digest",
        }
    if producer_digest != candidate_producer:
        raise IECRefusal(
            "REFUSED_PRODUCER_MISMATCH",
            "retirement receipt producer does not match candidate producer",
        )
    if not candidate["metrics"]["zero_llm_observed"]:
        return {
            "standing": "COUNTEREXAMPLE",
            "reason": "retirement receipt supplied but candidate observed LLM execution",
        }
    if (
        receipt.get("verdict") != Verdict.PASS.value
        or receipt.get("standing") != "RETIRED_FROM_LLM"
    ):
        return {
            "standing": "NOT_RETIRED",
            "reason": "IEC-C3 retirement evidence is not PASS/RETIRED_FROM_LLM",
            "ledger_entry_id": receipt["ledger_entry_id"],
        }
    return {
        "standing": "RETIRED_FROM_LLM",
        "ledger_entry_id": receipt["ledger_entry_id"],
        "verifier_set_id": receipt["verifier_set_id"],
        "evidence_digest": evidence_digest,
        "producer_digest": producer_digest,
    }


def compare_runs(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    fidelity_receipt: Mapping[str, Any] | None = None,
    retirement_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare fixed-workload modes; semantic fidelity is receipt-gated."""
    left = benchmark_trace(reference)
    right = benchmark_trace(candidate)
    if left["subject"] != right["subject"]:
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            f"{left['subject']} != {right['subject']}",
        )
    if left["workload_id"] != right["workload_id"]:
        raise IECRefusal(
            "REFUSED_WORKLOAD_MISMATCH",
            f"{left['workload_id']} != "
            f"{right['workload_id']}",
        )
    if left["edge_universe_id"] != right["edge_universe_id"]:
        raise IECRefusal(
            "REFUSED_WORKLOAD_MISMATCH",
            "declared run-scoped edge universes differ "
            "under the same workload_id",
        )

    fidelity = _fidelity(fidelity_receipt, left["subject"])
    failures: list[str] = []
    if right["coverage"]["verdict"] != Verdict.PASS.value:
        failures.append("CANDIDATE_EDGE_UNIVERSE_NOT_COVERED")
    if fidelity["verdict"] != Verdict.PASS.value:
        failures.append("SEMANTIC_FIDELITY_NOT_PASS")
    for failure in right["mode_falsifiers"]:
        if failure not in failures:
            failures.append(failure)

    retirement_standing = _retirement_standing(
        retirement_receipt,
        subject=left["subject"],
        workload_id=left["workload_id"],
        candidate=right,
    )

    ref_wall = left["run_wall_ms"]
    cand_wall = right["run_wall_ms"]
    comparison = {
        "schema": BENCHMARK_SCHEMA,
        "subject": left["subject"],
        "workload_id": left["workload_id"],
        "reference": left,
        "candidate": right,
        "delta": {
            "llm_execution_fraction": (
                right["metrics"][
                    "observed_llm_execution_fraction"
                ]
                - left["metrics"][
                    "observed_llm_execution_fraction"
                ]
            ),
            "machine_closed_fraction": (
                right["metrics"]["machine_closed_fraction"]
                - left["metrics"]["machine_closed_fraction"]
            ),
            "llm_tokens": (
                right["metrics"]["llm_tokens"]
                - left["metrics"]["llm_tokens"]
            ),
            "speedup": (
                None
                if cand_wall == 0
                else ref_wall / cand_wall
            ),
        },
        "ranking_preservation": _ranking_comparison(
            left["ranking"], right["ranking"]
        ),
        "fidelity": fidelity,
        "falsifiers": failures,
        "gate": (
            Verdict.PASS.value
            if not failures
            else Verdict.COUNTEREXAMPLE.value
        ),
        "retirement": (
            "UNCHANGED:benchmark-observation-does-not-write-"
            "retirement-ledger"
        ),
        "retirement_standing": retirement_standing,
    }
    comparison["id"] = content_id(comparison)
    return comparison


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal(
            "REFUSED_INVALID_RGI_TRACE",
            f"{path} must contain a JSON object",
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0]
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--fidelity-receipt", type=Path)
    parser.add_argument("--retirement-receipt", type=Path)
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)

    receipt = (
        _read(args.fidelity_receipt)
        if args.fidelity_receipt
        else None
    )
    retirement_receipt = (
        _read(args.retirement_receipt)
        if args.retirement_receipt
        else None
    )
    result = compare_runs(
        _read(args.reference),
        _read(args.candidate),
        fidelity_receipt=receipt,
        retirement_receipt=retirement_receipt,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        canonical_json(result) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "id": result["id"],
                "gate": result["gate"],
                "falsifiers": result["falsifiers"],
            }
        )
    )
    return (
        1
        if args.gate
        and result["gate"] != Verdict.PASS.value
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
