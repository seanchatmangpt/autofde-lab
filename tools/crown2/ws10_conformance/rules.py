#!/usr/bin/env python3
"""WS10 — OCEL 2.0 process-conformance rule engine (stdlib only).

Each rule is a falsifier: it returns the ids of VIOLATING events (empty list =
rule holds). Scoping conventions (the executable knowledge this module pins):

  * Every process event relates to exactly one `ProcessEpisode` object; that
    object is the case/scope for "followed by" / "before" rules.
  * Action-level rules correlate on the shared `Action` object.
  * Planner rules correlate on any shared related object (Domain/Plan/Episode).
  * "Terminal planner event"  = PlanProduced | PlanRefused.
  * "Consequence event"       = ActionCompleted | ActionFailed | QualificationObserved.
  * "Heartbeat episode"       = ProcessEpisode whose `label` starts with "heartbeat".
  * PRODUCTION_EVENT_TYPES    = event types a heartbeat episode must never emit.
  * Evidence paths (ReceiptIssued.evidence_path, Receipt.evidence_path) are
    resolved relative to `evidence_root` (default: the log file's directory).

CLI:  python3 rules.py <log.ocel.json> [--evidence-root DIR]
Prints JSON {rule_id: [violating event ids]} and exits 1 if any rule fires.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Callable

from ocel_parser import OcelEvent, OcelLog, load_ocel

TERMINAL_PLANNER_TYPES = {"PlanProduced", "PlanRefused"}
CONSEQUENCE_TYPES = {"ActionCompleted", "ActionFailed", "QualificationObserved"}
OBSERVATION_TYPES = {"WorldStateObserved", "QualificationObserved"}
LOOP_TERMINAL_TYPES = {"LoopClosed", "LoopBlocked"}
PRODUCTION_EVENT_TYPES = {
    "PlannerInvoked", "PlanProduced", "PlanRefused", "PredictionFrozen",
    "AuthorityEvaluated", "AuthorityGranted", "AuthorityRefused",
    "ActionStarted", "ActionCompleted", "ActionFailed", "ActionRefused",
    "QualificationObserved", "PredictionCompared",
}
HEARTBEAT_LABEL_PREFIX = "heartbeat"


def _episode(log: OcelLog, ev: OcelEvent) -> str | None:
    eps = log.related_of_type(ev, "ProcessEpisode")
    return eps[0] if eps else None


def _later_in_episode(log: OcelLog, ev: OcelEvent, types: set[str]) -> list[OcelEvent]:
    ep = _episode(log, ev)
    return [o for o in log.events if o.type in types and o.time >= ev.time and o.id != ev.id
            and _episode(log, o) == ep]


def _shares_object(a: OcelEvent, b: OcelEvent) -> bool:
    return bool(set(a.objects) & set(b.objects))


# --- R01 -------------------------------------------------------------------
def r01_planner_invoked_without_terminal(log: OcelLog) -> list[str]:
    out = []
    for ev in log.events_of_type("PlannerInvoked"):
        if not any(o.type in TERMINAL_PLANNER_TYPES and o.time >= ev.time and _shares_object(ev, o)
                   for o in log.events):
            out.append(ev.id)
    return out


# --- R02 -------------------------------------------------------------------
def r02_plan_produced_without_prediction_frozen(log: OcelLog) -> list[str]:
    out = []
    for ev in log.events_of_type("PlanProduced"):
        if not any(o.type == "PredictionFrozen" and o.time >= ev.time and _shares_object(ev, o)
                   for o in log.events):
            out.append(ev.id)
    return out


# --- R03 -------------------------------------------------------------------
def r03_action_started_before_prediction_frozen(log: OcelLog) -> list[str]:
    out = []
    for ev in log.events_of_type("ActionStarted"):
        ep = _episode(log, ev)
        frozen_before = [o for o in log.events if o.type == "PredictionFrozen"
                         and _episode(log, o) == ep and o.time <= ev.time]
        if not frozen_before:
            out.append(ev.id)
    return out


# --- R04 -------------------------------------------------------------------
def r04_action_without_authority_evaluated(log: OcelLog) -> list[str]:
    out = []
    for ev in log.events_of_type("ActionStarted"):
        actions = set(log.related_of_type(ev, "Action"))
        if not any(o.type == "AuthorityEvaluated" and o.time <= ev.time
                   and actions & set(o.objects) for o in log.events):
            out.append(ev.id)
    return out


# --- R05 -------------------------------------------------------------------
def r05_authority_refused_then_action_started(log: OcelLog) -> list[str]:
    out = []
    for ev in log.events_of_type("AuthorityRefused"):
        actions = set(log.related_of_type(ev, "Action"))
        for o in log.events:
            if o.type == "ActionStarted" and o.time >= ev.time and actions & set(o.objects):
                out.append(o.id)
    return out


# --- R06 -------------------------------------------------------------------
def r06_action_completed_without_observation(log: OcelLog) -> list[str]:
    return [ev.id for ev in log.events_of_type("ActionCompleted")
            if not _later_in_episode(log, ev, OBSERVATION_TYPES)]


# --- R07 -------------------------------------------------------------------
def r07_consequence_without_receipt(log: OcelLog) -> list[str]:
    return [ev.id for ev in log.events_of_type(*CONSEQUENCE_TYPES)
            if not _later_in_episode(log, ev, {"ReceiptIssued"})]


# --- R08 -------------------------------------------------------------------
def r08_loop_started_without_terminal(log: OcelLog) -> list[str]:
    return [ev.id for ev in log.events_of_type("LoopStarted")
            if not _later_in_episode(log, ev, LOOP_TERMINAL_TYPES)]


# --- R09 -------------------------------------------------------------------
def r09_heartbeat_emits_production_events(log: OcelLog) -> list[str]:
    heartbeat_eps = {o.id for o in log.objects_of_type("ProcessEpisode")
                     if str(o.attrs.get("label", "")).startswith(HEARTBEAT_LABEL_PREFIX)}
    return [ev.id for ev in log.events
            if ev.type in PRODUCTION_EVENT_TYPES and set(ev.objects) & heartbeat_eps]


# --- R10 -------------------------------------------------------------------
def r10_receipt_evidence_path_missing(log: OcelLog, evidence_root: str = ".") -> list[str]:
    def missing(p) -> bool:
        if not isinstance(p, str) or not p:
            return True
        return not os.path.exists(p if os.path.isabs(p) else os.path.join(evidence_root, p))

    out = []
    for ev in log.events_of_type("ReceiptIssued"):
        p = ev.attrs.get("evidence_path")
        if p is None:  # fall back to related Receipt object's path
            for oid in log.related_of_type(ev, "Receipt"):
                p = log.objects[oid].attrs.get("evidence_path", p)
        if missing(p):
            out.append(ev.id)
    return out


RULES: dict[str, Callable[..., list[str]]] = {
    "R01_planner_invoked_without_terminal": r01_planner_invoked_without_terminal,
    "R02_plan_produced_without_prediction_frozen": r02_plan_produced_without_prediction_frozen,
    "R03_action_started_before_prediction_frozen": r03_action_started_before_prediction_frozen,
    "R04_action_without_authority_evaluated": r04_action_without_authority_evaluated,
    "R05_authority_refused_then_action_started": r05_authority_refused_then_action_started,
    "R06_action_completed_without_observation": r06_action_completed_without_observation,
    "R07_consequence_without_receipt": r07_consequence_without_receipt,
    "R08_loop_started_without_terminal": r08_loop_started_without_terminal,
    "R09_heartbeat_emits_production_events": r09_heartbeat_emits_production_events,
    "R10_receipt_evidence_path_missing": r10_receipt_evidence_path_missing,
}


def check(log: OcelLog, evidence_root: str = ".") -> dict[str, list[str]]:
    res = {}
    for rid, fn in RULES.items():
        res[rid] = fn(log, evidence_root) if rid.startswith("R10") else fn(log)
    return res


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    root = os.path.dirname(os.path.abspath(path))
    if "--evidence-root" in argv:
        root = argv[argv.index("--evidence-root") + 1]
    res = check(load_ocel(path), root)
    print(json.dumps({"log": path, "violations": res}, indent=1))
    return 1 if any(res.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
