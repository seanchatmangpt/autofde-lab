"""Run-scoped uncertainty summaries for discrete survival reports."""

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping

from .model import IECRefusal, content_id
from .survival import REPORT_SCHEMA


def _wilson(successes: int, total: int, z: float) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 1.0)
    phat = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (phat + z2 / (2.0 * total)) / denominator
    half = (
        z
        * sqrt(
            phat * (1.0 - phat) / total
            + z2 / (4.0 * total * total)
        )
        / denominator
    )
    return (max(0.0, center - half), min(1.0, center + half))


def survival_uncertainty(
    report: Mapping[str, Any],
    *,
    z: float = 1.96,
) -> dict[str, Any]:
    """Add pointwise Greenwood/normal bounds without changing report standing."""
    if report.get("schema") != REPORT_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_REPORT",
            f"schema must be {REPORT_SCHEMA}",
        )
    if z <= 0:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_REPORT",
            "z must be positive",
        )

    greenwood_sum = 0.0
    curve = []
    for point in report["survival_curve"]:
        at_risk = int(point["at_risk"])
        failures = int(point["failures"])
        survival = float(point["survival"])
        if failures and at_risk > failures:
            greenwood_sum += failures / (
                at_risk * (at_risk - failures)
            )
        variance = survival * survival * greenwood_sum
        standard_error = sqrt(max(0.0, variance))
        curve.append(
            {
                "step": int(point["step"]),
                "survival": survival,
                "standard_error": standard_error,
                "lower": max(0.0, survival - z * standard_error),
                "upper": min(1.0, survival + z * standard_error),
            }
        )

    failures = int(report["failures"])
    episodes = int(report["episodes"])
    failure_lower, failure_upper = _wilson(failures, episodes, z)
    result = {
        "schema": "autofde-lab.premature-actuation-uncertainty/1",
        "survival_report_id": report["id"],
        "subject": report["subject"],
        "workload_id": report["workload_id"],
        "policy_id": report["policy_id"],
        "horizon": report["horizon"],
        "episodes": episodes,
        "z": z,
        "survival_curve": curve,
        "failure_probability_observed": {
            "value": float(report["failure_probability_observed"]),
            "lower": failure_lower,
            "upper": failure_upper,
            "method": "wilson-score",
        },
        "claim_ceiling": (
            "pointwise descriptive uncertainty for the observed bounded corpus; "
            "not a causal interval or production guarantee"
        ),
    }
    result["id"] = content_id(result)
    return result
