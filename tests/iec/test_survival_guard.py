from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival_guard import verify_guard


def episode(episode_id: str, *, unauthorized: bool) -> dict:
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "git:survival/example@0123456789abcdef",
        "workload_id": "sha256:guard",
        "policy_id": "policy",
        "episode_id": episode_id,
        "horizon": 3,
        "events": [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 3,
                "phase": "DO",
                "authorized": not unauthorized,
                "receipt_id": f"receipt:{episode_id}",
                "terminal_ready": True,
            },
        ],
    }


def test_guard_verification_observes_exact_failure_elimination() -> None:
    baseline = [
        episode("before-a", unauthorized=True),
        episode("before-b", unauthorized=True),
    ]
    guarded = [
        episode("after-a", unauthorized=False),
        episode("after-b", unauthorized=False),
    ]

    result = verify_guard(
        baseline,
        guarded,
        failure_type="UNAUTHORIZED_DO",
    )

    assert result["guard_id"] == "require_authority_before_do"
    assert result["baseline"]["rate"] == 1.0
    assert result["guarded"]["rate"] == 0.0
    assert result["delta_rate"] == -1.0
    assert result["observed_elimination"] is True
    assert result["standing"] == "OBSERVED_RUN_SCOPE"
    assert result["authority"] == "none"


def test_guard_verification_requires_baseline_failure() -> None:
    clean = [episode("clean", unauthorized=False)]
    with pytest.raises(
        IECRefusal,
        match="REFUSED_GUARD_WITHOUT_BASELINE_FAILURE",
    ):
        verify_guard(
            clean,
            clean,
            failure_type="UNAUTHORIZED_DO",
        )
