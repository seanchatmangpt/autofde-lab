"""G6: stub-site closure for gym/maze/graph/cgp/ray/openevolve (Chicago style: real objects)."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import gymnasium as gym
import numpy as np
import pytest

from autofde_lab import Domain
from autofde_lab.hub.domain.graph_domain.GraphDomain import ActionSpace, GraphDomain
from autofde_lab.hub.domain.gym import GymDomain
from autofde_lab.hub.domain.maze import maze as maze_module
from autofde_lab.hub.solver.cgp.cgp import change_interval
from autofde_lab.hub.solver.openevolve.initial_program_builder import (
    UnsupportedDomainTraitsError,
    build_initial_program,
)
from autofde_lab.hub.solver.ray_rllib.gnn.algorithms.ppo.ppo import (
    GraphPPO,
    UnsupportedFrameworkError,
)
from autofde_lab.hub.space.gym import DataSpace, GymSpace


def test_action_space_contains_reflects_membership():
    space = ActionSpace(["a", "b"])
    assert space.contains("a") is True
    assert space.contains("z") is False


def test_graph_domain_observation_space_is_the_graph_states():
    nsm = {0: {"go": 1}, 1: {"go": 2}}
    attrs = {0: {"go": {"weight": 1.0}}, 1: {"go": {"weight": 2.0}}}
    dom = GraphDomain(nsm, attrs, targets={2})
    obs = dom.get_observation_space()
    assert 0 in obs and 2 in obs and 99 not in obs


def _load_maze_without_ipython():
    saved = {k: sys.modules.get(k) for k in ("IPython", "IPython.display")}
    sys.modules["IPython"] = None
    sys.modules["IPython.display"] = None
    try:
        spec = importlib.util.spec_from_file_location(
            "maze_no_ipython", maze_module.__file__
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_maze_display_fallbacks_without_ipython_are_functional():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mod = _load_maze_without_ipython()
    fig = plt.figure()
    assert mod.clear_output(wait=True) is None
    fig.add_subplot(1, 1, 1).plot([0, 1])
    assert fig.stale
    assert mod.display(fig) is None
    assert not fig.stale  # the fallback really redrew the canvas
    plt.close(fig)


def test_gym_space_mirrors_shape_dtype_and_data_space_roundtrips():
    box = gym.spaces.Box(low=0.0, high=1.0, shape=(2,), dtype=np.float32)
    gs = GymSpace(box)
    assert gs.shape == (2,) and gs.dtype == np.float32

    @dataclass
    class P:
        x: int

    ds = DataSpace(P, {"x": gym.spaces.Discrete(3)})
    s = ds.sample()
    assert isinstance(s, P)
    assert [p.x for p in ds.from_unwrapped([{"x": 1}, {"x": 2}])] == [1, 2]


def test_gym_domain_step_returns_reward_as_first_value_and_rewards_kept():
    dom = GymDomain(gym.make("CartPole-v1"))
    dom.reset()
    out = dom.step(dom.get_action_space().sample())
    _, transition_value, _, _ = out.astuple()
    assert transition_value[0] == out.value.reward == 1.0


def test_cgp_change_interval_accepts_infinite_bounds_with_fallback():
    assert change_interval(5.0, -np.inf, np.inf, 0, 1) == pytest.approx(1.0)
    assert change_interval(0.0, -np.inf, np.inf, 0, 10) == pytest.approx(5.0)


def test_original_concat_samples_delegates_to_rllib_and_patch_roundtrips():
    from ray.rllib.policy.sample_batch import SampleBatch

    from autofde_lab.hub.solver.ray_rllib.gnn.policy.sample_batch_monkey_patch import (
        monkey_patch_concat_samples,
        unmonkey_patch_concat_samples,
    )
    from autofde_lab.hub.solver.ray_rllib.gnn.policy.sample_batch_original_code import (
        original_concat_samples,
    )

    a = SampleBatch({"x": np.array([1, 2])})
    b = SampleBatch({"x": np.array([3])})
    assert list(original_concat_samples([a, b])["x"]) == [1, 2, 3]
    monkey_patch_concat_samples()
    try:
        assert list(original_concat_samples([a, b])["x"]) == [1, 2, 3]
    finally:
        unmonkey_patch_concat_samples()
    assert list(original_concat_samples([a, b])["x"]) == [1, 2, 3]


def test_build_initial_program_refuses_untemplated_domain_with_typed_error():
    class Bare(Domain):
        pass

    with pytest.raises(UnsupportedDomainTraitsError) as ei:
        build_initial_program(Bare)
    assert isinstance(ei.value, NotImplementedError)
    from autofde_lab.hub.domain.maze.maze import Maze

    assert "Maze" in build_initial_program(Maze)


def test_graph_ppo_refuses_non_torch_framework_with_typed_error():
    with pytest.raises(UnsupportedFrameworkError):
        GraphPPO.get_default_policy_class({"framework": "tf2"})
    assert GraphPPO.get_default_policy_class({"framework": "torch"}).__name__ == (
        "PPOTorchGraphPolicy"
    )
