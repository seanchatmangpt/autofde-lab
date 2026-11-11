"""L8 Chicago tests: CGP Evaluator contract, GraphPPO framework refusal,
openevolve initial-program builder refusal (real collaborators, no mocks)."""

import pytest

from autofde_lab import Domain
from autofde_lab.hub.solver.cgp.pycgp.evaluator import Evaluator


def test_evaluator_is_abstract():
    with pytest.raises(TypeError):
        Evaluator()


def test_evaluator_partial_subclass_rejected():
    class OnlyEvaluate(Evaluator):
        def evaluate(self, cgp, it):
            return 1.0

    with pytest.raises(TypeError):
        OnlyEvaluate()


def test_evaluator_concrete_subclass_works():
    class Const(Evaluator):
        def __init__(self, v):
            self.v = v

        def evaluate(self, cgp, it):
            return self.v + it

        def clone(self):
            return Const(self.v)

    e = Const(2.0)
    c = e.clone()
    assert c is not e and c.evaluate(None, 1) == 3.0


def test_graphppo_torch_ok_and_other_frameworks_refused():
    from autofde_lab.hub.solver.ray_rllib.gnn.algorithms.ppo.ppo import GraphPPO
    from autofde_lab.hub.solver.ray_rllib.gnn.algorithms.ppo.ppo_torch_policy import (
        PPOTorchGraphPolicy,
    )

    assert GraphPPO.get_default_policy_class({"framework": "torch"}) is PPOTorchGraphPolicy
    for fw in ("tf", "tf2", "jax"):
        with pytest.raises(NotImplementedError, match=fw):
            GraphPPO.get_default_policy_class({"framework": fw})


def test_initial_program_builder_refuses_unsupported_domain():
    from autofde_lab.hub.solver.openevolve.initial_program_builder import (
        build_initial_program,
    )

    class Bare(Domain):
        pass

    with pytest.raises(NotImplementedError, match="template"):
        build_initial_program(Bare)
