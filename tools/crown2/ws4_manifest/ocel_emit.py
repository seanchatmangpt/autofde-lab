#!/usr/bin/env python3
"""ocel_emit.py — record a WS4 manifest stub on the OCEL 2.0 evidence plane.

Uses only object/event types ALREADY declared in tools/ocel_v2/emitter.py
(no schema extension needed):

  objects : GapDiagnosis (WS1 type)  — one per requirement gap
            Plan                     — the manifest stub (steps_json = rules,
                                       summary = project name, cost = #rules)
            Receipt                  — sha256 of the rendered ggen.toml
  events  : PlanProduced   -> Plan + every GapDiagnosis
            ReceiptIssued  -> Receipt + Plan

validate.py must stay green on the resulting log.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OCEL_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "ocel_v2"))
sys.path.insert(0, OCEL_DIR)
sys.path.insert(0, HERE)

import emitter  # noqa: E402
from manifest import GGenManifestStub  # noqa: E402
from requirement import CapabilityRequirement  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_stub(log_path: str, reqs: list[CapabilityRequirement], stub: GGenManifestStub,
              stub_id: str = "plan:ws4:stub") -> dict:
    if not os.path.exists(log_path):
        emitter.init(log_path)
    gap_ids = []
    for r in reqs:
        gid = f"gap:{r.gap.gap_id}"
        emitter.add_object(log_path, "GapDiagnosis", gid, {
            "gap_type": "ACTION_GAP",
            "planner": "ws4_manifest",
            "unavailable_transition": r.gap.missing_transition,
            "standing": "DIAGNOSED",
            "receipt_digest": ",".join(r.gap.evidence_refs),
        })
        gap_ids.append(gid)
    toml_text = stub.to_toml()
    digest = hashlib.sha256(toml_text.encode()).hexdigest()
    emitter.add_object(log_path, "Plan", stub_id, {
        "summary": stub.project_name,
        "steps_json": json.dumps({"rules": stub.rules, "preservation": stub.preservation_report()}, sort_keys=True),
        "cost_estimate": float(len(stub.rules)),
    })
    emitter.add_event(log_path, "PlanProduced", f"ev:{stub_id}:produced", {
        "summary": stub.description,
        "cost_estimate": float(len(stub.rules)),
    }, [stub_id, *gap_ids])
    rid = f"receipt:ws4:{digest[:16]}"
    emitter.add_object(log_path, "Receipt", rid, {
        "kind": "ggen-manifest-stub",
        "digest": digest,
        "issued_at": _now(),
    })
    emitter.add_event(log_path, "ReceiptIssued", f"ev:{rid}", {
        "digest": digest,
        "evidence_path": "ggen.toml",
    }, [rid, stub_id])
    return {"plan": stub_id, "receipt": rid, "digest": digest, "gaps": gap_ids}
