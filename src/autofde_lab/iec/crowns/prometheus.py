"""SWE-Prometheus paired-governance court with a discriminative-evidence ceiling.

This module reproduces the paper's headroom-normalized governance improvement (NGI)
from paired dimension scores and then adds one stricter claim: governance gain may
reach ALIVE standing only when behavior preservation is supported by a mutation-
detected gate and the clean/replay receipts pass. A weak gate can still report the
paper metric; it cannot crown the stronger VGG claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .model import IECRefusal, Verdict, canonical_json, content_id

CASE_SCHEMA = "autofde-lab.swe-prometheus-case/1"
REPORT_SCHEMA = "autofde-lab.swe-prometheus-vgg/1"
SCORE_MAX = 5.0
DIMENSIONS = (
    "tests_ci",
    "quality_gates",
    "docs_collaboration",
    "structure_maintainability",
    "reproducible_environment",
    "dependency_security",
)
EVIDENCE_STATUSES = {"pass", "fail", "timeout", "unavailable", "not_applicable"}
BEHAVIOR = {"preserved", "broken", "invalid", "unavailable"}
GATE_STRENGTH = {"detected", "blind", "vacuous", "none"}


def _score(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IECRefusal("REFUSED_INVALID_PROMETHEUS_CASE", f"{field} must be numeric")
    value = float(value)
    if not 1.0 <= value <= SCORE_MAX:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE",
            f"{field}={value} outside [1, {SCORE_MAX:g}]",
        )
    return value


def _receipt(record: Any, field: str) -> dict[str, str]:
    if not isinstance(record, Mapping):
        raise IECRefusal("REFUSED_INVALID_PROMETHEUS_CASE", f"{field} must be an object")
    verdict = str(record.get("verdict", ""))
    if verdict not in {v.value for v in Verdict}:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", f"{field}.verdict={verdict!r} is invalid"
        )
    receipt_id = str(record.get("receipt_id", "")).strip()
    if not receipt_id:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", f"{field}.receipt_id is required"
        )
    return {"verdict": verdict, "receipt_id": receipt_id}


def _dimension(name: str, row: Any) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", f"dimension {name} must be an object"
        )
    status = str(row.get("evidence_status", ""))
    if status not in EVIDENCE_STATUSES:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE",
            f"dimension {name} has invalid evidence_status {status!r}",
        )
    if status != "pass":
        return {
            "evidence_status": status,
            "scorable": False,
            "base": None,
            "treated": None,
            "delta": None,
            "headroom_normalized_gain": None,
            "regression": False,
        }
    base = _score(row.get("base"), f"dimensions.{name}.base")
    treated = _score(row.get("treated"), f"dimensions.{name}.treated")
    delta = treated - base
    normalized = None if base == SCORE_MAX else delta / (SCORE_MAX - base)
    return {
        "evidence_status": status,
        "scorable": True,
        "base": base,
        "treated": treated,
        "delta": delta,
        "headroom_normalized_gain": normalized,
        "regression": delta < 0,
    }


def _parse(case: Mapping[str, Any]) -> dict[str, Any]:
    if case.get("schema") != CASE_SCHEMA:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE",
            f"schema must be {CASE_SCHEMA}, got {case.get('schema')!r}",
        )
    repository = str(case.get("repository", "")).strip()
    base_commit = str(case.get("base_commit", "")).strip()
    patch_digest = str(case.get("patch_digest", "")).strip()
    if not repository or "/" not in repository:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", "repository must be owner/name"
        )
    if not base_commit or not patch_digest:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", "base_commit and patch_digest are required"
        )
    behavior = str(case.get("behavior", ""))
    gate_strength = str(case.get("gate_strength", ""))
    if behavior not in BEHAVIOR:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", f"invalid behavior {behavior!r}"
        )
    if gate_strength not in GATE_STRENGTH:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE",
            f"invalid gate_strength {gate_strength!r}",
        )
    mutation_receipt_id = case.get("mutation_receipt_id")
    if gate_strength == "detected" and not str(mutation_receipt_id or "").strip():
        raise IECRefusal(
            "REFUSED_UNBOUNDED_EQUIVALENCE",
            "detected gate must name mutation_receipt_id",
        )
    dimensions_raw = case.get("dimensions")
    if not isinstance(dimensions_raw, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE", "dimensions must be an object"
        )
    unknown = sorted(set(dimensions_raw) - set(DIMENSIONS))
    missing = sorted(set(DIMENSIONS) - set(dimensions_raw))
    if unknown or missing:
        raise IECRefusal(
            "REFUSED_INVALID_PROMETHEUS_CASE",
            f"dimension universe mismatch missing={missing} unknown={unknown}",
        )
    dimensions = {name: _dimension(name, dimensions_raw[name]) for name in DIMENSIONS}
    return {
        "repository": repository,
        "base_commit": base_commit,
        "patch_digest": patch_digest,
        "behavior": behavior,
        "gate_strength": gate_strength,
        "mutation_receipt_id": (
            None if mutation_receipt_id is None else str(mutation_receipt_id)
        ),
        "clean_environment": _receipt(case.get("clean_environment"), "clean_environment"),
        "replay": _receipt(case.get("replay"), "replay"),
        "dimensions": dimensions,
        "model": case.get("model"),
        "scaffold": case.get("scaffold"),
    }


def _ngi(dimensions: Mapping[str, Mapping[str, Any]]) -> tuple[float | None, list[str]]:
    eligible: list[str] = []
    values: list[float] = []
    for name in DIMENSIONS:
        row = dimensions[name]
        if row["scorable"] and row["base"] < SCORE_MAX:
            eligible.append(name)
            values.append(float(row["headroom_normalized_gain"]))
    if not values:
        return None, eligible
    return sum(values) / len(values), eligible


def _standing(parsed: Mapping[str, Any], no_regression: bool) -> tuple[str, str]:
    if parsed["behavior"] == "broken":
        return "BUILD_BROKEN", "treated characterization behavior regressed"
    if parsed["behavior"] != "preserved":
        return "UNKNOWN", f"behavior={parsed['behavior']}"
    if parsed["clean_environment"]["verdict"] != Verdict.PASS.value:
        return "PARTIAL_ALIVE", "clean-environment reconstruction is not PASS"
    if parsed["replay"]["verdict"] != Verdict.PASS.value:
        return "PARTIAL_ALIVE", "replay is not PASS"
    if not no_regression:
        return "PARTIAL_ALIVE", "one or more scorable governance dimensions regressed"
    if parsed["gate_strength"] == "detected":
        return "ALIVE", "mutation-detected preservation gate + clean replay"
    if parsed["gate_strength"] in {"blind", "vacuous"}:
        return "PARTIAL_ALIVE", f"behavior gate is {parsed['gate_strength']}"
    return "UNKNOWN", "no characterization gate"


def evaluate_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute paper NGI and apply the stronger VGG evidence ceiling."""
    parsed = _parse(case)
    dimensions = parsed["dimensions"]
    ngi, eligible = _ngi(dimensions)
    scorable = [name for name in DIMENSIONS if dimensions[name]["scorable"]]
    regressions = [name for name in DIMENSIONS if dimensions[name]["regression"]]
    no_regression = not regressions
    standing, reason = _standing(parsed, no_regression)
    behavior_valid = parsed["behavior"] == "preserved"
    strict_positive = ngi is not None and ngi > 0 and no_regression and behavior_valid
    admitted_vgg: float | str
    if standing == "ALIVE" and strict_positive:
        admitted_vgg = ngi
    else:
        admitted_vgg = "UNREPRESENTABLE:EVIDENCE_CEILING"
    falsifiers: list[str] = []
    if parsed["behavior"] == "broken":
        falsifiers.append("BEHAVIOR_BROKEN")
    elif parsed["behavior"] != "preserved":
        falsifiers.append("BEHAVIOR_NOT_PRESERVED")
    if regressions:
        falsifiers.append("GOVERNANCE_REGRESSION")
    if parsed["clean_environment"]["verdict"] != Verdict.PASS.value:
        falsifiers.append("CLEAN_ENVIRONMENT_NOT_PASS")
    if parsed["replay"]["verdict"] != Verdict.PASS.value:
        falsifiers.append("REPLAY_NOT_PASS")
    if parsed["gate_strength"] != "detected":
        falsifiers.append("NON_DISCRIMINATIVE_BEHAVIOR_GATE")
    if ngi is None:
        falsifiers.append("NO_NGI_DENOMINATOR")
    elif ngi <= 0:
        falsifiers.append("NO_POSITIVE_GOVERNANCE_GAIN")
    subject = f"git:{parsed['repository']}@{parsed['base_commit']}"
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "subject": subject,
        "patch_digest": parsed["patch_digest"],
        "paper": {
            "arxiv": "2609.29465",
            "ngi": ngi,
            "behavior_valid": behavior_valid,
            "gate_strength": parsed["gate_strength"],
            "eligible_dimensions": eligible,
            "scorable_dimensions": scorable,
            "regressions": regressions,
            "no_regression": no_regression,
        },
        "dimensions": dimensions,
        "evidence": {
            "clean_environment": parsed["clean_environment"],
            "replay": parsed["replay"],
            "mutation_receipt_id": parsed["mutation_receipt_id"],
        },
        "vgg": {
            "value": admitted_vgg,
            "standing": standing,
            "standing_reason": reason,
            "claim": "VERIFIED_GOVERNANCE_GAIN_FOR_EXACT_BASE_AND_PATCH",
        },
        "falsifiers": falsifiers,
        "gate": (
            Verdict.PASS.value
            if standing == "ALIVE" and strict_positive
            else Verdict.COUNTEREXAMPLE.value
        ),
        "claim_ceiling": (
            "paper NGI remains reportable for preserved weak-gate runs; "
            "ALIVE/VGG additionally requires a mutation-detected behavior gate, "
            "clean-environment PASS, replay PASS, positive NGI, and no regression"
        ),
        "model": parsed["model"],
        "scaffold": parsed["scaffold"],
    }
    report["id"] = content_id(report)
    return report


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IECRefusal("REFUSED_INVALID_PROMETHEUS_CASE", f"{path} must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)
    result = evaluate_case(_read(args.case))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "id": result["id"],
                "gate": result["gate"],
                "falsifiers": result["falsifiers"],
            }
        )
    )
    return 1 if args.gate and result["gate"] != Verdict.PASS.value else 0


if __name__ == "__main__":
    raise SystemExit(main())
