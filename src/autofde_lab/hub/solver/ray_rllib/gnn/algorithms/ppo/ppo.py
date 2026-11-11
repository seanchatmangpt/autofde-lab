from typing import Optional

from ray.rllib import Policy
from ray.rllib.algorithms import PPO, AlgorithmConfig

from autofde_lab.hub.solver.ray_rllib.gnn.algorithms.ppo.ppo_torch_policy import (
    PPOTorchGraphPolicy,
)


class UnsupportedFrameworkError(NotImplementedError):
    """GraphPPO only has a torch policy."""


class GraphPPO(PPO):
    @classmethod
    def get_default_policy_class(
        cls, config: AlgorithmConfig
    ) -> Optional[type[Policy]]:
        if config["framework"] == "torch":
            return PPOTorchGraphPolicy
        else:
            raise UnsupportedFrameworkError(
                f"GraphPPO implemented for torch context only; got framework "
                f"{config['framework']!r}"
            )
