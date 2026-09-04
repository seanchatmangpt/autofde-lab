#!/usr/bin/env python3
"""Emit a CapabilityResolution into an OCEL 2.0 log via tools/ocel_v2/emitter.py."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OCEL_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "ocel_v2")
sys.path.insert(0, OCEL_DIR)
import emitter  # noqa: E402


def emit_resolution(out_path: str, res, res_id: str) -> None:
    """Append one CapabilityResolution object + one CapabilityResolved event."""
    d = res.to_dict()
    emitter.add_object(
        out_path,
        "CapabilityResolution",
        res_id,
        {
            "gap_label": d["gap"].get("label", ""),
            "selected_kind": d["selected"]["kind"],
            "selected_ref": d["selected"]["ref"],
            "route_to_codegen": "false",
        },
    )
    emitter.add_event(
        out_path,
        "CapabilityResolved",
        f"ev_{res_id}",
        {
            "selected_kind": d["selected"]["kind"],
            "candidate_count": len(d["candidates"]),
            "dominated_count": len(d["dominated"]),
            "resolution_json": d,
        },
        [res_id],
    )
