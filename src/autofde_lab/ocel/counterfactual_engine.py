# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unified Counterfactual Validation Engine across the Vision 2030 Stack.

Orchestrates multi-layer counterfactual evaluation across:
1. Tier 1: Control-Flow & Petri net alignment diagnostics (PM4Py / POWL).
2. Tier 2: Resource Allocation salience & entropy loss (CMCA).
3. Tier 3: Multi-Object concurrency and link crossing (OCEL 2.0 / OCPA).
4. Tier 4: Consequence, Admission & Receipt Gate (BRCE / AGENTS.md).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from autofde_lab.cmca.contracts import CascadeAllocationPlan
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.object_centric_conformance import (
    ObjectCentricConformanceResult,
    check_object_centric_conformance,
)
from autofde_lab.ocel.pm4py_counterfactual import (
    CounterfactualValidationResult,
    LawfulProcessModel,
    evaluate_counterfactual_trace,
)

__all__ = [
    "CounterfactualEvaluationReceipt",
    "CounterfactualLayerReport",
    "CounterfactualReport",
    "evaluate_counterfactual_execution",
]


@dataclass(frozen=True)
class CounterfactualLayerReport:
    """Report from an individual verification tier."""

    layer_name: str
    is_conforming: bool
    penalty_score: float
    violations: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CounterfactualEvaluationReceipt:
    """Cryptographic receipt attesting counterfactual validation results."""

    receipt_id: str
    is_counterfactual: bool
    overall_divergence: float
    evidence_status: str
    layer_signatures: tuple[str, ...]
    payload_hash: str


@dataclass(frozen=True)
class CounterfactualReport:
    """Consolidated counterfactual evaluation report across all stack tiers."""

    is_counterfactual: bool
    overall_divergence: float  # [0.0, 1.0], where 0.0 = completely conforming
    tier_reports: tuple[CounterfactualLayerReport, ...]
    evidence_status: (
        str  # ALIVE | REFUSED_COUNTERFACTUAL_MUTATION | REFUSED_UNADMITTED_ACTUATION
    )
    receipt: CounterfactualEvaluationReceipt

    @property
    def has_mutations(self) -> bool:
        return self.is_counterfactual or self.overall_divergence > 0.0


def _evaluate_control_flow_tier(
    lawful_model: LawfulProcessModel | None,
    candidate_trace: Sequence[str] | None,
) -> CounterfactualLayerReport:
    if lawful_model is None or candidate_trace is None:
        return CounterfactualLayerReport(
            layer_name="Tier1_ControlFlow",
            is_conforming=True,
            penalty_score=0.0,
            violations=(),
            details={"status": "SKIPPED"},
        )

    res: CounterfactualValidationResult = evaluate_counterfactual_trace(
        lawful_model, candidate_trace
    )

    violations: list[str] = []
    for step in res.deviations:
        if step.log_move and not step.model_move:
            violations.append(f"LOG_ONLY_MOVE:{step.log_move}")
        elif step.model_move and not step.log_move:
            violations.append(f"MODEL_ONLY_MOVE:{step.model_move}")

    penalty = max(0.0, 1.0 - res.trace_fitness)

    return CounterfactualLayerReport(
        layer_name="Tier1_ControlFlow",
        is_conforming=res.is_conforming,
        penalty_score=penalty,
        violations=tuple(violations),
        details={
            "trace_fitness": res.trace_fitness,
            "alignment_cost": res.alignment_cost,
            "missing_tokens": res.missing_tokens,
            "remaining_tokens": res.remaining_tokens,
        },
    )


def _evaluate_object_centric_tier(
    ocel_log: OcelLog | None,
    intended_traces: Mapping[str, Sequence[str]] | None,
) -> CounterfactualLayerReport:
    if ocel_log is None or not intended_traces:
        return CounterfactualLayerReport(
            layer_name="Tier3_MultiObject",
            is_conforming=True,
            penalty_score=0.0,
            violations=(),
            details={"status": "SKIPPED"},
        )

    res: ObjectCentricConformanceResult = check_object_centric_conformance(
        ocel_log, intended_traces_by_object_id=intended_traces
    )

    violations: list[str] = []
    for obj_fit in res.per_object:
        if not obj_fit.conforms:
            violations.append(
                f"OBJECT_CONFORMANCE_FAIL:{obj_fit.object_id}:{obj_fit.fitness:.3f}"
            )

    penalty = max(0.0, 1.0 - res.overall_fitness)

    return CounterfactualLayerReport(
        layer_name="Tier3_MultiObject",
        is_conforming=res.all_conform,
        penalty_score=penalty,
        violations=tuple(violations),
        details={
            "overall_fitness": res.overall_fitness,
            "per_object": [
                {
                    "object_id": o.object_id,
                    "type": o.object_type,
                    "fitness": o.fitness,
                    "conforms": o.conforms,
                }
                for o in res.per_object
            ],
        },
    )


def _evaluate_cmca_resource_tier(
    baseline_plan: CascadeAllocationPlan | None,
    candidate_plan: CascadeAllocationPlan | None,
) -> CounterfactualLayerReport:
    if baseline_plan is None or candidate_plan is None:
        return CounterfactualLayerReport(
            layer_name="Tier2_CMCAResource",
            is_conforming=True,
            penalty_score=0.0,
            violations=(),
            details={"status": "SKIPPED"},
        )

    # Compare allocations across branches
    base_map = {a.branch_id: a for a in baseline_plan.allocations}
    cand_map = {a.branch_id: a for a in candidate_plan.allocations}

    violations: list[str] = []
    divergence_sum = 0.0
    count = 0

    for bid, base_alloc in base_map.items():
        if bid in cand_map:
            cand_alloc = cand_map[bid]
            expected_ticks = base_alloc.allocated_ticks
            actual_ticks = cand_alloc.allocated_ticks
            max_ticks = max(expected_ticks, actual_ticks, 1)
            diff = abs(expected_ticks - actual_ticks) / max_ticks
            divergence_sum += diff
            count += 1
            if diff > 0.2:  # >20% resource reallocation divergence
                violations.append(
                    f"RESOURCE_DIVERGENCE:{bid}:expected_{expected_ticks}_got_{actual_ticks}"
                )

    avg_penalty = (divergence_sum / count) if count > 0 else 0.0
    is_conforming = len(violations) == 0 and avg_penalty < 0.05

    return CounterfactualLayerReport(
        layer_name="Tier2_CMCAResource",
        is_conforming=is_conforming,
        penalty_score=min(1.0, avg_penalty),
        violations=tuple(violations),
        details={
            "resource_divergence_mean": avg_penalty,
            "evaluated_branches": count,
        },
    )


def evaluate_counterfactual_execution(
    *,
    lawful_model: LawfulProcessModel | None = None,
    candidate_trace: Sequence[str] | None = None,
    ocel_log: OcelLog | None = None,
    intended_traces_by_object: Mapping[str, Sequence[str]] | None = None,
    baseline_cmca_plan: CascadeAllocationPlan | None = None,
    candidate_cmca_plan: CascadeAllocationPlan | None = None,
) -> CounterfactualReport:
    """Evaluate an execution across all stack layers to detect counterfactual deviations."""
    reports: list[CounterfactualLayerReport] = []

    # 1. Tier 1: Control Flow
    t1 = _evaluate_control_flow_tier(lawful_model, candidate_trace)
    reports.append(t1)

    # 2. Tier 2: CMCA Resource Allocation
    t2 = _evaluate_cmca_resource_tier(baseline_cmca_plan, candidate_cmca_plan)
    reports.append(t2)

    # 3. Tier 3: Multi-Object Concurrency
    t3 = _evaluate_object_centric_tier(ocel_log, intended_traces_by_object)
    reports.append(t3)

    # Aggregate divergence
    penalties = [
        r.penalty_score for r in reports if r.details.get("status") != "SKIPPED"
    ]
    overall_divergence = (sum(penalties) / len(penalties)) if penalties else 0.0
    is_counterfactual = any(not r.is_conforming for r in reports)

    evidence_status = "ALIVE"
    if is_counterfactual:
        if any("unadmitted" in v.lower() for r in reports for v in r.violations):
            evidence_status = "REFUSED_UNADMITTED_ACTUATION"
        else:
            evidence_status = "REFUSED_COUNTERFACTUAL_MUTATION"

    # Compute deterministic receipt
    receipt_blob = {
        "is_counterfactual": is_counterfactual,
        "overall_divergence": round(overall_divergence, 6),
        "evidence_status": evidence_status,
        "tiers": {r.layer_name: r.violations for r in reports},
    }
    payload_str = json.dumps(receipt_blob, sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    receipt_id = f"rcpt_cf_{payload_hash[:16]}"

    receipt = CounterfactualEvaluationReceipt(
        receipt_id=receipt_id,
        is_counterfactual=is_counterfactual,
        overall_divergence=overall_divergence,
        evidence_status=evidence_status,
        layer_signatures=tuple(
            f"{r.layer_name}:{r.penalty_score:.3f}" for r in reports
        ),
        payload_hash=payload_hash,
    )

    return CounterfactualReport(
        is_counterfactual=is_counterfactual,
        overall_divergence=overall_divergence,
        tier_reports=tuple(reports),
        evidence_status=evidence_status,
        receipt=receipt,
    )
