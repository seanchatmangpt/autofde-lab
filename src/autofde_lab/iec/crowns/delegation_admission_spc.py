"""Statistical process control for delegation/admission headroom.

The monitored signal is admission headroom:

    headroom = admission_capacity_units - delegation_units

Negative headroom is already admission debt and belongs to the semantic court.
This module detects downward drift *before* debt using one-sided Western Electric
rules over an admitted baseline. A drift signal is observation, not refusal or
authority loss.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import IECRefusal, canonical_json, content_id

__all__ = ["SPC_SCHEMA", "analyze_headroom", "main"]

SPC_SCHEMA = "autofde-lab.delegation-admission-spc/1"


def _receipt(document: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    if document.get("schema") != "autofde-lab.delegation-admission-history-receipt/1":
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "SPC requires a delegation admission history receipt",
        )
    snapshots = document.get("snapshots")
    subject = document.get("subject")
    if not isinstance(snapshots, list) or not snapshots:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "history receipt has no snapshots",
        )
    if not isinstance(subject, str) or not subject:
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "history receipt subject is missing",
        )
    if not all(isinstance(snapshot, Mapping) for snapshot in snapshots):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "history snapshots must be objects",
        )
    return snapshots, subject


def _headroom(snapshot: Mapping[str, Any]) -> float:
    capacity = snapshot.get("admission_capacity_units")
    delegation = snapshot.get("delegation_units")
    if (
        isinstance(capacity, bool)
        or not isinstance(capacity, int)
        or isinstance(delegation, bool)
        or not isinstance(delegation, int)
    ):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            "capacity/delegation must be integers",
        )
    return float(capacity - delegation)


def _rule_2_of_3(values: Sequence[float], threshold: float) -> bool:
    return len(values) == 3 and sum(value < threshold for value in values) >= 2


def _rule_4_of_5(values: Sequence[float], threshold: float) -> bool:
    return len(values) == 5 and sum(value < threshold for value in values) >= 4


def analyze_headroom(
    document: Mapping[str, Any],
    *,
    baseline_count: int = 5,
) -> dict[str, Any]:
    """Run one-sided downward Western Electric rules on admission headroom."""
    if (
        isinstance(baseline_count, bool)
        or not isinstance(baseline_count, int)
        or baseline_count < 3
    ):
        raise IECRefusal(
            "REFUSED_INVALID_SPC_BASELINE",
            "baseline_count must be an integer >= 3",
        )

    snapshots, subject = _receipt(document)
    if len(snapshots) < baseline_count:
        report: dict[str, Any] = {
            "schema": SPC_SCHEMA,
            "subject": subject,
            "standing": "UNSUPPORTED",
            "reason": "INSUFFICIENT_BASELINE",
            "baseline_count": baseline_count,
            "observed_snapshots": len(snapshots),
            "signals": [],
            "claim_ceiling": "SPC observation only; no admission or authority effect",
        }
        report["receipt_id"] = content_id(report)
        return report

    baseline = snapshots[:baseline_count]
    if any(snapshot.get("gate") != "PASS" for snapshot in baseline):
        raise IECRefusal(
            "REFUSED_SPC_BASELINE_NOT_ADMITTED",
            "every baseline snapshot must have gate PASS",
        )

    headroom = [_headroom(snapshot) for snapshot in snapshots]
    baseline_values = headroom[:baseline_count]
    mean = statistics.mean(baseline_values)
    sigma = statistics.pstdev(baseline_values)

    signals: list[dict[str, Any]] = []
    post = headroom[baseline_count:]
    for offset, value in enumerate(post, start=baseline_count):
        if sigma == 0.0:
            if value < mean:
                signals.append(
                    {
                        "sequence": offset,
                        "rule": "ZERO_VARIANCE_DROP",
                        "headroom": value,
                        "threshold": mean,
                    }
                )
            continue

        if value < mean - 3 * sigma:
            signals.append(
                {
                    "sequence": offset,
                    "rule": "WE1_BELOW_3_SIGMA",
                    "headroom": value,
                    "threshold": mean - 3 * sigma,
                }
            )
        window3 = headroom[max(baseline_count, offset - 2) : offset + 1]
        if _rule_2_of_3(window3, mean - 2 * sigma):
            signals.append(
                {
                    "sequence": offset,
                    "rule": "WE2_TWO_OF_THREE_BELOW_2_SIGMA",
                    "headroom": value,
                    "threshold": mean - 2 * sigma,
                }
            )
        window5 = headroom[max(baseline_count, offset - 4) : offset + 1]
        if _rule_4_of_5(window5, mean - sigma):
            signals.append(
                {
                    "sequence": offset,
                    "rule": "WE3_FOUR_OF_FIVE_BELOW_1_SIGMA",
                    "headroom": value,
                    "threshold": mean - sigma,
                }
            )
        window8 = headroom[max(baseline_count, offset - 7) : offset + 1]
        if len(window8) == 8 and all(value_ < mean for value_ in window8):
            signals.append(
                {
                    "sequence": offset,
                    "rule": "WE4_EIGHT_BELOW_MEAN",
                    "headroom": value,
                    "threshold": mean,
                }
            )

    report = {
        "schema": SPC_SCHEMA,
        "subject": subject,
        "standing": "DRIFT_SIGNAL" if signals else "NO_SIGNAL_IN_BOUND",
        "baseline_count": baseline_count,
        "observed_snapshots": len(snapshots),
        "baseline": {
            "mean_headroom": mean,
            "sigma_headroom": sigma,
            "lower_1_sigma": mean - sigma,
            "lower_2_sigma": mean - 2 * sigma,
            "lower_3_sigma": mean - 3 * sigma,
        },
        "headroom": headroom,
        "signals": signals,
        "claim_ceiling": (
            "one-sided bounded SPC signal over admitted history; signal is not "
            "semantic refusal, causality, or authority loss"
        ),
    }
    report["receipt_id"] = content_id(report)
    return report


def _load(path: str) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise IECRefusal(
            "REFUSED_INVALID_DELEGATION_HISTORY_RECEIPT",
            f"{path}: top-level JSON value must be an object",
        )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history_receipt")
    parser.add_argument("spc_receipt")
    parser.add_argument("--baseline-count", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        report = analyze_headroom(
            _load(args.history_receipt),
            baseline_count=args.baseline_count,
        )
        Path(args.spc_receipt).write_text(
            canonical_json(report) + "\n",
            encoding="utf-8",
        )
    except (IECRefusal, OSError, json.JSONDecodeError):
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
