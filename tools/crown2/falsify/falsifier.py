#!/usr/bin/env python3
"""Independent Crown-2 falsifier (Task I).

Own parser of the OCEL 2.0 run log produced by the Crown-2 runner. Does NOT
import the runner. Decides four closures, each ALIVE / BLOCKED / UNVERIFIED,
with the event ids that carry the evidence, then a global verdict.

Closures
  1. control-invariant   : heartbeat episode >= 25 HeartbeatObserved spanning
                           >= 300s of event timestamps, every heartbeat's
                           embedded validate_json is 0/0/0.
  2. planner-loop        : >= 1 full relationship-linked production chain
                           WorldStateObserved -> PlannerInvoked -> PlanProduced
                           -> PredictionFrozen -> AuthorityEvaluated ->
                           ActionStarted -> ActionCompleted -> WorldStateObserved
                           -> QualificationObserved -> PredictionCompared ->
                           ReceiptIssued -> LoopClosed, PredictionFrozen strictly
                           before ActionStarted, AND >= 1 typed refusal/recovery
                           path (PlanRefused+GapDiagnosed or AuthorityRefused),
                           AND qualification stage progress first->last.
  3. native-bootstrap    : SolverImplementation with implementation='native'
                           referenced by a PlannerInvoked in the production
                           episode, plus NativePlannerBootstrapCompleted in the
                           native bootstrap OCEL.
  4. claude-telemetry    : >= 1 ClaudeToolInvocation linked via 'invokes' to an
                           Action that has an ActionCompleted.

Cross-checks: validate.py 0/0/0 recomputed on the run file; heartbeat episode
never emitted a production event type; AuthorityRefused never followed by
ActionStarted for the same action.

Global: ALIVE[BEAM4PM_REAL_PLANNER_LOOP] iff (2) and (3) and 0/0/0 and
elapsed >= 300s; otherwise a typed BLOCKED naming the first failed gate.

Usage:
    python3 falsifier.py [run.ocel.json] [native-bootstrap.ocel.json]
Writes falsifier-result.json next to this file. Exit 0 iff global ALIVE.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
DEFAULT_RUN = os.path.join(TOOLS, "crown2", "run", "crown-run-v3.ocel.json")
DEFAULT_NATIVE = os.path.join(TOOLS, "crown2", "native", "native-bootstrap.ocel.json")
VALIDATE_PY = os.path.join(TOOLS, "ocel_v2", "validate.py")
RESULT_PATH = os.path.join(HERE, "falsifier-result.json")

MIN_HEARTBEATS = 25
MIN_ELAPSED_S = 300.0

PRODUCTION_TYPES = {
    "LoopStarted", "WorldStateObserved", "QualificationObserved", "PlannerInvoked",
    "PlanProduced", "PlanRefused", "GapDiagnosed", "PredictionFrozen",
    "AuthorityEvaluated", "AuthorityGranted", "AuthorityRefused", "ActionStarted",
    "ActionCompleted", "PredictionCompared", "ReceiptIssued", "LoopClosed",
}
CHAIN = [
    "WorldStateObserved", "PlannerInvoked", "PlanProduced", "PredictionFrozen",
    "AuthorityEvaluated", "ActionStarted", "ActionCompleted", "WorldStateObserved",
    "QualificationObserved", "PredictionCompared", "ReceiptIssued", "LoopClosed",
]


# ---------------------------------------------------------------- parsing ---
def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Log:
    def __init__(self, path: str):
        with open(path) as fh:
            self.raw = json.load(fh)
        self.objects = {o["id"]: o for o in self.raw.get("objects", [])}
        self.events = sorted(self.raw.get("events", []), key=lambda e: (parse_time(e["time"]), e["id"]))
        self.by_id = {e["id"]: e for e in self.events}

    @staticmethod
    def attrs(x) -> dict:
        return {a["name"]: a["value"] for a in x.get("attributes", [])}

    @staticmethod
    def rels(e, qualifier=None):
        return [r["objectId"] for r in e.get("relationships", [])
                if qualifier is None or r.get("qualifier") == qualifier]

    def of_type(self, t: str):
        return [e for e in self.events if e["type"] == t]

    def episode_of(self, e) -> str | None:
        r = self.rels(e, "episode")
        return r[0] if r else None

    def linked_to(self, obj_id: str):
        return [e for e in self.events if obj_id in self.rels(e)]

    def obj_type(self, obj_id: str) -> str | None:
        o = self.objects.get(obj_id)
        return o["type"] if o else None


def closure(status: str, evidence: list, notes: list) -> dict:
    return {"status": status, "evidence_event_ids": sorted(set(evidence)), "notes": notes}


# --------------------------------------------------------------- closures ---
def check_control_invariant(log: Log) -> dict:
    hbs = [e for e in log.of_type("HeartbeatObserved")]
    notes, ev = [], [e["id"] for e in hbs]
    if not hbs:
        return closure("BLOCKED[NO_HEARTBEATS]", [], ["no HeartbeatObserved events"])
    episodes = {log.episode_of(e) for e in hbs}
    hb_episode = next(iter(episodes)) if len(episodes) == 1 else None
    if hb_episode is None:
        notes.append(f"heartbeats span multiple episodes: {sorted(map(str, episodes))}")
    span = (parse_time(hbs[-1]["time"]) - parse_time(hbs[0]["time"])).total_seconds()
    bad_checks = []
    for e in hbs:
        v = Log.attrs(e).get("validate_json")
        try:
            d = json.loads(v) if isinstance(v, str) else (v or {})
        except ValueError:
            d = {"parse_error": v}
        if any(d.get(k) != 0 for k in ("dangling_refs", "duplicate_ids", "strict_type_mismatches")):
            bad_checks.append(e["id"])
    # heartbeat episode never emitted a production event type
    leaked = [e["id"] for e in log.events
              if hb_episode and log.episode_of(e) == hb_episode and e["type"] in PRODUCTION_TYPES]
    notes += [f"heartbeats={len(hbs)} (min {MIN_HEARTBEATS})",
              f"heartbeat_span_s={span:.3f} (min {MIN_ELAPSED_S:.0f})",
              f"failed_checks={bad_checks}", f"production_types_in_heartbeat_episode={leaked}"]
    if len(hbs) < MIN_HEARTBEATS:
        return closure("BLOCKED[HEARTBEAT_COUNT]", ev, notes)
    if span < MIN_ELAPSED_S:
        return closure("BLOCKED[HEARTBEAT_SPAN_LT_300S]", ev, notes)
    if bad_checks:
        return closure("BLOCKED[HEARTBEAT_CHECK_FAILED]", ev, notes)
    if leaked:
        return closure("BLOCKED[HEARTBEAT_EPISODE_LEAKED_PRODUCTION]", ev, notes)
    if hb_episode is None:
        return closure("BLOCKED[HEARTBEAT_EPISODE_AMBIGUOUS]", ev, notes)
    return closure("ALIVE", ev, notes)


def find_full_chains(log: Log) -> list[dict]:
    """Return every relationship-linked full production chain found.

    Linking rules (relationship qualifiers, not event ordering):
      WSO(pre)  --'observed' ws--> PlanProduced 'from' ws   (same ws object)
      PlannerInvoked -- 'solver' --> PlanProduced 'solver'   (same solver)
      PlanProduced -- 'plan' --> plan object ; PredictionFrozen 'predicts' action
      PredictionFrozen 'prediction' == PredictionCompared 'prediction' == ReceiptIssued 'prediction'
      AuthorityEvaluated 'subject' == ActionStarted 'action' == ActionCompleted 'action'
                      == PredictionCompared 'action'
      PredictionCompared 'observed' ws == WSO(post) 'observed' == QualificationObserved 'observed'
      LoopClosed 'observed' ws == WSO(post) ws (or any later LoopClosed in the episode)
    """
    chains = []
    for pf in log.of_type("PredictionFrozen"):
        ep = log.episode_of(pf)
        pred = (log.rels(pf, "prediction") or [None])[0]
        action = (log.rels(pf, "predicts") or [None])[0]
        if not pred or not action:
            continue
        ae = [e for e in log.of_type("AuthorityEvaluated") if action in log.rels(e, "subject")]
        a_start = [e for e in log.of_type("ActionStarted") if action in log.rels(e, "action")]
        a_done = [e for e in log.of_type("ActionCompleted") if action in log.rels(e, "action")]
        pc = [e for e in log.of_type("PredictionCompared")
              if pred in log.rels(e, "prediction") and action in log.rels(e, "action")]
        ri = [e for e in log.of_type("ReceiptIssued") if pred in log.rels(e, "prediction")]
        if not (ae and a_start and a_done and pc and ri):
            continue
        post_ws = (log.rels(pc[0], "observed") or [None])[0]
        wso_post = [e for e in log.of_type("WorldStateObserved") if post_ws in log.rels(e, "observed")]
        qo = [e for e in log.of_type("QualificationObserved") if post_ws in log.rels(e, "observed")]
        lc = [e for e in log.of_type("LoopClosed")
              if log.episode_of(e) == ep and parse_time(e["time"]) >= parse_time(ri[0]["time"])]
        # plan side: the planner invocation preceding this prediction in the episode
        pp = [e for e in log.of_type("PlanProduced")
              if log.episode_of(e) == ep and parse_time(e["time"]) <= parse_time(pf["time"])]
        if not pp:
            continue
        pp = pp[-1]
        pre_ws = (log.rels(pp, "from") or [None])[0]
        solver = (log.rels(pp, "solver") or [None])[0]
        wso_pre = [e for e in log.of_type("WorldStateObserved") if pre_ws in log.rels(e, "observed")]
        pi = [e for e in log.of_type("PlannerInvoked")
              if solver in log.rels(e, "solver") and log.episode_of(e) == ep
              and parse_time(e["time"]) <= parse_time(pp["time"])]
        if not (wso_post and qo and lc and wso_pre and pi):
            continue
        frozen_before_start = parse_time(pf["time"]) < parse_time(a_start[0]["time"])
        order = [wso_pre[0], pi[-1], pp, pf, ae[0], a_start[0], a_done[0], wso_post[0], qo[0], pc[0], ri[0], lc[0]]
        times = [parse_time(e["time"]) for e in order]
        monotone = all(times[i] <= times[i + 1] for i in range(len(times) - 1))
        chains.append({
            "action": action, "prediction": pred, "episode": ep, "solver": solver,
            "event_ids": [e["id"] for e in order],
            "types": [e["type"] for e in order],
            "prediction_frozen_strictly_before_action_started": frozen_before_start,
            "timestamps_monotone": monotone,
            "valid": frozen_before_start and monotone and [e["type"] for e in order] == CHAIN,
        })
    return chains


def check_planner_loop(log: Log) -> dict:
    notes, ev = [], []
    chains = find_full_chains(log)
    valid = [c for c in chains if c["valid"]]
    for c in valid:
        ev += c["event_ids"]
    notes.append(f"full_chains_found={len(chains)} valid={len(valid)} actions={[c['action'] for c in valid]}")
    # typed refusal / recovery path
    pr = log.of_type("PlanRefused")
    gd = log.of_type("GapDiagnosed")
    ar = log.of_type("AuthorityRefused")
    refusal_ok = (bool(pr) and bool(gd)) or bool(ar)
    ev += [e["id"] for e in pr + gd + ar]
    notes.append(f"PlanRefused={len(pr)} GapDiagnosed={len(gd)} AuthorityRefused={len(ar)} refusal_path_present={refusal_ok}")
    # AuthorityRefused never followed by ActionStarted for the same action
    violations = []
    for r in ar:
        for act in log.rels(r, "subject"):
            later = [e for e in log.of_type("ActionStarted")
                     if act in log.rels(e, "action") and parse_time(e["time"]) > parse_time(r["time"])]
            violations += [e["id"] for e in later]
    notes.append(f"authority_refused_then_action_started={violations}")
    # qualification stage progress between first and last QualificationObserved
    qos = log.of_type("QualificationObserved")
    progress = None
    if len(qos) >= 2:
        first, last = Log.attrs(qos[0]), Log.attrs(qos[-1])
        try:
            m0, m1 = json.loads(first.get("metrics_json", "{}")), json.loads(last.get("metrics_json", "{}"))
            t0, t1 = sum(1 for v in m0.values() if v is True), sum(1 for v in m1.values() if v is True)
            progress = {"first": qos[0]["id"], "last": qos[-1]["id"], "true_gates_first": t0, "true_gates_last": t1,
                        "result_first": first.get("result"), "result_last": last.get("result"),
                        "progressed": t1 > t0 and first.get("result") != last.get("result")}
        except ValueError:
            progress = {"error": "metrics_json unparsable"}
        ev += [qos[0]["id"], qos[-1]["id"]]
    notes.append(f"qualification_progress={progress}")
    prog_ok = bool(progress and progress.get("progressed"))
    if not valid:
        return closure("BLOCKED[NO_FULL_LINKED_CHAIN]", ev, notes)
    if violations:
        return closure("BLOCKED[ACTION_STARTED_AFTER_AUTHORITY_REFUSED]", ev, notes)
    if not prog_ok:
        return closure("BLOCKED[NO_QUALIFICATION_PROGRESS]", ev, notes)
    if not refusal_ok:
        return closure("BLOCKED[NO_TYPED_REFUSAL_PATH]", ev, notes)
    return closure("ALIVE", ev, notes)


def check_native_bootstrap(log: Log, native_path: str) -> dict:
    notes, ev = [], []
    native_solvers = {}
    for oid, o in log.objects.items():
        if o["type"] == "SolverImplementation":
            a = Log.attrs(o)
            native_solvers[oid] = {"implementation": a.get("implementation"), "kind": a.get("kind"), "name": a.get("name")}
    notes.append(f"solver_objects={native_solvers}")
    prod_pi = [e for e in log.of_type("PlannerInvoked")
               if log.obj_type(log.episode_of(e) or "") == "ProcessEpisode"
               and "production" in Log.attrs(log.objects[log.episode_of(e)]).get("label", "")]
    ev += [e["id"] for e in prod_pi]
    referenced = {s for e in prod_pi for s in log.rels(e, "solver")}
    native_ref = [s for s in referenced if native_solvers.get(s, {}).get("implementation") == "native"]
    cpp_ref = [s for s in referenced if str(native_solvers.get(s, {}).get("kind", "")).startswith("cpp:")]
    notes.append(f"production_PlannerInvoked={len(prod_pi)} referenced_solvers={sorted(referenced)} "
                 f"implementation=native={native_ref} kind=cpp:*={cpp_ref}")
    boot_ok, boot_note = False, None
    if os.path.exists(native_path):
        nl = Log(native_path)
        bc = nl.of_type("NativePlannerBootstrapCompleted")
        ev += [e["id"] for e in bc]
        if bc:
            a = Log.attrs(bc[0])
            try:
                ss = json.loads(a.get("solve_summary_json", "{}"))
            except ValueError:
                ss = {}
            boot_ok = bool(ss.get("ok")) and bool(ss.get("goal_reached")) and "native" in str(ss.get("solver", ""))
            boot_note = {"event": bc[0]["id"], "ok": ss.get("ok"), "goal_reached": ss.get("goal_reached"), "solver": ss.get("solver")}
        else:
            boot_note = "NativePlannerBootstrapCompleted absent"
        nv = run_validate(native_path)
        notes.append(f"native_bootstrap_validate={nv}")
    else:
        boot_note = f"missing {native_path}"
    notes.append(f"bootstrap={boot_note}")
    if not prod_pi:
        return closure("BLOCKED[NO_PRODUCTION_PLANNER_INVOKED]", ev, notes)
    if not boot_ok:
        return closure("BLOCKED[NO_NATIVE_BOOTSTRAP_COMPLETED]", ev, notes)
    if native_ref:
        return closure("ALIVE", ev, notes)
    if cpp_ref:
        notes.append("SolverImplementation lacks attribute implementation='native'; only kind='cpp:*' asserts nativeness")
        return closure("BLOCKED[SOLVER_IMPLEMENTATION_ATTR_MISSING]", ev, notes)
    return closure("BLOCKED[NO_NATIVE_SOLVER_REFERENCED]", ev, notes)


def check_claude_telemetry(log: Log) -> dict:
    notes, ev, hits = [], [], []
    for e in log.events:
        if not e["type"].startswith("Claude."):
            continue
        invs = [r["objectId"] for r in e.get("relationships", [])
                if log.obj_type(r["objectId"]) == "ClaudeToolInvocation"]
        actions = log.rels(e, "invokes")
        for act in actions:
            done = [d for d in log.of_type("ActionCompleted") if act in log.rels(d, "action")]
            if invs and done:
                hits.append((e["id"], invs[0], act, done[0]["id"]))
                ev += [e["id"], done[0]["id"]]
    notes.append(f"claude_invocations_linked_to_completed_actions={len(hits)}")
    notes.append(f"pairs={[list(h) for h in hits]}")
    return closure("ALIVE" if hits else "BLOCKED[NO_CLAUDE_TOOL_INVOCATION_LINKED]", ev, notes)


def run_validate(path: str) -> dict:
    sys.path.insert(0, os.path.dirname(VALIDATE_PY))
    import importlib
    validate = importlib.import_module("validate")
    with open(path) as fh:
        return validate.validate(json.load(fh))


# ------------------------------------------------------------------ main ---
def main(argv: list[str]) -> int:
    run_path = argv[1] if len(argv) > 1 else DEFAULT_RUN
    native_path = argv[2] if len(argv) > 2 else DEFAULT_NATIVE
    log = Log(run_path)
    v = run_validate(run_path)
    zero = all(v.get(k) == 0 for k in ("strict_type_mismatches", "duplicate_ids", "dangling_refs"))
    elapsed = (parse_time(log.events[-1]["time"]) - parse_time(log.events[0]["time"])).total_seconds() if log.events else 0.0

    closures = {
        "control_invariant": check_control_invariant(log),
        "planner_loop": check_planner_loop(log),
        "native_bootstrap": check_native_bootstrap(log, native_path),
        "claude_telemetry": check_claude_telemetry(log),
    }
    gates = [
        ("planner_loop", closures["planner_loop"]["status"] == "ALIVE", closures["planner_loop"]["status"]),
        ("native_bootstrap", closures["native_bootstrap"]["status"] == "ALIVE", closures["native_bootstrap"]["status"]),
        ("validate_0_0_0", zero, f"BLOCKED[VALIDATE_{v}]"),
        ("elapsed_ge_300", elapsed >= MIN_ELAPSED_S, f"BLOCKED[ELAPSED_{elapsed:.3f}S_LT_300]"),
    ]
    failed = [g for g in gates if not g[1]]
    if failed:
        global_status = failed[0][2] if failed[0][2].startswith("BLOCKED") else f"BLOCKED[{failed[0][0].upper()}]"
    else:
        global_status = "ALIVE[BEAM4PM_REAL_PLANNER_LOOP]"
    result = {
        "run_file": run_path, "native_bootstrap_file": native_path,
        "event_count": len(log.events), "object_count": len(log.objects),
        "validate": v, "elapsed_seconds": round(elapsed, 3),
        "first_event": log.events[0]["id"] if log.events else None,
        "last_event": log.events[-1]["id"] if log.events else None,
        "closures": closures,
        "global_gates": [{"gate": g[0], "passed": g[1]} for g in gates],
        "failed_gates": [g[0] for g in failed],
        "global_status": global_status,
    }
    with open(RESULT_PATH, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    print(json.dumps({k: result[k] for k in ("validate", "elapsed_seconds", "failed_gates", "global_status")}))
    for name, c in closures.items():
        print(f"{name}: {c['status']}  evidence={len(c['evidence_event_ids'])} events")
        for n in c["notes"]:
            print(f"    - {n}")
    print(f"wrote {RESULT_PATH}")
    return 0 if global_status.startswith("ALIVE") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
