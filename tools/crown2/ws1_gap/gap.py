#!/usr/bin/env python3
"""
gap.py — WS1 Gap Diagnosis: a NO_PLAN_FOUND interceptor.

When a planner (e.g. A* over a staged-qualification domain) returns
NO_PLAN_FOUND, the *reason* is not "the planner failed" — it is one of a
closed set of structural gaps between goal, world, domain, repo surface,
authority policy, sensors and manufacturers. `classify()` reasons from the
single missing transition (the stage no explored action could supply) to
exactly one GapType, deterministically, with no LLM in the loop.

Staged stages observed on beam4pm (Crown-2 evidence, 2026-09):
  SUBMODULES_READY -> SYNC_READY -> LINT_TRUTH_READY -> RUST_TESTS_READY
  -> ELIXIR_DEPS_READY -> MIX_TEST_RUNNABLE -> NATIVE_ORACLES_BUILT
  -> ORACLE_ENV_SET -> MIX_TEST_GREEN -> QUALIFICATION_COMPLETE

Precedence of the decision procedure (first match wins):

  1. goal contradicts an invariant or itself            -> GOAL_IMPOSSIBLE
  2. sensor for the missing precondition absent/stale   -> OBSERVATION_GAP
     (only when some action could supply it; otherwise fall through, since
     you cannot observe your way out of a missing action)
  3. a DOMAIN action supplies the transition but was rejected:
       reason authority          -> AUTHORITY_GAP
       reason qualification      -> QUALIFICATION_GAP
       reason ambiguity (>1 admissible, undominated) -> NOVEL_INFORMATION_GAP
  4. no domain action, but a REPO-SURFACE action supplies it:
       all such actions forbidden by policy (destructive / forbidden name /
       credential required with no grant)            -> AUTHORITY_GAP
       only source is a marketplace pack (external capital, not in repo,
       semantics not yet modelled)                     -> KNOWLEDGE_GAP
       >1 admissible, undominated                      -> NOVEL_INFORMATION_GAP
       otherwise (docs / CI / generated / undocumented) -> ACTION_DISCOVERY_GAP
  5. absent from both domain and repo surface:
       a registered manufacturer provides it           -> ACTION_GAP
       none                                            -> MANUFACTURING_GAP
  6. transition supplied and admissible, but no qualification environment
                                                        -> QUALIFICATION_GAP

Fixture shape consumed by `classify_fixture()` (see fixtures/*.json):

  {
    "name": str, "expected_gap_type": str, "note": str,
    "no_plan": {"goal": {...}, "initial_world_state": {...}, "planner": str,
                "explored_actions": [str], "rejected_actions": [{"name","reason"}],
                "missing_transition": {"provides": str},
                "invariants": [{"stage": str, "value": bool}]},
    "domain_actions": [{"name", "provides": [str], "requires": [str]}],
    "repo_surface_actions": [{"name", "provides": [str], "source": str,
                              "documented": bool, "requires_credential": bool,
                              "destructive": bool, "dominated_by": str|null}],
    "authority_policy": {"forbidden_actions": [str], "forbid_destructive": bool,
                         "credential_grants": [str]},
    "sensors": [{"precondition": str, "status": "fresh"|"stale"|"missing"}],
    "manufacturers": [{"name", "provides": [str]}],
    "qualification_env": {"available": bool}
  }
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GapType(str, Enum):
    GOAL_IMPOSSIBLE = "GOAL_IMPOSSIBLE"
    OBSERVATION_GAP = "OBSERVATION_GAP"
    ACTION_DISCOVERY_GAP = "ACTION_DISCOVERY_GAP"
    ACTION_GAP = "ACTION_GAP"
    MANUFACTURING_GAP = "MANUFACTURING_GAP"
    QUALIFICATION_GAP = "QUALIFICATION_GAP"
    AUTHORITY_GAP = "AUTHORITY_GAP"
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"
    NOVEL_INFORMATION_GAP = "NOVEL_INFORMATION_GAP"


BEAM4PM_STAGES: tuple[str, ...] = (
    "SUBMODULES_READY",
    "SYNC_READY",
    "LINT_TRUTH_READY",
    "RUST_TESTS_READY",
    "ELIXIR_DEPS_READY",
    "MIX_TEST_RUNNABLE",
    "NATIVE_ORACLES_BUILT",
    "ORACLE_ENV_SET",
    "MIX_TEST_GREEN",
    "QUALIFICATION_COMPLETE",
)

NO_PLAN_FOUND = "NO_PLAN_FOUND"


@dataclass
class NoPlanFound:
    goal: dict[str, Any]
    initial_world_state: dict[str, Any]
    planner: str
    explored_actions: list[str] = field(default_factory=list)
    rejected_actions: list[dict[str, str]] = field(default_factory=list)
    missing_transition: dict[str, Any] = field(default_factory=dict)
    invariants: list[dict[str, Any]] = field(default_factory=list)
    status: str = NO_PLAN_FOUND


@dataclass
class GapDiagnosis:
    gap_type: GapType
    goal: dict[str, Any]
    initial_world_state: dict[str, Any]
    planner: str
    explored_actions: list[str]
    rejected_actions: list[dict[str, str]]
    missing_preconditions: list[str]
    unavailable_transition: str
    supporting_observations: list[str]
    standing: str = "LAB_PROVEN"
    receipt_digest: str = ""

    def __post_init__(self) -> None:
        if not self.receipt_digest:
            self.receipt_digest = self.compute_digest()

    def canonical_payload(self) -> dict[str, Any]:
        d = asdict(self)
        d["gap_type"] = self.gap_type.value
        d.pop("receipt_digest", None)
        return d

    def compute_digest(self) -> str:
        blob = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_json(self) -> dict[str, Any]:
        d = self.canonical_payload()
        d["receipt_digest"] = self.receipt_digest
        return d


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _goal_contradiction(no_plan: NoPlanFound) -> list[str]:
    """Return observations proving the goal is impossible, or []."""
    obs: list[str] = []
    goal = no_plan.goal
    for inv in no_plan.invariants:
        stage, value = inv.get("stage"), inv.get("value")
        if stage in goal and goal[stage] != value:
            obs.append(f"goal requires {stage}={goal[stage]} but invariant fixes {stage}={value}")
    # self-contradiction: goal asserts a stage and its explicit negation
    for key, val in goal.items():
        neg = goal.get("NOT_" + key)
        if neg is not None and neg == val:
            obs.append(f"goal asserts {key}={val} and NOT_{key}={neg} simultaneously")
    return obs


def _sensor_status(sensors: list[dict[str, Any]], precondition: str) -> str:
    for s in sensors:
        if s.get("precondition") == precondition:
            return s.get("status", "missing")
    return "missing"


def _forbidden(action: dict[str, Any], policy: dict[str, Any]) -> str | None:
    if action.get("name") in policy.get("forbidden_actions", []):
        return f"{action['name']} is in forbidden_actions"
    if action.get("destructive") and policy.get("forbid_destructive", True):
        return f"{action['name']} is destructive and policy forbids destructive actions"
    if action.get("requires_credential"):
        cred = action.get("credential", action["name"])
        if cred not in policy.get("credential_grants", []):
            return f"{action['name']} requires credential {cred!r} with no grant"
    return None


def _providers(actions: list[dict[str, Any]], transition: str) -> list[dict[str, Any]]:
    return [a for a in actions if transition in a.get("provides", [])]


# ---------------------------------------------------------------------------
# the interceptor
# ---------------------------------------------------------------------------


def classify(
    no_plan: NoPlanFound,
    domain_actions: list[dict[str, Any]],
    repo_surface_actions: list[dict[str, Any]],
    authority_policy: dict[str, Any],
    sensors: list[dict[str, Any]],
    manufacturers: list[dict[str, Any]],
    qualification_env: dict[str, Any] | None = None,
) -> GapDiagnosis:
    if no_plan.status != NO_PLAN_FOUND:
        raise ValueError(f"classify() only intercepts {NO_PLAN_FOUND}, got {no_plan.status!r}")
    qualification_env = qualification_env or {"available": True}
    transition = no_plan.missing_transition.get("provides", "")
    missing_pre = list(no_plan.missing_transition.get("missing_preconditions", [transition]))
    obs: list[str] = []

    def done(gt: GapType) -> GapDiagnosis:
        return GapDiagnosis(
            gap_type=gt,
            goal=no_plan.goal,
            initial_world_state=no_plan.initial_world_state,
            planner=no_plan.planner,
            explored_actions=list(no_plan.explored_actions),
            rejected_actions=list(no_plan.rejected_actions),
            missing_preconditions=missing_pre,
            unavailable_transition=transition,
            supporting_observations=obs,
        )

    # 1. impossible goal
    contra = _goal_contradiction(no_plan)
    if contra:
        obs.extend(contra)
        return done(GapType.GOAL_IMPOSSIBLE)

    domain_prov = _providers(domain_actions, transition)
    repo_prov = _providers(repo_surface_actions, transition)
    manu_prov = _providers(manufacturers, transition)
    any_supplier = bool(domain_prov or repo_prov)

    # 2. observation gap — the precondition might already hold, we can't see it
    for pre in missing_pre:
        st = _sensor_status(sensors, pre)
        if st in ("stale", "missing") and any_supplier:
            obs.append(f"sensor for {pre} is {st}; suppliers exist ({[a['name'] for a in domain_prov + repo_prov]})")
            return done(GapType.OBSERVATION_GAP)

    # 3. domain supplies it but planner rejected it
    if domain_prov:
        rejected = {r["name"]: r.get("reason", "") for r in no_plan.rejected_actions}
        reasons = {rejected.get(a["name"], "") for a in domain_prov}
        for a in domain_prov:
            f = _forbidden(a, authority_policy)
            if f:
                obs.append(f)
                return done(GapType.AUTHORITY_GAP)
        if any(r.startswith("authority") for r in reasons):
            obs.append(f"domain action(s) {[a['name'] for a in domain_prov]} rejected by authority: {sorted(reasons)}")
            return done(GapType.AUTHORITY_GAP)
        if not qualification_env.get("available", True) or any(r.startswith("qualification") for r in reasons):
            obs.append(f"domain action(s) {[a['name'] for a in domain_prov]} supply {transition} but no qualification environment")
            return done(GapType.QUALIFICATION_GAP)
        admissible = [a for a in domain_prov if not a.get("dominated_by")]
        if len(admissible) > 1:
            obs.append(f"{len(admissible)} admissible undominated domain actions supply {transition}: {[a['name'] for a in admissible]}")
            return done(GapType.NOVEL_INFORMATION_GAP)
        obs.append(f"domain action {admissible[0]['name'] if admissible else domain_prov[0]['name']} supplies {transition} but planner rejected: {sorted(reasons)}")
        return done(GapType.NOVEL_INFORMATION_GAP)

    # 4. repo surface supplies it, domain does not
    if repo_prov:
        forb = [(a, _forbidden(a, authority_policy)) for a in repo_prov]
        if all(f for _, f in forb):
            obs.extend(f for _, f in forb if f)
            return done(GapType.AUTHORITY_GAP)
        allowed = [a for a, f in forb if not f]
        if all(a.get("source") == "marketplace-pack" for a in allowed):
            obs.append(f"{transition} supplied only by marketplace pack(s) {[a['name'] for a in allowed]}; semantics not yet in domain or repo")
            return done(GapType.KNOWLEDGE_GAP)
        undominated = [a for a in allowed if not a.get("dominated_by")]
        if len(undominated) > 1:
            obs.append(f"{len(undominated)} admissible undominated repo actions supply {transition}: {[a['name'] for a in undominated]}")
            return done(GapType.NOVEL_INFORMATION_GAP)
        a = undominated[0] if undominated else allowed[0]
        obs.append(
            f"repo-surface action {a['name']!r} (source={a.get('source')}, documented={a.get('documented')}) "
            f"supplies {transition} but is absent from domain"
        )
        return done(GapType.ACTION_DISCOVERY_GAP)

    # 5. absent everywhere
    if manu_prov:
        obs.append(f"no action supplies {transition}; manufacturer(s) {[m['name'] for m in manu_prov]} registered")
        return done(GapType.ACTION_GAP)
    obs.append(f"no action and no manufacturer supplies {transition}")
    return done(GapType.MANUFACTURING_GAP)


def classify_fixture(fx: dict[str, Any]) -> GapDiagnosis:
    np_ = fx["no_plan"]
    no_plan = NoPlanFound(
        goal=np_["goal"],
        initial_world_state=np_["initial_world_state"],
        planner=np_.get("planner", "astar"),
        explored_actions=np_.get("explored_actions", []),
        rejected_actions=np_.get("rejected_actions", []),
        missing_transition=np_.get("missing_transition", {}),
        invariants=np_.get("invariants", []),
    )
    return classify(
        no_plan,
        fx.get("domain_actions", []),
        fx.get("repo_surface_actions", []),
        fx.get("authority_policy", {}),
        fx.get("sensors", []),
        fx.get("manufacturers", []),
        fx.get("qualification_env"),
    )


if __name__ == "__main__":
    import sys

    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            fx = json.load(f)
        d = classify_fixture(fx)
        print(json.dumps({"fixture": fx["name"], "expected": fx["expected_gap_type"], "got": d.gap_type.value, "digest": d.receipt_digest}))
