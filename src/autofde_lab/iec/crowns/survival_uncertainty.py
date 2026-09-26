"""Dependency-free uncertainty intervals for autonomic-survival evidence."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import survival_report

__all__ = ["survival_uncertainty_report"]


def _wilson_interval(successes: int, total: int, z: float) -> tuple[float, float]:
    if total < 1:
        raise ValueError("Wilson interval requires positive total")
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    half = (
        z
        * math.sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total)
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def _km_loglog_interval(
    survival: float,
    greenwood_sum: float,
    z: float,
) -> tuple[float, float]:
    if survival <= 0.0:
        return 0.0, 0.0
    if survival >= 1.0:
        return 1.0, 1.0
    if greenwood_sum <= 0.0:
        return survival, survival

    log_survival = math.log(survival)
    se_loglog = math.sqrt(greenwood_sum) / abs(log_survival)
    center = math.log(-log_survival)
    lower_loglog = center - z * se_loglog
    upper_loglog = center + z * se_loglog

    # The exp(-exp(x)) transform is decreasing, so transformed endpoints swap.
    lower = math.exp(-math.exp(upper_loglog))
    upper = math.exp(-math.exp(lower_loglog))
    return max(0.0, lower), min(1.0, upper)


def survival_uncertainty_report(
    documents: Sequence[Mapping[str, Any]],
    *,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Add finite-sample uncertainty to one exact policy survival stratum."""

    if not 0.0 < confidence < 1.0:
        raise IECRefusal(
            "REFUSED_SURVIVAL_CONFIDENCE",
            "confidence must be strictly between 0 and 1",
        )
    report = survival_report(documents)
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)

    greenwood_sum = 0.0
    curve: list[dict[str, Any]] = []
    for point in report["survival_curve"]:
        at_risk = int(point["at_risk"])
        failures = int(point["failures"])
        if failures and at_risk > failures:
            greenwood_sum += failures / (at_risk * (at_risk - failures))
        survival = float(point["survival"])
        variance = (
            survival * survival * greenwood_sum
            if 0.0 < survival < 1.0
            else 0.0
        )
        lower, upper = _km_loglog_interval(survival, greenwood_sum, z)
        curve.append(
            {
                **point,
                "greenwood_sum": greenwood_sum,
                "survival_variance": variance,
                "survival_standard_error": math.sqrt(variance),
                "confidence_lower": lower,
                "confidence_upper": upper,
            }
        )

    failure_lower, failure_upper = _wilson_interval(
        int(report["failures"]),
        int(report["episodes"]),
        z,
    )
    result = {
        "schema": "autofde-lab.survival-uncertainty/1",
        "subject": report["subject"],
        "workload_id": report["workload_id"],
        "policy_id": report["policy_id"],
        "horizon": report["horizon"],
        "episodes": report["episodes"],
        "failures": report["failures"],
        "confidence": confidence,
        "z": z,
        "failure_probability_observed": report["failure_probability_observed"],
        "failure_probability_wilson": {
            "lower": failure_lower,
            "upper": failure_upper,
        },
        "survival_curve": curve,
        "claim_ceiling": (
            "frequentist finite-sample intervals over the fixed observed stratum; "
            "no causal, production, or future-population standing is implied"
        ),
    }
    result["id"] = content_id(result)
    return result
