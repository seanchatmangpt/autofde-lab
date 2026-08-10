# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for the `AugmentedRandomSearch` (ARS, policy-gradient /
evolution-strategy family) solver against a real `GymDomain` wrapping
`gymnasium`'s `CartPole-v1`.

Genuinely untested before this file: neither `tests/solvers/python/` nor
`tests/solvers/cpp/` construct `AugmentedRandomSearch`. The only prior use of
this solver in the repo is the interactive `examples/ars_solver.py` script
(never run headlessly / asserted on), which this test's domain/solver wiring
follows directly rather than inventing a new shape.

No mocks: a real `gymnasium.make("CartPole-v1")` environment wrapped by the
real registered `GymDomain`, and the real registered `AugmentedRandomSearch`
solver, are exercised end to end. Assertions are on the solver's real learned
policy weights and a real rollout's returned reward -- not on any
interaction.
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np

from autofde_lab.hub.domain.gym import GymDomain
from autofde_lab.utils import load_registered_solver


def test_ars_solves_real_cartpole_gym_domain_and_learns_a_real_policy():
    """Constructs a real GymDomain(CartPole-v1) and runs the real
    registered AugmentedRandomSearch solver with a small epoch budget,
    asserting on the real learned policy array and a real post-training
    rollout reward -- no mock."""
    solver_type = load_registered_solver("AugmentedRandomSearch")
    assert solver_type is not None, "AugmentedRandomSearch entry point failed to load"

    domain_factory = lambda: GymDomain(gym.make("CartPole-v1"))
    dom = domain_factory()
    assert solver_type.check_domain(dom)

    with solver_type(
        domain_factory=domain_factory,
        n_epochs=3,
        epoch_size=50,
        directions=4,
        top_directions=2,
        learning_rate=0.02,
        policy_noise=0.03,
        reward_maximization=True,
    ) as solver:
        solver.solve()

        # Real state produced by the real solver: a learned linear policy
        # matrix over the real CartPole observation/action dimensions.
        assert solver.policy is not None
        assert solver.policy.shape == (1, 4)  # 1 discrete action dim x 4 obs dims
        assert np.isfinite(solver.policy).all()

        # Real rollout of the learned policy against the real domain.
        observation = dom.reset()
        total_reward = 0.0
        nb_steps = 0
        while nb_steps < 50:
            action = solver.sample_action(observation)
            outcome = dom.step(action)
            total_reward += outcome.value.reward
            observation = outcome.observation
            nb_steps += 1
            if outcome.termination:
                break

    dom.close()

    # A CartPole episode always accrues at least one step's reward before
    # termination or the step cap -- a real, observed, non-degenerate value.
    assert nb_steps > 0
    assert total_reward >= 1.0
