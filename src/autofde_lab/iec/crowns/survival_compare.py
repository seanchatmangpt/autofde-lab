"""Cross-policy comparison for exact autonomic-survival experiments.

The single-policy survival courts intentionally refuse policy drift. This module
adds the next layer without weakening that invariant: each policy is analyzed
independently first, then the resulting reports are compared only when subject,
workload, and horizon are identical.

The cohort/pairwise-delta court (``cohort_report``, ``compare_policy_reports``)
composes admitted single-policy reports over one exact subject/workload/horizon.

All comparisons are descriptive. A Pareto relation over observed metrics is not
a causal claim and does not grant production standing or execution authority.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .recurrent_survival import recurrent_survival_report
from .survival import analyze_episode, survival_report
from .survival_logrank import logrank_survival_test
from .survival_uncertainty import survival_uncertainty_report

__all__ = [
    "COHORT_SCHEMA",
    "PolicyMetrics",
    "cohort_report",
    "compare_policy_reports",
    "compare_survival_policies",
    "observed_pareto_frontier",
]

COHORT_SCHEMA = "autofde-lab.premature-actuation-cohort/1"


@dataclass(frozen=True)
class PolicyMetrics:
    policy_id: str
    episodes: int
    failures: int
    failure_probability_observed: float
    rmst_steps: float
    terminal_survival: float
    receipt_coverage: float | None
    replay_coverage: float | None
    llm_dependency_fraction: float
    llm_tokens: int

    def objective_vector(self) -> tuple[float, float, float, float, float, float]:
        """Return a maximize-only observed objective vector.

        Lower failure probability and lower LLM dependency are represented by
        their complements so every dimension has the same dominance direction.
        Missing receipt/replay coverage remains below any observed coverage and
        therefore can never manufacture dominance.
        """

        return (
            self.rmst_steps,
            self.terminal_survival,
            1.0 - self.failure_probability_observed,
            -1.0 if self.receipt_coverage is None else self.receipt_coverage,
            -1.0 if self.replay_coverage is None else self.replay_coverage,
            1.0 - self.llm_dependency_fraction,
        )


def _metrics(documents: Sequence[Mapping[str, Any]]) -> PolicyMetrics:
    survival = survival_report(documents)
    recurrent = recurrent_survival_report(documents)
    curve = survival["survival_curve"]
    terminal_survival = float(curve[-1]["survival"]) if curve else 1.0
    return PolicyMetrics(
        policy_id=str(survival["policy_id"]),
        episodes=int(survival["episodes"]),
        failures=int(survival["failures"]),
        failure_probability_observed=float(survival["failure_probability_observed"]),
        rmst_steps=float(survival["rmst_steps"]),
        terminal_survival=terminal_survival,
        receipt_coverage=recurrent["receipt_coverage"],
        replay_coverage=recurrent["replay_coverage"],
        llm_dependency_fraction=float(recurrent["llm_dependency_fraction"]),
        llm_tokens=int(recurrent["llm_tokens"]),
    )


def _dominates(left: PolicyMetrics, right: PolicyMetrics) -> bool:
    left_vector = left.objective_vector()
    right_vector = right.objective_vector()
    return all(a >= b for a, b in zip(left_vector, right_vector, strict=True)) and any(
        a > b for a, b in zip(left_vector, right_vector, strict=True)
    )


def observed_pareto_frontier(metrics: Sequence[PolicyMetrics]) -> tuple[str, ...]:
    """Return policy ids not strictly dominated on the declared observed axes."""

    frontier = []
    for candidate in metrics:
        if any(
            other.policy_id != candidate.policy_id and _dominates(other, candidate)
            for other in metrics
        ):
            continue
        frontier.append(candidate.policy_id)
    return tuple(sorted(frontier))


def compare_survival_policies(
    policy_documents: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Compare exact policy strata without pooling their survival processes."""

    if len(policy_documents) < 2:
        raise IECRefusal(
            "REFUSED_SURVIVAL_COMPARISON_UNDERPOWERED",
            "at least two policy strata are required for comparison",
        )

    rows: list[PolicyMetrics] = []
    comparison_subject: str | None = None
    comparison_workload: str | None = None
    comparison_horizon: int | None = None

    for expected_policy_id, documents in sorted(policy_documents.items()):
        if not expected_policy_id:
            raise IECRefusal(
                "REFUSED_POLICY_MISMATCH",
                "comparison policy key may not be empty",
            )
        if not documents:
            raise IECRefusal(
                "REFUSED_SURVIVAL_COMPARISON_UNDERPOWERED",
                f"{expected_policy_id}: no episodes",
            )

        report = survival_report(documents)
        if report["policy_id"] != expected_policy_id:
            raise IECRefusal(
                "REFUSED_POLICY_MISMATCH",
                f"comparison key {expected_policy_id!r} != report policy {report['policy_id']!r}",
            )
        if comparison_subject is None:
            comparison_subject = str(report["subject"])
            comparison_workload = str(report["workload_id"])
            comparison_horizon = int(report["horizon"])
        else:
            if report["subject"] != comparison_subject:
                raise IECRefusal(
                    "REFUSED_EXACT_SUBJECT_MISMATCH",
                    "policy strata refer to different subjects",
                )
            if report["workload_id"] != comparison_workload:
                raise IECRefusal(
                    "REFUSED_WORKLOAD_MISMATCH",
                    "policy strata refer to different workloads",
                )
            if int(report["horizon"]) != comparison_horizon:
                raise IECRefusal(
                    "REFUSED_HORIZON_MISMATCH",
                    "policy strata use different fixed horizons",
                )
        rows.append(_metrics(documents))

    pairwise: list[dict[str, Any]] = []
    for left in rows:
        for right in rows:
            if left.policy_id >= right.policy_id:
                continue
            pairwise.append(
                {
                    "left_policy_id": left.policy_id,
                    "right_policy_id": right.policy_id,
                    "rmst_delta_steps": left.rmst_steps - right.rmst_steps,
                    "terminal_survival_delta": left.terminal_survival
                    - right.terminal_survival,
                    "failure_probability_delta": left.failure_probability_observed
                    - right.failure_probability_observed,
                    "llm_dependency_delta": left.llm_dependency_fraction
                    - right.llm_dependency_fraction,
                    "left_observed_dominates_right": _dominates(left, right),
                    "right_observed_dominates_left": _dominates(right, left),
                    "logrank": logrank_survival_test(
                        policy_documents[left.policy_id],
                        policy_documents[right.policy_id],
                    ),
                }
            )

    result = {
        "schema": "autofde-lab.survival-policy-comparison/1",
        "subject": comparison_subject,
        "workload_id": comparison_workload,
        "horizon": comparison_horizon,
        "policies": [
            {
                "policy_id": row.policy_id,
                "episodes": row.episodes,
                "failures": row.failures,
                "failure_probability_observed": row.failure_probability_observed,
                "rmst_steps": row.rmst_steps,
                "terminal_survival": row.terminal_survival,
                "receipt_coverage": row.receipt_coverage,
                "replay_coverage": row.replay_coverage,
                "llm_dependency_fraction": row.llm_dependency_fraction,
                "llm_tokens": row.llm_tokens,
                "uncertainty": survival_uncertainty_report(
                    policy_documents[row.policy_id]
                ),
            }
            for row in rows
        ],
        "observed_pareto_frontier": list(observed_pareto_frontier(rows)),
        "pairwise": pairwise,
        "claim_ceiling": (
            "descriptive exact-stratum comparison only; Pareto dominance is over "
            "declared observed metrics and implies neither causality nor production standing"
        ),
    }
    result["id"] = content_id(result)
    return result


def _mean(total: int | float, count: int) -> float:
    return 0.0 if count == 0 else float(total) / count


def _terminal_cumulative_hazard(report: Mapping[str, Any]) -> float:
    return sum(float(point["hazard"]) for point in report["survival_curve"])


def compare_policy_reports(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two already-built single-policy reports on the same bounded subject."""
    for field, refusal in (
        ("subject", "REFUSED_EXACT_SUBJECT_MISMATCH"),
        ("workload_id", "REFUSED_WORKLOAD_MISMATCH"),
        ("horizon", "REFUSED_HORIZON_MISMATCH"),
    ):
        if left.get(field) != right.get(field):
            raise IECRefusal(
                refusal,
                f"survival policy reports differ on {field}",
            )
    if left.get("policy_id") == right.get("policy_id"):
        raise IECRefusal(
            "REFUSED_POLICY_MISMATCH",
            "pairwise comparison requires two distinct policy ids",
        )

    left_episodes = int(left["episodes"])
    right_episodes = int(right["episodes"])
    comparison = {
        "schema": "autofde-lab.premature-actuation-policy-comparison/1",
        "subject": left["subject"],
        "workload_id": left["workload_id"],
        "horizon": left["horizon"],
        "left_policy_id": left["policy_id"],
        "right_policy_id": right["policy_id"],
        "left_episodes": left_episodes,
        "right_episodes": right_episodes,
        "delta": {
            "failure_probability_observed": (
                float(right["failure_probability_observed"])
                - float(left["failure_probability_observed"])
            ),
            "rmst_steps": float(right["rmst_steps"]) - float(left["rmst_steps"]),
            "terminal_cumulative_hazard": (
                _terminal_cumulative_hazard(right) - _terminal_cumulative_hazard(left)
            ),
            "tool_invocations_per_episode": (
                _mean(int(right["tool_invocations"]), right_episodes)
                - _mean(int(left["tool_invocations"]), left_episodes)
            ),
            "llm_tokens_per_episode": (
                _mean(int(right["llm_tokens"]), right_episodes)
                - _mean(int(left["llm_tokens"]), left_episodes)
            ),
        },
        "claim_ceiling": (
            "observed pairwise deltas over a fixed subject/workload/horizon; "
            "no causal effect, ranking, production standing, or authority implied"
        ),
    }
    comparison["id"] = content_id(comparison)
    return comparison


def cohort_report(
    documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one exact-subject cohort report with per-policy courts and pairwise deltas."""
    if not documents:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "at least one episode is required",
        )

    analyzed = [analyze_episode(document) for document in documents]
    first = analyzed[0]
    for report in analyzed[1:]:
        if report["subject"] != first["subject"]:
            raise IECRefusal(
                "REFUSED_EXACT_SUBJECT_MISMATCH",
                "cohort episodes have different subjects",
            )
        if report["workload_id"] != first["workload_id"]:
            raise IECRefusal(
                "REFUSED_WORKLOAD_MISMATCH",
                "cohort episodes have different workload ids",
            )
        if report["horizon"] != first["horizon"]:
            raise IECRefusal(
                "REFUSED_HORIZON_MISMATCH",
                "cohort episodes have different horizons",
            )

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for document, report in zip(documents, analyzed, strict=True):
        grouped[str(report["policy_id"])].append(document)

    policies = {
        policy_id: survival_report(grouped[policy_id]) for policy_id in sorted(grouped)
    }
    pairwise = [
        compare_policy_reports(policies[left], policies[right])
        for left, right in combinations(sorted(policies), 2)
    ]

    result = {
        "schema": COHORT_SCHEMA,
        "subject": first["subject"],
        "workload_id": first["workload_id"],
        "horizon": first["horizon"],
        "episodes": len(documents),
        "policy_count": len(policies),
        "policies": policies,
        "pairwise": pairwise,
        "claim_ceiling": (
            "descriptive multi-policy cohort over one exact subject/workload/horizon; "
            "no causal interpretation or policy ranking implied"
        ),
    }
    result["id"] = content_id(result)
    return result
