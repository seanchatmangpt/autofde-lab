"""Batch league for SWE-Prometheus/VGG reports with comparability guards."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from .model import IECRefusal, canonical_json, content_id
from .prometheus import CASE_SCHEMA, DIMENSIONS, REPORT_SCHEMA, evaluate_case

LEAGUE_SCHEMA = "autofde-lab.swe-prometheus-league/1"


def _system_id(report: Mapping[str, Any]) -> str:
    model = str(report.get("model") or "UNSPECIFIED_MODEL").strip()
    scaffold = str(report.get("scaffold") or "UNSPECIFIED_SCAFFOLD").strip()
    return f"{model}::{scaffold}"


def _as_report(document: Mapping[str, Any]) -> dict[str, Any]:
    schema = document.get("schema")
    if schema == CASE_SCHEMA:
        return evaluate_case(document)
    if schema != REPORT_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_LEAGUE",
            f"unsupported document schema {schema!r}",
        )
    required = {
        "id",
        "subject",
        "paper",
        "dimensions",
        "evidence",
        "vgg",
        "falsifiers",
        "gate",
    }
    missing = sorted(required - set(document))
    if missing:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_LEAGUE",
            f"report missing fields {missing}",
        )
    return dict(document)


def _numeric(values: Sequence[Any]) -> list[float]:
    return [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _dimension_stats(
    reports: Sequence[Mapping[str, Any]],
    dimension: str,
) -> dict[str, Any]:
    rows = [
        report["dimensions"][dimension]
        for report in reports
        if isinstance(report.get("dimensions"), Mapping)
        and dimension in report["dimensions"]
    ]
    scorable = [row for row in rows if row.get("scorable") is True]
    base = _numeric([row.get("base") for row in scorable])
    treated = _numeric([row.get("treated") for row in scorable])
    delta = _numeric([row.get("delta") for row in scorable])
    return {
        "observed": len(rows),
        "scorable": len(scorable),
        "coverage_rate": _ratio(len(scorable), len(reports)),
        "mean_base": None if not base else mean(base),
        "mean_treated": None if not treated else mean(treated),
        "mean_delta": None if not delta else mean(delta),
        "regressions": sum(bool(row.get("regression")) for row in scorable),
        "evidence_statuses": dict(
            sorted(Counter(str(row.get("evidence_status")) for row in rows).items())
        ),
    }


def _metrics(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {
            "runs": 0,
            "subjects": 0,
            "behavior_preserved_rate": 0.0,
            "detected_gate_rate": 0.0,
            "alive_rate": 0.0,
            "vgg_admission_rate": 0.0,
            "mean_ngi": None,
            "mean_numeric_vgg": None,
            "regression_rate": 0.0,
            "clean_environment_pass_rate": 0.0,
            "replay_pass_rate": 0.0,
            "falsifiers": {},
            "dimensions": {
                dimension: _dimension_stats([], dimension)
                for dimension in DIMENSIONS
            },
        }

    ngi = _numeric([report["paper"].get("ngi") for report in reports])
    vgg = _numeric([report["vgg"].get("value") for report in reports])
    return {
        "runs": len(reports),
        "subjects": len({str(report["subject"]) for report in reports}),
        "behavior_preserved_rate": _ratio(
            sum(bool(report["paper"].get("behavior_valid")) for report in reports),
            len(reports),
        ),
        "detected_gate_rate": _ratio(
            sum(
                report["paper"].get("gate_strength") == "detected"
                for report in reports
            ),
            len(reports),
        ),
        "alive_rate": _ratio(
            sum(report["vgg"].get("standing") == "ALIVE" for report in reports),
            len(reports),
        ),
        "vgg_admission_rate": _ratio(len(vgg), len(reports)),
        "mean_ngi": None if not ngi else mean(ngi),
        "mean_numeric_vgg": None if not vgg else mean(vgg),
        "regression_rate": _ratio(
            sum(not bool(report["paper"].get("no_regression")) for report in reports),
            len(reports),
        ),
        "clean_environment_pass_rate": _ratio(
            sum(
                report["evidence"]["clean_environment"].get("verdict") == "PASS"
                for report in reports
            ),
            len(reports),
        ),
        "replay_pass_rate": _ratio(
            sum(
                report["evidence"]["replay"].get("verdict") == "PASS"
                for report in reports
            ),
            len(reports),
        ),
        "falsifiers": dict(
            sorted(
                Counter(
                    falsifier
                    for report in reports
                    for falsifier in report.get("falsifiers", [])
                ).items()
            )
        ),
        "dimensions": {
            dimension: _dimension_stats(reports, dimension)
            for dimension in DIMENSIONS
        },
    }


def build_league(
    documents: Sequence[Mapping[str, Any]],
    *,
    require_common_subjects: bool = False,
) -> dict[str, Any]:
    """Aggregate systems without turning incomparable subject sets into a ranking."""
    reports = [_as_report(document) for document in documents]
    if not reports:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_LEAGUE",
            "at least one case/report is required",
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    for report in reports:
        system = _system_id(report)
        subject = str(report["subject"])
        key = (system, subject)
        if key in seen:
            raise IECRefusal(
                "REFUSED_DUPLICATE_BENCHMARK_SUBJECT",
                f"{system} has more than one report for {subject}",
            )
        seen.add(key)
        grouped.setdefault(system, []).append(report)

    subject_sets = {
        system: {str(report["subject"]) for report in rows}
        for system, rows in grouped.items()
    }
    all_sets = list(subject_sets.values())
    common_subjects = set.intersection(*all_sets) if all_sets else set()
    union_subjects = set.union(*all_sets) if all_sets else set()
    fully_comparable = all(
        subjects == all_sets[0] for subjects in all_sets[1:]
    ) if all_sets else True

    if require_common_subjects and not fully_comparable:
        missing = {
            system: sorted(union_subjects - subjects)
            for system, subjects in subject_sets.items()
            if subjects != union_subjects
        }
        raise IECRefusal(
            "REFUSED_INCOMPARABLE_SUBJECT_SETS",
            f"systems do not share an exact subject set: {missing}",
        )

    systems: dict[str, Any] = {}
    for system, rows in sorted(grouped.items()):
        common_rows = [
            report
            for report in rows
            if str(report["subject"]) in common_subjects
        ]
        systems[system] = {
            "model": rows[0].get("model"),
            "scaffold": rows[0].get("scaffold"),
            "subjects": sorted(subject_sets[system]),
            "all_observed": _metrics(rows),
            "common_subjects_only": _metrics(common_rows),
        }

    league: dict[str, Any] = {
        "schema": LEAGUE_SCHEMA,
        "comparability": {
            "standing": "FULL" if fully_comparable else "PARTIAL",
            "common_subjects": sorted(common_subjects),
            "union_subjects": sorted(union_subjects),
            "subject_sets": {
                system: sorted(subjects)
                for system, subjects in sorted(subject_sets.items())
            },
            "claim_ceiling": (
                "cross-system comparisons are bounded to common_subjects_only "
                "unless all systems share the exact same subject set"
            ),
        },
        "systems": systems,
        "reports": [
            {
                "id": report["id"],
                "system": _system_id(report),
                "subject": report["subject"],
                "patch_digest": report.get("patch_digest"),
                "gate": report["gate"],
                "standing": report["vgg"].get("standing"),
            }
            for report in sorted(
                reports,
                key=lambda item: (_system_id(item), str(item["subject"])),
            )
        ],
    }
    league["id"] = content_id(league)
    return league


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_LEAGUE",
            f"{path} must contain a JSON object",
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("documents", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-common-subjects", action="store_true")
    args = parser.parse_args(argv)

    result = build_league(
        [_read(path) for path in args.documents],
        require_common_subjects=args.require_common_subjects,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "id": result["id"],
                "comparability": result["comparability"]["standing"],
                "systems": len(result["systems"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
