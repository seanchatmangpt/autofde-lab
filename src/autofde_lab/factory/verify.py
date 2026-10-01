"""Fresh verifier: recomputes standing from the durable ledger alone.

It never imports the loop. It DOES replay the fault world from the spec
recorded in the ledger header: an investigation row is accepted only if the
world, re-run from that spec, yields the same disposition at the same cost.
That rules out fabricated rows, but not a forger who also writes a consistent
fake world spec -- identity of the world spec is an open dependency (see
docs/STATUS.md), not something this file can establish.

Relations are accepted only through explicit fields (``derived_from_case``);
a class_key match never creates a join.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from autofde_lab.wd_fa.receipts import VerificationReceipt, verify_receipt
from autofde_lab.wd_fa.synthetic import RULES

from .chain import chain_findings
from .world import WORLD_ID, FaultWorld

SCHEMA = "autofde.factory.ledger.v1"
ROUTES = frozenset({"seed_rule", "investigation", "experience", "unresolved"})
STANDINGS = frozenset({"ALIVE", "PARTIAL_ALIVE", "UNKNOWN"})
_ROW_KEYS = {
    "seq": int,
    "case_id": str,
    "class_key": list,
    "evidence_kinds": list,
    "standing": str,
    "route": str,
    "cost": int,
    "admitted_mode": (str, type(None)),
    "receipt": (dict, type(None)),
    "experience_id": (str, type(None)),
    "derived_from_case": (str, type(None)),
    "human_gate": str,
    "authority": str,
}
_SEED_MODES = frozenset(r.mode_id for r in RULES)


@dataclass(frozen=True)
class FactoryVerdict:
    technical_standing: str
    # No component computes organizational standing (see standing-law.md).
    organizational_standing: str = "UNKNOWN"
    enterprise_standing: str = "UNKNOWN"
    findings: tuple[str, ...] = field(default_factory=tuple)
    experience_routes: int = 0
    unresolved: int = 0
    investigation_cost: int = 0
    replay_cost: int = 0


def _receipt(d: dict) -> VerificationReceipt:
    d = dict(d)
    d["evidence_digests"] = tuple(d["evidence_digests"])
    return VerificationReceipt(**d)


def _schema_finding(r: dict) -> str | None:
    for k, t in _ROW_KEYS.items():
        if k not in r or isinstance(r[k], bool) or not isinstance(r[k], t):
            return f"ROW_SCHEMA:{r.get('case_id', '?')}:{k}"
    if r["route"] not in ROUTES or r["standing"] not in STANDINGS:
        return f"ROW_ENUM:{r['case_id']}"
    if (r["route"] == "unresolved") == (r["standing"] == "ALIVE"):
        return f"ROUTE_STANDING_MISMATCH:{r['case_id']}"
    return None


def verify_ledger(path: Path, head: Path | None = None) -> FactoryVerdict:
    path = Path(path)
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    if not rows:
        return FactoryVerdict("UNKNOWN", findings=("EMPTY_LEDGER",))
    findings: list[str] = chain_findings(rows)
    head = head if head is not None else path.with_suffix(".head")
    if not head.exists():
        findings.append("HEAD_MISSING")
    elif head.read_text().strip() != rows[-1].get("digest"):
        findings.append("HEAD_MISMATCH")

    hdr, body = rows[0], rows[1:]
    if hdr.get("schema") != SCHEMA or hdr.get("type") != "header":
        return FactoryVerdict("BUILD_BROKEN", findings=(*findings, "HEADER_MISSING"))
    try:
        world = FaultWorld.from_spec(hdr["world"])
        budget = int(hdr["budget"])
    except (KeyError, TypeError, ValueError):
        return FactoryVerdict("BUILD_BROKEN", findings=(*findings, "HEADER_WORLD_SPEC"))

    bad = [f for r in body if (f := _schema_finding(r))]
    if bad:
        return FactoryVerdict("BUILD_BROKEN", findings=(*findings, *bad))
    by_case = {r["case_id"]: r for r in body}
    if len(by_case) != len(body) or [r["seq"] for r in body] != list(range(len(body))):
        findings.append("LEDGER_IDENTITY_OR_ORDER")

    compiled: dict[tuple, int] = {}
    inv_cost = replay_cost = routes = unresolved = 0
    for r in body:
        key = tuple(r["class_key"])
        if r["route"] == "seed_rule":
            if (
                r["admitted_mode"] not in _SEED_MODES
                or r["receipt"] is not None
                or r["experience_id"]
                or r["derived_from_case"]
                or r["cost"] != 0
            ):
                findings.append(f"SEED_RULE_CLAIM:{r['case_id']}")
        elif r["route"] == "investigation":
            inv_cost += r["cost"]
            rc = r["receipt"]
            if rc is None or not verify_receipt(_receipt(rc)):
                findings.append(f"INVALID_RECEIPT:{r['case_id']}")
            elif (
                rc["subject_id"] != r["case_id"]
                or rc["observed_disposition"] != r["admitted_mode"]
                or rc["verifier_id"] != WORLD_ID
            ):
                findings.append(f"RECEIPT_BINDING:{r['case_id']}")
            obs = world.investigate_key(key, budget)
            if (
                obs is None
                or obs.mode_id != r["admitted_mode"]
                or obs.probes != r["cost"]
            ):
                findings.append(f"WORLD_REPLAY_MISMATCH:{r['case_id']}")
            if key in compiled:
                findings.append(f"ARCHITECTURE_REGRESSION:{r['case_id']}")
            compiled.setdefault(key, r["seq"])
        elif r["route"] == "experience":
            routes += 1
            replay_cost += r["cost"]
            src = by_case.get(r["derived_from_case"])
            if (
                src is None
                or src["route"] != "investigation"
                or src["seq"] >= r["seq"]
                or tuple(src["class_key"]) != key
                or src["admitted_mode"] != r["admitted_mode"]
                or not set(src["evidence_kinds"]) <= set(r["evidence_kinds"])
            ):
                findings.append(f"UNDERIVED_EXPERIENCE:{r['case_id']}")
            if r["cost"] != 0:
                findings.append(f"ARCHITECTURE_REGRESSION:{r['case_id']}")
        else:
            unresolved += 1
            if r["admitted_mode"] is not None or r["receipt"] is not None:
                findings.append(f"UNRESOLVED_WITH_CLAIM:{r['case_id']}")
            if r.get(
                "reason"
            ) == "NO_OBSERVATION_WITHIN_BUDGET" and world.investigate_key(key, budget):
                findings.append(f"UNRESOLVED_BUT_OBSERVABLE:{r['case_id']}")
    common = dict(
        experience_routes=routes,
        unresolved=unresolved,
        investigation_cost=inv_cost,
        replay_cost=replay_cost,
    )
    if findings:
        return FactoryVerdict("BUILD_BROKEN", findings=tuple(findings), **common)
    return FactoryVerdict("ALIVE" if routes > 0 else "UNKNOWN", **common)
