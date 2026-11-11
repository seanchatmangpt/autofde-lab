"""Chicago-style closure tests for stable_baselines stub sites (lane G5).

Real collaborators only: real SB3 vectorized envs, real buffers, real algorithms.
Every unsupported-configuration guard raises the typed UnsupportedConfigurationError
(a NotImplementedError subclass, but not a bare NotImplementedError).
"""

import gymnasium as gym
import numpy as np
import pytest
import torch as th
from stable_baselines3.common.vec_env import DummyVecEnv

from autofde_lab.hub.solver.stable_baselines.autoregressive.common.buffers import (
    ApplicableActionsRolloutBuffer,
)
from autofde_lab.hub.solver.stable_baselines.autoregressive.common.distributions import (
    MaskableCategoricalDistribution,
    MultiMaskableCategoricalDistribution,
)
from autofde_lab.hub.solver.stable_baselines.autoregressive.ppo.autoregressive_ppo import (
    AutoregressivePPO,
)
from autofde_lab.hub.solver.stable_baselines.common.buffers import (
    ScikitDecideRolloutBuffer,
)
from autofde_lab.hub.solver.stable_baselines.errors import (
    UnsupportedConfigurationError,
)
from autofde_lab.hub.solver.stable_baselines.gnn.common.buffers import (
    GraphReplayBuffer,
    MaskableGraph2NodeRolloutBuffer,
)
from autofde_lab.hub.solver.stable_baselines.gnn.common.vec_env.dummy_vec_env import (
    GraphDummyVecEnv,
)
from autofde_lab.hub.solver.stable_baselines.gnn.dqn.dqn import GraphDQN
from autofde_lab.hub.solver.stable_baselines.gnn.ppo.ppo import GraphPPO
from autofde_lab.hub.solver.stable_baselines.gnn.ppo_mask.ppo_mask import (
    MaskableGraph2NodePPO,
)

from .autoregressive.conftest import GraphWalkEnv


def _graph_space() -> gym.spaces.Graph:
    return gym.spaces.Graph(
        node_space=gym.spaces.Box(-1, 1, (3,), dtype=np.float32),
        edge_space=gym.spaces.Box(-1, 1, (2,), dtype=np.float32),
    )


class _SpaceEnv(gym.Env):
    def __init__(self, observation_space):
        self.observation_space = observation_space
        self.action_space = gym.spaces.Discrete(2)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def _two_env_vec(space):
    if isinstance(space, gym.spaces.Graph):
        # same dummy shape/dtype patch the repo's wrap_graph_env applies
        space._shape = (0,)
        space.dtype = np.float64
        return GraphDummyVecEnv([lambda: _SpaceEnv(space), lambda: _SpaceEnv(space)])
    return DummyVecEnv([lambda: _SpaceEnv(space), lambda: _SpaceEnv(space)])


def _raises_typed(call, match=None):
    with pytest.raises(UnsupportedConfigurationError, match=match) as ei:
        call()
    assert type(ei.value) is not NotImplementedError
    assert isinstance(ei.value, NotImplementedError)


# --- distributions (6 sites) -------------------------------------------------


def test_multi_maskable_distribution_typed_contract():
    dist = MultiMaskableCategoricalDistribution(
        distributions=[MaskableCategoricalDistribution(action_dim=2)]
    )
    for call in (
        dist.sample,
        dist.mode,
        dist.actions_from_params,
        dist.log_prob_from_params,
        dist.proba_distribution_net,
        dist.proba_distribution,
    ):
        _raises_typed(call, "autoregressive")


# --- autoregressive policy / algorithm ----------------------------------------


def test_autoregressive_policy_get_distribution_typed_contract():
    algo = AutoregressivePPO("MlpPolicy", GraphWalkEnv(), n_steps=16)
    _raises_typed(lambda: algo.policy.get_distribution(th.zeros(1, 5)), "autoregressive")


def test_applicable_actions_on_policy_rejects_real_vectorization():
    venv = _two_env_vec(gym.spaces.Box(-1, 1, (2,), dtype=np.float32))
    _raises_typed(
        lambda: AutoregressivePPO("MlpPolicy", venv, n_steps=8),
        "real vectorized",
    )


# --- buffers ------------------------------------------------------------------


def test_applicable_actions_buffer_add_masks_guard_and_flatten_noop():
    buf = ApplicableActionsRolloutBuffer(
        4,
        gym.spaces.Box(-1, 1, (2,), dtype=np.float32),
        gym.spaces.Discrete(2),
    )
    _raises_typed(lambda: buf._add_action_masks(None), "action masks")
    _raises_typed(lambda: buf._add_action_masks(np.ones((2, 3))), "action masks")
    buf._add_action_masks(np.ones((1, 3)))
    assert len(buf.action_masks) == 1
    assert buf._swap_and_flatten_action_masks() is None
    assert len(buf.action_masks) == 1  # genuine no-op: nothing reshaped


def test_base_rollout_buffer_flatten_masks_default_is_noop():
    buf = ScikitDecideRolloutBuffer(
        4, gym.spaces.Box(-1, 1, (2,), dtype=np.float32), gym.spaces.Discrete(2)
    )
    assert buf._swap_and_flatten_action_masks() is None


def test_graph_replay_buffer_typed_guards():
    space, act = _graph_space(), gym.spaces.Discrete(2)
    _raises_typed(
        lambda: GraphReplayBuffer(
            4, space, act, optimize_memory_usage=True, handle_timeout_termination=False
        ),
        "memory usage",
    )
    _raises_typed(
        lambda: GraphReplayBuffer(4, space, act, n_envs=2), "multiple vectorized"
    )


def test_maskable_graph2node_buffer_typed_guards_and_flatten():
    buf = MaskableGraph2NodeRolloutBuffer(4, _graph_space(), gym.spaces.Discrete(2))
    _raises_typed(lambda: buf._add_action_masks(None), "action_masks")
    buf._add_action_masks(np.ones((1, 2, 2)))
    buf._swap_and_flatten_action_masks()
    assert buf.action_masks[0].shape == (4,)
    buf.n_envs = 2
    _raises_typed(buf._swap_and_flatten_action_masks, "vectorized")


# --- gnn algorithms -----------------------------------------------------------


def test_graph_on_policy_rejects_real_vectorization():
    venv = _two_env_vec(_graph_space())
    _raises_typed(lambda: GraphPPO("GraphInputPolicy", venv), "GraphOnPolicy")


def test_graph_off_policy_rejects_real_vectorization():
    venv = _two_env_vec(_graph_space())
    _raises_typed(lambda: GraphDQN("GraphInputPolicy", venv), "GraphOffPolicy")


def test_maskable_graph2node_ppo_rejects_dict_observations():
    env = _SpaceEnv(gym.spaces.Dict({"a": gym.spaces.Box(-1, 1, (2,))}))
    _raises_typed(
        lambda: MaskableGraph2NodePPO("GraphInputPolicy", env), "Dict observation"
    )
