# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""GymAct Environment Provider for Autonomous Software Development simulation.

Connects FOND x HDDL product states to GymAct Capability, ActuationIntent,
Observation, and Consequence models with zero ambient actuation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence

from gymact.models import (
    ActuationIntent,
    Capability,
    Consequence,
    MaterializationIntent,
    Observation,
    Standing,
)

from autofde_lab.ocel.log import EventObjectLink, OcelEvent, OcelLog, OcelObject
from autofde_lab.planning.fond_hddl_product import (
    HDDLDomain,
    ProductState,
    method_refinements,
    ready_action_transitions,
)

__all__ = [
    "AutoDevGymActEnvironment",
    "AutoDevGymActProvider",
]


class AutoDevGymActEnvironment:
    """A governed GymAct environment executing auto-dev software steps over ProductState.

    Nondeterministic (FOND) actions such as ``run_tests`` declare multiple
    successors; which one the simulator takes is governed by the explicit
    ``outcome_oracle`` parameter (AFDE-2602) -- never a hidden preference:

    - ``"reference"``: prefer the passing successor (deterministic happy-path
      simulation; the historical behaviour, now explicit).
    - ``"adversarial"``: prefer the failing successor (repair-path
      falsification; the previously unreachable edge).
    - ``"alternate"``: cycle through the declared successors in order, so
      repeated execution reaches every declared outcome.
    """

    OUTCOME_ORACLES = ("reference", "adversarial", "alternate")

    def __init__(
        self,
        domain: HDDLDomain,
        initial_state: ProductState,
        episode_id: str | None = None,
        outcome_oracle: str = "reference",
    ) -> None:
        if outcome_oracle not in self.OUTCOME_ORACLES:
            raise ValueError(
                f"unknown outcome_oracle {outcome_oracle!r}; "
                f"expected one of {self.OUTCOME_ORACLES}"
            )
        self.domain = domain
        self.current_state = initial_state
        self.episode_id = episode_id or f"ep_{uuid.uuid4().hex[:8]}"
        self.outcome_oracle = outcome_oracle
        self._outcome_cycle: dict[str, int] = {}
        self._history: list[tuple[str, ProductState]] = [("init", initial_state)]
        self._recorded_events: list[OcelEvent] = []
        self._step_counter = 0

    def _order_by_outcome_oracle(self, action_name, transitions):
        """Order a FOND action's declared successors per the outcome oracle.

        Stable over the domain's declared transition order, so each oracle's
        choice is deterministic and replayable.
        """
        if self.outcome_oracle == "reference":
            return sorted(
                transitions,
                key=lambda t: 0 if "tests_pass" in t.outcome.add else 1,
            )
        if self.outcome_oracle == "adversarial":
            return sorted(
                transitions,
                key=lambda t: 1 if "tests_pass" in t.outcome.add else 0,
            )
        # alternate: cycle through the declared successors per action name
        idx = self._outcome_cycle.get(action_name, 0)
        self._outcome_cycle[action_name] = idx + 1
        rotated = list(transitions[idx % len(transitions) :]) + list(
            transitions[: idx % len(transitions)]
        )
        return rotated

    def capabilities(self) -> Sequence[Capability]:
        """List enabled capabilities based on current ProductState."""
        caps: list[Capability] = []

        # 1. Method refinements (hierarchical decomposition)
        for ref in method_refinements(self.domain, self.current_state):
            caps.append(
                Capability(
                    iri=f"urn:autodev:capability:refine:{ref.method}",
                    title=f"Refine method: {ref.method}",
                    consequence=Consequence.READ,
                    binding=f"refine:{ref.method}",
                )
            )

        # 2. Ready primitive actions
        for trans in ready_action_transitions(self.domain, self.current_state):
            caps.append(
                Capability(
                    iri=f"urn:autodev:capability:action:{trans.action}",
                    title=f"Execute action: {trans.action}",
                    consequence=Consequence.DO,
                    binding=trans.action,
                )
            )

        return tuple(caps)

    def actuate(self, intent: ActuationIntent) -> Observation:
        """Advance the simulated state according to the selected intent."""
        self._step_counter += 1
        cap_str = intent.capability
        binding = cap_str.split(":")[-1]
        action_name = binding
        if cap_str.startswith("urn:autodev:capability:refine:"):
            method_name = cap_str.split(":")[-1]
            action_name = f"refine:{method_name}"

            # Apply method refinement
            refinements = method_refinements(self.domain, self.current_state)
            matching = [r for r in refinements if r.method == method_name]
            if not matching:
                return Observation(
                    state={"error": f"Refinement {method_name} not admissible"},
                    standing=Standing.REFUSED,
                )
            self.current_state = matching[0].successor
        else:
            # Apply ready primitive action
            transitions = ready_action_transitions(self.domain, self.current_state)
            matching_trans = [t for t in transitions if t.action == action_name]
            if not matching_trans:
                return Observation(
                    state={"error": f"Action {action_name} not admissible"},
                    standing=Standing.REFUSED,
                )
            # Outcome selection for nondeterministic (FOND) actions is an
            # explicit, documented oracle -- not a hidden sort preference
            # (AFDE-2602: the fail successor must be reachable).
            ordered = self._order_by_outcome_oracle(action_name, matching_trans)
            self.current_state = ordered[0].successor

        self._history.append((action_name, self.current_state))

        # Record OCEL event
        evt_id = f"evt_{self.episode_id}_{self._step_counter}"
        ts_ns = self._step_counter * 1_000_000_000
        self._recorded_events.append(
            OcelEvent(id=evt_id, activity=action_name, timestamp_ns=ts_ns)
        )

        state_dict = {
            "world": sorted(self.current_state.world),
            "tau": list(self.current_state.tau),
            "step": self._step_counter,
        }
        digest = hashlib.sha256(
            json.dumps(state_dict, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return Observation(
            episode_id=self.episode_id,
            state=state_dict,
            state_digest=digest,
        )

    def to_ocel_log(self) -> OcelLog:
        """Export the execution episode as a formal OCEL 2.0 log."""
        ep_obj = OcelObject(id=self.episode_id, object_type="AutoDevEpisode")
        links = [
            EventObjectLink(
                event_id=e.id, object_id=self.episode_id, qualifier="episode"
            )
            for e in self._recorded_events
        ]
        return OcelLog(
            events=tuple(self._recorded_events),
            objects=(ep_obj,),
            event_object_links=tuple(links),
        )


class AutoDevGymActProvider:
    """GymAct environment provider creating AutoDev simulation environments."""

    def __init__(self, domain: HDDLDomain) -> None:
        self.domain = domain

    def materialize(self, intent: MaterializationIntent) -> AutoDevGymActEnvironment:
        initial_state = intent.parameters.get("initial_state")
        if not isinstance(initial_state, ProductState):
            raise TypeError("intent.parameters['initial_state'] must be a ProductState")
        return AutoDevGymActEnvironment(
            domain=self.domain,
            initial_state=initial_state,
            episode_id=intent.world_id,
        )
