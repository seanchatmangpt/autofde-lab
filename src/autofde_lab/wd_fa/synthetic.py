from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pandas as pd

from .domain import EvidenceArtifact, FailureCase, FailureModeRule


RULES = (
    FailureModeRule(
        mode_id="MODE-A-FIRMWARE",
        applicability={"symptom_code": 1, "firmware": 1},
        falsifiers={"firmware": 2},
        required_evidence_kinds=frozenset({"test", "waveform"}),
        next_action="run_firmware_regression",
    ),
    FailureModeRule(
        mode_id="MODE-B-SUPPLIER",
        applicability={"symptom_code": 1, "supplier": 2},
        falsifiers={"supplier": 1},
        required_evidence_kinds=frozenset({"test", "lot_trace"}),
        next_action="inspect_supplier_lot",
    ),
    FailureModeRule(
        mode_id="MODE-C-SERVO",
        applicability={"symptom_code": 3, "station": 9},
        falsifiers={"station": 4},
        required_evidence_kinds=frozenset({"test", "servo_trace"}),
        next_action="run_servo_calibration",
    ),
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def evidence(case_id: str, kinds: tuple[str, ...]) -> tuple[EvidenceArtifact, ...]:
    return tuple(
        EvidenceArtifact(f"{case_id}:{kind}", kind, _digest(f"{case_id}:{kind}"))
        for kind in kinds
    )


def make_case(
    case_id: str,
    *,
    symptom_code: int,
    firmware: int,
    supplier: int,
    station: int,
    lot_risk: float,
    rework_count: int,
    vibration: float,
    kinds: tuple[str, ...],
    process: tuple[str, ...],
) -> FailureCase:
    return FailureCase(
        case_id=case_id,
        drive_id=f"DRIVE-{case_id}",
        symptom=f"symptom-{symptom_code}",
        facts={
            "symptom_code": symptom_code,
            "firmware": firmware,
            "supplier": supplier,
            "station": station,
            "lot_risk": lot_risk,
            "rework_count": rework_count,
            "vibration": vibration,
        },
        evidence=evidence(case_id, kinds),
        process=process,
    )


def named_cases() -> dict[str, FailureCase]:
    return {
        "known_a": make_case(
            "KNOWN-A",
            symptom_code=1, firmware=1, supplier=1, station=4,
            lot_risk=0.15, rework_count=0, vibration=0.22,
            kinds=("test", "waveform"),
            process=("drive_built", "firmware_loaded", "test_failed", "evidence_collected"),
        ),
        "known_b_misleading": make_case(
            "KNOWN-B",
            symptom_code=1, firmware=1, supplier=2, station=4,
            lot_risk=0.82, rework_count=1, vibration=0.24,
            kinds=("test", "lot_trace"),
            process=("drive_built", "test_failed", "drive_reworked", "test_failed", "evidence_collected"),
        ),
        "incomplete_a": make_case(
            "PARTIAL-A",
            symptom_code=1, firmware=1, supplier=1, station=4,
            lot_risk=0.16, rework_count=0, vibration=0.23,
            kinds=("test",),
            process=("drive_built", "firmware_loaded", "test_failed"),
        ),
        "novel_x": make_case(
            "NOVEL-X",
            symptom_code=7, firmware=3, supplier=4, station=12,
            lot_risk=0.47, rework_count=2, vibration=0.91,
            kinds=("test", "waveform", "lot_trace"),
            process=("drive_built", "test_failed", "drive_reworked", "evidence_collected"),
        ),
        "novel_x_replay": make_case(
            "NOVEL-X-REPLAY",
            symptom_code=7, firmware=3, supplier=4, station=12,
            lot_risk=0.48, rework_count=2, vibration=0.90,
            kinds=("test", "waveform", "lot_trace"),
            process=("drive_built", "test_failed", "drive_reworked", "evidence_collected"),
        ),
    }


FEATURE_COLUMNS = (
    "symptom_code", "firmware", "supplier", "station",
    "lot_risk", "rework_count", "vibration",
)


def training_frame() -> tuple[pd.DataFrame, pd.Series]:
    rows: list[dict[str, float | int]] = []
    labels: list[str] = []
    for idx in range(18):
        rows.append({"symptom_code":1, "firmware":1, "supplier":1, "station":4,
                     "lot_risk":0.08 + idx * 0.008, "rework_count":idx % 2, "vibration":0.18 + idx * 0.004})
        labels.append("MODE-A-FIRMWARE")
        rows.append({"symptom_code":1, "firmware":1 + (idx % 3 == 0), "supplier":2, "station":4,
                     "lot_risk":0.72 + idx * 0.009, "rework_count":1 + idx % 2, "vibration":0.20 + idx * 0.004})
        labels.append("MODE-B-SUPPLIER")
        rows.append({"symptom_code":3, "firmware":2, "supplier":1, "station":9,
                     "lot_risk":0.22 + idx * 0.006, "rework_count":idx % 2, "vibration":0.58 + idx * 0.006})
        labels.append("MODE-C-SERVO")
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS), pd.Series(labels, name="failure_mode")


def feature_frame(case: FailureCase) -> pd.DataFrame:
    return pd.DataFrame([{name: case.facts[name] for name in FEATURE_COLUMNS}], columns=FEATURE_COLUMNS)


def event_rows(case: FailureCase) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = datetime(2026, 9, 21, 12, tzinfo=UTC)
    event_records = []
    object_records = [
        {"ocel:oid": case.drive_id, "ocel:type": "Drive"},
        {"ocel:oid": case.case_id, "ocel:type": "FailureCase"},
        {"ocel:oid": f"LOT-{case.facts['supplier']}", "ocel:type": "Lot"},
        {"ocel:oid": f"FW-{case.facts['firmware']}", "ocel:type": "FirmwareRevision"},
        {"ocel:oid": f"STATION-{case.facts['station']}", "ocel:type": "TestStation"},
    ]
    relations = []
    for idx, activity in enumerate(case.process):
        eid = f"{case.case_id}:E{idx:02d}"
        timestamp = base + timedelta(minutes=idx)
        event_records.append({"ocel:eid": eid, "ocel:activity": activity, "ocel:timestamp": timestamp})
        related = (
            (case.drive_id, "Drive", "subject"),
            (case.case_id, "FailureCase", "case"),
            (f"LOT-{case.facts['supplier']}", "Lot", "context"),
            (f"FW-{case.facts['firmware']}", "FirmwareRevision", "context"),
            (f"STATION-{case.facts['station']}", "TestStation", "context"),
        )
        for oid, otype, qualifier in related:
            relations.append({
                "ocel:eid": eid, "ocel:activity": activity, "ocel:timestamp": timestamp,
                "ocel:oid": oid, "ocel:type": otype, "ocel:qualifier": qualifier,
            })
    return pd.DataFrame(event_records), pd.DataFrame(object_records), pd.DataFrame(relations)
