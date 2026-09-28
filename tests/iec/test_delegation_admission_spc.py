"""SPC tests for delegation/admission headroom drift."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.delegation_admission_spc import analyze_headroom
from autofde_lab.iec.crowns.model import IECRefusal


def receipt(headroom: list[int], *, gate: str = "PASS") -> dict:
    return {
        "schema": "autofde-lab.delegation-admission-history-receipt/1",
        "subject": "git:example/repo@spc",
        "receipt_id": "sha256:history",
        "snapshots": [
            {
                "sequence": index,
                "subject": "git:example/repo@spc",
                "receipt_id": f"sha256:{index}",
                "gate": gate,
                "delegation_units": 10,
                "admission_capacity_units": 10 + margin,
                "admission_debt_units": max(0, -margin),
                "standing": "PARTIAL_ALIVE",
                "falsifiers": [],
            }
            for index, margin in enumerate(headroom)
        ],
        "transitions": [],
    }


def test_stable_headroom_has_no_signal() -> None:
    report = analyze_headroom(receipt([3, 4, 5, 4, 4, 4, 5, 3, 4]), baseline_count=5)
    assert report["standing"] == "NO_SIGNAL_IN_BOUND"
    assert report["signals"] == []


def test_single_large_downward_excursion_fires_three_sigma_rule() -> None:
    report = analyze_headroom(receipt([3, 4, 5, 4, 4, 1]), baseline_count=5)
    assert report["standing"] == "DRIFT_SIGNAL"
    assert "WE1_BELOW_3_SIGMA" in {signal["rule"] for signal in report["signals"]}


def test_zero_variance_baseline_detects_any_downward_drop() -> None:
    report = analyze_headroom(receipt([4, 4, 4, 4, 4, 3]), baseline_count=5)
    assert report["standing"] == "DRIFT_SIGNAL"
    assert report["signals"] == [
        {
            "sequence": 5,
            "rule": "ZERO_VARIANCE_DROP",
            "headroom": 3.0,
            "threshold": 4.0,
        }
    ]


def test_insufficient_history_is_typed_unsupported_not_false_green() -> None:
    report = analyze_headroom(receipt([4, 4, 4]), baseline_count=5)
    assert report["standing"] == "UNSUPPORTED"
    assert report["reason"] == "INSUFFICIENT_BASELINE"


def test_nonadmitted_baseline_is_refused() -> None:
    with pytest.raises(
        IECRefusal,
        match="REFUSED_SPC_BASELINE_NOT_ADMITTED",
    ):
        analyze_headroom(receipt([4, 4, 4, 4, 4, 3], gate="COUNTEREXAMPLE"))


@pytest.mark.parametrize("baseline", [0, 1, 2, True])
def test_invalid_baseline_count_is_refused(baseline) -> None:
    with pytest.raises(IECRefusal, match="REFUSED_INVALID_SPC_BASELINE"):
        analyze_headroom(receipt([4, 4, 4, 4, 4]), baseline_count=baseline)
