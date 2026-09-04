#!/usr/bin/env python3
"""Shared harness for WS10 falsifiers: builds logs through the REAL emitter,
runs the REAL rules engine (rules.check) and, when rdflib is importable, the
REAL SPARQL engine (run_sparql.run). No mocks.

Each falsifier calls `verdict(name, reproduced, detail)`; exit code 0 means the
counterexample REPRODUCED (target gave the wrong answer), 1 means it did NOT.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
WS10 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(WS10, "..", "..", ".."))
EMITTER = os.path.join(REPO, "tools", "ocel_v2", "emitter.py")
VALIDATE = os.path.join(REPO, "tools", "ocel_v2", "validate.py")
OUT = os.path.join(HERE, "out")
sys.path.insert(0, WS10)

from ocel_parser import load_ocel  # noqa: E402
from rules import check  # noqa: E402

_spec = importlib.util.spec_from_file_location("emitter", EMITTER)
emitter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(emitter)

T0 = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)


def ts(step: float) -> str:
    return (T0 + timedelta(seconds=step)).isoformat()


# Same object universe as fixtures/build_fixtures.py (real emitter schema).
OBJECTS = [
    ("ProcessEpisode", "ep1", {"label": "production-run-1", "started_at": ts(0), "ended_at": ts(20)}),
    ("ProcessEpisode", "hb1", {"label": "heartbeat-1", "started_at": ts(17), "ended_at": ts(19)}),
    ("Domain", "dom1", {"name": "maze", "description": "fixture domain"}),
    ("Plan", "plan1", {"summary": "walk", "steps_json": ["a", "b"], "cost_estimate": 2.0}),
    ("Plan", "plan2", {"summary": "unfrozen", "steps_json": ["c"], "cost_estimate": 9.0}),
    ("Action", "act1", {"name": "apply-patch", "kind": "edit", "args_json": {"file": "x.py"}}),
    ("Action", "act2", {"name": "rm-rf", "kind": "destructive", "args_json": {"path": "/"}}),
    ("Receipt", "rcpt1", {"kind": "standing", "digest": "sha256:abc", "issued_at": ts(15),
                          "evidence_path": "evidence/receipt-001.txt"}),
]


def build(name: str, events, objects=OBJECTS, sort_by_step: bool = True) -> str:
    """events: (step, type, id, attrs, related). Returns path. Document order =
    step order unless sort_by_step=False (then the list order is the file order)."""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}.ocel.json")
    emitter.init(path)
    for otype, oid, attrs in objects:
        emitter.add_object(path, otype, oid, attrs)
    seq = sorted(events, key=lambda e: e[0]) if sort_by_step else list(events)
    for step, etype, eid, attrs, objs in seq:
        emitter.add_event(path, etype, eid, attrs, objs, time=ts(step))
    return path


def validate(path: str) -> dict:
    p = subprocess.run([sys.executable, VALIDATE, path], capture_output=True, text=True)
    return {"rc": p.returncode, **json.loads(p.stdout or "{}")}


def python_engine(path: str, evidence_root: str | None = None) -> dict[str, list[str]]:
    return check(load_ocel(path), evidence_root or os.path.dirname(path))


def sparql_engine(path: str, evidence_root: str | None = None):
    try:
        from run_sparql import run
    except ImportError:
        return None
    try:
        return run(path, evidence_root or os.path.dirname(path))
    except ImportError:
        return None


def fired(res: dict[str, list[str]]) -> dict[str, list[str]]:
    return {k: v for k, v in res.items() if v}


def verdict(name: str, reproduced: bool, detail) -> int:
    print(json.dumps({"falsifier": name,
                      "result": "REPRODUCED" if reproduced else "NOT_REPRODUCED",
                      "detail": detail}, indent=1, default=str))
    return 0 if reproduced else 1
