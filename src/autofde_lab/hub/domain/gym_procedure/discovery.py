"""Autonomous procedure discovery from observations and opaque capabilities.

This module belongs to the Hub SELECT plane. It never imports a recipe, source
walkthrough, provider transition model, or execution runtime. Consequential probes
are opaque requests to an external harness; this module only selects candidate
actions from receipted observations and carries no execution authority.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

FactState = frozenset[str]
ActionId = str
Plan = tuple[ActionId, ...]


class DiscoveryRefused(RuntimeError):
    """The bounded observable state graph does not contain a verified goal path."""


@dataclass(frozen=True)
class DiscoveryChallenge:
    """All information admitted to the discovery planner."""

    subject: str
    initial_facts: FactState
    goal_facts: FactState
    action_ids: tuple[ActionId, ...]
    max_states: int = 100_000
    max_probes: int = 1_000_000

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("DISCOVERY_SUBJECT_REQUIRED")
        if not self.goal_facts:
            raise ValueError("DISCOVERY_GOAL_REQUIRED")
        if not self.action_ids:
            raise ValueError("DISCOVERY_CAPABILITIES_REQUIRED")
        if len(set(self.action_ids)) != len(self.action_ids):
            raise ValueError("DISCOVERY_CAPABILITIES_MUST_BE_UNIQUE")
        if self.max_states < 1 or self.max_probes < 1:
            raise ValueError("DISCOVERY_BOUNDS_MUST_BE_POSITIVE")


@dataclass(frozen=True)
class ProbeEvidence:
    """Observed result of one externally executed, receipted probe."""

    action_id: ActionId
    prefix: Plan
    accepted: bool
    before_facts: FactState
    after_facts: FactState
    standing: str
    receipt_ids: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class LearnedTransition:
    before_facts: FactState
    action_id: ActionId
    after_facts: FactState
    receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryResult:
    subject: str
    plan: Plan
    goal_state: FactState
    probes: int
    rejected_probes: int
    visited_states: int
    learned_transitions: tuple[LearnedTransition, ...]
    evidence_receipt_ids: tuple[str, ...]


Probe = Callable[[Plan, ActionId], Awaitable[ProbeEvidence]]


async def discover_procedure(
    challenge: DiscoveryChallenge,
    probe: Probe,
) -> DiscoveryResult:
    """Discover a shortest observed goal path by bounded black-box BFS.

    The search has no transition model. For each reached state it asks the
    external harness to execute an opaque action from a replayable prefix.
    Failed actions are topology evidence; accepted actions manufacture observed
    graph edges. No provider failure is interpreted as global graph failure.
    """

    if challenge.goal_facts <= challenge.initial_facts:
        return DiscoveryResult(
            subject=challenge.subject,
            plan=(),
            goal_state=challenge.initial_facts,
            probes=0,
            rejected_probes=0,
            visited_states=1,
            learned_transitions=(),
            evidence_receipt_ids=(),
        )

    queue: deque[tuple[FactState, Plan]] = deque([(challenge.initial_facts, ())])
    seen: set[FactState] = {challenge.initial_facts}
    learned: list[LearnedTransition] = []
    evidence_ids: list[str] = []
    probes = 0
    rejected = 0

    while queue:
        state, prefix = queue.popleft()
        for action_id in challenge.action_ids:
            if probes >= challenge.max_probes:
                raise DiscoveryRefused("DISCOVERY_PROBE_BOUND_EXHAUSTED")

            observed = await probe(prefix, action_id)
            probes += 1

            if observed.action_id != action_id or observed.prefix != prefix:
                raise DiscoveryRefused("DISCOVERY_EVIDENCE_IDENTITY_MISMATCH")
            if observed.before_facts != state:
                raise DiscoveryRefused("DISCOVERY_REPLAY_STATE_MISMATCH")
            if not observed.receipt_ids:
                raise DiscoveryRefused("UNRECEIPTED_DISCOVERY_PROBE_REFUSED")
            evidence_ids.extend(observed.receipt_ids)

            if not observed.accepted:
                rejected += 1
                continue

            after = observed.after_facts
            learned.append(
                LearnedTransition(
                    before_facts=state,
                    action_id=action_id,
                    after_facts=after,
                    receipt_ids=observed.receipt_ids,
                )
            )
            candidate = prefix + (action_id,)

            if challenge.goal_facts <= after:
                return DiscoveryResult(
                    subject=challenge.subject,
                    plan=candidate,
                    goal_state=after,
                    probes=probes,
                    rejected_probes=rejected,
                    visited_states=len(seen) + (after not in seen),
                    learned_transitions=tuple(learned),
                    evidence_receipt_ids=tuple(evidence_ids),
                )

            if after == state or after in seen:
                continue
            if len(seen) >= challenge.max_states:
                raise DiscoveryRefused("DISCOVERY_STATE_BOUND_EXHAUSTED")
            seen.add(after)
            queue.append((after, candidate))

    raise DiscoveryRefused("DISCOVERY_GOAL_UNREACHABLE_WITH_OBSERVED_CAPABILITIES")
