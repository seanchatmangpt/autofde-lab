# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""An LLM-backed policy solver using DSPy.

Follows the same structure as `skdecide.hub.solver.simple_greedy.SimpleGreedy`:
a pure-Python `DeterministicPolicySolver` that computes its policy online
(no offline `_solve` computation), except each action is chosen by prompting
a language model through a `dspy.Predict` module instead of by evaluating
transition values.

The language model backend is any OpenAI-compatible chat-completions
endpoint via `dspy.LM` -- by default a local TurboFieldfare server
(https://github.com/drumih/turbo-fieldfare), started separately with
`TurboFieldfareServer --model <path> --port 8080`. No network call or API
key is required for that default.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import numpy  # noqa: F401 -- must be imported before dspy: dspy's lazy numpy
# loader (dspy.utils.lazy_import) recurses infinitely (RecursionError) if
# numpy is not already a real, fully-loaded module in sys.modules at the
# point dspy is first imported -- reproduced under pytest's import order,
# not present when dspy happens to be imported first in a fresh interpreter.
import dspy

from skdecide import Domain
from skdecide.builders.domain import (
    Environment,
    Initializable,
    Markovian,
    MultiAgent,
    Rewards,
    Sequential,
    TransformedObservable,
    UnrestrictedActions,
)
from skdecide.core import autocast
from skdecide.solvers import DeterministicPolicySolver

logger = logging.getLogger(__name__)

DEFAULT_LM_MODEL = "openai/gemma-4-26b-a4b-it"
DEFAULT_LM_API_BASE = "http://127.0.0.1:8080/v1"
DEFAULT_LM_API_KEY = "local"  # ignored by TurboFieldfare; required by the OpenAI client shape


def default_lm(
    model: str = DEFAULT_LM_MODEL,
    api_base: str = DEFAULT_LM_API_BASE,
    api_key: str = DEFAULT_LM_API_KEY,
) -> dspy.LM:
    """Build a dspy.LM pointed at a local, OpenAI-compatible TurboFieldfare server."""
    return dspy.LM(model, api_base=api_base, api_key=api_key)


class ChooseMove(dspy.Signature):
    """Choose the next move in a game given a short text description of the
    situation and the exact list of legal moves. Reply with exactly one of
    the legal moves, verbatim.
    """

    situation: str = dspy.InputField()
    legal_moves: str = dspy.InputField(desc="comma-separated exact legal move names")
    move: str = dspy.OutputField(desc="exactly one of legal_moves, verbatim")


class D(
    Domain,
    MultiAgent,
    Sequential,
    Environment,
    UnrestrictedActions,
    Initializable,
    Markovian,
    TransformedObservable,
    Rewards,
):
    pass


class DSPyPolicy(DeterministicPolicySolver):
    """A DeterministicPolicySolver whose per-agent action at every step is
    chosen by a real call to a real language model through DSPy.

    Requires a MultiAgent, Sequential, Environment-level domain with an
    enumerable per-agent action space (checked via `_check_domain_additional`),
    matching `RockPaperScissors` and similarly-shaped small game domains.
    """

    T_domain = D

    def __init__(
        self,
        domain_factory: Callable[[], Domain],
        lm: Optional[dspy.LM] = None,
        situation_formatter: Callable[[Any, str], str] = (
            lambda observation, agent: f"You are playing as '{agent}'. "
            f"Your last observation was: {observation!r}."
        ),
    ) -> None:
        """Construct a DSPyPolicy solver instance.

        # Parameters
        domain_factory: The lambda function to create a domain instance.
        lm: The dspy.LM to query for every action. Defaults to `default_lm()`
            (a local TurboFieldfare server on 127.0.0.1:8080).
        situation_formatter: Builds the natural-language `situation` field
            passed to the LLM for a given (observation, agent_name) pair.
            Override this to give the model richer context for other domains.
        """
        super().__init__(domain_factory=domain_factory)
        self._lm = lm or default_lm()
        self._predict = dspy.Predict(ChooseMove)
        self._situation_formatter = situation_formatter
        self._domain = None

    @classmethod
    def _check_domain_additional(cls, domain: D) -> bool:
        get_action_space = autocast(domain.get_action_space, domain, cls.T_domain)
        action_space = get_action_space()
        return all(hasattr(space, "get_elements") for space in action_space.values())

    def _solve(self) -> None:
        self._domain = self._domain_factory()

    def _get_next_action(
        self, observation: D.T_agent[D.T_observation], domain: Optional[D] = None
    ) -> D.T_agent[D.T_concurrency[D.T_event]]:
        if domain is None:
            domain = self._domain
            logger.warning(
                "Rollout domain not given. Using domain seen during solve instead."
            )
        get_action_space = autocast(domain.get_action_space, domain, self.T_domain)
        action_space = get_action_space()

        actions: dict[Any, Any] = {}
        for agent, obs in observation.items():
            legal = action_space[agent].get_elements()
            legal_by_name = {str(m): m for m in legal}
            with dspy.context(lm=self._lm):
                prediction = self._predict(
                    situation=self._situation_formatter(obs, agent),
                    legal_moves=", ".join(legal_by_name),
                )
            chosen_text = prediction.move.strip()
            move = legal_by_name.get(chosen_text)
            if move is None:
                # Real, observable LLM failure -- do not silently default to
                # an arbitrary move. Try a case-insensitive/substring match
                # before giving up, since models often add stray punctuation.
                lowered = chosen_text.lower()
                candidates = [m for name, m in legal_by_name.items() if name.lower() in lowered]
                if len(candidates) == 1:
                    move = candidates[0]
                else:
                    raise ValueError(
                        f"DSPyPolicy: model returned {chosen_text!r} for agent "
                        f"{agent!r}, which does not match any legal move in "
                        f"{list(legal_by_name)}."
                    )
            actions[agent] = move
        return actions

    def _is_policy_defined_for(self, observation: D.T_agent[D.T_observation]) -> bool:
        return True
