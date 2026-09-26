"""Content-addressed survival evidence bundle and replay receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import IECRefusal, content_id
from .survival import analyze_episode
from .survival_compare import cohort_report
from .survival_ocel import episode_to_ocel_log
from .survival_recurrence import recurrence_report
from .survival_uncertainty import survival_uncertainty

BUNDLE_SCHEMA = "autofde-lab.premature-actuation-bundle/1"
REPLAY_SCHEMA = "autofde-lab.premature-actuation-bundle-replay/1"


def _episode_evidence(
    documents: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for document in documents:
        report = analyze_episode(document)
        log = episode_to_ocel_log(document)
        rows.append(
            {
                "episode_id": report["episode_id"],
                "policy_id": report["policy_id"],
                "episode_report_id": report["id"],
                "ocel_digest": log.digest(),
                "failed": report["failed"],
                "first_failure_step": report["first_failure_step"],
                "first_failure_types": report["first_failure_types"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["policy_id"]),
            str(row["episode_id"]),
        ),
    )


def build_survival_bundle(
    documents: Sequence[Mapping[str, Any]],
    *,
    min_occurrences: int = 2,
) -> dict[str, Any]:
    """Build one replayable receipt over cohort, recurrence, and OCEL evidence."""
    cohort = cohort_report(documents)
    recurrence = recurrence_report(
        documents,
        min_occurrences=min_occurrences,
    )
    episode_evidence = _episode_evidence(documents)
    policy_uncertainty = {
        policy_id: survival_uncertainty(report)
        for policy_id, report in cohort["policies"].items()
    }

    bundle = {
        "schema": BUNDLE_SCHEMA,
        "subject": cohort["subject"],
        "workload_id": cohort["workload_id"],
        "horizon": cohort["horizon"],
        "episodes": cohort["episodes"],
        "policy_count": cohort["policy_count"],
        "cohort_id": cohort["id"],
        "recurrence_id": recurrence["id"],
        "policy_uncertainty_ids": {
            policy_id: report["id"]
            for policy_id, report in sorted(policy_uncertainty.items())
        },
        "min_occurrences": min_occurrences,
        "episode_evidence": episode_evidence,
        "authority": "none",
        "actuation_performed": False,
        "standing": "STRUCTURAL",
        "claim_ceiling": (
            "content-addressed observed survival evidence only; no causal effect, "
            "production standing, guard installation, or DO authority implied"
        ),
    }
    bundle["id"] = content_id(bundle)
    return bundle


def replay_survival_bundle(
    documents: Sequence[Mapping[str, Any]],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the bundle and report exact replay mismatch categories."""
    if expected.get("schema") != BUNDLE_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_BUNDLE",
            f"schema must be {BUNDLE_SCHEMA}",
        )
    threshold = expected.get("min_occurrences")
    if isinstance(threshold, bool) or not isinstance(threshold, int):
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_BUNDLE",
            "min_occurrences must be an integer",
        )

    observed = build_survival_bundle(
        documents,
        min_occurrences=threshold,
    )
    mismatches: list[str] = []
    for field, code in (
        ("subject", "SUBJECT_MISMATCH"),
        ("workload_id", "WORKLOAD_MISMATCH"),
        ("horizon", "HORIZON_MISMATCH"),
        ("episodes", "EPISODE_COUNT_MISMATCH"),
        ("policy_count", "POLICY_COUNT_MISMATCH"),
        ("cohort_id", "COHORT_MISMATCH"),
        ("recurrence_id", "RECURRENCE_MISMATCH"),
        ("policy_uncertainty_ids", "UNCERTAINTY_MISMATCH"),
        ("episode_evidence", "OCEL_OR_EPISODE_EVIDENCE_MISMATCH"),
        ("id", "BUNDLE_ID_MISMATCH"),
    ):
        if expected.get(field) != observed.get(field):
            mismatches.append(code)

    receipt = {
        "schema": REPLAY_SCHEMA,
        "expected_bundle_id": expected.get("id"),
        "observed_bundle_id": observed["id"],
        "matched": not mismatches,
        "mismatches": mismatches,
        "authority": "none",
        "actuation_performed": False,
    }
    receipt["id"] = content_id(receipt)
    return receipt


def _read_episode_list(path: Path) -> list[Mapping[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise IECRefusal(
            "REFUSED_INVALID_SURVIVAL_EPISODE",
            "input must be a JSON list of episode objects",
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("episodes", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--min-occurrences", type=int, default=2)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args(argv)

    documents = _read_episode_list(args.episodes)
    if args.replay is None:
        result = build_survival_bundle(
            documents,
            min_occurrences=args.min_occurrences,
        )
        exit_code = 0
    else:
        expected = json.loads(args.replay.read_text(encoding="utf-8"))
        if not isinstance(expected, dict):
            raise IECRefusal(
                "REFUSED_INVALID_SURVIVAL_BUNDLE",
                "replay target must be a JSON object",
            )
        result = replay_survival_bundle(documents, expected)
        exit_code = 0 if result["matched"] else 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"id": result["id"]}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
