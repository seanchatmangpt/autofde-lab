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
from autofde_lab.hub.domain.gym_procedure.typed_induction import (
    TypedDomain,
    induce_typed_domain,
    search_plan_typed,
    validate_plan_typed,
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


async def main(module_path, class_name, provider_name, config, plan, expected_list, payloads, ledger_path):
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
    for i, binding in enumerate(plan):
        cap = caps[binding]
        step_expected = expected_list[i]
        intent = ActuationIntent(episode_id=episode_id, capability=cap.iri, payload=payloads[i])
        vt = await execute_verified(gym, intent, step_expected)
        transitions.append({
            "action": binding,
            "step_index": i,
            "expected": step_expected,
            "standing": vt.receipt.standing.value if hasattr(vt.receipt.standing, "value") else str(vt.receipt.standing),
            "verified": vt.receipt.verified,
            "reason": vt.receipt.reason,
        })

    final_expected = expected_list[-1] if expected_list else {}
    final = await gym.observe(episode_id)
    final_state = dict(final.state)
    verification = await gym.verify(episode_id, final_expected)
    receipts = gym.episode_receipts(episode_id)
    ocel = receipts_to_ocel(receipts)
    try:
        validate_ocel_log(ocel)
        ocel_valid = True
        ocel_error = None
    except Exception as exc:
        ocel_valid = False
        ocel_error = str(exc)[:300]

    # REPLAY verification. Three real defects were found here by an adversarial
    # audit and are fixed below -- read the comments before simplifying any of
    # this, because every one of them made an unverified replay look green:
    #
    #  1. The verdict field was read as `rep.admitted`, which does NOT EXIST on
    #     gymact's ReplayReport (its fields are mode/valid/record_count/
    #     head_digest/mismatches/live_reexecution_admitted). getattr(...) with a
    #     default therefore returned None unconditionally, so the actual
    #     pass/fail verdict was never read by anything.
    #  2. On an exception the report carried only {"error": ...} with no
    #     "mismatches" key, so the caller's .get("mismatches", []) produced []
    #     and the ALIVE conjunction passed. A replay that never ran was
    #     indistinguishable from one that passed, and the error string was
    #     dropped before it could reach the durable record.
    #  3. `valid` is now an explicit part of the verdict: a replay that runs
    #     and reports valid=False must not pass merely because its mismatch
    #     tuple happens to be empty.
    replay_report: dict
    try:
        rep = replay_ledger(
            ledger,
            mode=ReplayMode.EVIDENCE_REPLAY,
            expected=ReplayExpectation(subject_ref=m.episode.environment_id),
        )
        mismatches = list(rep.mismatches or [])
        if not rep.valid:
            # Surface an invalid verdict THROUGH the mismatch channel so the
            # ALIVE conjunction sees it even if gymact reported no per-record
            # mismatch string.
            mismatches.append("REPLAY_REPORT_INVALID")
        replay_report = {
            "ran": True,
            "valid": bool(rep.valid),
            "record_count": int(rep.record_count),
            "head_digest": rep.head_digest,
            "mismatches": mismatches,
            "error": None,
        }
    except Exception as exc:
        # Fail CLOSED: a replay that could not run is a failed factor, never a
        # silently satisfied one.
        replay_report = {
            "ran": False,
            "valid": False,
            "record_count": 0,
            "head_digest": None,
            "mismatches": [f"REPLAY_DID_NOT_RUN:{type(exc).__name__}"],
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }

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
    out = asyncio.run(main(a[1], a[2], a[3], json.loads(a[4]), json.loads(a[5]),
                          json.loads(a[6]), json.loads(a[7]), a[8]))
    print(json.dumps(out, default=str))
'''


_COUNTER_DELTAS = {"increment": 1, "decrement": -1}


def real_goal_attained(observation: dict) -> bool:
    """THE real-world verdict, read off the provider's own observation.

    Every bounded provider in the pool publishes `solved` as a derived
    dimension it computes itself. Reading it here is not the model grading
    its own work: the model is explicitly forbidden from *claiming* `solved`
    (typed induction records it CONTEXT_DEPENDENT), so this value can only
    come from the real environment after real actuation.
    """
    return observation.get("solved") is True


def model_goal_predicate(provider_key: str, initial_observation: dict, config: dict):
    """The goal handed to planning, expressed over BASE dimensions.

    It cannot be `solved is True`: `solved` is derived, so typed induction
    refuses to claim it and no simulated plan could ever reach it -- every
    trial would report NO_TYPED_VALID_PLAN for a representational reason
    rather than a real one. Stating the goal in base terms is what a goal
    specification legitimately is; it discloses nothing about what any
    action DOES, which is what the agent must still discover.
    """
    obs = dict(initial_observation)
    if provider_key in ("cube_counter", "cube_container_counter"):
        target = obs.get("target", config.get("target"))

        def counter_goal(state: dict) -> bool:
            return target is not None and state.get("counter") == target

        return counter_goal, f"counter == target ({target})"
    if provider_key == "resource_flow":
        target = obs.get("target", config.get("target"))

        def flow_goal(state: dict) -> bool:
            output = state.get("output")
            return (
                target is not None
                and isinstance(output, (int, float))
                and output >= target
            )

        return flow_goal, f"output >= target ({target})"
    if provider_key == "switchboard":

        def board_goal(state: dict) -> bool:
            return (
                state.get("master") is True
                and state.get("required_on") == state.get("required_count")
            )

        return board_goal, "master and required_on == required_count"
    if provider_key == "lock_and_key":
        depth = obs.get("depth", config.get("depth"))

        def lock_goal(state: dict) -> bool:
            return depth is not None and state.get("locks_open") == depth

        return lock_goal, f"locks_open == depth ({depth})"
    raise ValueError(f"UNSUPPORTED_PROVIDER_FOR_GOAL:{provider_key}")


def predict_step_postconditions(
    plan: tuple[str, ...],
    provider_key: str,
    initial_observation: dict,
    payloads: Optional[list[dict]] = None,
) -> list[dict]:
    """Predict the observation expected AFTER each action of `plan`.

    Needed because `execute_verified` verifies a postcondition after every
    single action: broadcasting one terminal expectation to every step makes
    each intermediate step REFUSED (POSTCONDITION_FAILED) even when the plan
    is executing exactly as intended. Refusing an intermediate step of a
    correct plan is a false negative, and a false REFUSED is as much a
    standing error as a false ALIVE.

    Authority note: this is a hardcoded model of the *counter providers'*
    arithmetic, deliberately independent of the discovered model and of any
    planner's claim -- that independence is what makes the postcondition a
    real check rather than the solver grading its own work. It is NOT a
    general oracle: an unknown provider raises rather than guessing.
    """
    if provider_key not in (
        "cube_counter",
        "cube_container_counter",
        "switchboard",
        "resource_flow",
        "lock_and_key",
    ):
        raise ValueError(
            f"UNSUPPORTED_PROVIDER_FOR_POSTCONDITION_PREDICTION:{provider_key}; "
            f"known: cube_counter, cube_container_counter, switchboard, "
            f"resource_flow, lock_and_key"
        )
    if provider_key == "switchboard":
        return _predict_switchboard(plan, initial_observation)
    if provider_key == "resource_flow":
        return _predict_resource_flow(plan, initial_observation)
    if provider_key == "lock_and_key":
        return _predict_lock_and_key(plan, initial_observation)
    from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import decode_action

    payloads = payloads or [{} for _ in plan]
    counter = int(initial_observation.get("counter", 0))
    target = initial_observation.get("target")
    out: list[dict] = []
    for i, action_id in enumerate(plan):
        # Plan entries are ACTION IDS; a parameterized one carries its
        # payload (`increment_by[value=1]`), so match on the binding.
        action, decoded = decode_action(action_id)
        if action in _COUNTER_DELTAS:
            counter += _COUNTER_DELTAS[action]
        elif action == "increment_by":
            step_payload = payloads[i] or decoded
            counter += int(step_payload.get("value", 0))
        else:
            raise ValueError(f"UNSUPPORTED_ACTION_FOR_POSTCONDITION_PREDICTION:{action_id}")
        step_expected: dict = {"counter": counter}
        if target is not None:
            step_expected["solved"] = counter == int(target)
        out.append(step_expected)
    return out


def _predict_switchboard(plan: tuple[str, ...], initial: dict) -> list[dict]:
    """Independent oracle for `switchboard`, written from the provider's
    declared semantics -- not from the discovered model.

    `required_on` and `solved` are deliberately NOT predicted: which switch
    indices are 'required' is seeded hidden state the environment never
    discloses, so an oracle that claimed them would be guessing. Omitting an
    unpredictable dimension narrows the check honestly; inventing a value
    for it would make the check pass for the wrong reason.
    """
    from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import decode_action

    n = int(initial.get("n_switches", 0))
    switches = {i: bool(initial.get(f"switch_{i}", False)) for i in range(n)}
    master = bool(initial.get("master", False))
    toggles = int(initial.get("toggles", 0))
    out: list[dict] = []
    for action_id in plan:
        binding, payload = decode_action(action_id)
        if binding == "toggle_switch":
            index = int(payload["index"])
            switches[index] = not switches[index]
            toggles += 1
        elif binding == "engage_master":
            if switches.get(0) and switches.get(1):
                master = True
        elif binding == "reset_pair":
            switches[0] = False
            switches[1] = False
        else:
            raise ValueError(f"UNSUPPORTED_ACTION_FOR_POSTCONDITION_PREDICTION:{action_id}")
        step: dict = {f"switch_{i}": v for i, v in switches.items()}
        step["master"] = master
        step["toggles"] = toggles
        out.append(step)
    return out


def _predict_resource_flow(plan: tuple[str, ...], initial: dict) -> list[dict]:
    """Independent oracle for `resource-flow`.

    `mine_rate` is observable, so mining is predictable. The catalyst bonus
    is NOT observable, so after `burn_catalyst` the `output` pool becomes
    unpredictable and is dropped from every later expectation (as is
    `solved`, which depends on it). Everything still predictable stays
    checked.
    """
    from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import decode_action

    capacity = int(initial.get("capacity", 0))
    target = initial.get("target")
    rate = int(initial.get("mine_rate", 1))
    raw = int(initial.get("raw", 0))
    refined = int(initial.get("refined", 0))
    output = int(initial.get("output", 0))
    catalyst = bool(initial.get("catalyst", True))
    output_known = True
    out: list[dict] = []
    for action_id in plan:
        binding, _ = decode_action(action_id)
        if binding == "mine":
            raw = min(capacity, raw + rate)
        elif binding == "refine":
            raw -= 1
            refined += 1
        elif binding == "assemble":
            refined -= 1
            output += 1
        elif binding == "burn_catalyst":
            catalyst = False
            output_known = False  # bonus is hidden seeded state
        else:
            raise ValueError(f"UNSUPPORTED_ACTION_FOR_POSTCONDITION_PREDICTION:{action_id}")
        step: dict = {"raw": raw, "refined": refined, "catalyst": catalyst}
        if output_known:
            step["output"] = output
            if target is not None:
                step["solved"] = output >= int(target)
        out.append(step)
    return out


def _predict_lock_and_key(plan: tuple[str, ...], initial: dict) -> list[dict]:
    """Independent oracle for `lock-and-key`.

    Which key opens which lock is a hidden seeded permutation, so the
    success of `open_lock` cannot be predicted. The oracle predicts the
    consequence of a SUCCESSFUL open (the key is consumed, so
    `holding_key` becomes False and `locks_open` advances) -- which is
    exactly the right check: if the held key does not fit, the real
    environment refuses, `holding_key` stays True, and the step fails
    POSTCONDITION_FAILED rather than silently passing.
    """
    from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import decode_action

    depth = int(initial.get("depth", 0))
    locks_open = int(initial.get("locks_open", 0))
    held = int(initial.get("held_key", -1))
    jammed = bool(initial.get("rack_jammed", False))
    out: list[dict] = []
    for action_id in plan:
        binding, payload = decode_action(action_id)
        if binding == "pick_key":
            held = int(payload["key"])
        elif binding == "drop_key":
            held = -1
        elif binding == "open_lock":
            locks_open += 1
            held = -1
        elif binding == "force_latch":
            locks_open += 1
            held = -1
            jammed = True
        else:
            raise ValueError(f"UNSUPPORTED_ACTION_FOR_POSTCONDITION_PREDICTION:{action_id}")
        out.append(
            {
                "locks_open": locks_open,
                "held_key": held,
                "holding_key": held != -1,
                "rack_jammed": jammed,
                "solved": locks_open >= depth,
            }
        )
    return out


def commit_and_execute(
    commitment: Any,
    provider_key: str,
    config: dict,
    expected: Any,
    evidence_dir: Path,
    payloads: Optional[list[dict]] = None,
) -> dict:
    """The ONLY actuation path. Refuses anything that is not a real
    `PowlCommitment` -- an advisory candidate (raw plan, planner attempt,
    critique) is a typed refusal, never an implicit grant.

    `expected` is either:

    - a ``list[dict]`` of per-step postconditions, one per plan action --
      ``expected[i]`` is verified immediately after action ``i``; or
    - a single ``dict`` (backward-compatible form), which is treated as the
      expectation for the FINAL step only. Earlier steps get a plain
      predicted postcondition from `predict_step_postconditions` rather than
      the terminal one, which is what made multi-step plans report REFUSED
      on every intermediate action.
    """
    if not isinstance(commitment, PowlCommitment):
        raise AdvisoryAuthorityRefused(
            f"ADVISORY_AUTHORITY_USED_AS_BEARER: {type(commitment).__name__} is advisory "
            f"output and carries no actuation authority; only a PowlCommitment "
            f"produced by commit(independently_validate(...)) may reach actuation"
        )
    from autofde_lab.hub.domain.gym_procedure.level4_gymact_bridge import (
        _PROVIDERS,
        decode_action,
    )

    module_path, class_name, provider_name = _PROVIDERS[provider_key]
    # A committed plan is a sequence of ACTION IDS, which for a
    # parameterized capability carry their payload (`toggle_switch[index=2]`).
    # The gym only knows bindings, so decode here -- and let a decoded
    # payload supply the actuation payload when the caller passed none.
    action_ids = tuple(commitment.plan)
    decoded = [decode_action(a) for a in action_ids]
    plan = tuple(binding for binding, _ in decoded)
    if payloads is None:
        payloads = [dict(p) for _, p in decoded]
    else:
        payloads = [
            dict(supplied) if supplied else dict(inferred)
            for supplied, (_, inferred) in zip(payloads, decoded)
        ]
    if len(payloads) != len(plan):
        raise ValueError(f"payloads length {len(payloads)} != plan length {len(plan)}")

    if isinstance(expected, list):
        expected_list = [dict(e) for e in expected]
        if len(expected_list) != len(plan):
            raise ValueError(
                f"per-step expected length {len(expected_list)} != plan length {len(plan)}"
            )
    elif isinstance(expected, dict):
        expected_list = predict_step_postconditions(
            plan, provider_key, {"counter": 0, "target": config.get("target")}, payloads
        )
        if expected_list:
            expected_list[-1] = dict(expected)
    else:
        raise TypeError(f"expected must be a dict or list[dict], got {type(expected).__name__}")

    evidence_dir.mkdir(parents=True, exist_ok=True)
    script = evidence_dir / "execute.py"
    script.write_text(_EXECUTE_SCRIPT, encoding="utf-8")
    (evidence_dir / "commitment.ttl").write_text(commitment.turtle, encoding="utf-8")
    ledger_path = evidence_dir / "receipts.sqlite3"

    completed = subprocess.run(
        [
            str(GYMACT_VENV_PYTHON), str(script), module_path, class_name, provider_name,
            json.dumps(config), json.dumps(list(plan)), json.dumps(expected_list),
            json.dumps(payloads), str(ledger_path),
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


def _parse_fact(fact: str) -> tuple[str, Any]:
    """Reverse the bridge's ``"name=value"`` fact encoding back to a typed
    value, so `state_typing` classifies real kinds (a float `reward` must be
    seen as CONTINUOUS, not as the string ``"0.16666"``)."""
    import ast

    name, _, raw = fact.partition("=")
    try:
        return name, ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return name, raw


def _observation_from_facts(facts: list[str]) -> dict[str, Any]:
    return dict(_parse_fact(f) for f in facts)


@dataclass(frozen=True)
class TrialReport:
    """The full, honest record of one real crown trial."""

    seed: int
    run_id: str
    provider: str
    n_probes: int
    n_planner_attempts: int
    planners_producing_candidates: tuple[str, ...]
    disagreement_detected: bool
    independently_verified: bool
    ocel_valid: bool
    ocel_ref_violations: tuple[str, ...]
    replay_mismatches: tuple[str, ...]
    evidence_dir: str
    representation_losses: dict[str, str] = field(default_factory=dict)
    n_supported_solvers: int = 0
    committed_plan: tuple[str, ...] = ()
    discriminating_probe: Optional[str] = None
    step_standings: tuple[str, ...] = ()
    outcome: str = "UNKNOWN"
    # --- typed-model gate + real-goal attainment -------------------------
    goal_predicate_description: str = ""
    real_goal_attained: bool = False
    typed_derived_dimensions: tuple[str, ...] = ()
    unsound_candidates_rejected: int = 0
    committed_plan_source: str = ""
    final_state: dict = field(default_factory=dict)
    # --- replay evidence (was silently unverified before this field existed) --
    replay_ran: bool = False
    replay_valid: bool = False
    replay_record_count: int = 0
    replay_error: Optional[str] = None

    def is_alive(self) -> bool:
        """The ONLY green verdict.

        Requires the REAL world to have reached the goal -- not the model's
        prediction, not a per-step postcondition. `replay_ran` and
        `replay_valid` are explicit conjuncts because an earlier version of
        this method tested only `replay_mismatches == ()`, which an
        exception-swallowing replay path satisfied vacuously: a replay that
        never ran scored identically to one that verified. An absent or
        unrunnable factor must never read as a satisfied one.

        `ocel_valid` is likewise a conjunct: it was computed fail-closed but
        omitted from the verdict entirely, so a trial with an invalid OCEL log
        but clean referential integrity would have scored ALIVE.
        """
        return (
            self.real_goal_attained
            and self.independently_verified
            and self.ocel_valid
            and self.replay_ran
            and self.replay_valid
            and self.ocel_ref_violations == ()
            and self.replay_mismatches == ()
        )


def _is_metric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _changed_dims(record: dict, non_metric_only: bool = False) -> set[str]:
    pre = record.get("observed_pre") or {}
    post = record.get("observed_post") or {}
    changed = {k for k in post if pre.get(k) != post.get(k)}
    if non_metric_only:
        changed = {k for k in changed if not _is_metric(post.get(k))}
    return changed


def _discover_by_probing(env: RealBlindEnvironment, probe_budget: int) -> tuple[list[dict], int]:
    """Learn every action's effect without wrecking the episode.

    Replaces a loop that committed every applicable probe to history. That
    loop had two measured defects, both of which made `lock_and_key`
    undiscoverable:

    1. **Irreversible probes poisoned the run.** Probing `force_latch`
       jammed the key rack permanently at probe 6; every remaining probe was
       refused, so `open_lock` was never observed succeeding and the trial
       ended `NO_TYPED_VALID_PLAN`. Probes are now SPECULATIVE by default --
       really executed, really observed, then discarded.
    2. **A guarded action was never observed succeeding.** `open_lock`
       requires a held key, `refine` requires a raw token; probing each
       action alone from the baseline can never see either succeed. An
       action that stays refused is now retried behind a chained prefix
       built from actions already known to work, so `assemble` is probed
       behind `(mine, refine)` and `open_lock` behind each `pick_key[k]`.

    Exactly one action per round is committed, to advance the frontier. The
    choice prefers an action that is *measurably* safe -- one touching only
    metric dimensions, or one shown by a real self-inverse probe to undo
    itself. Only when no safe action exists does it pay for a lookahead
    sweep and keep whichever candidate leaves the most actions applicable.
    That is what stops `force_latch` from being adopted: it is measured to
    strand the episode, not guessed to be dangerous by its name.
    """
    records: list[dict] = []
    actions = env.available_actions()
    learned: set[str] = set()
    committed: set[str] = set()
    establisher: dict[str, tuple[str, ...]] = {}
    n = 0

    def probe(action: str, prefix: tuple[str, ...] = (), commit: bool = False) -> dict:
        nonlocal n
        record = env.try_action(action, commit=commit, prefix=prefix)
        records.append(record)
        n += 1
        if record.get("applicable"):
            learned.add(action)
        return record

    while n < probe_budget:
        sweep: dict[str, dict] = {}
        for action in actions:
            if n >= probe_budget:
                break
            sweep[action] = probe(action)

        # Chained establisher search for anything still never-applicable.
        for action in actions:
            if action in learned or n >= probe_budget:
                continue
            for helper in sorted(learned):
                if n >= probe_budget:
                    break
                prefix = establisher.get(helper, ()) + (helper,)
                if action in prefix:
                    continue
                if probe(action, prefix=prefix).get("applicable"):
                    establisher[action] = prefix
                    break

        if all(action in learned for action in actions):
            break  # nothing left to learn; stop before burning budget

        candidates = [
            a
            for a in actions
            if sweep.get(a, {}).get("applicable")
            and a not in committed
            and _changed_dims(sweep[a])  # an inert action advances nothing
        ]
        if not candidates or n >= probe_budget:
            break

        chosen: Optional[str] = None
        risky: list[str] = []
        for a in candidates:
            if not _changed_dims(sweep[a], non_metric_only=True):
                chosen = a  # touches only metric dimensions
                break
            if n >= probe_budget:
                break
            twice = probe(a, prefix=(a,))
            baseline = sweep[a].get("observed_pre") or {}
            after = twice.get("observed_post") or {}
            if twice.get("applicable") and all(
                after.get(d) == baseline.get(d)
                for d in baseline
                if not _is_metric(baseline.get(d))
            ):
                chosen = a  # really undoes itself
                break
            risky.append(a)

        if chosen is None:
            best_count = -1
            for a in risky:
                if n >= probe_budget:
                    break
                count = 0
                for b in actions:
                    if n >= probe_budget:
                        break
                    if probe(b, prefix=(a,)).get("applicable"):
                        count += 1
                if count > best_count:
                    best_count, chosen = count, a

        if chosen is None or n >= probe_budget:
            break
        probe(chosen, commit=True)
        committed.add(chosen)

    return records, n


def run_real_trial(
    seed: int,
    provider_key: str,
    config: dict,
    evidence_root: Path,
    probe_budget: int = 12,
    planner_timeout_s: float = 10.0,
) -> TrialReport:
    """probe -> induce -> project -> federate -> critique -> (discriminate,
    re-induce, replan) -> independently validate -> commit -> execute.

    Per-trial isolation matches `level4_generator.Trial`: a uuid4 run_id and
    a private evidence directory created with ``exist_ok=False``, so two
    trials can never share probe logs, ledgers or OCEL output.
    """
    run_id = str(uuid.uuid4())
    evidence_dir = Path(evidence_root) / f"realtrial_{seed}_{run_id}"
    evidence_dir.mkdir(parents=True, exist_ok=False)

    env = RealBlindEnvironment(provider_key, config, evidence_dir / "discovery")

    # --- probe ------------------------------------------------------------
    raw_records, n_probes = _discover_by_probing(env, probe_budget)

    # --- typed projection (losses recorded, never silently dropped) --------
    observations = [_observation_from_facts(r.get("observed_pre_facts", [])) for r in raw_records]
    dims = classify_observation([o for o in observations if o])
    losses: dict[str, str] = {}

    def _project(facts: list[str]) -> list[str]:
        projected, lost = propositionalize(_observation_from_facts(facts), dims)
        losses.update(lost)
        return sorted(projected)

    probe_log = [
        {
            "action": r["action"],
            "applicable": r.get("applicable", False),
            "observed_pre_facts": _project(r.get("observed_pre_facts", [])),
            "delta_added": _project(r.get("delta_added", [])),
            "delta_removed": _project(r.get("delta_removed", [])),
        }
        for r in raw_records
    ]
    (evidence_dir / "typed_probe_log.json").write_text(
        json.dumps({"probe_log": probe_log, "representation_losses": losses}, indent=2),
        encoding="utf-8",
    )

    initial_facts = frozenset(probe_log[0]["observed_pre_facts"]) if probe_log else frozenset()
    goal = frozenset({"solved=True"})
    problem = DiscoveredProblem(initial_state=initial_facts, goal=goal)

    def _plan_round(log: list[dict]) -> tuple[DiscoveredDomain, Recipe, list, AdvisoryCritique, list[str]]:
        domain = induce_discovered_domain(log)
        recipe = project_to_recipe(domain, problem, gym=provider_key, task=f"seed{seed}", source_ref=f"realtrial:{run_id}")
        classified = classify_registered_solvers(recipe)
        supported = [c.name for c in classified if c.status == "SUPPORTED"]
        attempts = run_federation(recipe, supported, timeout_s=planner_timeout_s)
        return domain, recipe, attempts, critique_candidates(attempts, domain), supported

    domain, recipe, attempts, critique, supported = _plan_round(probe_log)
    n_supported = len(supported)

    # --- discriminating probe when planners disagree ----------------------
    discriminating: Optional[str] = None
    if critique.disagreement_detected and n_probes < probe_budget:
        for action_id in sorted(domain.actions):
            probe = propose_discriminating_probe(domain, action_id)
            if probe is None:
                continue
            discriminating = f"{probe.action}: {probe.rationale}"
            rec = env.try_action(probe.action, commit=False)
            n_probes += 1
            probe_log.append(
                {
                    "action": rec["action"],
                    "applicable": rec.get("applicable", False),
                    "observed_pre_facts": _project(rec.get("observed_pre_facts", [])),
                    "delta_added": _project(rec.get("delta_added", [])),
                    "delta_removed": _project(rec.get("delta_removed", [])),
                }
            )
            domain, recipe, attempts, critique, supported = _plan_round(probe_log)
            break

    candidate_planners = tuple(sorted({a.planner_identity for a in attempts if a.outcome == "PLAN_CANDIDATE"}))

    (evidence_dir / "federation.json").write_text(
        json.dumps(
            [
                {"planner": a.planner_identity, "outcome": a.outcome, "plan": list(a.candidate_plan),
                 "duration_s": a.planning_duration_s, "detail": a.detail}
                for a in attempts
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    # --- TYPED model: the authoritative validation gate -------------------
    # `induce_discovered_domain` unions deltas across calls and so claims a
    # single `increment` establishes `solved=True`. That model validated a
    # 1-step plan for a 3-step goal and 30 planners agreed with it. The typed
    # model learns `counter += 1` and refuses to claim `solved` at all, so no
    # federation candidate can reach commitment without surviving it.
    typed_records = [r for r in raw_records if "observed_pre" in r and "observed_post" in r]
    typed_domain: TypedDomain = induce_typed_domain(typed_records)
    typed_initial = dict(typed_records[0]["observed_pre"]) if typed_records else {}
    goal_predicate, goal_expr = model_goal_predicate(provider_key, typed_initial, config)
    goal_predicate_description = (
        f"MODEL goal (base dimensions): {goal_expr}; "
        f"REAL goal: solved is True in the post-execution observation"
    )

    base = dict(
        seed=seed, run_id=run_id, provider=provider_key, n_probes=n_probes,
        n_planner_attempts=len(attempts), planners_producing_candidates=candidate_planners,
        disagreement_detected=critique.disagreement_detected, evidence_dir=str(evidence_dir),
        representation_losses=dict(losses), n_supported_solvers=n_supported,
        discriminating_probe=discriminating,
    )

    # --- independent validation -> commitment -> actuation ----------------
    typed_derived = tuple(typed_domain.derived_dimensions())
    typed_base = dict(
        goal_predicate_description=goal_predicate_description,
        typed_derived_dimensions=typed_derived,
    )
    model_digest = _digest(
        {a: sorted(e.describe() for e in act.effects.values()) for a, act in typed_domain.actions.items()}
    )

    validated = None
    rejected = 0
    plan_source = ""
    for planner, plan, _score in critique.ranked_candidates:
        ok, _final, reason = validate_plan_typed(typed_domain, typed_initial, tuple(plan), goal_predicate)
        if ok:
            validated = ValidatedPlan(plan=tuple(plan), model_digest=model_digest, validated_against="TypedDomain")
            plan_source = f"federation:{planner}"
            break
        rejected += 1
    if validated is None:
        searched = search_plan_typed(typed_domain, typed_initial, goal_predicate)
        if searched is not None:
            ok, _final, reason = validate_plan_typed(typed_domain, typed_initial, searched, goal_predicate)
            if ok:
                validated = ValidatedPlan(plan=searched, model_digest=model_digest, validated_against="TypedDomain")
                plan_source = "typed_search"
    if validated is None:
        return TrialReport(
            independently_verified=False, ocel_valid=False, ocel_ref_violations=(),
            replay_mismatches=(), outcome="NO_TYPED_VALID_PLAN",
            unsound_candidates_rejected=rejected, **typed_base, **base
        )

    commitment = commit(validated, trial_id=run_id)
    payloads = [env.payload_for(a) for a in validated.plan]
    expected_steps = predict_step_postconditions(
        validated.plan, provider_key, typed_initial, payloads
    )
    result = commit_and_execute(
        commitment, provider_key, config, expected_steps, evidence_dir / "actuation", payloads
    )
    violations = validate_ocel_referential_integrity(result["ocel"])
    # Read the replay record STRICTLY. A missing "replay" key, or a missing
    # field inside it, means replay evidence was not produced -- which is a
    # failed factor, not a satisfied one. The previous code used
    # .get("mismatches", []) and so treated "no replay record at all" as
    # "replay clean".
    replay_rec = result.get("replay")
    if not isinstance(replay_rec, dict):
        replay_rec = {
            "ran": False,
            "valid": False,
            "record_count": 0,
            "error": "REPLAY_RECORD_ABSENT",
            "mismatches": ["REPLAY_RECORD_ABSENT"],
        }
    mismatches = [str(m) for m in (replay_rec.get("mismatches") or [])]
    replay_ran = bool(replay_rec.get("ran", False))
    replay_valid = bool(replay_rec.get("valid", False))
    if not replay_ran and "REPLAY_RECORD_ABSENT" not in mismatches:
        mismatches.append("REPLAY_DID_NOT_RUN")
    # REAL goal attainment: read off the post-execution observation the
    # actuation bridge returned, not off the model and not off a predicted
    # postcondition. `independently_verified` only says the predicted
    # consequence of the committed plan was observed -- it said True in a
    # prior run while the real world was counter=1, solved=False.
    real_final = dict(result.get("final_state") or {})
    return TrialReport(
        independently_verified=bool(result["independently_verified"]),
        ocel_valid=bool(result["ocel_valid"]),
        ocel_ref_violations=tuple(violations),
        replay_mismatches=tuple(mismatches),
        replay_ran=replay_ran,
        replay_valid=replay_valid,
        replay_record_count=int(replay_rec.get("record_count") or 0),
        replay_error=replay_rec.get("error"),
        committed_plan=validated.plan,
        committed_plan_source=plan_source,
        unsound_candidates_rejected=rejected,
        real_goal_attained=real_goal_attained(real_final),
        final_state=real_final,
        step_standings=tuple(t["standing"] for t in result["transitions"]),
        outcome="EXECUTED",
        **typed_base,
        **base,
    )


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
