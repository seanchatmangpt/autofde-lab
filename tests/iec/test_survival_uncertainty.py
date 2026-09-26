from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival import survival_report
from autofde_lab.iec.crowns.survival_uncertainty import survival_uncertainty


def episode(episode_id: str, fail_step: int | None) -> dict:
    events = [{"step": 1, "phase": "OBSERVE"}]
    if fail_step is None:
        events.append({"step": 4, "phase": "VERIFY"})
    else:
        events.append(
            {
                "step": fail_step,
                "phase": "DO",
                "authorized": False,
                "receipt_id": f"receipt:{episode_id}",
            }
        )
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "git:survival/example@0123456789abcdef",
        "workload_id": "sha256:uncertainty",
        "policy_id": "policy",
        "episode_id": episode_id,
        "horizon": 4,
        "events": events,
    }


def test_uncertainty_adds_greenwood_and_wilson_bounds() -> None:
    report = survival_report(
        [
            episode("a", 2),
            episode("b", None),
            episode("c", None),
            episode("d", None),
        ]
    )
    result = survival_uncertainty(report)

    assert result["survival_report_id"] == report["id"]
    assert len(result["survival_curve"]) == 4
    assert all(
        0.0 <= point["lower"] <= point["survival"] <= point["upper"] <= 1.0
        for point in result["survival_curve"]
    )
    probability = result["failure_probability_observed"]
    assert probability["value"] == 0.25
    assert 0.0 <= probability["lower"] < probability["value"]
    assert probability["value"] < probability["upper"] <= 1.0


def test_uncertainty_refuses_non_survival_report_or_nonpositive_z() -> None:
    with pytest.raises(IECRefusal, match="REFUSED_INVALID_SURVIVAL_REPORT"):
        survival_uncertainty({"schema": "other"})

    report = survival_report([episode("a", None)])
    with pytest.raises(IECRefusal, match="z must be positive"):
        survival_uncertainty(report, z=0)
