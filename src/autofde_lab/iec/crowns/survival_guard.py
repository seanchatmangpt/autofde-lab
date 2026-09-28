"""Observed verification court for manufactured survival guard candidates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import analyze_episode
from .survival_recurrence import recurrence_report


def _failure_observation(
    documents: Sequence[Mapping[str, Any]],
    failure_type: str,
) -> dict[str, Any]:
    reports = [analyze_episode(document) for document in documents]
    if not reports:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "guard verification corpus is empty",
        )
    first = reports[0]
    for report in reports[1:]:
        if report["subject"] != first["subject"]:
            raise IECRefusal(
                "REFUSED_EXACT_SUBJECT_MISMATCH",
                "guard corpus has different subjects",
            )
        if report["workload_id"] != first["workload_id"]:
            raise IECRefusal(
                "REFUSED_WORKLOAD_MISMATCH",
                "guard corpus has different workload ids",
            )
        if report["horizon"] != first["horizon"]:
            raise IECRefusal(
                "REFUSED_HORIZON_MISMATCH",
                "guard corpus has different horizons",
            )

    matching = [
        report
        for report in reports
        if failure_type in report["first_failure_types"]
    ]
    return {
        "subject": first["subject"],
        "workload_id": first["workload_id"],
        "horizon": first["horizon"],
        "episodes": len(reports),
        "occurrences": len(matching),
        "rate": len(matching) / len(reports),
        "episode_report_ids": sorted(report["id"] for report in matching),
    }


def verify_guard(
    baseline: Sequence[Mapping[str, Any]],
    guarded: Sequence[Mapping[str, Any]],
    *,
    failure_type: str,
) -> dict[str, Any]:
    """Measure exact failure recurrence before and after a candidate guard."""
    candidates = recurrence_report(
        baseline,
        min_occurrences=1,
    )["guard_candidates"]
    candidate = next(
        (
            row
            for row in candidates
            if row["failure_type"] == failure_type
        ),
        None,
    )
    if candidate is None:
        raise IECRefusal(
            "REFUSED_GUARD_WITHOUT_BASELINE_FAILURE",
            f"baseline does not observe {failure_type}",
        )

    before = _failure_observation(baseline, failure_type)
    after = _failure_observation(guarded, failure_type)
    for field, refusal in (
        ("subject", "REFUSED_EXACT_SUBJECT_MISMATCH"),
        ("workload_id", "REFUSED_WORKLOAD_MISMATCH"),
        ("horizon", "REFUSED_HORIZON_MISMATCH"),
    ):
        if before[field] != after[field]:
            raise IECRefusal(
                refusal,
                f"baseline and guarded corpora differ on {field}",
            )

    result = {
        "schema": "autofde-lab.premature-actuation-guard-verification/1",
        "subject": before["subject"],
        "workload_id": before["workload_id"],
        "horizon": before["horizon"],
        "failure_type": failure_type,
        "guard_id": candidate["guard_id"],
        "guard_candidate_id": candidate["id"],
        "baseline": before,
        "guarded": after,
        "delta_rate": after["rate"] - before["rate"],
        "observed_elimination": (
            before["occurrences"] > 0
            and after["occurrences"] == 0
        ),
        "standing": "OBSERVED_RUN_SCOPE",
        "authority": "none",
        "installation": "EXTERNAL_TO_THIS_COURT",
        "claim_ceiling": (
            "exact observed recurrence comparison only; elimination in this corpus "
            "does not establish global prevention or production standing"
        ),
    }
    result["id"] = content_id(result)
    return result
