"""Chicago-style closure tests for stable_baselines stubs (lane L7).

Real collaborators only: SB3's own VecNormalize is the numerical oracle for graph
observation normalization.
"""

import gymnasium as gym
import numpy as np
import pytest
import torch as th
from stable_baselines3.common.running_mean_std import RunningMeanStd
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from autofde_lab.hub.solver.stable_baselines.autoregressive.common.distributions import (
    MultiMaskableCategoricalDistribution,
    MaskableCategoricalDistribution,
)
from autofde_lab.hub.solver.stable_baselines.autoregressive.ppo.autoregressive_ppo import (
    AutoregressivePPO,
)
from autofde_lab.hub.solver.stable_baselines.gnn.common.buffers import (
    DictGraphReplayBuffer,
    GraphReplayBuffer,
    MaskableGraph2NodeRolloutBuffer,
)

from .autoregressive.conftest import GraphWalkEnv

NODE_DIM = 3
EDGE_DIM = 2


class _BoxEnv(gym.Env):
    def __init__(self, dim: int):
        self.observation_space = gym.spaces.Box(-100, 100, (dim,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def _fitted_vecnormalize(dim: int, n_steps: int = 60, **kwargs) -> VecNormalize:
    venv = VecNormalize(DummyVecEnv([lambda: _BoxEnv(dim)]), **kwargs)
    venv.reset()
    for _ in range(n_steps):
        venv.step(np.array([0]))
    return venv


class _GraphNormStats:
    """Hand-written real normalization stats holder (graph nodes + edges)."""

    def __init__(self, nodes: VecNormalize, edges: VecNormalize):
        self.obs_rms = {"nodes": nodes.obs_rms, "edges": edges.obs_rms}
        self.epsilon = nodes.epsilon
        self.clip_obs = nodes.clip_obs
        self.norm_obs = True


def _graph_space() -> gym.spaces.Graph:
    return gym.spaces.Graph(
        node_space=gym.spaces.Box(-100, 100, (NODE_DIM,), dtype=np.float32),
        edge_space=gym.spaces.Box(-100, 100, (EDGE_DIM,), dtype=np.float32),
    )


def _random_graph(rng: np.random.Generator, scale: float = 30.0):
    n = int(rng.integers(2, 5))
    links = np.array([[i, (i + 1) % n] for i in range(n)])
    return gym.spaces.GraphInstance(
        nodes=(rng.normal(size=(n, NODE_DIM)) * scale).astype(np.float32),
        edges=(rng.normal(size=(n, EDGE_DIM)) * scale).astype(np.float32),
        edge_links=links,
    )


def _filled_buffer(cls, space, n=6, seed=0):
    rng = np.random.default_rng(seed)
    buf = cls(buffer_size=n, observation_space=space, action_space=gym.spaces.Discrete(2))
    obs_list, next_list = [], []
    for _ in range(n):
        o, nxt = _random_graph(rng), _random_graph(rng)
        obs_list.append(o)
        next_list.append(nxt)
        buf._add_obs(o, nxt)
    return buf, obs_list, next_list


def _sample(buf, inds, env=None):
    return buf._get_observations_samples(
        np.array(inds), env_indices=np.zeros(len(inds), dtype=int), env=env
    )


def test_graph_replay_buffer_normalization_matches_sb3_vecnormalize():
    nodes_vn = _fitted_vecnormalize(NODE_DIM)
    edges_vn = _fitted_vecnormalize(EDGE_DIM)
    stats = _GraphNormStats(nodes_vn, edges_vn)
    buf, obs_list, next_list = _filled_buffer(GraphReplayBuffer, _graph_space())
    inds = [0, 3, 5]

    obs, next_obs = _sample(buf, inds, env=stats)

    exp_nodes = np.concatenate([nodes_vn.normalize_obs(obs_list[i].nodes) for i in inds])
    exp_edges = np.concatenate([edges_vn.normalize_obs(obs_list[i].edges) for i in inds])
    exp_next_nodes = np.concatenate(
        [nodes_vn.normalize_obs(next_list[i].nodes) for i in inds]
    )
    np.testing.assert_allclose(obs.x.numpy(), exp_nodes, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(obs.edge_attr.numpy(), exp_edges, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(next_obs.x.numpy(), exp_next_nodes, rtol=1e-5, atol=1e-5)
    # normalization actually changed the values
    raw = np.concatenate([obs_list[i].nodes for i in inds])
    assert not np.allclose(raw, obs.x.numpy())


def test_graph_replay_buffer_normalization_accepts_plain_vecnormalize_for_nodes():
    nodes_vn = _fitted_vecnormalize(NODE_DIM)  # real VecNormalize, single rms
    buf, obs_list, _ = _filled_buffer(GraphReplayBuffer, _graph_space())
    obs, _ = _sample(buf, [1, 2], env=nodes_vn)
    expected = np.concatenate([nodes_vn.normalize_obs(obs_list[i].nodes) for i in (1, 2)])
    np.testing.assert_allclose(obs.x.numpy(), expected, rtol=1e-5, atol=1e-5)
    # edges untouched when no edge stats
    raw_edges = np.concatenate([obs_list[i].edges for i in (1, 2)])
    np.testing.assert_allclose(obs.edge_attr.numpy(), raw_edges, rtol=1e-6)


def test_graph_replay_buffer_normalization_clips_like_sb3():
    nodes_vn = _fitted_vecnormalize(NODE_DIM, clip_obs=0.5)
    edges_vn = _fitted_vecnormalize(EDGE_DIM, clip_obs=0.5)
    stats = _GraphNormStats(nodes_vn, edges_vn)
    buf, _, _ = _filled_buffer(GraphReplayBuffer, _graph_space())
    obs, _ = _sample(buf, [0, 1, 2], env=stats)
    assert obs.x.abs().max().item() <= 0.5 + 1e-6
    assert obs.x.abs().max().item() == pytest.approx(0.5, abs=1e-6)


def test_graph_replay_buffer_next_observations_come_from_next_observations():
    buf, obs_list, next_list = _filled_buffer(GraphReplayBuffer, _graph_space())
    inds = [0, 4]
    obs, next_obs = _sample(buf, inds)
    np.testing.assert_allclose(
        obs.x.numpy(), np.concatenate([obs_list[i].nodes for i in inds]), rtol=1e-6
    )
    np.testing.assert_allclose(
        next_obs.x.numpy(),
        np.concatenate([next_list[i].nodes for i in inds]),
        rtol=1e-6,
    )


def test_dict_graph_replay_buffer_normalization_matches_sb3():
    space = gym.spaces.Dict(
        {
            "g": _graph_space(),
            "v": gym.spaces.Box(-100, 100, (4,), dtype=np.float32),
        }
    )
    nodes_vn = _fitted_vecnormalize(NODE_DIM)
    edges_vn = _fitted_vecnormalize(EDGE_DIM)
    vec_vn = _fitted_vecnormalize(4)
    stats = _GraphNormStats(nodes_vn, edges_vn)
    stats.obs_rms = {"g": stats.obs_rms, "v": vec_vn.obs_rms}

    n = 5
    rng = np.random.default_rng(1)
    buf = DictGraphReplayBuffer(
        buffer_size=n, observation_space=space, action_space=gym.spaces.Discrete(2)
    )
    graphs, nexts, vecs = [], [], []
    for _ in range(n):
        g, ng = _random_graph(rng), _random_graph(rng)
        v = (rng.normal(size=(1, 4)) * 30).astype(np.float32)
        nv = (rng.normal(size=(1, 4)) * 30).astype(np.float32)
        graphs.append(g)
        nexts.append(ng)
        vecs.append(v)
        buf._add_obs({"g": [g], "v": v}, {"g": [ng], "v": nv})

    obs, next_obs = _sample(buf, [0, 2], env=stats)
    np.testing.assert_allclose(
        obs["g"].x.numpy(),
        np.concatenate([nodes_vn.normalize_obs(graphs[i].nodes) for i in (0, 2)]),
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        next_obs["g"].x.numpy(),
        np.concatenate([nodes_vn.normalize_obs(nexts[i].nodes) for i in (0, 2)]),
        rtol=1e-5,
        atol=1e-5,
    )
    assert obs["v"].shape[-1] == 4


def test_graph_replay_buffer_contract_guards():
    space = _graph_space()
    act = gym.spaces.Discrete(2)
    with pytest.raises(NotImplementedError, match="memory usage"):
        GraphReplayBuffer(
            4, space, act, optimize_memory_usage=True, handle_timeout_termination=False
        )
    with pytest.raises(NotImplementedError, match="multiple vectorized"):
        GraphReplayBuffer(4, space, act, n_envs=2)


def test_maskable_graph2node_rollout_buffer_requires_masks():
    space = _graph_space()
    buf = MaskableGraph2NodeRolloutBuffer(4, space, gym.spaces.Discrete(2))
    with pytest.raises(NotImplementedError):
        buf._add_action_masks(None)


def test_multi_maskable_distribution_contract_is_explicit():
    dist = MultiMaskableCategoricalDistribution(
        distributions=[MaskableCategoricalDistribution(action_dim=2)]
    )
    for call in (
        lambda: dist.sample(),
        lambda: dist.mode(),
        lambda: dist.actions_from_params(),
        lambda: dist.log_prob_from_params(),
        lambda: dist.proba_distribution_net(),
        lambda: dist.proba_distribution(),
    ):
        with pytest.raises(NotImplementedError, match="autoregressive"):
            call()


def test_autoregressive_policy_get_distribution_contract_is_explicit():
    algo = AutoregressivePPO("MlpPolicy", GraphWalkEnv(), n_steps=16)
    with pytest.raises(NotImplementedError, match="autoregressive"):
        algo.policy.get_distribution(th.zeros(1, 5))


def test_autoregressive_policy_unshared_features_extractor_trains():
    env = GraphWalkEnv()
    algo = AutoregressivePPO(
        "MlpPolicy",
        env,
        n_steps=64,
        policy_kwargs={"share_features_extractor": False},
    )
    policy = algo.policy
    assert not policy.share_features_extractor
    assert policy.pi_features_extractor is not policy.vf_features_extractor
    pi_before = [p.detach().clone() for p in policy.pi_features_extractor.parameters()]
    value_before = [p.detach().clone() for p in policy.value_net.parameters()]

    algo.learn(total_timesteps=256)

    value_after = list(policy.value_net.parameters())
    assert any(
        not th.allclose(b, a) for b, a in zip(value_before, value_after)
    ), "value net not updated"
    # the pi extractor (FlattenExtractor) has no params; ensure api consistent
    assert len(pi_before) == len(list(policy.pi_features_extractor.parameters()))

    obs, _ = env.reset()
    action, _ = algo.predict(obs, action_masks=env.action_masks())
    assert action.shape[-1] == 3
    values = policy.predict_values(th.as_tensor([obs]))
    assert values.shape == (1, 1)


def test_multi_maskable_distribution_log_prob_with_int_actions_and_partial_mask():
    """log_prob must work on int64 actions when some samples have a 0-mask row."""
    dist = MultiMaskableCategoricalDistribution(
        distributions=[MaskableCategoricalDistribution(action_dim=3)]
    )
    logits = th.tensor([[0.1, 0.2, 0.3], [1.0, 0.0, -1.0]])
    dist.set_proba_distribution_component(i_component=0, action_component_logits=logits)
    masks = th.tensor([[True, True, True], [False, False, False]])
    dist.apply_masking_component(i_component=0, component_masks=masks)
    actions = th.tensor([[2], [-1]], dtype=th.int64)

    logp = dist.log_prob(actions)

    expected_first = th.log_softmax(logits[0], dim=-1)[2]
    assert logp.dtype == th.float32
    assert logp[0].item() == pytest.approx(expected_first.item(), abs=1e-6)
    assert logp[1].item() == 0.0  # fully-masked sample contributes nothing
