"""Hand-grounded candidate FOND policy for the sa2a-v26.9.17 domain.

============================================================================
SCOPE BOUNDARY -- read this before reading anything else in this module, per
``.claude/rules/ecosystem-boundary.md`` and this repo's ``A = mu(O*)`` law
(``CLAUDE.md``). The repo names appearing as string fragments in the state
ids below (``ash-a2a``, ``ggen``, and -- named but not grounded into any
transition -- ``ash-r2rml``, ``bcinr``, ``ggen-igniter``, ``xaas``,
``affidavit``, ``beam4pm``, ``unrdf``, ``wasm4pm``) are labels for OBJECTS
INSIDE A FORMAL PLANNING MODEL. Every function in this module constructs and
checks a CANDIDATE POLICY over an ABSTRACT MODEL. Nothing this module
produces, and nothing any ``check_candidate_policy()`` run against its
output can produce, is an observation about the real sibling repositories --
no real repo is verified, qualified, admitted, actuated, or given standing
by anything here. This repo computes candidate plans; it does not actuate.
============================================================================

Provenance -- corrected grounding, superseding an earlier same-session pass
--------------------------------------------------------------------------
This module hand-grounds the FOND/HDDL specification now checked into this
repo verbatim at ``tests/domains/htn_fixtures/sa2a-v26.9.17-SOURCE.md`` --
a byte-for-byte copy of the user's own pasted message, recovered from this
session's transcript after context compaction, with its own provenance
header. Every state/action below cites the action name and the effect shape
given in that file; nothing here is paraphrased from a summary.

An earlier same-session grounding pass (workflow task ``whwez2z1w``) built a
*different*, less faithful version of this module from a paraphrase: its
authoring prompt told the grounding subagent to "read the conversation for
the full text," but Workflow subagents never inherit the orchestrator's
conversation, so no agent in that pass ever saw the user's literal text --
both the grounding agent and its own skeptic verifier disclosed this
independently in their self-reports. That version applied one generic
4-outcome ``oneof`` (closed / build-broken / blocked / unsupported) uniformly
to every non-deterministic step. Checked against the real text in
``sa2a-v26.9.17-SOURCE.md``, that is wrong for all but two of the domain's
non-deterministic actions:

* ``verify-boundary`` (SOURCE.md ``:action verify-boundary``) is the only
  action with a literally-defined 4-way ``oneof`` (qualified / build-broken /
  blocked / unsupported) *and* an explicit recovery task
  (``resolve-boundary-result``: repair-on-build-broken, reroute-on-blocked,
  no recovery method for unsupported).
* ``admit-candidate`` (``:action admit-candidate``) also has a real 4-way
  ``oneof`` (admitted / candidate-refused / candidate-blocked /
  candidate-unsupported), but the source text defines **no** recovery task
  for any of its three non-admitted outcomes -- unlike ``verify-boundary``,
  none of them repairs or reroutes.
* Every other named non-deterministic action in the domain --
  ``observe-classification``, ``bound-allocation``, ``manufacture``,
  ``admit-authority``, ``execute-command``, ``close-receipt``,
  ``independent-verify``, ``observe-process``, ``admit-machine-experience``,
  ``prove-semantic-equivalence``, and their episode-2 counterparts -- has its
  **own** literally 2-outcome ``oneof`` in the source text, with its own
  named success/failure predicates. None of them is the generic 4-way shape,
  and the source text defines no recovery task for any of their negative
  outcomes.

Correcting this is not a stylistic fix. The uniform-4-way grounding is what
produced a same-session adversarial finding (``zeroUnreceiptedActuation``,
``claim_holds=False``) that a state reachable via ``close-receipt``'s generic
"unsupported" branch has ``actuated=true`` and zero outgoing transitions.
Checked against the real text, ``close-receipt`` (SOURCE.md lines ~512-529)
has no "unsupported" outcome at all -- it has exactly two: a durable receipt,
or ``receipt-reconcile-blocked``, whose own comment in the source text reads
"consequence known, receipt still unresolved: NEVER replay automatically."
Grounded faithfully, the *same* real, adversarially-relevant state still
exists (an actuated command whose receipt-closing step lands in a terminal,
no-further-transitions state) -- but now it is exactly what the user's own
domain specifies, not an artifact of an over-generalized helper. That is a
stronger, not weaker, finding: see
``tests/planning/test_sa2a_v26_9_17_policy.py`` for the real,
unmodified re-check.

Disclosed gap in the source text itself (not silently smoothed over, per
``.claude/rules/absence-is-not-evidence.md``): the replay-episode task list
(``k6``-``k10`` in ``run-known-replay-episode``) names
``dispatch-replay-command``, ``execute-replay-command``,
``close-replay-receipt``, ``verify-replay``, and ``observe-replay-process``,
but the source text defines no separate ``:action`` block for any of them --
unlike every Episode-1 action, which is explicitly defined. This module
grounds each by disclosed structural analogy to its Episode-1 counterpart
(``dispatch-command``, ``execute-command``, ``close-receipt``,
``independent-verify``, ``observe-process`` respectively) because each
replay-episode task reuses the *same* real predicates
(``authority-admitted``, ``actuated``, ``receipt-pending``,
``receipt-durable``/``receipt-reconcile-blocked``, ``verified``,
``process-conformant``) parameterized over ``command-episode-2`` /
``receipt-episode-2`` instead of the episode-1 objects -- but this is an
inferred analogy, not a literal transcription, and is named as such here so
it is never mistaken for one.

Also disclosed: ``classify-problem`` (SOURCE.md lines ~344-347) is declared
as an ``:action`` whose own precondition is ``(classified ?e)`` and whose
effect is empty -- it can only fire *after* ``classified`` is already true,
which only ``observe-classification`` can establish. It is therefore a
no-op pass-through once reached and is not modeled as a separate state
transition here; ``observe-classification`` is treated as the real episode-1
classification primitive.

Grounding-scope disclosure (exhaustive vs representative):

* **Representative, not exhaustive** -- ``close-critical-repo-boundaries``.
  The source text's ``:objects`` names 10 distinct repos
  (``SA2A_MODEL_REPOS`` below) against 9 critical repo/capability pairs
  (``r1``-``r9`` in ``m-close-critical-repo-boundaries``; ``unrdf`` and
  ``wasm4pm`` are named objects with owned capabilities that are never
  marked ``critical`` in the source ``:init``, so the HTN's own boundary
  closure never visits them either -- a real property of the source text,
  not an omission here). Exactly 2 of the 9 critical pairs are grounded:
  ``(ash-a2a, cap-orchestration)`` as a clean single-outcome pass (the
  "succeeds cleanly" representative case) and ``(ggen, cap-manufacture)``
  with the real, full 4-way ``verify-boundary`` ``oneof`` plus its real
  recursive repair/reroute/typed-stop loop (the "requires the
  build-broken-repair cycle" representative case).
* **Exhaustive** -- every other named non-deterministic action reachable in
  ``run-discovery-episode`` (episode-1) and ``run-known-replay-episode``
  (episode-2) is grounded, each with its own literal oneof arity and named
  outcomes (see the per-action groundings below), not a shared template.

Two goal-state framings are checked (both real, neither a special-cased
``if`` inserted to force a particular verdict):

* ``STRICT_GOAL_STATES`` -- only ``"release-certified"`` counts as done.
* ``EXTENDED_GOAL_STATES`` -- ``STRICT_GOAL_STATES`` unioned with every
  ``typed-stopped`` terminal state, treating an honest, disclosed typed-stop
  as an accepted terminal outcome (consistent with
  ``.claude/rules/absence-is-not-evidence.md``: "an honest
  NO_TYPED_VALID_PLAN is strictly better than a confident wrong plan").

Which framing is "correct" is not decided by this module -- see the paired
test module for the real, unmodified ``check_candidate_policy()`` result
under each.
"""

from __future__ import annotations

from .fond_hddl import HDDLProgressWitness
from .fond_policy import ActionId, CandidatePolicy, FONDProblem, StateId

# Candidate-model repo roster, from SOURCE.md's (:objects ... - repo) block.
# Objects inside the planning model only -- see the SCOPE BOUNDARY above.
SA2A_MODEL_REPOS: tuple[str, ...] = (
    "ash-a2a",
    "ash-r2rml",
    "bcinr",
    "ggen",
    "ggen-igniter",
    "xaas",
    "affidavit",
    "beam4pm",
    "unrdf",
    "wasm4pm",
)

# The 9 critical repo/capability pairs from m-close-critical-repo-boundaries
# (r1..r9). unrdf/wasm4pm own capabilities (cap-runtime,
# cap-portable-runtime) that SOURCE.md's own (:init) never marks critical,
# so the HTN's own closure never reaches them -- correctly absent here.
CRITICAL_REPO_CAPABILITY_PAIRS: tuple[tuple[str, str], ...] = (
    ("ash-a2a", "cap-orchestration"),
    ("ash-r2rml", "cap-semantic-feedback"),
    ("bcinr", "cap-bounded-select"),
    ("ggen", "cap-manufacture"),
    ("ggen-igniter", "cap-framework-projection"),
    ("xaas", "cap-system-authority"),
    ("affidavit", "cap-standing"),
    ("beam4pm", "cap-process-court"),
    ("autofde-lab", "cap-crown"),
)

GROUNDED_REPO_CAPABILITY_PAIRS: tuple[tuple[str, str], ...] = (
    ("ash-a2a", "cap-orchestration"),
    ("ggen", "cap-manufacture"),
)

# Named non-deterministic actions grounded exhaustively for episode 1
# (run-discovery-episode) with their own literal oneof arity -- not a
# shared template. Order matches the real e1..e16 sequence in SOURCE.md.
DISCOVERY_EPISODE_TWO_OUTCOME_STEPS: tuple[str, ...] = (
    "bound-allocation",
    "manufacture",
    "admit-authority",
    "execute-command",
    "close-receipt",
    "independent-verify",
    "observe-process",
    "admit-machine-experience",
)

# Episode 2 (run-known-replay-episode); k6-k10 are disclosed structural
# analogies to their episode-1 counterparts (see module docstring) since
# SOURCE.md defines no separate :action block for them.
REPLAY_EPISODE_TWO_OUTCOME_STEPS: tuple[str, ...] = (
    "prove-semantic-equivalence",
    "admit-authority-replay",
    "execute-replay-command",
    "close-replay-receipt",
    "verify-replay",
    "observe-replay-process",
)


def _ground_boundary_verification_step(
    step_name: str,
    *,
    pending: StateId,
    on_success: StateId,
) -> tuple[
    dict[tuple[StateId, ActionId], frozenset[StateId]],
    dict[StateId, ActionId],
    frozenset[StateId],
]:
    """Ground ``verify-boundary``'s real 4-way oneof plus its real recursive
    repair-on-build-broken / reroute-on-blocked / typed-stop-on-unsupported
    resolution loop (SOURCE.md ``:action verify-boundary`` +
    ``:task resolve-boundary-result``'s three methods). The ONLY action in
    this domain with a defined recovery path for two of its three negative
    outcomes -- do not reuse this helper for any other action.
    """

    closed = f"{step_name}/closed"
    build_broken = f"{step_name}/build-broken"
    repair_reattempt = f"{step_name}/repair-reattempt"
    blocked = f"{step_name}/blocked"
    reroute_reattempt = f"{step_name}/reroute-reattempt"
    unsupported = f"{step_name}/unsupported"
    typed_stopped = f"{step_name}/typed-stopped"

    attempt_action = f"attempt-{step_name}"
    oneof_outcomes = frozenset({closed, build_broken, blocked, unsupported})

    transitions: dict[tuple[StateId, ActionId], frozenset[StateId]] = {}
    policy: dict[StateId, ActionId] = {}

    transitions[(pending, attempt_action)] = oneof_outcomes
    policy[pending] = attempt_action

    advance_action = f"close-{step_name}-and-advance"
    transitions[(closed, advance_action)] = frozenset({on_success})
    policy[closed] = advance_action

    repair_action = f"diagnose-and-repair-{step_name}"
    transitions[(build_broken, repair_action)] = frozenset({repair_reattempt})
    policy[build_broken] = repair_action
    transitions[(repair_reattempt, attempt_action)] = oneof_outcomes
    policy[repair_reattempt] = attempt_action

    reroute_action = f"reroute-{step_name}"
    transitions[(blocked, reroute_action)] = frozenset({reroute_reattempt})
    policy[blocked] = reroute_action
    transitions[(reroute_reattempt, attempt_action)] = oneof_outcomes
    policy[reroute_reattempt] = attempt_action

    typed_stop_action = f"typed-stop-{step_name}"
    transitions[(unsupported, typed_stop_action)] = frozenset({typed_stopped})
    policy[unsupported] = typed_stop_action

    return transitions, policy, frozenset({typed_stopped})


def _ground_two_outcome_step(
    step_name: str,
    *,
    action_name: str,
    pending: StateId,
    success_state: StateId,
    failure_state: StateId,
) -> tuple[
    dict[tuple[StateId, ActionId], frozenset[StateId]],
    dict[StateId, ActionId],
    frozenset[StateId],
]:
    """Ground one of this domain's real 2-outcome ``oneof`` actions.

    SOURCE.md defines no recovery task for any of these actions' negative
    outcomes, so the failure branch is a genuine terminal typed-stop -- no
    repair/reroute loop is invented. ``success_state``/``failure_state``
    carry the real predicate-derived names (e.g. ``receipt-durable`` /
    ``receipt-reconcile-blocked``), not a generic ``closed``/``unsupported``
    pair, so the grounding stays traceable to the literal source text.
    """

    failure_typed_stopped = f"{failure_state}/typed-stopped"
    typed_stop_action = f"typed-stop-{step_name}"

    transitions: dict[tuple[StateId, ActionId], frozenset[StateId]] = {
        (pending, action_name): frozenset({success_state, failure_state}),
        (failure_state, typed_stop_action): frozenset({failure_typed_stopped}),
    }
    policy: dict[StateId, ActionId] = {
        pending: action_name,
        failure_state: typed_stop_action,
    }
    return transitions, policy, frozenset({failure_typed_stopped})


def _ground_admit_candidate_step(
    *, pending: StateId, on_success: StateId
) -> tuple[
    dict[tuple[StateId, ActionId], frozenset[StateId]],
    dict[StateId, ActionId],
    frozenset[StateId],
]:
    """Ground ``admit-candidate``'s real 4-way oneof (SOURCE.md ``:action
    admit-candidate``): admitted / candidate-refused / candidate-blocked /
    candidate-unsupported. Unlike ``verify-boundary``, the source text
    defines no recovery task for ANY of the three negative outcomes -- all
    three are genuine terminal typed-stops, not a repair/reroute loop.
    """

    admitted = "candidate/admitted"
    refused = "candidate/refused"
    blocked = "candidate/blocked"
    unsupported = "candidate/unsupported"

    transitions: dict[tuple[StateId, ActionId], frozenset[StateId]] = {
        (pending, "admit-candidate"): frozenset(
            {admitted, refused, blocked, unsupported}
        ),
        (admitted, "proceed-after-candidate-admitted"): frozenset({on_success}),
    }
    policy: dict[StateId, ActionId] = {
        pending: "admit-candidate",
        admitted: "proceed-after-candidate-admitted",
    }

    typed_stopped: set[StateId] = set()
    for outcome, action in (
        (refused, "typed-stop-candidate-refused"),
        (blocked, "typed-stop-candidate-blocked"),
        (unsupported, "typed-stop-candidate-unsupported"),
    ):
        stop_state = f"{outcome}/typed-stopped"
        transitions[(outcome, action)] = frozenset({stop_state})
        policy[outcome] = action
        typed_stopped.add(stop_state)

    return transitions, policy, frozenset(typed_stopped)


# (success_state, failure_state) per two-outcome step, named after the real
# predicates SOURCE.md gives each action's oneof -- not a generic pair.
_TWO_OUTCOME_STATE_NAMES: dict[str, tuple[str, str]] = {
    "bound-allocation": ("episode1/allocation-bounded", "episode1/allocation-blocked"),
    "manufacture": ("episode1/manufactured", "episode1/manufacture-failed"),
    "admit-authority": ("episode1/authority-admitted", "episode1/authority-refused"),
    "execute-command": (
        "episode1/actuated-receipt-pending",
        "episode1/actuation-failed",
    ),
    "close-receipt": ("episode1/receipt-durable", "episode1/receipt-reconcile-blocked"),
    "independent-verify": ("episode1/verified", "episode1/verification-failed"),
    "observe-process": (
        "episode1/process-conformant",
        "episode1/process-nonconformant",
    ),
    "admit-machine-experience": (
        "episode1/experience-admitted",
        "episode1/experience-admission-refused",
    ),
    "prove-semantic-equivalence": (
        "episode2/equivalent",
        "episode2/equivalence-failed",
    ),
    "admit-authority-replay": (
        "episode2/authority-admitted",
        "episode2/authority-refused",
    ),
    "execute-replay-command": (
        "episode2/actuated-receipt-pending",
        "episode2/actuation-failed",
    ),
    "close-replay-receipt": (
        "episode2/receipt-durable",
        "episode2/receipt-reconcile-blocked",
    ),
    "verify-replay": ("episode2/verified", "episode2/verification-failed"),
    "observe-replay-process": (
        "episode2/process-conformant",
        "episode2/process-nonconformant",
    ),
}


def build_sa2a_v26_9_17_transitions_and_policy() -> tuple[
    dict[tuple[StateId, ActionId], frozenset[StateId]],
    dict[StateId, ActionId],
    frozenset[StateId],
]:
    """Ground the full 5-phase sa2a-v26.9.17 pipeline as real FOND data,
    action-by-action faithful to ``tests/domains/htn_fixtures/sa2a-v26.9.17-SOURCE.md``.

    Returns ``(transitions, policy_actions, typed_stopped_states)`` spanning:
    orient-release -> close-critical-repo-boundaries (2 representative
    pairs) -> run-discovery-episode (exhaustive) ->
    run-known-replay-episode (exhaustive) -> certify-release.
    """

    transitions: dict[tuple[StateId, ActionId], frozenset[StateId]] = {}
    policy: dict[StateId, ActionId] = {}
    typed_stopped_states: set[StateId] = set()

    def _merge(
        step_transitions: dict[tuple[StateId, ActionId], frozenset[StateId]],
        step_policy: dict[StateId, ActionId],
        step_typed_stops: frozenset[StateId],
    ) -> None:
        transitions.update(step_transitions)
        policy.update(step_policy)
        typed_stopped_states.update(step_typed_stops)

    # --- phase 1: orient-release (deterministic, single outcome). ---
    start = "top/start"
    pair_a_pending = "boundary/ash-a2a:cap-orchestration/pending"
    transitions[(start, "pin-exact-heads")] = frozenset({pair_a_pending})
    policy[start] = "pin-exact-heads"

    # --- phase 2, pair A (ash-a2a, cap-orchestration) -- representative
    # "succeeds cleanly" pair, single-outcome simplification (module docstring). ---
    pair_a_closed = "boundary/ash-a2a:cap-orchestration/closed"
    pair_b_pending = "boundary/ggen:cap-manufacture/pending"
    transitions[(pair_a_pending, "verify-boundary-ash-a2a")] = frozenset(
        {pair_a_closed}
    )
    policy[pair_a_pending] = "verify-boundary-ash-a2a"
    transitions[(pair_a_closed, "close-boundary-ash-a2a-and-advance")] = frozenset(
        {pair_b_pending}
    )
    policy[pair_a_closed] = "close-boundary-ash-a2a-and-advance"

    # --- phase 2, pair B (ggen, cap-manufacture) -- representative
    # "build-broken-repair cycle" pair, real full 4-way oneof + recovery loop. ---
    all_boundaries_closed = "phase2/all-critical-boundaries-closed"
    _merge(
        *_ground_boundary_verification_step(
            "verify-boundary-ggen",
            pending=pair_b_pending,
            on_success=all_boundaries_closed,
        )
    )

    # --- phase 2 -> phase 3 bridge (begin-run-discovery-episode). ---
    e1_pending = "episode1/pending"
    transitions[(all_boundaries_closed, "begin-run-discovery-episode")] = frozenset(
        {e1_pending}
    )
    policy[all_boundaries_closed] = "begin-run-discovery-episode"

    # --- e1: reconstruct-world (deterministic). ---
    world_reconstructed = "episode1/world-reconstructed"
    transitions[(e1_pending, "reconstruct-world-episode1")] = frozenset(
        {world_reconstructed}
    )
    policy[e1_pending] = "reconstruct-world-episode1"

    # --- e2/e3: observe-classification (real 2-outcome oneof: known vs
    # unknown -- both outcomes proceed, neither is a failure). ---
    known = "episode1/known"
    unknown = "episode1/unknown"
    problem_solved = "episode1/problem-solved"
    transitions[(world_reconstructed, "observe-classification")] = frozenset(
        {known, unknown}
    )
    policy[world_reconstructed] = "observe-classification"

    transitions[(known, "proceed-known-problem")] = frozenset({problem_solved})
    policy[known] = "proceed-known-problem"

    # unknown -> explore-unknown (deterministic) -> admit-candidate (real
    # 4-way oneof, no recovery task -- see _ground_admit_candidate_step).
    candidate_produced = "episode1/candidate-produced"
    transitions[(unknown, "explore-unknown")] = frozenset({candidate_produced})
    policy[unknown] = "explore-unknown"
    _merge(
        *_ground_admit_candidate_step(
            pending=candidate_produced, on_success=problem_solved
        )
    )

    # --- e4: construct-plan (deterministic). ---
    plan_built = "episode1/plan-built"
    transitions[(problem_solved, "construct-plan")] = frozenset({plan_built})
    policy[problem_solved] = "construct-plan"

    # --- e5..e10, e11..e15: the 8 real 2-outcome oneof steps, each with its
    # own named success/failure predicates, chained in the real e5..e15
    # order, terminating at issue-affidavit (deterministic, e16). ---
    two_outcome_chain = list(DISCOVERY_EPISODE_TWO_OUTCOME_STEPS)
    current_pending = plan_built
    for step_name in two_outcome_chain:
        success_state, failure_state = _TWO_OUTCOME_STATE_NAMES[step_name]
        step_transitions, step_policy, step_typed_stops = _ground_two_outcome_step(
            step_name,
            action_name=step_name,
            pending=current_pending,
            success_state=success_state,
            failure_state=failure_state,
        )
        _merge(step_transitions, step_policy, step_typed_stops)
        current_pending = success_state

        # e8: dispatch-command is deterministic and sits between
        # admit-authority's success and execute-command's pending state.
        if step_name == "admit-authority":
            command_issued = "episode1/command-issued"
            transitions[(current_pending, "dispatch-command")] = frozenset(
                {command_issued}
            )
            policy[current_pending] = "dispatch-command"
            current_pending = command_issued

    # e13/e14: record-feedback, create-machine-experience (deterministic),
    # chained after observe-process's real success state.
    feedback_recorded = "episode1/feedback-recorded"
    experience_created = "episode1/experience-created"
    transitions[(current_pending, "record-feedback")] = frozenset({feedback_recorded})
    policy[current_pending] = "record-feedback"
    transitions[(feedback_recorded, "create-machine-experience")] = frozenset(
        {experience_created}
    )
    policy[feedback_recorded] = "create-machine-experience"
    current_pending = experience_created

    # e15: admit-machine-experience (real 2-outcome oneof).
    success_state, failure_state = _TWO_OUTCOME_STATE_NAMES["admit-machine-experience"]
    _merge(
        *_ground_two_outcome_step(
            "admit-machine-experience",
            action_name="admit-machine-experience",
            pending=current_pending,
            success_state=success_state,
            failure_state=failure_state,
        )
    )

    # e16: issue-affidavit (deterministic) -- discovery episode complete.
    discovery_complete = "phase3/discovery-episode-complete"
    transitions[(success_state, "issue-affidavit-episode1")] = frozenset(
        {discovery_complete}
    )
    policy[success_state] = "issue-affidavit-episode1"

    # --- phase 3 -> phase 4 bridge. ---
    e2_pending = "episode2/pending"
    transitions[(discovery_complete, "end-discovery-begin-replay-episode")] = frozenset(
        {e2_pending}
    )
    policy[discovery_complete] = "end-discovery-begin-replay-episode"

    # --- k1: reconstruct-world, reused for episode 2 (deterministic). ---
    e2_world_reconstructed = "episode2/world-reconstructed"
    transitions[(e2_pending, "reconstruct-world-episode2")] = frozenset(
        {e2_world_reconstructed}
    )
    policy[e2_pending] = "reconstruct-world-episode2"

    # --- k2..k10: the 6 real replay-episode 2-outcome oneof steps, with
    # k3 (route-known-replay) and k4 (replay-known-transition) as
    # deterministic single-effect actions interleaved between them, matching
    # SOURCE.md's real precondition chain exactly. ---
    replay_chain = list(REPLAY_EPISODE_TWO_OUTCOME_STEPS)
    current_pending = e2_world_reconstructed
    for step_name in replay_chain:
        success_state, failure_state = _TWO_OUTCOME_STATE_NAMES[step_name]
        step_transitions, step_policy, step_typed_stops = _ground_two_outcome_step(
            step_name,
            action_name=step_name,
            pending=current_pending,
            success_state=success_state,
            failure_state=failure_state,
        )
        _merge(step_transitions, step_policy, step_typed_stops)
        current_pending = success_state

        if step_name == "prove-semantic-equivalence":
            # k3/k4: route-known-replay, replay-known-transition
            # (deterministic single-effect actions).
            known_e2 = "episode2/known"
            replayed_e2 = "episode2/replayed"
            transitions[(current_pending, "route-known-replay")] = frozenset({known_e2})
            policy[current_pending] = "route-known-replay"
            transitions[(known_e2, "replay-known-transition")] = frozenset(
                {replayed_e2}
            )
            policy[known_e2] = "replay-known-transition"
            current_pending = replayed_e2
        elif step_name == "admit-authority-replay":
            # k6: dispatch-replay-command (deterministic; disclosed
            # structural analogy to dispatch-command -- see module docstring).
            command_issued_e2 = "episode2/command-issued"
            transitions[(current_pending, "dispatch-replay-command")] = frozenset(
                {command_issued_e2}
            )
            policy[current_pending] = "dispatch-replay-command"
            current_pending = command_issued_e2

    # k11: issue-affidavit, reused for episode 2 -- replay episode complete.
    replay_complete = "phase4/replay-episode-complete"
    transitions[(current_pending, "issue-affidavit-episode2")] = frozenset(
        {replay_complete}
    )
    policy[current_pending] = "issue-affidavit-episode2"

    # --- phase 5: certify-release (deterministic, single outcome, the goal). ---
    transitions[(replay_complete, "certify-release")] = frozenset({"release-certified"})
    policy[replay_complete] = "certify-release"

    return transitions, policy, frozenset(typed_stopped_states)


_TRANSITIONS, _POLICY_ACTIONS, TYPED_STOPPED_STATES = (
    build_sa2a_v26_9_17_transitions_and_policy()
)

STRICT_GOAL_STATES: frozenset[StateId] = frozenset({"release-certified"})
EXTENDED_GOAL_STATES: frozenset[StateId] = STRICT_GOAL_STATES | TYPED_STOPPED_STATES


def build_sa2a_v26_9_17_problem(*, goal_states: frozenset[StateId]) -> FONDProblem:
    """Build the real ``FONDProblem`` for the given goal-state framing."""

    return FONDProblem(
        initial_state="top/start",
        goal_states=goal_states,
        transitions=dict(_TRANSITIONS),
    )


def build_sa2a_v26_9_17_policy() -> CandidatePolicy:
    """Build the real ``CandidatePolicy`` matching the corrected, per-action
    faithful grounding: repair-on-build-broken/reroute-on-blocked/
    typed-stop-on-unsupported ONLY for verify-boundary; typed-stop-only (no
    recovery) for every other negative outcome, per SOURCE.md."""

    return CandidatePolicy(actions=dict(_POLICY_ACTIONS))


def build_sa2a_v26_9_17_hierarchy_witnesses() -> dict[
    StateId, frozenset[HDDLProgressWitness]
]:
    """Ground one HDDL task-network progress witness per reachable non-goal
    state, permitting exactly the primitive action this policy selects
    there. Real data, derived from the same real grounding above -- not a
    synchronized FOND-times-HDDL product proof (see fond_hddl.py's module
    docstring for that explicit non-claim), just a real, checked frontier
    witness for every state this policy actually visits.
    """

    return {
        state: frozenset(
            {HDDLProgressWitness(f"{state}/progress", frozenset({action}))}
        )
        for state, action in _POLICY_ACTIONS.items()
    }
