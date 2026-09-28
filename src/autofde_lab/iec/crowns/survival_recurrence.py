"""Failure recurrence analysis and powerless guard manufacture.

Repeated first-failure types are compressed into candidate guard requirements.
The function never installs a guard, changes a policy, grants authority, or
claims that recurrence alone proves generality.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import analyze_episode

RECURRENCE_SCHEMA = "autofde-lab.premature-actuation-recurrence/1"

_GUARD_BY_FAILURE = {
    "WRONG_SUBJECT_DO": "require_exact_subject_before_do",
    "UNAUTHORIZED_DO": "require_authority_before_do",
    "UNADMITTED_DO": "require_admission_before_do",
    "UNRECEIPTED_DO": "require_receipt_before_do",
    "PREMATURE_DO": "require_terminal_predicate_before_do",
}


def recurrence_report(
    documents: Sequence[Mapping[str, Any]],
    *,
    min_occurrences: int = 2,
) -> dict[str, Any]:
    """Compress recurrent observed first failures into guard candidates."""
    if min_occurrences < 1:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "min_occurrences must be at least one",
        )
    if not documents:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "at least one episode is required",
        )

    reports = [analyze_episode(document) for document in documents]
    first = reports[0]
    for report in reports[1:]:
        if report["subject"] != first["subject"]:
            raise IECRefusal(
                "REFUSED_EXACT_SUBJECT_MISMATCH",
                "recurrence episodes have different subjects",
            )
        if report["workload_id"] != first["workload_id"]:
            raise IECRefusal(
                "REFUSED_WORKLOAD_MISMATCH",
                "recurrence episodes have different workload ids",
            )
        if report["horizon"] != first["horizon"]:
            raise IECRefusal(
                "REFUSED_HORIZON_MISMATCH",
                "recurrence episodes have different horizons",
            )

    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for report in reports:
        for failure_type in report["first_failure_types"]:
            evidence[failure_type].append(
                {
                    "episode_id": report["episode_id"],
                    "policy_id": report["policy_id"],
                    "first_failure_step": report["first_failure_step"],
                    "episode_report_id": report["id"],
                }
            )

    candidates = []
    for failure_type in sorted(evidence):
        rows = evidence[failure_type]
        if len(rows) < min_occurrences:
            continue
        guard = {
            "failure_type": failure_type,
            "guard_id": _GUARD_BY_FAILURE[failure_type],
            "occurrences": len(rows),
            "evidence": sorted(
                rows,
                key=lambda row: (
                    str(row["policy_id"]),
                    str(row["episode_id"]),
                ),
            ),
            "standing": "CANDIDATE",
            "authority": "none",
            "installation": "NOT_PERFORMED",
        }
        guard["id"] = content_id(guard)
        candidates.append(guard)

    result = {
        "schema": RECURRENCE_SCHEMA,
        "subject": first["subject"],
        "workload_id": first["workload_id"],
        "horizon": first["horizon"],
        "episodes": len(reports),
        "min_occurrences": min_occurrences,
        "guard_candidates": candidates,
        "uncompressed_failure_types": sorted(
            failure_type
            for failure_type, rows in evidence.items()
            if len(rows) < min_occurrences
        ),
        "claim_ceiling": (
            "recurrence manufactures powerless guard candidates only; "
            "installation requires separate admission and authority"
        ),
    }
    result["id"] = content_id(result)
    return result
