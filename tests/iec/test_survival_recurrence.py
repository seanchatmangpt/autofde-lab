from __future__ import annotations

from autofde_lab.iec.crowns.survival_recurrence import recurrence_report

SUBJECT = "git:survival/example@0123456789abcdef"
WORKLOAD = "sha256:recurrence"


def failed(episode_id: str, *, failure: str) -> dict:
    row = {
        "step": 2,
        "phase": "DO",
        "receipt_id": f"receipt:{episode_id}",
        "terminal_ready": True,
    }
    if failure == "UNAUTHORIZED_DO":
        row["authorized"] = False
    elif failure == "UNRECEIPTED_DO":
        row["receipt_id"] = None
    elif failure == "PREMATURE_DO":
        row["terminal_ready"] = False
    return {
        "schema": "autofde-lab.premature-actuation-episode/1",
        "subject": SUBJECT,
        "workload_id": WORKLOAD,
        "policy_id": "policy:a",
        "episode_id": episode_id,
        "horizon": 3,
        "events": [{"step": 1, "phase": "OBSERVE"}, row],
    }


def test_recurrence_compresses_repeated_failure_into_powerless_guard_candidate() -> None:
    report = recurrence_report(
        [
            failed("a", failure="UNAUTHORIZED_DO"),
            failed("b", failure="UNAUTHORIZED_DO"),
            failed("c", failure="PREMATURE_DO"),
        ],
        min_occurrences=2,
    )

    assert len(report["guard_candidates"]) == 1
    guard = report["guard_candidates"][0]
    assert guard["failure_type"] == "UNAUTHORIZED_DO"
    assert guard["guard_id"] == "require_authority_before_do"
    assert guard["occurrences"] == 2
    assert guard["standing"] == "CANDIDATE"
    assert guard["authority"] == "none"
    assert guard["installation"] == "NOT_PERFORMED"
    assert report["uncompressed_failure_types"] == ["PREMATURE_DO"]


def test_threshold_one_manufactures_candidate_for_every_observed_failure_type() -> None:
    report = recurrence_report(
        [
            failed("a", failure="UNRECEIPTED_DO"),
            failed("b", failure="PREMATURE_DO"),
        ],
        min_occurrences=1,
    )
    assert {row["guard_id"] for row in report["guard_candidates"]} == {
        "require_receipt_before_do",
        "require_terminal_predicate_before_do",
    }
