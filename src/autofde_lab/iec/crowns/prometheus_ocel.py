"""OCEL 2.0 projection for observed SWE-Prometheus/VGG probe execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import IECRefusal, canonical_json, content_id
from .prometheus import DIMENSIONS, REPORT_SCHEMA
from .prometheus_probe import PAIR_SCHEMA, RUN_SCHEMA

OCEL_SCHEMA = "autofde-lab.swe-prometheus-ocel/1"


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise IECRefusal(
            "REFUSED_OCEL_WITHOUT_OBSERVED_TIME",
            f"invalid observed_at {value!r}",
        )
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IECRefusal(
            "REFUSED_OCEL_WITHOUT_OBSERVED_TIME",
            f"invalid observed_at {value!r}",
        ) from exc
    if parsed.tzinfo is None:
        raise IECRefusal(
            "REFUSED_OCEL_WITHOUT_OBSERVED_TIME",
            f"observed_at must be timezone-aware: {value!r}",
        )
    return parsed


def _attr(name: str, value: Any) -> dict[str, Any]:
    return {"name": name, "value": value}


def _relationship(object_id: str, qualifier: str) -> dict[str, str]:
    return {"objectId": object_id, "qualifier": qualifier}


def _validate_run(
    run: Mapping[str, Any],
    *,
    side: str,
    pair: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    if run.get("schema") != RUN_SCHEMA or run.get("side") != side:
        raise IECRefusal(
            "REFUSED_INVALID_OCEL_INPUT",
            f"{side} probe run schema/side mismatch",
        )
    if run.get("run_id") != pair.get(f"{side}_run_id"):
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            f"{side} run id does not match pair",
        )
    rows = run.get("receipts")
    if not isinstance(rows, list):
        raise IECRefusal(
            "REFUSED_INVALID_OCEL_INPUT",
            f"{side} receipts must be a list",
        )
    return [row for row in rows if isinstance(row, Mapping)]


def project_ocel(
    base_run: Mapping[str, Any],
    treated_run: Mapping[str, Any],
    pair: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Project observations and derived court decisions without inventing wall time."""
    if pair.get("schema") != PAIR_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_OCEL_INPUT",
            "invalid pair schema",
        )
    if report.get("schema") != REPORT_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_OCEL_INPUT",
            "invalid VGG report schema",
        )

    subject = f"git:{pair.get('repository')}@{pair.get('base_commit')}"
    if report.get("subject") != subject:
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            "VGG report subject does not match probe pair",
        )
    if report.get("patch_digest") != pair.get("patch_digest"):
        raise IECRefusal(
            "REFUSED_EXACT_SUBJECT_MISMATCH",
            "VGG report patch digest does not match probe pair",
        )

    base_rows = _validate_run(base_run, side="base", pair=pair)
    treated_rows = _validate_run(treated_run, side="treated", pair=pair)
    all_rows = base_rows + treated_rows
    if not all_rows:
        raise IECRefusal(
            "REFUSED_OCEL_WITHOUT_OBSERVED_TIME",
            "no probe observations to project",
        )
    observed_times = [_parse_time(row.get("observed_at")) for row in all_rows]
    latest = max(observed_times).isoformat().replace("+00:00", "Z")

    case_object = str(pair["pair_id"])
    report_object = str(report["id"])
    patch_object = str(pair["patch_digest"])

    objects: list[dict[str, Any]] = [
        {
            "id": subject,
            "type": "repository_snapshot",
            "attributes": [],
            "relationships": [],
        },
        {
            "id": patch_object,
            "type": "patch",
            "attributes": [],
            "relationships": [
                _relationship(subject, "applies-to"),
            ],
        },
        {
            "id": case_object,
            "type": "governance_case",
            "attributes": [],
            "relationships": [
                _relationship(subject, "base-subject"),
                _relationship(patch_object, "candidate-patch"),
            ],
        },
        {
            "id": report_object,
            "type": "vgg_report",
            "attributes": [],
            "relationships": [
                _relationship(case_object, "evaluates"),
            ],
        },
    ]
    for dimension in DIMENSIONS:
        objects.append(
            {
                "id": f"dimension:{dimension}",
                "type": "governance_dimension",
                "attributes": [],
                "relationships": [],
            }
        )

    receipt_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    for side, rows in (("base", base_rows), ("treated", treated_rows)):
        for row in rows:
            receipt_id = str(row.get("semantic_id", "")).strip()
            if not receipt_id:
                raise IECRefusal(
                    "REFUSED_INVALID_OCEL_INPUT",
                    f"{side} probe receipt has no semantic_id",
                )
            if receipt_id not in receipt_ids:
                receipt_ids.add(receipt_id)
                objects.append(
                    {
                        "id": receipt_id,
                        "type": "evidence_receipt",
                        "attributes": [],
                        "relationships": [
                            _relationship(case_object, "evidence-for"),
                        ],
                    }
                )

            relationships = [
                _relationship(case_object, "case"),
                _relationship(receipt_id, "produces"),
                _relationship(subject, "observes"),
            ]
            if side == "treated":
                relationships.append(
                    _relationship(patch_object, "under-patch")
                )
            dimension = row.get("dimension")
            if dimension in DIMENSIONS:
                relationships.append(
                    _relationship(
                        f"dimension:{dimension}",
                        "governance-dimension",
                    )
                )

            events.append(
                {
                    "id": content_id(
                        "prometheus-probe-event",
                        side,
                        receipt_id,
                    ),
                    "type": "probe.execute",
                    "time": str(row["observed_at"]),
                    "attributes": [
                        _attr("side", side),
                        _attr("probe_id", row.get("probe_id")),
                        _attr("role", row.get("role")),
                        _attr("status", row.get("status")),
                        _attr("exit_code", row.get("exit_code")),
                        _attr("stdout_digest", row.get("stdout_digest")),
                        _attr("stderr_digest", row.get("stderr_digest")),
                        _attr("duration_ms", row.get("duration_ms")),
                    ],
                    "relationships": relationships,
                }
            )

    events.append(
        {
            "id": content_id("prometheus-pair-event", pair["pair_id"]),
            "type": "pair.evaluate",
            "time": latest,
            "attributes": [
                _attr("behavior", pair.get("behavior")),
                _attr("gate_strength", pair.get("gate_strength")),
                _attr("time_basis", "latest-input-observation"),
            ],
            "relationships": [
                _relationship(case_object, "evaluates"),
                _relationship(subject, "base-subject"),
                _relationship(patch_object, "candidate-patch"),
            ],
        }
    )
    events.append(
        {
            "id": content_id("prometheus-vgg-event", report["id"]),
            "type": "vgg.evaluate",
            "time": latest,
            "attributes": [
                _attr("gate", report.get("gate")),
                _attr("standing", report["vgg"].get("standing")),
                _attr("ngi", report["paper"].get("ngi")),
                _attr("vgg", report["vgg"].get("value")),
                _attr("time_basis", "latest-input-observation"),
            ],
            "relationships": [
                _relationship(report_object, "produces"),
                _relationship(case_object, "evaluates"),
            ],
        }
    )

    events.sort(key=lambda event: (event["time"], event["id"]))
    objects.sort(key=lambda obj: (obj["type"], obj["id"]))

    document: dict[str, Any] = {
        "schema": OCEL_SCHEMA,
        "objectTypes": [
            {"name": "repository_snapshot", "attributes": []},
            {"name": "patch", "attributes": []},
            {"name": "governance_case", "attributes": []},
            {"name": "governance_dimension", "attributes": []},
            {"name": "evidence_receipt", "attributes": []},
            {"name": "vgg_report", "attributes": []},
        ],
        "eventTypes": [
            {
                "name": "probe.execute",
                "attributes": [
                    {"name": "side", "type": "string"},
                    {"name": "probe_id", "type": "string"},
                    {"name": "role", "type": "string"},
                    {"name": "status", "type": "string"},
                    {"name": "exit_code", "type": "integer"},
                    {"name": "stdout_digest", "type": "string"},
                    {"name": "stderr_digest", "type": "string"},
                    {"name": "duration_ms", "type": "float"},
                ],
            },
            {
                "name": "pair.evaluate",
                "attributes": [
                    {"name": "behavior", "type": "string"},
                    {"name": "gate_strength", "type": "string"},
                    {"name": "time_basis", "type": "string"},
                ],
            },
            {
                "name": "vgg.evaluate",
                "attributes": [
                    {"name": "gate", "type": "string"},
                    {"name": "standing", "type": "string"},
                    {"name": "ngi", "type": "float"},
                    {"name": "vgg", "type": "string"},
                    {"name": "time_basis", "type": "string"},
                ],
            },
        ],
        "objects": objects,
        "events": events,
        "claim_ceiling": (
            "probe.execute times are observed receipt times; pair/vgg evaluation "
            "events use latest-input-observation as an explicit logical time basis"
        ),
    }
    document["id"] = content_id(document)
    return document


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal(
            "REFUSED_INVALID_OCEL_INPUT",
            f"{path} must contain a JSON object",
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_run", type=Path)
    parser.add_argument("treated_run", type=Path)
    parser.add_argument("pair", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)

    result = project_ocel(
        _read(args.base_run),
        _read(args.treated_run),
        _read(args.pair),
        _read(args.report),
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
                "events": len(result["events"]),
                "objects": len(result["objects"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
