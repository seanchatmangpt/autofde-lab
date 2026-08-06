# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-school tests for real DSPyPolicy against real single- and
multi-agent domains.

`DSPyPolicy._get_next_action` / `_check_domain_additional` must handle both
shapes `D.T_agent[X]` can take at runtime:

- MultiAgent domains (e.g. `RockPaperScissors`): `get_action_space()` and a
  policy observation are real per-agent dicts (`{"player1": ..., ...}`).
- SingleAgent domains (e.g. `Maze`, `SimpleGridWorld`, `MasterMind`):
  `D.T_agent[X]` collapses to plain `X` at the domain's own boundary, but
  `Solver.__init__`'s `autocast_all(domain, domain, self.T_domain)` still
  presents them through the solver as a single-key dict (`{"agent": ...}`)
  since `DSPyPolicy.T_domain` declares `MultiAgent`. Both shapes were
  verified directly against real instances of each domain before writing
  these tests (not assumed from reading the mixin hierarchy).

Every test here drives a real, registered domain through a real `DSPyPolicy`
solver backed by a real running TurboFieldfareServer -- the same real
external server (and its shared fixtures/skip marker) used by
`tests/test_self_play_dspy_turbofieldfare_chicago.py`, factored into
`tests/conftest.py` to avoid duplicating the real server-process lifecycle
code. No mocks anywhere in this file: every assertion below was run against
the real server before being written, per this repo's Chicago-school
convention.
"""

from __future__ import annotations

from typing import Callable

import pytest

from conftest import requires_real_turbo_fieldfare_binary_and_model


@requires_real_turbo_fieldfare_binary_and_model
def test_real_dspy_policy_solves_real_single_agent_maze_and_returns_a_real_legal_action(
    real_dspy_lm,
):
    """Real domain: Maze (SingleAgent, DeterministicPlanningDomain).
    Real solver: DSPyPolicy.
    Real check: `solver.sample_action` returns a real member of the real
    domain's real action space, with no crash from the SingleAgent ->
    MultiAgent-declared-T_domain shape mismatch this test exists to cover.
    """
    from skdecide.hub.domain.maze import Maze
    from skdecide.hub.solver.dspy_policy import DSPyPolicy

    def domain_factory() -> Maze:
        return Maze()

    assert DSPyPolicy.check_domain(Maze())

    with DSPyPolicy(domain_factory=domain_factory, lm=real_dspy_lm) as solver:
        solver.solve()
        observation = solver._domain.reset()
        action = solver.sample_action(observation)

        legal_actions = solver._domain.get_action_space()["agent"].get_elements()
        assert action in legal_actions


@requires_real_turbo_fieldfare_binary_and_model
def test_real_dspy_policy_solves_real_single_agent_simple_grid_world_and_returns_a_real_legal_action(
    real_dspy_lm,
):
    """Real domain: SimpleGridWorld (SingleAgent, DeterministicPlanningDomain).
    Real solver: DSPyPolicy.
    Real check: real legal action returned, same SingleAgent shape as Maze.
    """
    from skdecide.hub.domain.simple_grid_world import SimpleGridWorld
    from skdecide.hub.solver.dspy_policy import DSPyPolicy

    def domain_factory() -> SimpleGridWorld:
        return SimpleGridWorld()

    assert DSPyPolicy.check_domain(SimpleGridWorld())

    with DSPyPolicy(domain_factory=domain_factory, lm=real_dspy_lm) as solver:
        solver.solve()
        observation = solver._domain.reset()
        action = solver.sample_action(observation)

        legal_actions = solver._domain.get_action_space()["agent"].get_elements()
        assert action in legal_actions


@requires_real_turbo_fieldfare_binary_and_model
def test_real_dspy_policy_solves_real_single_agent_mastermind_and_returns_a_real_legal_action(
    real_dspy_lm,
):
    """Real domain: MasterMind (SingleAgent, GoalPOMDPDomain, PartiallyObservable).
    Real solver: DSPyPolicy.
    Real check: real legal guess returned even though the domain is only
    partially observable (observation is a real `Score`, not a state).
    """
    from skdecide.hub.domain.mastermind import MasterMind
    from skdecide.hub.solver.dspy_policy import DSPyPolicy

    def domain_factory() -> MasterMind:
        return MasterMind()

    assert DSPyPolicy.check_domain(MasterMind())

    with DSPyPolicy(domain_factory=domain_factory, lm=real_dspy_lm) as solver:
        solver.solve()
        observation = solver._domain.reset()
        action = solver.sample_action(observation)

        legal_actions = solver._domain.get_action_space()["agent"].get_elements()
        assert action in legal_actions


@requires_real_turbo_fieldfare_binary_and_model
def test_real_dspy_policy_solves_real_multi_agent_rock_paper_scissors_and_returns_one_real_action_per_agent(
    real_dspy_lm,
):
    """Real domain: RockPaperScissors (MultiAgent, Environment, no Goals).
    Real solver: DSPyPolicy.
    Real check: `solver.sample_action` returns a real per-agent dict, one
    real legal `Move` per real agent name, using the real multi-agent branch
    of `_get_next_action` (the shape this solver originally supported).
    """
    from skdecide.hub.domain.rock_paper_scissors import RockPaperScissors
    from skdecide.hub.solver.dspy_policy import DSPyPolicy

    max_moves = 2

    def domain_factory() -> RockPaperScissors:
        return RockPaperScissors(max_moves=max_moves)

    assert DSPyPolicy.check_domain(RockPaperScissors(max_moves=max_moves))

    with DSPyPolicy(domain_factory=domain_factory, lm=real_dspy_lm) as solver:
        solver.solve()
        observation = solver._domain.reset()
        action = solver.sample_action(observation)

        legal_action_spaces = solver._domain.get_action_space()
        assert set(action) == {"player1", "player2"}
        for agent, move in action.items():
            assert move in legal_action_spaces[agent].get_elements()


@requires_real_turbo_fieldfare_binary_and_model
def test_real_rollout_utility_with_real_dspy_policy_on_real_single_agent_maze_runs_without_crashing(
    real_dspy_lm,
):
    """Real domain: Maze.
    Real solver: DSPyPolicy.
    Real rollout: `skdecide.utils.rollout` (the generic single-agent-capable
    rollout, unlike `skdecide.self_play.self_play_rollout` which is
    RockPaperScissors-specific), 2 real episodes, small `max_steps`.
    Real check: rollout completes without crashing and returns one real
    episode entry per requested episode, each with at least one real,
    legal action recorded.
    """
    from skdecide.hub.domain.maze import Maze
    from skdecide.hub.solver.dspy_policy import DSPyPolicy
    from skdecide.utils import rollout

    max_steps = 3

    def domain_factory() -> Maze:
        return Maze()

    with DSPyPolicy(domain_factory=domain_factory, lm=real_dspy_lm) as solver:
        solver.solve()
        rollout_domain = Maze()
        legal_actions = rollout_domain.get_action_space().get_elements()

        episodes = rollout(
            rollout_domain,
            solver=solver,
            num_episodes=2,
            max_steps=max_steps,
            render=False,
            verbose=False,
            return_episodes=True,
        )

    assert episodes is not None
    assert len(episodes) == 2
    for observations, actions, values in episodes:
        assert len(actions) >= 1
        for action in actions:
            assert action in legal_actions
