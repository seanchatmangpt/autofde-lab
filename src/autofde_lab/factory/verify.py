"""Fresh verifier: recomputes standing from the durable ledger alone.

Imports neither the loop nor the world. Relations are accepted only through
explicit fields (``derived_from_case``); a class_key match never creates a join.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from autofde_lab.wd_fa.receipts import VerificationReceipt, verify_receipt


@dataclass(frozen=True)
class FactoryVerdict:
    technical_standing: str
    # No component computes organizational standing (see standing-law.md).
    organizational_standing: str = "UNKNOWN"
    enterprise_standing: str = "UNKNOWN"
    findings: tuple[str, ...] = field(default_factory=tuple)
    experience_routes: int = 0
    investigation_cost: int = 0
    replay_cost: int = 0


def _receipt(d: dict) -> VerificationReceipt:
    d = dict(d)
    d["evidence_digests"] = tuple(d["evidence_digests"])
    return VerificationReceipt(**d)


def verify_ledger(path: Path) -> FactoryVerdict:
    rows = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    if not rows:
        return FactoryVerdict("UNKNOWN", findings=("EMPTY_LEDGER",))
    findings: list[str] = []
    by_case = {r["case_id"]: r for r in rows}
    if len(by_case) != len(rows) or [r["seq"] for r in rows] != list(range(len(rows))):
        findings.append("LEDGER_IDENTITY_OR_ORDER")
    compiled: dict[tuple, int] = {}
    inv_cost = replay_cost = routes = 0
    for r in rows:
        key = tuple(r["class_key"])
        if r["route"] == "investigation":
            inv_cost += r["cost"]
            rc = r["receipt"]
            if rc is None or not verify_receipt(_receipt(rc)):
                findings.append(f"INVALID_RECEIPT:{r['case_id']}")
            elif (rc["subject_id"] != r["case_id"]
                  or rc["observed_disposition"] != r["admitted_mode"]):
                findings.append(f"RECEIPT_BINDING:{r['case_id']}")
            if key in compiled:
                findings.append(f"ARCHITECTURE_REGRESSION:{r['case_id']}")
            compiled.setdefault(key, r["seq"])
        elif r["route"] == "experience":
            routes += 1
            replay_cost += r["cost"]
            src = by_case.get(r["derived_from_case"])
            if (src is None or src["route"] != "investigation"
                    or src["seq"] >= r["seq"]
                    or tuple(src["class_key"]) != key
                    or src["admitted_mode"] != r["admitted_mode"]):
                findings.append(f"UNDERIVED_EXPERIENCE:{r['case_id']}")
            if r["cost"] != 0:
                findings.append(f"ARCHITECTURE_REGRESSION:{r['case_id']}")
        elif r["route"] == "unresolved" and r["standing"] == "ALIVE":
            findings.append(f"ALIVE_WITHOUT_ROUTE:{r['case_id']}")
    if findings:
        return FactoryVerdict("BUILD_BROKEN", findings=tuple(findings),
                              experience_routes=routes,
                              investigation_cost=inv_cost, replay_cost=replay_cost)
    standing = "ALIVE" if routes > 0 else "UNKNOWN"
    return FactoryVerdict(standing, experience_routes=routes,
                          investigation_cost=inv_cost, replay_cost=replay_cost)
