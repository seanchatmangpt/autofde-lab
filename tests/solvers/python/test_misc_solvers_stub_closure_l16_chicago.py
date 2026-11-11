"""L16 Chicago tests: misc-solver stub closure (do_solver, MDP/SSP/POMDP/RL solver dirs).

Real collaborators only: real domains, real C++/Python solvers, real subprocess, real files.
No mocks, no monkeypatch, no sleeps. Oracles:
  * GraphMDP: s0 -a-> s1 (0.8) | s0 (0.2), all unit costs, s1 -a-> goal, s0 -b-> s2 (cost 5).
    Optimal expected cost from s0 = 1 + 0.8*1 + 0.2*E  =>  E = 1.8 / 0.8 = 2.25 (action 'a').
  * Acyclic GraphMDP: E = 1 + (0.9*1 + 0.1*(1+1)) = 2.1.
  * Tiger POMDP: listen is the only sensible first action from the uniform belief.
"""

from __future__ import annotations

import importlib.util
import os
import random
import subprocess
import sys
import textwrap
from enum import Enum
from pathlib import Path
from typing import NamedTuple

import pytest

from autofde_lab import (
    DiscreteDistribution,
    Domain,
    SingleValueDistribution,
    Value,
)
from autofde_lab.builders.domain import (
    Actions,
    DeterministicInitialized,
    EnumerableTransitions,
    Markovian,
    PartiallyObservable,
    Rewards,
    Sequential,
    SingleAgent,
    UncertainInitialized,
)
from autofde_lab.hub.domain.graph_domain.GraphDomain import GraphDomainUncertain
from autofde_lab.hub.space.gym import EnumSpace, ListSpace
from autofde_lab.utils import get_registered_solvers, load_registered_solver

REPO = Path(__file__).resolve().parents[3]

# --------------------------------------------------------------------------------------
# Domains
# --------------------------------------------------------------------------------------


class GraphMDP(DeterministicInitialized, GraphDomainUncertain):
    def _get_initial_state_(self):
        return "s0"

    def _state_reset(self):
        return "s0"


def gmdp():
    nm = {
        "s0": {"a": {"s1": (0.8, 1.0), "s0": (0.2, 1.0)}, "b": {"s2": (1.0, 5.0)}},
        "s1": {"a": {"g": (1.0, 1.0)}},
        "s2": {"a": {"g": (1.0, 1.0)}},
        "g": {},
    }
    term = {k: k == "g" for k in nm}
    return GraphMDP(nm, term, dict(term))


def gmdp_acyclic():
    nm = {
        "s0": {"a": {"s1": (1.0, 1.0)}, "b": {"s2": (1.0, 5.0)}},
        "s1": {"a": {"g": (0.9, 1.0), "s2": (0.1, 1.0)}},
        "s2": {"a": {"g": (1.0, 1.0)}},
        "g": {},
    }
    term = {k: k == "g" for k in nm}
    return GraphMDP(nm, term, dict(term))


class TigerState(NamedTuple):
    tiger: str


class TigerObs(NamedTuple):
    heard: str


class TigerAct(Enum):
    listen = 0
    open_left = 1
    open_right = 2


class Tiger(
    Domain,
    SingleAgent,
    Sequential,
    EnumerableTransitions,
    Actions,
    Markovian,
    PartiallyObservable,
    Rewards,
    UncertainInitialized,
):
    T_state = TigerState
    T_observation = TigerObs
    T_event = TigerAct
    T_value = float
    T_predicate = bool
    T_info = None

    def _get_initial_state_distribution_(self):
        return DiscreteDistribution(
            [(TigerState("left"), 0.5), (TigerState("right"), 0.5)]
        )

    def _state_reset(self):
        return TigerState("left")

    def _get_next_state_distribution(self, memory, action):
        if action == TigerAct.listen:
            return SingleValueDistribution(memory)
        return DiscreteDistribution(
            [(TigerState("left"), 0.5), (TigerState("right"), 0.5)]
        )

    def _get_observation_distribution(self, state, action=None):
        if action is None or action == TigerAct.listen:
            p = 0.85 if state.tiger == "left" else 0.15
            return DiscreteDistribution(
                [(TigerObs("left"), p), (TigerObs("right"), 1 - p)]
            )
        return DiscreteDistribution([(TigerObs("left"), 0.5), (TigerObs("right"), 0.5)])

    def _get_transition_value(self, memory, action, next_state=None):
        if action == TigerAct.listen:
            return Value(reward=-1)
        bad = "left" if action == TigerAct.open_left else "right"
        return Value(reward=-100 if memory.tiger == bad else 10)

    def _is_terminal(self, state):
        return False

    def _get_action_space_(self):
        return EnumSpace(TigerAct)

    def _get_applicable_actions_from(self, memory):
        return self._get_action_space_()

    def _get_observation_space_(self):
        return ListSpace([TigerObs("left"), TigerObs("right")])


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------------
# 1. Loader census: every registered solver loads in this venv
# --------------------------------------------------------------------------------------

L16_OWNED = [
    "AOstar", "ILAOstar", "VI", "PI", "LRTDP", "MARTDP", "MAHD", "POMCP", "pPOMCP",
    "SimpleGreedy", "DOSolver", "GPHH", "PilePolicy", "UPSolver", "SSiPP", "FRET",
    "MDPLP", "SSPLP", "IDual", "CIDual", "GPCI", "SARSOP", "DESPOT", "RTDPBel",
    "Witness", "HSVI", "GoalHSVI", "AugmentedRandomSearch", "MaxentIRL",
    "RDDLJaxSolver", "RDDLGurobiSolver", "SSPReplan", "SSPDetHindsight",
    "SSPPlanMerger", "FF", "FFReplan", "PPDDLReplan", "FFDetHindsight",
    "PPDDLDetHindsight", "PPDDLPlanMerger", "RFF",
]


@pytest.mark.parametrize("name", L16_OWNED)
def test_registered_solver_loads(name):
    assert name in get_registered_solvers()
    assert load_registered_solver(name) is not None


# --------------------------------------------------------------------------------------
# 2. Goal-MDP / SSP family: construct + solve + exact oracle
# --------------------------------------------------------------------------------------

DP_EXACT = ["ILAOstar", "VI", "PI", "LRTDP", "SSiPP", "FRET", "MDPLP", "SSPLP", "IDual", "GPCI"]


@pytest.mark.parametrize("name", DP_EXACT)
def test_mdp_dp_solver_matches_oracle(name):
    cls = load_registered_solver(name)
    dom = gmdp()
    with cls(domain_factory=gmdp) as slv:
        slv.solve()
        s0 = dom.reset()
        assert slv.sample_action(s0) == "a"
        assert slv.get_utility(s0).cost == pytest.approx(2.25, abs=0.05)


def test_aostar_acyclic_matches_oracle():
    cls = load_registered_solver("AOstar")
    dom = gmdp_acyclic()
    with cls(
        domain_factory=gmdp_acyclic, heuristic=lambda d, s: Value(cost=0)
    ) as slv:
        slv.solve()
        s0 = dom.reset()
        assert slv.sample_action(s0) == "a"
        assert slv.get_utility(s0).cost == pytest.approx(2.1, abs=1e-6)


@pytest.mark.parametrize("name", ["SSPReplan", "SSPDetHindsight", "SSPPlanMerger"])
def test_ssp_determinization_solvers_choose_cheap_branch(name):
    cls = load_registered_solver(name)
    dom = gmdp()
    with cls(domain_factory=gmdp) as slv:
        slv.solve()
        assert slv.sample_action(dom.reset()) == "a"


# --------------------------------------------------------------------------------------
# 3. POMDP family on Tiger
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["SARSOP", "Witness"])
def test_pomdp_exact_solvers_listen_first(name):
    cls = load_registered_solver(name)
    with cls(domain_factory=Tiger) as slv:
        slv.solve()
        assert slv.sample_action(Tiger().reset()) == TigerAct.listen


def test_hsvi_listen_first():
    cls = load_registered_solver("HSVI")
    with cls(
        domain_factory=Tiger, epsilon=1.0, time_budget=3000, max_sample_depth=20
    ) as slv:
        slv.solve()
        assert slv.sample_action(Tiger().reset()) == TigerAct.listen


@pytest.mark.parametrize("name", ["POMCP", "DESPOT"])
def test_pomdp_online_solvers_return_applicable_action(name):
    cls = load_registered_solver(name)
    with cls(domain_factory=Tiger) as slv:
        slv.solve()
        assert slv.sample_action(Tiger().reset()) in set(TigerAct)


def test_ppomcp_rollout_on_mastermind():
    from autofde_lab.hub.domain.mastermind import MasterMind
    from autofde_lab.utils import rollout

    cls = load_registered_solver("pPOMCP")
    dom = MasterMind(3, 3)
    assert cls.check_domain(dom)
    with cls(domain_factory=lambda: MasterMind(3, 3)) as slv:
        slv.solve()
        rollout(dom, slv, num_episodes=1, max_steps=20, verbose=False)


# --------------------------------------------------------------------------------------
# 4. RL / IRL solvers on real gymnasium envs
# --------------------------------------------------------------------------------------


def test_ars_solves_cartpole():
    import gymnasium as gym

    from autofde_lab.hub.domain.gym import GymDomain

    def fac():
        return GymDomain(gym.make("CartPole-v1"))

    cls = load_registered_solver("AugmentedRandomSearch")
    assert cls.check_domain(fac())
    with cls(
        domain_factory=fac, n_epochs=2, epoch_size=5, directions=2, top_directions=1
    ) as slv:
        slv.solve()
        dom = fac()
        obs = dom.reset()
        slv.reset()
        assert slv.sample_action(obs) in (0, 1)


def test_maxent_irl_learns_q_table_from_expert_demo(tmp_path):
    import gymnasium as gym
    import numpy as np

    from autofde_lab.hub.domain.gym import GymDomain

    env = gym.make("MountainCar-v0")
    demo = np.zeros((3, 20, 3))
    for i in range(3):
        o, _ = env.reset(seed=i)
        for t in range(20):
            a = 2 if o[1] >= 0 else 0
            demo[i, t] = [o[0], o[1], a]
            o, *_ = env.step(a)
    demo_path = tmp_path / "demo.npy"
    np.save(demo_path, demo)

    def fac():
        return GymDomain(gym.make("MountainCar-v0"))

    cls = load_registered_solver("MaxentIRL")
    cwd = os.getcwd()
    os.chdir(tmp_path)  # solver writes maxent.png next to its q-table
    try:
        with cls(domain_factory=fac, n_epochs=2, expert_trajectories=str(demo_path)) as slv:
            slv.solve()
            dom = fac()
            obs = dom.reset()
            slv.reset()
            assert slv.sample_action(obs) in (0, 1, 2)
    finally:
        os.chdir(cwd)
    q = np.load(tmp_path / "demo_maxent_q_table.npy")
    assert q.shape == (400, 3)


# --------------------------------------------------------------------------------------
# 5. Multi-agent: MARTDP + MAHD (real maze example module)
# --------------------------------------------------------------------------------------

MAZE_EXAMPLE = REPO / "examples" / "maze_multiagent_mdp_multisolve.py"


@pytest.fixture(scope="module")
def maze():
    return _load_module("l16_maze_example", MAZE_EXAMPLE)


def test_martdp_solves_multiagent_maze(maze):
    random.seed(0)
    cls = load_registered_solver("MARTDP")
    dom = maze.MultiAgentMaze()
    assert cls.check_domain(dom)

    def heur(d, s):
        return (
            {a: Value(cost=0) for a in s},
            {a: maze.AgentAction.stay for a in s},
        )

    with cls(
        domain_factory=lambda: maze.MultiAgentMaze(),
        heuristic=heur,
        time_budget=2000,
        max_depth=50,
        rollout_budget=200,
    ) as slv:
        slv.solve()
        action = slv.sample_action(dom.get_initial_state())
    assert set(action) == set(dom.get_agents())


def _mahd_kwargs(maze):
    from math import sqrt

    MARTDP = load_registered_solver("MARTDP")
    LRTDP = load_registered_solver("LRTDP")
    return dict(
        multiagent_solver_class=MARTDP,
        singleagent_solver_class=LRTDP,
        multiagent_domain_factory=lambda: maze.MultiAgentMaze(),
        singleagent_domain_factory=lambda md, ag: maze.SingleAgentMaze(
            md._maze, md._agents_goals[ag]
        ),
        multiagent_solver_kwargs=dict(
            domain_factory=lambda: maze.MultiAgentMaze(),
            time_budget=3000,
            max_depth=50,
            rollout_budget=200,
            max_feasibility_trials=10,
            graph_expansion_rate=0.01,
            dead_end_cost=1000,
        ),
        singleagent_solver_kwargs=dict(
            heuristic=lambda d, s: Value(
                cost=sqrt((d._goal.x - s.x) ** 2 + (d._goal.y - s.y) ** 2)
            ),
            time_budget=1000,
            max_depth=100,
            parallel=False,
        ),
    )


def test_mahd_each_agent_solver_gets_its_own_goal(maze):
    """Regression: the per-agent domain factory closed over the loop variable, so every
    single-agent solver was handed the LAST agent's domain (and goal)."""
    random.seed(0)
    MAHD = load_registered_solver("MAHD")
    slv = MAHD(**_mahd_kwargs(maze))
    md = slv._multiagent_domain
    assert len(slv._singleagent_solvers) == 4
    for agent, sub in slv._singleagent_solvers.items():
        assert sub._domain_factory()._goal == md._agents_goals[agent]
    goals = {sub._domain_factory()._goal for sub in slv._singleagent_solvers.values()}
    assert len(goals) > 1


MAHD_EXIT_SCRIPT = textwrap.dedent(
    """
    import importlib.util, random, sys, warnings
    warnings.filterwarnings("ignore")
    spec = importlib.util.spec_from_file_location("mm", {example!r})
    mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)
    from math import sqrt
    from autofde_lab import Value
    from autofde_lab.utils import load_registered_solver
    random.seed(0)
    MARTDP = load_registered_solver("MARTDP"); LRTDP = load_registered_solver("LRTDP")
    MAHD = load_registered_solver("MAHD")
    cfg = dict(
        multiagent_solver_class=MARTDP, singleagent_solver_class=LRTDP,
        multiagent_domain_factory=lambda: mm.MultiAgentMaze(),
        singleagent_domain_factory=lambda md, ag: mm.SingleAgentMaze(md._maze, md._agents_goals[ag]),
        multiagent_solver_kwargs=dict(domain_factory=lambda: mm.MultiAgentMaze(), time_budget=3000,
            max_depth=50, rollout_budget=200, max_feasibility_trials=10,
            graph_expansion_rate=0.01, dead_end_cost=1000),
        singleagent_solver_kwargs=dict(
            heuristic=lambda d, s: Value(cost=sqrt((d._goal.x - s.x) ** 2 + (d._goal.y - s.y) ** 2)),
            time_budget=1000, max_depth=100, parallel=False))
    with MAHD(**cfg) as s:
        s.solve()
    print("MAHD-SOLVED-AND-CLEANED")
    """
)


def test_mahd_clean_interpreter_exit():
    """Regression: MAHD._cleanup destroyed the native solvers in creation order, which
    segfaulted the interpreter at exit (rc 139). Reverse (LIFO) destruction exits 0."""
    script = MAHD_EXIT_SCRIPT.format(example=str(MAZE_EXAMPLE))
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=REPO
    )
    assert "MAHD-SOLVED-AND-CLEANED" in proc.stdout, proc.stderr[-2000:]
    assert proc.returncode == 0, proc.stderr[-2000:]


# --------------------------------------------------------------------------------------
# 6. do_solver contract: the two former bare NotImplementedError sites
# --------------------------------------------------------------------------------------


def test_from_solution_to_policy_rejects_unknown_solution_type():
    from autofde_lab.hub.solver.do_solver.do_solver_scheduling import (
        from_solution_to_policy,
    )

    with pytest.raises(TypeError, match="got str"):
        from_solution_to_policy("not-a-solution", domain=None, policy_method_params=None)


def test_non_renewable_unary_resource_is_a_typed_refusal():
    from autofde_lab.hub.solver.do_solver.sk_to_do_binding import (
        UnsupportedSchedulingModelError,
        build_do_domain,
    )

    mod = _load_module(
        "l16_toy_scheduling", REPO / "tests" / "scheduling" / "test_scheduling.py"
    )

    class NonRenewableUnit(mod.ToySchedulingDomain):
        renewability = {**mod.ToySchedulingDomain.renewability, "employee-1": False}

    # control: the renewable domain converts
    assert build_do_domain(mod.ToySchedulingDomain()) is not None
    with pytest.raises(UnsupportedSchedulingModelError, match=r"\['employee-1'\]") as ei:
        build_do_domain(NonRenewableUnit())
    assert isinstance(ei.value, NotImplementedError)
