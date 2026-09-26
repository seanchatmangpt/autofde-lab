"""SPC drift court tests for repeated survival batches."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival_spc import CusumConfig, survival_spc_report


def episode(
    batch: str,
    index: int,
    *,
    failed: bool,
    workload_id: str = "workload",
    policy_id: str = "formal",
    horizon: int = 3,
    include_do: bool = True,
) -> dict:
    events = [{"step": 1, "phase": "OBSERVE"}]
    if include_do:
        events.append(
            {
                "step": 2 if failed else horizon,
                "phase": "DO",
                "authorized": not failed,
                "admitted": True,
                "receipt_id": f"receipt:{batch}:{index}",
                "replay_verified": True,
                "terminal_ready": True,
            }
        )
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": f"git:repo@{batch}",
        "workload_id": workload_id,
        "policy_id": policy_id,
        "episode_id": f"{batch}-{index}",
        "horizon": horizon,
        "events": events,
    }


def batch(label: str, failures: int, total: int = 4, **kwargs) -> tuple[str, list[dict]]:
    return (
        label,
        [
            episode(label, index, failed=index < failures, **kwargs)
            for index in range(total)
        ],
    )


def test_positive_cusum_signals_sustained_failure_rate_drift_across_exact_subjects() -> None:
    report = survival_spc_report(
        [
            batch("sha-a", 1),
            batch("sha-b", 2),
            batch("sha-c", 2),
            batch("sha-d", 2),
        ],
        series_id="formal-release-series",
        metric="failure_probability_observed",
        config=CusumConfig(target=0.25, allowance=0.05, decision_interval=0.4),
    )

    assert [point["subject"] for point in report["points"]] == [
        "git:repo@sha-a",
        "git:repo@sha-b",
        "git:repo@sha-c",
        "git:repo@sha-d",
    ]
    assert report["points"][0]["positive_cusum"] == pytest.approx(0.0)
    assert report["points"][1]["positive_cusum"] == pytest.approx(0.2)
    assert report["points"][2]["positive_cusum"] == pytest.approx(0.4)
    assert report["points"][3]["positive_cusum"] == pytest.approx(0.6)
    assert report["first_positive_alarm"] == "sha-d"
    assert report["first_negative_alarm"] is None


def test_negative_cusum_can_signal_lower_than_target_metric() -> None:
    report = survival_spc_report(
        [
            batch("a", 0),
            batch("b", 0),
            batch("c", 0),
        ],
        series_id="rmst-series",
        metric="failure_probability_observed",
        config=CusumConfig(target=0.5, allowance=0.0, decision_interval=1.0),
    )

    assert report["points"][0]["negative_cusum"] == pytest.approx(0.5)
    assert report["points"][1]["negative_cusum"] == pytest.approx(1.0)
    assert report["points"][2]["negative_cusum"] == pytest.approx(1.5)
    assert report["first_negative_alarm"] == "c"


def test_spc_refuses_workload_policy_or_horizon_drift() -> None:
    with pytest.raises(IECRefusal, match="REFUSED_WORKLOAD_MISMATCH"):
        survival_spc_report(
            [
                batch("a", 0),
                batch("b", 0, workload_id="other"),
            ],
            series_id="series",
            metric="rmst_steps",
            config=CusumConfig(target=3.0, allowance=0.1, decision_interval=1.0),
        )

    with pytest.raises(IECRefusal, match="REFUSED_POLICY_MISMATCH"):
        survival_spc_report(
            [
                batch("a", 0),
                batch("b", 0, policy_id="other"),
            ],
            series_id="series",
            metric="rmst_steps",
            config=CusumConfig(target=3.0, allowance=0.1, decision_interval=1.0),
        )

    with pytest.raises(IECRefusal, match="REFUSED_HORIZON_MISMATCH"):
        survival_spc_report(
            [
                batch("a", 0),
                batch("b", 0, horizon=4),
            ],
            series_id="series",
            metric="rmst_steps",
            config=CusumConfig(target=3.0, allowance=0.1, decision_interval=1.0),
        )


def test_spc_refuses_undefined_receipt_coverage() -> None:
    no_do = (
        "a",
        [episode("a", 0, failed=False, include_do=False)],
    )

    with pytest.raises(IECRefusal, match="UNOBSERVED_METRIC"):
        survival_spc_report(
            [no_do],
            series_id="series",
            metric="receipt_coverage",
            config=CusumConfig(target=1.0, allowance=0.01, decision_interval=0.1),
        )
