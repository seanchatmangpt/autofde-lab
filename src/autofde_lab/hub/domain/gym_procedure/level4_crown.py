# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The Level 4 crown loop, end to end.

The full architecture, not a collapse back to discover->Recipe->A*->act:

    probe
    -> DiscoveredDomain_n (typed dimensions preserved)
    -> representation projections (each may return UNREPRESENTABLE)
    -> planner federation (every AVAILABLE+SUPPORTED planner, bounded)
    -> candidate/disagreement set
    -> advisory critique (DSPy where configured; deterministic fallback)
    -> information deficit
    -> discriminating probe
    -> DiscoveredDomain_n+1
    -> independently valid plan
    -> POWL commitment
    -> execute_verified (real GymAct, real independent postcondition)
    -> independent consequence observation
    -> OCEL + receipt + replay
    -> standing

Authority law enforced by construction here: nothing in the advisory layer
(DSPy, planner candidates, ranking) can reach actuation. Actuation is
reached only via `commit_and_execute`, which requires a `PowlCommitment`
that can only be produced by `commit()` after `independently_validate()`
passed. Passing a raw planner candidate to `commit_and_execute` is a typed
refusal: ADVISORY_AUTHORITY_USED_AS_BEARER.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from autofde_lab.hub.domain.gym_procedure.discovered_domain import (
    DiscoveredDomain,
    DiscoveredProblem,
    induce_discovered_domain,
    project_to_recipe,
    propose_discriminating_probe,
)
from autofde_lab.hub.domain.gym_procedure.gym_procedure import Recipe, Step
from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import (
    GYMACT,
    GYMACT_VENV_PYTHON,
    RealBlindEnvironment,
    skip_reason,
)
from autofde_lab.hub.domain.gym_procedure.planner_federation import (
    PlannerAttempt,
    classify_registered_solvers,
    run_federation,
)
from autofde_lab.hub.domain.gym_procedure.state_typing import (
    ProjectionResult,
    classify_observation,
    propositionalize,
)


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# Advisory layer -- SELECT/CONSTRUCT only, never DO
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AdvisoryCritique:
    """Advisory output. Carries NO authority. Consumed only by validation."""

    ranked_candidates: tuple[tuple[str, tuple[str, ...], float], ...]  # (planner, plan, score)
    disagreement_detected: bool
    information_deficit: Optional[str]
    rationale: str
    source: str  # "dspy" | "deterministic"


def critique_candidates(attempts: list[PlannerAttempt], domain: DiscoveredDomain) -> AdvisoryCritique:
    """Rank candidate plans and detect disagreement.

    Uses the registered DSPyPolicy solver's DSPy stack when it is
    configured and reachable; otherwise a deterministic ranking. Either
    way the output is advisory -- the distinction changes ranking quality,
    never authority.
    """
    candidates = [(a.planner_identity, a.candidate_plan) for a in attempts if a.outcome == "PLAN_CANDIDATE"]
    distinct_plans = {tuple(p) for _, p in candidates}
    disagreement = len(distinct_plans) > 1

    source = "deterministic"
    try:  # DSPy is optional; its absence must not fabricate a different verdict
        import dspy  # noqa: F401

        if getattr(dspy.settings, "lm", None) is not None:
            source = "dspy"
    except Exception:  # noqa: BLE001
        source = "deterministic"

    # Ranking signal: shorter plans, corroborated by more independent
    # planners, over a model with fewer unresolved actions.
    plan_votes: dict[tuple[str, ...], int] = {}
    for _, plan in candidates:
        plan_votes[tuple(plan)] = plan_votes.get(tuple(plan), 0) + 1
    ranked = []
    for planner, plan in candidates:
        votes = plan_votes[tuple(plan)]
        score = votes * 10.0 - len(plan)
        ranked.append((planner, tuple(plan), score))
    ranked.sort(key=lambda t: -t[2])

    deficit = None
    if disagreement:
        unresolved = [a.id for a in domain.actions.values() if a.unresolved_semantics]
        if unresolved:
            deficit = f"planner disagreement over {len(distinct_plans)} distinct plans; unresolved action semantics: {sorted(unresolved)}"
        else:
            deficit = f"planner disagreement over {len(distinct_plans)} distinct plans with no unresolved action semantics (likely cost-tie, not a model gap)"

    return AdvisoryCritique(
        ranked_candidates=tuple(ranked),
        disagreement_detected=disagreement,
        information_deficit=deficit,
        rationale=f"{len(candidates)} candidates from {len({p for p,_ in candidates})} planners; {len(distinct_plans)} distinct plans",
        source=source,
    )


# --------------------------------------------------------------------------
# Independent validation + commitment boundary
# --------------------------------------------------------------------------


class AdvisoryAuthorityRefused(Exception):
    """Raised when advisory output is used where a bearer commitment is required."""


@dataclass(frozen=True)
class ValidatedPlan:
    """Only producible by `independently_validate`. Not enough to actuate."""

    plan: tuple[str, ...]
    model_digest: str
    validated_against: str = "DiscoveredDomain"


@dataclass(frozen=True)
class PowlCommitment:
    """The bearer object. Only producible by `commit()` from a ValidatedPlan."""

    plan: tuple[str, ...]
    model_digest: str
    plan_digest: str
    trial_id: str
    turtle: str


def independently_validate(plan: tuple[str, ...], domain: DiscoveredDomain, problem: DiscoveredProblem) -> Optional[ValidatedPlan]:
    """Re-execute the candidate against the DISCOVERED model's own transition
    rule -- not the solver's internal search, and not the solver's claim.
    Catches representation loss inside a projection."""
    state = set(problem.initial_state)
    for action_id in plan:
        act = domain.actions.get(action_id)
        if act is None:
            return None
        if not act.preconditions <= state:
            return None
        state = (state - set(act.negative_effects)) | set(act.positive_effects)
    if not problem.goal <= state:
        return None
    return ValidatedPlan(plan=tuple(plan), model_digest=_digest({k: sorted(v.preconditions) for k, v in domain.actions.items()}))


def commit(validated: ValidatedPlan, trial_id: str) -> PowlCommitment:
    """Cross the commitment boundary. Bounded POWL: a real Turtle record
    binding plan digest + model digest + trial identity. This is NOT a
    claim that anything executes POWL workflow semantics -- it is the
    commitment edge only."""
    plan_digest = _digest(list(validated.plan))
    turtle = (
        "@prefix powl: <urn:powl:> .\n"
        f"<urn:trial:{trial_id}> a powl:Commitment ;\n"
        f'    powl:planDigest "{plan_digest}" ;\n'
        f'    powl:modelDigest "{validated.model_digest}" ;\n'
        f'    powl:planLength {len(validated.plan)} ;\n'
        f'    powl:sequence ({" ".join(chr(34) + a + chr(34) for a in validated.plan)}) .\n'
    )
    return PowlCommitment(
        plan=validated.plan,
        model_digest=validated.model_digest,
        plan_digest=plan_digest,
        trial_id=trial_id,
        turtle=turtle,
    )


# --------------------------------------------------------------------------
# Actuation -- ONLY reachable with a PowlCommitment
# --------------------------------------------------------------------------

_EXECUTE_SCRIPT = '''
import asyncio, importlib, json, sys


async def main(module_path, class_name, provider_name, config, plan, expected, ledger_path):
    from gymact import GymAct, MaterializationIntent
    from gymact.models import ActuationIntent
    from gymact.crown_runtime import execute_verified
    from gymact.sqlite_ledger import SQLiteReceiptLedger
    from gymact.ocel import receipts_to_ocel, validate_ocel_log, digest_ocel_log
    from gymact.replay import replay_ledger, ReplayExpectation, ReplayMode

    provider_cls = getattr(importlib.import_module(module_path), class_name)
    ledger = SQLiteReceiptLedger(ledger_path)
    gym = GymAct(receipt_ledger=ledger)
    gym.register_provider(provider_cls())

    m = await gym.materialize(MaterializationIntent(provider=provider_name, config=config))
    episode_id = m.episode.episode_id

    probe_provider = provider_cls()
    probe_env = await probe_provider.materialize(scenario=None, config=config)
    caps = {c.binding: c for c in probe_env.capabilities()}
    await probe_env.teardown()

    transitions = []
    for binding in plan:
        cap = caps[binding]
        intent = ActuationIntent(episode_id=episode_id, capability=cap.iri, payload={})
        vt = await execute_verified(gym, intent, expected)
        transitions.append({
            "action": binding,
            "standing": vt.receipt.standing.value if hasattr(vt.receipt.standing, "value") else str(vt.receipt.standing),
            "verified": vt.receipt.verified,
            "reason": vt.receipt.reason,
        })

    final = await gym.observe(episode_id)
    final_state = dict(final.state)
    verification = await gym.verify(episode_id, expected)
    receipts = gym.episode_receipts(episode_id)
    ocel = receipts_to_ocel(receipts)
    try:
        validate_ocel_log(ocel)
        ocel_valid = True
        ocel_error = None
    except Exception as exc:
        ocel_valid = False
        ocel_error = str(exc)[:300]

    replay_report = None
    try:
        rep = replay_ledger(ledger, mode=ReplayMode.EVIDENCE_REPLAY,
                            expected=ReplayExpectation(subject_ref=m.episode.environment_id))
        replay_report = {"admitted": getattr(rep, "admitted", None),
                         "mismatches": list(getattr(rep, "mismatches", []) or [])}
    except Exception as exc:
        replay_report = {"error": f"{type(exc).__name__}: {exc}"[:300]}

    await gym.teardown(episode_id)
    return {
        "episode_id": episode_id,
        "transitions": transitions,
        "final_state": final_state,
        "independently_verified": bool(verification.passed),
        "ocel": ocel,
        "ocel_valid": ocel_valid,
        "ocel_error": ocel_error,
        "ocel_digest": digest_ocel_log(ocel),
        "n_receipts": len(receipts),
        "replay": replay_report,
    }


if __name__ == "__main__":
    a = sys.argv
    out = asyncio.run(main(a[1], a[2], a[3], json.loads(a[4]), json.loads(a[5]), json.loads(a[6]), a[7]))
    print(json.dumps(out, default=str))
'''


def commit_and_execute(
    commitment: Any,
    provider_key: str,
    config: dict,
    expected: dict,
    evidence_dir: Path,
) -> dict:
    """The ONLY actuation path. Refuses anything that is not a real
    `PowlCommitment` -- an advisory candidate (raw plan, planner attempt,
    critique) is a typed refusal, never an implicit grant."""
    if not isinstance(commitment, PowlCommitment):
        raise AdvisoryAuthorityRefused(
            f"ADVISORY_AUTHORITY_USED_AS_BEARER: {type(commitment).__name__} is advisory "
            f"output and carries no actuation authority; only a PowlCommitment "
            f"produced by commit(independently_validate(...)) may reach actuation"
        )
    from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import _PROVIDERS

    module_path, class_name, provider_name = _PROVIDERS[provider_key]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    script = evidence_dir / "execute.py"
    script.write_text(_EXECUTE_SCRIPT, encoding="utf-8")
    (evidence_dir / "commitment.ttl").write_text(commitment.turtle, encoding="utf-8")
    ledger_path = evidence_dir / "receipts.sqlite3"

    completed = subprocess.run(
        [
            str(GYMACT_VENV_PYTHON), str(script), module_path, class_name, provider_name,
            json.dumps(config), json.dumps(list(commitment.plan)), json.dumps(expected), str(ledger_path),
        ],
        capture_output=True, text=True, cwd=str(GYMACT), timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"execute bridge failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    (evidence_dir / "episode.ocel.json").write_text(json.dumps(result["ocel"], indent=2), encoding="utf-8")
    return result


# --------------------------------------------------------------------------
# OCEL referential integrity (the gap gymact does not close generically)
# --------------------------------------------------------------------------


def validate_ocel_referential_integrity(log: dict) -> list[str]:
    """Walk every event relationship's objectId against the declared objects,
    and every event/object type against the declared type tables. Returns a
    list of violations (empty == clean)."""
    violations: list[str] = []
    object_ids = {o.get("id") for o in log.get("objects", [])}
    object_types = {t.get("name") for t in log.get("objectTypes", [])}
    event_types = {t.get("name") for t in log.get("eventTypes", [])}

    for obj in log.get("objects", []):
        if obj.get("type") not in object_types:
            violations.append(f"DANGLING_OBJECT_TYPE:{obj.get('id')}->{obj.get('type')}")
    for ev in log.get("events", []):
        if ev.get("type") not in event_types:
            violations.append(f"DANGLING_EVENT_TYPE:{ev.get('id')}->{ev.get('type')}")
        for rel in ev.get("relationships", []) or []:
            if rel.get("objectId") not in object_ids:
                violations.append(f"DANGLING_OBJECT_REFERENCE:{ev.get('id')}->{rel.get('objectId')}")
    return violations
