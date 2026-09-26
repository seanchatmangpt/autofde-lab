"""Statistical-process-control drift courts for repeated survival batches.

SPC is intentionally separate from exact-subject survival admission. A release
series may contain different exact subjects over time; the caller must bind
those releases under an explicit series_id. Workload, policy, and horizon must
remain fixed or the series is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .recurrent_survival import recurrent_survival_report
from .survival import survival_report

__all__ = ["CusumConfig", "survival_spc_report"]


@dataclass(frozen=True)
class CusumConfig:
    target: float
    allowance: float
    decision_interval: float

    def __post_init__(self) -> None:
        if self.allowance < 0:
            raise ValueError("allowance must be non-negative")
        if self.decision_interval <= 0:
            raise ValueError("decision_interval must be positive")


def _metric(
    documents: Sequence[Mapping[str, Any]],
    metric: str,
) -> tuple[dict[str, Any], float]:
    survival = survival_report(documents)
    if metric == "failure_probability_observed":
        return survival, float(survival["failure_probability_observed"])
    if metric == "rmst_steps":
        return survival, float(survival["rmst_steps"])

    recurrent = recurrent_survival_report(documents)
    if metric == "llm_dependency_fraction":
        return survival, float(recurrent["llm_dependency_fraction"])
    if metric == "receipt_coverage":
        value = recurrent["receipt_coverage"]
        if value is None:
            raise IECRefusal(
                "REFUSED_SURVIVAL_SPC_UNOBSERVED_METRIC",
                "receipt_coverage is undefined because the batch has no DO",
            )
        return survival, float(value)
    if metric == "replay_coverage":
        value = recurrent["replay_coverage"]
        if value is None:
            raise IECRefusal(
                "REFUSED_SURVIVAL_SPC_UNOBSERVED_METRIC",
                "replay_coverage is undefined because the batch has no receipted DO",
            )
        return survival, float(value)
    raise IECRefusal(
        "REFUSED_SURVIVAL_SPC_METRIC",
        f"unsupported survival SPC metric {metric!r}",
    )


def survival_spc_report(
    batches: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
    *,
    series_id: str,
    metric: str,
    config: CusumConfig,
) -> dict[str, Any]:
    """Run a two-sided tabular CUSUM over ordered survival batches."""

    if not series_id.strip():
        raise IECRefusal(
            "REFUSED_SURVIVAL_SPC_SERIES",
            "series_id must be non-empty",
        )
    if not batches:
        raise IECRefusal(
            "REFUSED_SURVIVAL_SPC_EMPTY",
            "at least one ordered batch is required",
        )

    baseline: dict[str, Any] | None = None
    points: list[dict[str, Any]] = []
    positive = 0.0
    negative = 0.0
    first_positive_alarm: str | None = None
    first_negative_alarm: str | None = None
    labels: set[str] = set()

    for label, documents in batches:
        if not label or label in labels:
            raise IECRefusal(
                "REFUSED_SURVIVAL_SPC_SERIES",
                f"batch label {label!r} is empty or duplicated",
            )
        labels.add(label)
        report, value = _metric(documents, metric)
        if baseline is None:
            baseline = report
        else:
            if report["workload_id"] != baseline["workload_id"]:
                raise IECRefusal(
                    "REFUSED_WORKLOAD_MISMATCH",
                    "SPC batches use different workloads",
                )
            if report["policy_id"] != baseline["policy_id"]:
                raise IECRefusal(
                    "REFUSED_POLICY_MISMATCH",
                    "SPC batches use different policies",
                )
            if report["horizon"] != baseline["horizon"]:
                raise IECRefusal(
                    "REFUSED_HORIZON_MISMATCH",
                    "SPC batches use different horizons",
                )

        positive = max(0.0, positive + value - config.target - config.allowance)
        negative = max(0.0, negative + config.target - value - config.allowance)
        positive_alarm = positive > config.decision_interval
        negative_alarm = negative > config.decision_interval
        if positive_alarm and first_positive_alarm is None:
            first_positive_alarm = label
        if negative_alarm and first_negative_alarm is None:
            first_negative_alarm = label

        points.append(
            {
                "batch": label,
                "subject": report["subject"],
                "episodes": report["episodes"],
                "metric_value": value,
                "positive_cusum": positive,
                "negative_cusum": negative,
                "positive_alarm": positive_alarm,
                "negative_alarm": negative_alarm,
            }
        )

    assert baseline is not None
    result = {
        "schema": "autofde-lab.survival-spc/1",
        "series_id": series_id,
        "metric": metric,
        "target": config.target,
        "allowance": config.allowance,
        "decision_interval": config.decision_interval,
        "workload_id": baseline["workload_id"],
        "policy_id": baseline["policy_id"],
        "horizon": baseline["horizon"],
        "points": points,
        "first_positive_alarm": first_positive_alarm,
        "first_negative_alarm": first_negative_alarm,
        "claim_ceiling": (
            "configured CUSUM signal over an explicitly bound release series; "
            "absence of an alarm is not proof of no drift and exact subjects remain distinct"
        ),
    }
    result["id"] = content_id(result)
    return result
