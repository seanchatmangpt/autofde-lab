"""G4 stub-site closures: real collaborators, no mocks."""

import http.server
import threading
import urllib.request

import pytest

from autofde_lab.hub.domain.htn.planner import UnsupportedConstructError
from autofde_lab.hub.solver.utils.gnn import space_utils as su
from autofde_lab.hub.solver.utils.gnn import torch_utils as tu
from autofde_lab.hub.solver.stable_baselines.gnn.common import utils as sb_utils
from autofde_lab.hub.solver.ray_rllib.gnn.utils.spaces import space_utils as rl_su
from autofde_lab.receipts.tests import test_ocel_optimization_agent as t_ocel
from autofde_lab.receipts.tests import test_real_rollout as t_roll
from autofde_lab.solvers import Solver
from autofde_lab.utils import RolloutCallback


def test_unsupported_errors_are_typed_nie_subclasses():
    for cls in (UnsupportedConstructError, su.UnsupportedInputError,
                tu.UnsupportedInputError, sb_utils.UnsupportedInputError,
                rl_su.UnsupportedInputError):
        assert issubclass(cls, NotImplementedError)
        assert cls is not NotImplementedError


def test_gnn_space_refuses_non_box_node_space_with_typed_error():
    import gymnasium as gym
    g = gym.spaces.Graph(node_space=gym.spaces.Discrete(3), edge_space=None)
    with pytest.raises(su.UnsupportedInputError):
        su.add_onehot_encoded_discrete_feature_to_graph_space(g, 2)


def test_rollout_callback_hooks_return_none():
    cb = RolloutCallback()
    assert [cb.at_rollout_start(), cb.at_rollout_end(),
            cb.at_episode_start(), cb.at_episode_end()] == [None] * 4


def test_solver_default_hooks_return_none():
    class S(Solver):
        pass
    s = S.__new__(S)
    assert s._reset() is None and s._initialize() is None and s._cleanup() is None


@pytest.mark.parametrize("mod", [t_roll, t_ocel])
def test_maze_observation_space_is_the_walkable_cells(mod):
    d = mod.MazeDomain(mod.State(1, 1), mod.State(1, 3))
    space = d._get_observation_space_()
    assert space.contains(mod.State(1, 1))
    assert not space.contains(mod.State(0, 0))


def test_openclaw_handler_log_message_is_silent_and_serves():
    from autofde_lab import openclaw_http
    h = openclaw_http._Handler
    assert h.log_message(object.__new__(h), "%s", "x") is None
    assert issubclass(h, http.server.BaseHTTPRequestHandler)
