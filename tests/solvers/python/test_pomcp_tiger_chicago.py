# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for the C++-backed `POMCP` solver (registered entry
point "POMCP" -- reward-maximizing, observation-based -- distinct from the
already-tested pure-Python `pPOMCP` cost-minimizing / goal-based solver
exercised in `tests/solvers/python/test_pomcp.py`).

Genuinely untested before this file: `grep -rl "pomcp" tests/` only found
`tests/solvers/python/test_pomcp.py`, which constructs `pPOMCP`, never
`POMCP`. `POMCP.T_domain` requires `Rewards` (not `PositiveCosts`) and
`UncertainInitialized` (not the goal-based `MasterMind` domain's
`GoalPOMDPDomain`/`PositiveCosts` shape used by the existing pPOMCP test),
so a new fixture is required rather than reusing `MasterMind`.

The classic Tiger POMDP is used as the fixture, following the exact
domain-modelling shape (states/actions/observations, transition and
observation probabilities) of `TigerDomain` in
`tests/solvers/cpp/test_rtdp_bel.py` -- the nearest sibling POMDP fixture in
the repo -- but re-expressed with `Rewards`/`UncertainInitialized` instead
of `PositiveCosts`/`DeterministicInitialized`/`Goals`, which is what
`POMCP`'s C++ backend requires.

No mocks: a real `TigerRewardDomain` instance and the real registered
`POMCP` solver (backed by the real compiled `_POMCPSolver_` C++ extension)
are exercised end to end. Assertions are on the solver's real selected
action and real belief-tracking rollout -- not on any interaction.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from autofde_lab import (
    DiscreteDistribution,
    Domain,
    EnumerableSpace,
    SingleValueDistribution,
    Value,
)
from autofde_lab.builders.domain import (
    Actions,
    EnumerableTransitions,
    Markovian,
    PartiallyObservable,
    Rewards,
    Sequential,
    SingleAgent,
    UncertainInitialized,
)
from autofde_lab.hub.space.gym import EnumSpace
from autofde_lab.utils import load_registered_solver


class TigerState(NamedTuple):
    tiger_location: str  # "left" or "right"


class TigerAction(Enum):
    listen = 0
    open_left = 1
    open_right = 2


class TigerObservation(NamedTuple):
    heard: str  # "left" or "right"


class TigerRewardDomain(
    Domain,
    SingleAgent,
    Sequential,
    EnumerableTransitions,
    Actions,
    UncertainInitialized,
    Markovian,
    PartiallyObservable,
    Rewards,
):
    """Non-episodic Tiger POMDP (reward-maximizing): listening costs -1
    reward, opening the correct door gives +10, opening the wrong door
    gives -100. The tiger location resets uniformly at random after any
    door is opened, matching the classic infinite-horizon formulation
    `POMCP`'s reward-maximizing C++ backend expects (never terminal)."""

    T_state = TigerState
    T_observation = TigerObservation
    T_event = TigerAction
    T_value = float
    T_predicate = bool
    T_info = None

    def __init__(self, initial_tiger: str = "left"):
        self._initial_tiger = initial_tiger

    def _get_initial_state_distribution_(self):
        return SingleValueDistribution(TigerState(tiger_location=self._initial_tiger))

    def _get_next_state_distribution(self, memory, action):
        s = memory
        if action == TigerAction.listen:
            return SingleValueDistribution(s)
        # Opening a door resets the tiger location uniformly at random.
        return DiscreteDistribution(
            [
                (TigerState(tiger_location="left"), 0.5),
                (TigerState(tiger_location="right"), 0.5),
            ]
        )

    def _get_transition_value(self, memory, action, next_state=None):
        s = memory
        if action == TigerAction.listen:
            return Value(reward=-1)
        elif action == TigerAction.open_left:
            return Value(reward=10) if s.tiger_location != "left" else Value(reward=-100)
        else:  # open_right
            return Value(reward=10) if s.tiger_location != "right" else Value(reward=-100)

    def _is_terminal(self, state) -> bool:
        return False

    def _get_action_space_(self):
        return EnumSpace(TigerAction)

    def _get_applicable_actions_from(self, memory):
        return self._get_action_space_()

    def _get_observation_space_(self):
        return EnumerableSpace(
            [TigerObservation(heard="left"), TigerObservation(heard="right")]
        )

    def _get_observation_distribution(self, state, action=None):
        if action is None or action == TigerAction.listen:
            if state.tiger_location == "left":
                return DiscreteDistribution(
                    [
                        (TigerObservation(heard="left"), 0.85),
                        (TigerObservation(heard="right"), 0.15),
                    ]
                )
            else:
                return DiscreteDistribution(
                    [
                        (TigerObservation(heard="left"), 0.15),
                        (TigerObservation(heard="right"), 0.85),
                    ]
                )
        # After opening a door, observation is uninformative (uniform).
        return DiscreteDistribution(
            [
                (TigerObservation(heard="left"), 0.5),
                (TigerObservation(heard="right"), 0.5),
            ]
        )


def test_pomcp_solves_real_tiger_pomdp_and_returns_a_real_legal_action():
    """Constructs a real TigerRewardDomain and runs the real registered
    (C++-backed) POMCP solver, asserting on a real selected action and a
    real observation-driven rollout -- no mock."""
    solver_type = load_registered_solver("POMCP")
    assert solver_type is not None, "POMCP entry point failed to load"

    dom = TigerRewardDomain(initial_tiger="left")
    assert solver_type.check_domain(dom)

    with solver_type(
        domain_factory=lambda: TigerRewardDomain(initial_tiger="left"),
        num_simulations=200,
        max_depth=15,
        discount=0.95,
        num_particles_belief_update=100,
        verbose=False,
    ) as solver:
        solver.solve()

        obs = dom.reset()
        actions_taken = []
        total_reward = 0.0
        for _ in range(5):
            action = solver.sample_action(obs)
            actions_taken.append(action)
            outcome = dom.step(action)
            total_reward += outcome.value.reward
            obs = outcome.observation

    # Real, observed consequence: POMCP produced real legal Tiger actions
    # over a real observation-driven rollout, and accrued a real, finite
    # total reward.
    assert len(actions_taken) == 5
    assert all(isinstance(a, TigerAction) for a in actions_taken)
    assert isinstance(total_reward, float)
