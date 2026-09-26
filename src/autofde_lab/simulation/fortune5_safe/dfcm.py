"""DfCM feasibility, diversity, Pareto preservation, and full experiment matrix."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from .engine import run_episode
from .model import (
    AUTOFDE_BASE_SHA,
    DoctrineSpec,
    EpisodeMetrics,
    ExperimentResult,
    Fortune5Config,
    PolicyAggregate,
    PolicyVector,
    Scenario,
    ScenarioName,
    resolve,
    stable_digest,
)
from .space import SCENARIOS, all_policies
from .topology import build_topology
from .worldgen import WorldSample

#: The five feasibility constraints as one pinned table: (constraint name,
#: EpisodeMetrics attribute, PolicyAggregate attribute, bound, upper?).
#: Row-level feasibility (`first_violated_constraint`) and aggregate
#: feasibility (`_is_feasible`) read the same bounds in the same order, so the
#: first violated name is deterministic and single-sourced.
_FEASIBILITY_CHECKS: tuple[tuple[str, str, str, float, bool], ...] = (
    ("reliability", "reliability", "worst_reliability", 0.54, False),
    ("compliance_risk", "compliance_risk", "worst_compliance_risk", 0.40, True),
    ("predictability", "predictability", "mean_predictability", 0.52, False),
    ("budget_variance", "budget_variance", "mean_budget_variance", 0.24, True),
    ("employee_load", "employee_load", "worst_employee_load", 1.55, True),
)


def _constraint_value(item: object, metrics_attr: str, aggregate_attr: str) -> float:
    if isinstance(item, Mapping):
        return float(item[metrics_attr])
    if isinstance(item, EpisodeMetrics):
        return float(getattr(item, metrics_attr))
    return float(getattr(item, aggregate_attr))


def first_violated_constraint(item: object) -> str | None:
    """Name of the first feasibility constraint the metrics violate, else None.

    Accepts an `EpisodeMetrics`, a metrics mapping (e.g. a persisted outcome
    row's `metrics` dict), or a `PolicyAggregate` (worst/mean attributes).
    Checks run in `_FEASIBILITY_CHECKS` order, so "first" is deterministic.
    """
    for name, metrics_attr, aggregate_attr, bound, upper in _FEASIBILITY_CHECKS:
        value = _constraint_value(item, metrics_attr, aggregate_attr)
        if value > bound if upper else value < bound:
            return name
    return None


def _is_feasible(item: PolicyAggregate) -> bool:
    return first_violated_constraint(item) is None


def _dominates(left: PolicyAggregate, right: PolicyAggregate) -> bool:
    left_values = (
        left.mean_throughput,
        left.mean_business_value,
        left.mean_predictability,
        left.worst_reliability,
        -left.worst_compliance_risk,
        -left.mean_lead_time_days,
        -left.mean_coordination_overhead,
        -left.mean_budget_variance,
    )
    right_values = (
        right.mean_throughput,
        right.mean_business_value,
        right.mean_predictability,
        right.worst_reliability,
        -right.worst_compliance_risk,
        -right.mean_lead_time_days,
        -right.mean_coordination_overhead,
        -right.mean_budget_variance,
    )
    return all(a >= b for a, b in zip(left_values, right_values)) and any(
        a > b for a, b in zip(left_values, right_values)
    )


def _pareto_frontier(feasible: Sequence[PolicyAggregate]) -> tuple[str, ...]:
    return tuple(
        sorted(
            candidate.policy.id
            for candidate in feasible
            if not any(
                other.policy.id != candidate.policy.id and _dominates(other, candidate)
                for other in feasible
            )
        )
    )


def _hamming(left: PolicyVector, right: PolicyVector) -> float:
    a = (
        left.priority,
        left.funding,
        left.capacity,
        left.cadence,
        left.architecture,
        left.risk,
    )
    b = (
        right.priority,
        right.funding,
        right.capacity,
        right.cadence,
        right.architecture,
        right.risk,
    )
    return sum(x != y for x, y in zip(a, b)) / len(a)


def _diversity(policies: Sequence[PolicyVector]) -> float:
    if len(policies) < 2:
        return 0.0
    return fmean(
        _hamming(left, right)
        for index, left in enumerate(policies)
        for right in policies[index + 1 :]
    )


def run_full_matrix(
    config: Fortune5Config = Fortune5Config(),
    policies: Sequence[PolicyVector] | None = None,
    scenarios: Sequence[Scenario] = SCENARIOS,
) -> ExperimentResult:
    """Evaluate the lawful policy × disruption product without selecting a winner."""
    topology = build_topology(config)
    policy_space = tuple(policies or all_policies())
    if not policy_space:
        raise ValueError("policy space must be non-empty")
    if not scenarios:
        raise ValueError("scenario space must be non-empty")

    aggregates: list[PolicyAggregate] = []
    episode_receipts: list[str] = []
    for policy in policy_space:
        results = tuple(
            run_episode(policy, scenario, config, topology) for scenario in scenarios
        )
        provisional = PolicyAggregate(
            policy,
            False,
            len(results),
            fmean(r.metrics.throughput for r in results),
            fmean(r.metrics.business_value for r in results),
            fmean(r.metrics.predictability for r in results),
            min(r.metrics.reliability for r in results),
            max(r.metrics.compliance_risk for r in results),
            fmean(r.metrics.lead_time_days for r in results),
            fmean(r.metrics.coordination_overhead for r in results),
            fmean(r.metrics.budget_variance for r in results),
            max(r.metrics.employee_load for r in results),
        )
        aggregates.append(
            PolicyAggregate(
                provisional.policy,
                _is_feasible(provisional),
                provisional.scenario_count,
                provisional.mean_throughput,
                provisional.mean_business_value,
                provisional.mean_predictability,
                provisional.worst_reliability,
                provisional.worst_compliance_risk,
                provisional.mean_lead_time_days,
                provisional.mean_coordination_overhead,
                provisional.mean_budget_variance,
                provisional.worst_employee_load,
            )
        )
        episode_receipts.extend(result.receipt.replay_digest for result in results)

    feasible = tuple(item for item in aggregates if item.feasible)
    feasible_policies = tuple(item.policy for item in feasible)
    frontier = _pareto_frontier(feasible)
    matrix_digest = stable_digest(
        {
            "topology": topology.digest,
            "policy_ids": [policy.id for policy in policy_space],
            "scenario_names": [scenario.name.value for scenario in scenarios],
            "episode_receipts": episode_receipts,
            "frontier": frontier,
        }
    )
    return ExperimentResult(
        len(policy_space),
        len(scenarios),
        len(policy_space) * len(scenarios),
        tuple(sorted(policy.id for policy in feasible_policies)),
        frontier,
        _diversity(feasible_policies),
        matrix_digest,
        tuple(aggregates),
    )


def _world_label(world: Scenario | WorldSample) -> str:
    if isinstance(world, WorldSample):
        return world.world_id
    return world.name.value


def run_outcome_matrix(
    doctrines: Sequence[DoctrineSpec],
    worlds: Sequence[Scenario | WorldSample],
    seeds: Sequence[int],
    config: Fortune5Config = Fortune5Config(),
    output_path: str | Path | None = None,
) -> tuple[dict, ...]:
    """Evaluate arbitrary doctrines over sampled worlds and persist Outcome rows.

    Mirrors `run_full_matrix` but the product is doctrine × world × seed, the
    policies come from `resolve(doctrine)` (so doctrines outside the 2,160
    enum space inject through the same engine fast path), and every episode
    becomes a persisted row pinned to lane RESOLUTIONS #7:
    ``{backend, doctrine_id, world_id, seed, metrics, feasible,
    receipt_digests}``. Rows are returned in a deterministic order (doctrines
    in caller order, worlds in caller order, seeds sorted ascending) and, when
    `output_path` is given, written as NDJSON — one `json.dumps(...,
    sort_keys=True)` object per line. There is no winner field: the matrix is
    evidence, not selection.
    """
    if not doctrines:
        raise ValueError("doctrine space must be non-empty")
    if not worlds:
        raise ValueError("world space must be non-empty")
    if not seeds:
        raise ValueError("seed space must be non-empty")
    topology = build_topology(config)
    ordered_seeds = sorted(int(seed) for seed in seeds)
    rows: list[dict] = []
    for doctrine in doctrines:
        policy = resolve(doctrine)
        for world in worlds:
            for seed in ordered_seeds:
                episode_config = replace(config, seed=seed)
                result = run_episode(policy, world, episode_config, topology)
                metrics = asdict(result.metrics)
                rows.append(
                    {
                        "backend": f"fortune5_safe@{AUTOFDE_BASE_SHA[:12]}",
                        "doctrine_id": doctrine.id,
                        "world_id": _world_label(world),
                        "seed": seed,
                        "metrics": metrics,
                        "feasible": first_violated_constraint(metrics) is None,
                        "receipt_digests": [result.receipt.replay_digest],
                    }
                )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                )
    return tuple(rows)


def boundary_report(rows: Sequence[Mapping]) -> tuple[dict, ...]:
    """Per-doctrine empirical boundary conditions from persisted outcome rows.

    For each doctrine (in first-appearance row order): the sorted ids of every
    world with at least one infeasible seed, and `first_violated_constraint`
    — which metric crossed which pinned bound first — taken from the first
    infeasible row for that doctrine in the rows' deterministic order (None
    when the doctrine is feasible everywhere in the matrix).
    """
    report: list[dict] = []
    index: dict[str, dict] = {}
    for row in rows:
        doctrine_id = row["doctrine_id"]
        entry = index.get(doctrine_id)
        if entry is None:
            entry = {
                "doctrine_id": doctrine_id,
                "infeasible_world_ids": [],
                "first_violated_constraint": None,
            }
            index[doctrine_id] = entry
            report.append(entry)
        if row["feasible"]:
            continue
        if row["world_id"] not in entry["infeasible_world_ids"]:
            entry["infeasible_world_ids"].append(row["world_id"])
        if entry["first_violated_constraint"] is None:
            entry["first_violated_constraint"] = first_violated_constraint(
                row["metrics"]
            )
    return tuple(
        {
            "doctrine_id": entry["doctrine_id"],
            "infeasible_world_ids": tuple(sorted(entry["infeasible_world_ids"])),
            "first_violated_constraint": entry["first_violated_constraint"],
        }
        for entry in report
    )


def claims_robustness(doctrine: DoctrineSpec) -> bool:
    """Precise robustness-claim predicate (doctrine falsifier, clause 1).

    A doctrine claims robustness iff either:
    - its text contains the marker "robust" (case-insensitive substring), or
    - its weights assert it: a metadata weight key "robustness" or
      "resilience" with value >= 0.5.
    """
    if "robust" in doctrine.text.lower():
        return True
    for key in ("robustness", "resilience"):
        value = doctrine.weights.get(key)
        if value is not None and math.isfinite(float(value)) and float(value) >= 0.5:
            return True
    return False


def kill_doctrines(
    doctrines: Sequence[DoctrineSpec],
    worlds: Sequence[Scenario | WorldSample],
    seeds: Sequence[int],
    baseline: Scenario | WorldSample = Scenario(ScenarioName.BASELINE),
    config: Fortune5Config = Fortune5Config(),
) -> tuple[dict, ...]:
    """Doctrine falsifier: report which self-claimed-robust doctrines die.

    A doctrine is KILLED iff it claims robustness (`claims_robustness`) AND
    either (a) it is infeasible on the baseline world for any seed, or (b) it
    is infeasible on more than 50% of the targeted worlds — a world counts as
    infeasible when any of its seeds produces an infeasible row. Doctrines
    that never claimed robustness are never killed; claims that survive the
    matrix are reported as falsifier survivors. Deterministic: built on
    `run_outcome_matrix`'s deterministic row order.
    """
    baseline_label = _world_label(baseline)
    rows = run_outcome_matrix(
        doctrines,
        tuple(worlds) + (baseline,),
        seeds,
        config,
    )
    targeted_ids = {_world_label(world) for world in worlds}
    verdicts: list[dict] = []
    for doctrine in doctrines:
        doctrine_rows = [row for row in rows if row["doctrine_id"] == doctrine.id]
        baseline_infeasible = any(
            not row["feasible"]
            for row in doctrine_rows
            if row["world_id"] == baseline_label
        )
        infeasible_world_ids = {
            row["world_id"] for row in doctrine_rows if not row["feasible"]
        } & targeted_ids
        fraction = (
            len(infeasible_world_ids) / len(targeted_ids) if targeted_ids else 0.0
        )
        claimed = claims_robustness(doctrine)
        killed = claimed and (baseline_infeasible or fraction > 0.5)
        if not claimed:
            reason = "no_robustness_claim"
        elif baseline_infeasible:
            reason = "infeasible_on_baseline"
        elif fraction > 0.5:
            reason = "infeasible_on_majority_of_targeted_worlds"
        else:
            reason = "claim_survives"
        verdicts.append(
            {
                "doctrine_id": doctrine.id,
                "claims_robustness": claimed,
                "baseline_feasible": not baseline_infeasible,
                "infeasible_world_ids": tuple(sorted(infeasible_world_ids)),
                "infeasible_world_fraction": fraction,
                "killed": killed,
                "reason": reason,
            }
        )
    return tuple(verdicts)
