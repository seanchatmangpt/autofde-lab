"""Dependency-free two-sample log-rank test for exact survival strata."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import analyze_episode

__all__ = ["logrank_survival_test"]


def _validated_reports(
    documents: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    if not documents:
        raise IECRefusal(
            "REFUSED_SURVIVAL_LOGRANK_EMPTY",
            "each log-rank stratum requires at least one episode",
        )
    reports = tuple(analyze_episode(document) for document in documents)
    first = reports[0]
    for report in reports[1:]:
        if report["subject"] != first["subject"]:
            raise IECRefusal(
                "REFUSED_EXACT_SUBJECT_MISMATCH",
                "log-rank stratum contains multiple subjects",
            )
        if report["workload_id"] != first["workload_id"]:
            raise IECRefusal(
                "REFUSED_WORKLOAD_MISMATCH",
                "log-rank stratum contains multiple workloads",
            )
        if report["policy_id"] != first["policy_id"]:
            raise IECRefusal(
                "REFUSED_POLICY_MISMATCH",
                "log-rank input stratum contains multiple policies",
            )
        if report["horizon"] != first["horizon"]:
            raise IECRefusal(
                "REFUSED_HORIZON_MISMATCH",
                "log-rank stratum contains multiple horizons",
            )
    return reports


def logrank_survival_test(
    left_documents: Sequence[Mapping[str, Any]],
    right_documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare first-failure time distributions for two exact policy strata."""

    left = _validated_reports(left_documents)
    right = _validated_reports(right_documents)
    l0 = left[0]
    r0 = right[0]
    if l0["subject"] != r0["subject"]:
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            "log-rank policy strata refer to different subjects",
        )
    if l0["workload_id"] != r0["workload_id"]:
        raise IECRefusal(
            "REFUSED_WORKLOAD_MISMATCH",
            "log-rank policy strata refer to different workloads",
        )
    if l0["horizon"] != r0["horizon"]:
        raise IECRefusal(
            "REFUSED_HORIZON_MISMATCH",
            "log-rank policy strata use different horizons",
        )
    if l0["policy_id"] == r0["policy_id"]:
        raise IECRefusal(
            "REFUSED_SURVIVAL_LOGRANK_SAME_POLICY",
            "log-rank comparison requires two distinct policy ids",
        )

    left_failures = Counter(
        int(report["first_failure_step"])
        for report in left
        if report["first_failure_step"] is not None
    )
    right_failures = Counter(
        int(report["first_failure_step"])
        for report in right
        if report["first_failure_step"] is not None
    )

    left_at_risk = len(left)
    right_at_risk = len(right)
    observed_left = 0.0
    expected_left = 0.0
    variance = 0.0
    contributions: list[dict[str, Any]] = []

    horizon = int(l0["horizon"])
    for step in range(1, horizon + 1):
        d_left = left_failures.get(step, 0)
        d_right = right_failures.get(step, 0)
        d_total = d_left + d_right
        n_total = left_at_risk + right_at_risk
        expected = (
            d_total * left_at_risk / n_total
            if d_total and n_total
            else 0.0
        )
        var = 0.0
        if d_total and n_total > 1:
            var = (
                left_at_risk
                * right_at_risk
                * d_total
                * (n_total - d_total)
                / (n_total * n_total * (n_total - 1))
            )
        observed_left += d_left
        expected_left += expected
        variance += var
        contributions.append(
            {
                "step": step,
                "left_at_risk": left_at_risk,
                "right_at_risk": right_at_risk,
                "left_failures": d_left,
                "right_failures": d_right,
                "left_expected_failures": expected,
                "variance_contribution": var,
            }
        )
        left_at_risk -= d_left
        right_at_risk -= d_right

    delta = observed_left - expected_left
    statistic = delta * delta / variance if variance > 0.0 else 0.0
    # Chi-square(1) survival function: erfc(sqrt(x/2)).
    p_value = math.erfc(math.sqrt(statistic / 2.0))

    result = {
        "schema": "autofde-lab.survival-logrank/1",
        "subject": l0["subject"],
        "workload_id": l0["workload_id"],
        "horizon": horizon,
        "left_policy_id": l0["policy_id"],
        "right_policy_id": r0["policy_id"],
        "left_episodes": len(left),
        "right_episodes": len(right),
        "left_failures": sum(left_failures.values()),
        "right_failures": sum(right_failures.values()),
        "left_observed_minus_expected": delta,
        "variance": variance,
        "chi_square_1df": statistic,
        "p_value": p_value,
        "contributions": contributions,
        "claim_ceiling": (
            "two-sample log-rank test over exact observed first-failure strata; "
            "p-value is not an effect size, causal claim, ranking, or production standing"
        ),
    }
    result["id"] = content_id(result)
    return result
