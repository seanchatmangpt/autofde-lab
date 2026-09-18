"""Chicago-style checks of the hand-grounded sa2a-v26.9.17 candidate policy.

SCOPE BOUNDARY (see src/autofde_lab/planning/sa2a_v26_9_17_policy.py's module
docstring and .claude/rules/ecosystem-boundary.md): every assertion below is
about a CANDIDATE POLICY over an ABSTRACT PLANNING MODEL. Nothing here
observes, verifies, admits, or actuates any real sibling repository.

Real collaborators throughout, per .claude/rules/testing-chicago-style.md:
the real FONDProblem/CandidatePolicy dataclasses from fond_policy.py, the
real check_candidate_policy()/check_fond_hddl_frontier_closure() functions,
and real, hand-built (not mocked) transition/policy data from
sa2a_v26_9_17_policy.py -- itself grounded action-by-action against the
verbatim source text checked into
tests/domains/htn_fixtures/sa2a-v26.9.17-SOURCE.md. No unittest.mock, Mock,
MagicMock, patch, or monkeypatch anywhere in this file -- every assertion is
state-based, against the real PolicyCheck/FONDHDDLFrontierCheck fields these
real functions return, run this session.

Every numeric assertion below (state counts, cycle sizes, etc.) was obtained
by actually running check_candidate_policy() against this real grounding
this session -- not derived algebraically or carried over from the earlier,
paraphrase-based grounding this module supersedes (see the policy module's
docstring for why that earlier grounding was wrong).
"""

from autofde_lab.planning.fond_hddl import check_fond_hddl_frontier_closure
from autofde_lab.planning.fond_policy import PolicySemantics, check_candidate_policy
from autofde_lab.planning.sa2a_v26_9_17_policy import (
    CRITICAL_REPO_CAPABILITY_PAIRS,
    DISCOVERY_EPISODE_TWO_OUTCOME_STEPS,
    EXTENDED_GOAL_STATES,
    GROUNDED_REPO_CAPABILITY_PAIRS,
    REPLAY_EPISODE_TWO_OUTCOME_STEPS,
    SA2A_MODEL_REPOS,
    STRICT_GOAL_STATES,
    TYPED_STOPPED_STATES,
    build_sa2a_v26_9_17_hierarchy_witnesses,
    build_sa2a_v26_9_17_policy,
    build_sa2a_v26_9_17_problem,
)


def test_model_roster_names_all_ten_repos_and_nine_critical_pairs() -> None:
    # SOURCE.md's (:objects ... - repo) block names 10 repos; its
    # m-close-critical-repo-boundaries method names 9 critical pairs (r1..r9)
    # -- unrdf/wasm4pm are named objects whose owned capabilities are never
    # marked critical in (:init), so the real HTN closure never visits them.
    assert len(SA2A_MODEL_REPOS) == 10
    assert SA2A_MODEL_REPOS == (
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
    assert len(CRITICAL_REPO_CAPABILITY_PAIRS) == 9
    assert GROUNDED_REPO_CAPABILITY_PAIRS == (
        ("ash-a2a", "cap-orchestration"),
        ("ggen", "cap-manufacture"),
    )
    assert set(GROUNDED_REPO_CAPABILITY_PAIRS) <= set(CRITICAL_REPO_CAPABILITY_PAIRS)


def test_episode_step_rosters_match_the_real_per_action_oneof_arities() -> None:
    """Every step here has SOURCE.md's own literal 2-outcome oneof -- not the
    generic 4-way shape the superseded grounding applied uniformly."""

    assert DISCOVERY_EPISODE_TWO_OUTCOME_STEPS == (
        "bound-allocation",
        "manufacture",
        "admit-authority",
        "execute-command",
        "close-receipt",
        "independent-verify",
        "observe-process",
        "admit-machine-experience",
    )
    assert REPLAY_EPISODE_TWO_OUTCOME_STEPS == (
        "prove-semantic-equivalence",
        "admit-authority-replay",
        "execute-replay-command",
        "close-replay-receipt",
        "verify-replay",
        "observe-replay-process",
    )
    # 8 real 2-outcome discovery steps + 3-way admit-candidate + 6 real
    # 2-outcome replay steps + verify-boundary-ggen's single "unsupported"
    # outcome == 18 real typed-stopped terminals, each independently named
    # after its own source-text predicate (no generic bucket).
    assert len(TYPED_STOPPED_STATES) == 18


def test_real_policy_reaches_the_full_grounded_state_space() -> None:
    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=EXTENDED_GOAL_STATES)

    check = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG_CYCLIC)

    # Real, exact reachable-state count for this real, corrected grounding --
    # computed by actually running check_candidate_policy() this session.
    assert len(check.reachable_states) == 77
    assert "top/start" in check.reachable_states
    assert "release-certified" in check.reachable_states
    for typed_stopped in TYPED_STOPPED_STATES:
        assert typed_stopped in check.reachable_states


def test_strong_semantics_rejects_the_real_repair_cycle_that_strong_cyclic_accepts() -> None:
    """Isolates the real cycle: same graph, extended (typed-stop-accepting)
    goal set so missing/cannot-reach-goal are both empty either way -- the
    STRONG vs STRONG_CYCLIC difference below is caused by the repair/reroute
    cycle alone. Unlike the superseded grounding (which invented a
    repair/reroute loop on every one of 9 steps and so counted 40 cyclic
    states), the ONLY action in this domain with a defined recovery task is
    verify-boundary -- so this real cycle is much smaller, and provably
    isolated to verify-boundary-ggen's own repair/reroute states."""

    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=EXTENDED_GOAL_STATES)

    strong = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG)
    strong_cyclic = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG_CYCLIC)

    assert not strong.missing_policy_states
    assert not strong.cannot_reach_goal_states
    assert strong.non_goal_cycle_states  # the real cycle is really there
    assert len(strong.non_goal_cycle_states) == 4
    assert not strong.valid  # STRONG rejects it solely because of the cycle

    assert strong_cyclic.non_goal_cycle_states == strong.non_goal_cycle_states
    assert strong_cyclic.valid  # STRONG_CYCLIC accepts the identical cycle

    # Every cyclic state belongs to verify-boundary-ggen's real
    # repair/reroute loop -- confirms the cycle is not spread across
    # unrelated steps.
    assert all(state.startswith("verify-boundary-ggen/") for state in strong.non_goal_cycle_states)
    assert "verify-boundary-ggen/build-broken" in strong.non_goal_cycle_states
    assert "verify-boundary-ggen/repair-reattempt" in strong.non_goal_cycle_states
    assert "verify-boundary-ggen/blocked" in strong.non_goal_cycle_states
    assert "verify-boundary-ggen/reroute-reattempt" in strong.non_goal_cycle_states


def test_strict_goal_honestly_reports_typed_stop_states_as_unreachable_to_goal() -> None:
    """The real, unmodified check_candidate_policy() result under the strict
    goal framing (only "release-certified" counts as done). This pins the
    real, honest, negative result -- not adjusted to force validity."""

    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=STRICT_GOAL_STATES)

    check = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG_CYCLIC)

    assert not check.valid
    assert check.missing_policy_states == TYPED_STOPPED_STATES
    assert TYPED_STOPPED_STATES <= check.cannot_reach_goal_states
    assert len(check.cannot_reach_goal_states) == 36
    assert check.dead_end_states == frozenset()


def test_extended_goal_accepting_typed_stop_as_a_real_terminal_is_strong_cyclic_valid() -> None:
    """Same real graph, same real policy -- only the goal-state framing
    changes (typed-stop terminals are additionally accepted as a done
    state, matching this repo's absence-is-not-evidence.md: an honest,
    disclosed refusal is a result, not a gap). Under that framing the real,
    unmodified check is valid."""

    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=EXTENDED_GOAL_STATES)

    check = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG_CYCLIC)

    assert check.valid
    assert check.missing_policy_states == frozenset()
    assert check.dead_end_states == frozenset()
    assert check.cannot_reach_goal_states == frozenset()
    assert check.claim_ceiling == "candidate_policy_only"


def test_ash_a2a_representative_pair_closes_cleanly_without_repair() -> None:
    """The "succeeds cleanly" representative pair never even visits a
    build-broken/blocked/unsupported state -- confirmed against the real
    reachable-state set, not asserted from the construction code alone."""

    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=EXTENDED_GOAL_STATES)
    check = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG_CYCLIC)

    assert "boundary/ash-a2a:cap-orchestration/pending" in check.reachable_states
    assert "boundary/ash-a2a:cap-orchestration/closed" in check.reachable_states
    for suffix in ("build-broken", "blocked", "unsupported", "typed-stopped", "repair-reattempt", "reroute-reattempt"):
        assert f"boundary/ash-a2a:cap-orchestration/{suffix}" not in check.reachable_states


def test_zero_unreceipted_actuation_still_fails_under_the_real_faithful_grounding() -> None:
    """The adversarial finding from the superseded grounding
    (claim_holds=False: an actuated command's receipt-closing step can
    itself terminally fail) is re-checked here against the real,
    per-action-faithful grounding -- and it still holds, for the RIGHT
    reason this time: SOURCE.md's own close-receipt action (not a generic
    4-way oneof this module invented) has exactly two outcomes, and its own
    comment names the failure outcome "NEVER replay automatically". Real,
    both for episode 1 and episode 2 (which reuses the same real predicates
    by disclosed structural analogy -- see the policy module docstring)."""

    policy = build_sa2a_v26_9_17_policy()

    # STRICT framing on purpose: under EXTENDED framing every typed-stopped
    # state (this one included) IS a goal state, so check_candidate_policy's
    # BFS stops there as satisfied and never even asks whether it has a
    # policy action -- that would silently hide this exact finding. STRICT
    # goal states are the framing that lets missing_policy_states show it.
    problem = build_sa2a_v26_9_17_problem(goal_states=STRICT_GOAL_STATES)
    check = check_candidate_policy(problem, policy, semantics=PolicySemantics.STRONG_CYCLIC)

    # episode 2 reuses close-receipt's real predicates under the task's own
    # "-replay"-prefixed action name (close-replay-receipt) -- see the
    # disclosed structural-analogy note in the policy module docstring.
    close_receipt_action_by_episode = {
        "episode1": "close-receipt",
        "episode2": "close-replay-receipt",
    }

    for episode in ("episode1", "episode2"):
        actuated_pending_state = f"{episode}/actuated-receipt-pending"
        blocked_state = f"{episode}/receipt-reconcile-blocked"
        blocked_typed_stop = f"{blocked_state}/typed-stopped"

        assert actuated_pending_state in check.reachable_states
        assert blocked_state in check.reachable_states
        assert blocked_typed_stop in check.reachable_states

        # The only real inbound transition to the blocked state is from the
        # actuated+receipt-pending state via the real close-receipt action --
        # confirming the blocked state really does represent "actuated but
        # never durably receipted", not an unrelated state that merely
        # shares a name fragment.
        close_receipt_outcomes = problem.outcomes(
            actuated_pending_state, close_receipt_action_by_episode[episode]
        )
        assert blocked_state in close_receipt_outcomes

        # The typed-stopped terminal has zero further transitions and no
        # assigned policy action -- a real, permanent dead end reachable
        # after actuation, exactly matching SOURCE.md's own "NEVER replay
        # automatically" comment on receipt-reconcile-blocked. Also confirm
        # it is reachable but not a dead_end_states entry: reaching it costs
        # a transition (via the typed-stop action on the blocked state
        # itself), so it lands in missing_policy_states, the same real
        # shape as every other typed-stopped terminal in this grounding.
        assert blocked_typed_stop not in policy.actions
        assert blocked_typed_stop in check.missing_policy_states
        assert blocked_typed_stop not in check.dead_end_states


def test_hierarchy_witnesses_cover_every_real_policy_state() -> None:
    policy = build_sa2a_v26_9_17_policy()
    witnesses = build_sa2a_v26_9_17_hierarchy_witnesses()

    assert set(witnesses.keys()) == set(policy.actions.keys())
    for state, action in policy.actions.items():
        state_witnesses = witnesses[state]
        assert len(state_witnesses) == 1
        witness = next(iter(state_witnesses))
        assert witness.task_network_state == f"{state}/progress"
        assert action in witness.permitted_primitive_actions


def test_fond_hddl_frontier_closes_under_the_extended_goal_framing() -> None:
    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=EXTENDED_GOAL_STATES)
    witnesses = build_sa2a_v26_9_17_hierarchy_witnesses()

    check = check_fond_hddl_frontier_closure(
        problem, policy, semantics=PolicySemantics.STRONG_CYCLIC, hierarchy_witnesses=witnesses
    )

    assert check.valid
    assert check.policy_check.valid
    assert check.missing_hierarchy_witness_states == frozenset()
    assert check.malformed_hierarchy_witness_states == frozenset()
    assert check.hierarchy_rejected_action_states == frozenset()
    assert check.claim_ceiling == "candidate_fond_hddl_frontier_only"


def test_fond_hddl_frontier_carries_the_same_real_gap_under_the_strict_goal_framing() -> None:
    """The frontier check cannot promote an invalid FOND policy (per
    fond_hddl.py's own docstring); confirms that against this real
    grounding's real strict-goal gap, not just the synthetic fixtures in
    test_fond_hddl_frontier.py."""

    policy = build_sa2a_v26_9_17_policy()
    problem = build_sa2a_v26_9_17_problem(goal_states=STRICT_GOAL_STATES)
    witnesses = build_sa2a_v26_9_17_hierarchy_witnesses()

    check = check_fond_hddl_frontier_closure(
        problem, policy, semantics=PolicySemantics.STRONG_CYCLIC, hierarchy_witnesses=witnesses
    )

    assert not check.valid
    assert not check.policy_check.valid
    assert check.policy_check.missing_policy_states == TYPED_STOPPED_STATES
