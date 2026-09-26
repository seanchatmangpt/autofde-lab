"""Stratified campaign-survival analysis tests."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.survival_strata import stratified_survival_report


def episode(
    episode_id: str,
    policy_id: str,
    machinery: str,
    *,
    authorized: bool = True,
    fault_plan_id: str | None = None,
    authority_level: str = "filtered",
) -> dict:
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": "git:seanchatmangpt/gymact@0123456789abcdef",
        "workload_id": "sha256:strata-workload",
        "policy_id": policy_id,
        "episode_id": episode_id,
        "horizon": 3,
        "events": [
            {"step": 1, "phase": "OBSERVE"},
            {
                "step": 3,
                "phase": "DO",
                "authorized": authorized,
                "admitted": True,
                "receipt_id": f"receipt:{episode_id}",
                "replay_verified": True,
                "terminal_ready": True,
            },
        ],
        "gymact": {
            "scenario_id": "world",
            "machinery": machinery,
            "factor_assignments": [
                {"name": "authority", "level": authority_level},
            ],
            "fault_plan_id": fault_plan_id,
            "synthetic": True,
        },
    }


def test_strata_keep_baseline_and_faulted_campaigns_separate() -> None:
    documents = [
        episode("formal-base", "formal::factor", "formal-generated"),
        episode("llm-base", "llm::factor", "llm-native"),
        episode(
            "formal-fault",
            "formal::factor",
            "formal-generated",
            authorized=False,
            fault_plan_id="fault:authority_drop:step-3",
        ),
        episode(
            "llm-fault",
            "llm::factor",
            "llm-native",
            authorized=False,
            fault_plan_id="fault:authority_drop:step-3",
        ),
    ]

    report = stratified_survival_report(
        documents,
        factor_names=("authority",),
        stratify_fault=True,
    )

    assert report["strata_count"] == 2
    assert report["compared_strata"] == 2
    by_fault = {row["key"]["fault_plan_id"]: row for row in report["strata"]}
    assert set(by_fault) == {"baseline", "fault:authority_drop:step-3"}
    assert by_fault["baseline"]["comparison"]["policies"][0]["failures"] == 0
    fault_rows = by_fault["fault:authority_drop:step-3"]["comparison"]["policies"]
    assert all(row["failures"] == 1 for row in fault_rows)


def test_strata_preserve_factor_levels_as_separate_comparison_courts() -> None:
    documents = [
        episode("f-filtered", "formal::filtered", "formal-generated"),
        episode("l-filtered", "llm::filtered", "llm-native"),
        episode(
            "f-expired",
            "formal::expired",
            "formal-generated",
            authority_level="expired",
            authorized=False,
        ),
        episode(
            "l-expired",
            "llm::expired",
            "llm-native",
            authority_level="expired",
            authorized=False,
        ),
    ]

    report = stratified_survival_report(documents, factor_names=("authority",))

    assert report["strata_count"] == 2
    assert {
        row["key"]["factor:authority"] for row in report["strata"]
    } == {"filtered", "expired"}


def test_single_policy_stratum_is_retained_as_coverage_gap() -> None:
    report = stratified_survival_report(
        [episode("only", "formal::factor", "formal-generated")],
        factor_names=("authority",),
    )

    assert report["compared_strata"] == 0
    assert report["strata"][0]["comparison_status"] == "INSUFFICIENT_POLICY_STRATA"
    assert report["strata"][0]["comparison"] is None


def test_missing_requested_factor_is_refused_not_pooled() -> None:
    document = episode("missing", "formal", "formal-generated")
    document["gymact"]["factor_assignments"] = []

    with pytest.raises(IECRefusal, match="missing factor"):
        stratified_survival_report([document], factor_names=("authority",))


def test_policy_to_machinery_drift_inside_stratum_is_refused() -> None:
    documents = [
        episode("a", "same-policy", "formal-generated"),
        episode("b", "same-policy", "llm-native"),
    ]

    with pytest.raises(IECRefusal, match="multiple machinery"):
        stratified_survival_report(documents, factor_names=("authority",))
