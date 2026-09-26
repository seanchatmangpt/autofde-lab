"""Multi-policy descriptive comparison for premature-actuation survival.

The single-policy court in :mod:`survival` deliberately refuses mixed policy
identities. This module composes those admitted single-policy reports into one
fixed-subject cohort view.

The output is descriptive only. Pairwise deltas do not establish a causal
effect, policy superiority, production standing, or authority.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import analyze_episode, survival_report

COHORT_SCHEMA = "autofde-lab.premature-actuation-cohort/1"


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
                _terminal_cumulative_hazard(right)
                - _terminal_cumulative_hazard(left)
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
        policy_id: survival_report(grouped[policy_id])
        for policy_id in sorted(grouped)
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
