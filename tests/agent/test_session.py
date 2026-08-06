# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for :class:`skdecide.agent.session.AgentSession`.

Real ``Maze`` domain, real ``rollout``, real POWL executor. Nothing mocked.
"""

from __future__ import annotations

from typing import Any

import pytest

from skdecide.agent.models import EpochStanding
from skdecide.agent.refusals import (
    BLOCKED_ACTION_NODE_UNRESOLVED,
    AgentRefusal,
    AgentRefusalCode,
)
from skdecide.agent.epoch import DecisionEpoch
from skdecide.agent.session import AgentSession
from skdecide.hub.domain.maze import Maze
from skdecide.hub.domain.maze.maze import Action
from skdecide.powl.algebra import Atom, PartialOrder
from skdecide.powl.bounds import ExecutionBound

# ── fixtures: a scripted policy so the trace is deterministic ───────────────


class ScriptedPolicy:
    """Replays a fixed action list. Real object, not a mock."""

    def __init__(self, actions: list[Any]) -> None:
        self.actions = list(actions)
        self.index = 0

    def sample_action(self, observation: Any, domain: Any = None) -> Any:
        action = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return action

    def is_policy_defined_for(self, observation: Any) -> bool:
        return True


def _unordered(*labels: str) -> PartialOrder:
    """A partial order with no edges: every child is enabled at once."""
    return PartialOrder(tuple(Atom(label=label) for label in labels))


def _session(actions: list[Any], **kwargs: Any) -> AgentSession:
    return AgentSession(Maze(), ScriptedPolicy(actions), **kwargs)


# ── the session advances across two epochs ─────────────────────────────────


def test_session_advances_across_two_epochs():
    session = _session([Action.up, Action.right, Action.down, Action.left])

    session.open_epoch(_unordered("up", "right"))
    first = session.advance(max_steps=2)

    assert first.steps == 2
    assert sorted(first.trace) == ["right", "up"]
    assert first.standing is EpochStanding.ALIVE  # both atoms fired => final
    assert first.blocked_reason is None

    second_epoch = session.open_epoch(_unordered("down", "left"))
    second = session.advance(max_steps=2)

    assert second.epoch_id == second_epoch.epoch_id
    assert second.steps == 2
    assert sorted(second.trace) == ["down", "left"]
    assert second.standing is EpochStanding.ALIVE

    outcome = session.outcome()
    assert len(outcome.epochs) == 2
    assert outcome.standing is EpochStanding.ALIVE
    # Four committed occurrences across both epochs, none re-executed.
    assert len(session.ledger.occurrences()) == 4
    assert len({k.context_sha256 for k in session.ledger.occurrences()}) == 2


def test_a_partially_traversed_epoch_is_partial_alive_not_alive():
    session = _session([Action.up])
    session.open_epoch(_unordered("up", "right"))
    receipt = session.advance(max_steps=1)

    assert receipt.steps == 1
    assert receipt.standing is EpochStanding.PARTIAL_ALIVE
    assert session.outcome().standing is EpochStanding.PARTIAL_ALIVE


# ── the bound digest must change the outcome digest ────────────────────────


def test_bound_digest_changes_the_outcome_digest():
    def run(bound: ExecutionBound):
        session = _session(
            [Action.up, Action.right], bound=bound, session_id="fixed-session"
        )
        session.open_epoch(_unordered("up", "right"))
        session.advance(max_steps=2)
        return session.outcome()

    default = run(ExecutionBound())
    tighter = run(ExecutionBound(max_activity_fires=4))

    assert default.epochs[0].trace == tighter.epochs[0].trace  # same observed run
    assert default.input_sha256 != tighter.input_sha256
    assert default.receipt_sha256 != tighter.receipt_sha256


def test_same_bound_and_session_id_reproduce_the_same_digest():
    def run():
        session = _session(
            [Action.up, Action.right],
            bound=ExecutionBound(),
            session_id="fixed-session",
        )
        session.open_epoch(_unordered("up", "right"))
        session.advance(max_steps=2)
        return session.outcome()

    assert run().receipt_sha256 == run().receipt_sha256


# ── ACTION_NODE_UNRESOLVED ─────────────────────────────────────────────────


def test_action_node_unresolved_when_no_enabled_node_matches():
    session = _session([Action.left])  # model offers only "up"/"right"
    session.open_epoch(_unordered("up", "right"))
    receipt = session.advance(max_steps=1)

    assert receipt.standing is EpochStanding.BLOCKED
    assert receipt.blocked_reason == BLOCKED_ACTION_NODE_UNRESOLVED
    assert receipt.steps == 0
    # The refusal fired *before* any intent was written, so nothing is dangling.
    assert session.ledger.is_resumable() is True
    assert session.outcome().standing is EpochStanding.BLOCKED


def test_action_node_unresolved_when_two_enabled_nodes_share_a_label():
    """Action -> node is not injective here, and that is refused, never guessed."""
    session = _session([Action.up])
    session.open_epoch(_unordered("up", "up"))  # two identically-labelled atoms

    receipt = session.advance(max_steps=1)
    assert receipt.standing is EpochStanding.BLOCKED
    assert receipt.blocked_reason == BLOCKED_ACTION_NODE_UNRESOLVED
    assert receipt.steps == 0


def test_resolution_refusal_names_the_enabled_set_it_could_not_disambiguate():
    from skdecide.agent.bridge import resolve_enabled_node

    session = _session([])
    epoch = session.open_epoch(_unordered("up", "up"))
    with pytest.raises(AgentRefusal) as excinfo:
        resolve_enabled_node(epoch, Action.up)
    assert excinfo.value.code is AgentRefusalCode.ACTION_NODE_UNRESOLVED
    assert excinfo.value.details["matches"] == [[0], [1]]


# ── replan / supersede ─────────────────────────────────────────────────────


def test_replan_supersedes_the_previous_epoch_and_keeps_it_in_the_stack():
    session = _session([Action.up, Action.right, Action.down])
    first = session.open_epoch(_unordered("up", "right"))
    session.advance(max_steps=1)

    session.replan(_unordered("right", "down"), preserves=("right",))

    assert len(session.epochs) == 2  # append-only: nothing was popped
    assert session.epochs[0].epoch_id == first.epoch_id
    assert session.epochs[0].standing is EpochStanding.SUPERSEDED


def test_replan_that_drops_a_preserved_activity_is_refused():
    session = _session([Action.up])
    session.open_epoch(_unordered("up", "right"))
    with pytest.raises(AgentRefusal) as excinfo:
        session.replan(_unordered("down", "left"), preserves=("right",))
    assert excinfo.value.code is AgentRefusalCode.PRESERVATION_VIOLATED
    assert excinfo.value.details["missing"] == ["right"]


def test_advance_without_an_open_epoch_is_refused():
    session = _session([Action.up])
    with pytest.raises(AgentRefusal) as excinfo:
        session.advance(max_steps=1)
    assert excinfo.value.code is AgentRefusalCode.NO_OPEN_EPOCH


def test_supersedes_an_epoch_this_session_never_opened_is_refused():
    session = _session([])
    with pytest.raises(AgentRefusal) as excinfo:
        session.open_epoch(_unordered("up", "right"), supersedes=("not-an-epoch",))
    assert excinfo.value.code is AgentRefusalCode.UNKNOWN_SUPERSEDED_EPOCH


# ── envelope shape ─────────────────────────────────────────────────────────


def test_outcome_carries_the_claim_ceiling_and_is_json_shaped():
    from skdecide.agent.refusals import CLAIM_CEILING
    from skdecide.fabric.canonical import canonical_json

    session = _session([Action.up, Action.right])
    session.open_epoch(_unordered("up", "right"))
    session.advance(max_steps=2)
    outcome = session.outcome()

    assert outcome.claim_ceiling == CLAIM_CEILING
    assert "does not actuate" in outcome.claim_ceiling
    canonical_json(outcome.as_dict())  # must not raise
    assert outcome.epochs[0].evidence is not None
    assert len(outcome.epochs[0].evidence.steps) == 2


def test_session_random_is_seeded_from_session_id():
    a = _session([], session_id="seed-a")
    b = _session([], session_id="seed-a")
    c = _session([], session_id="seed-b")
    assert a.random.random() == b.random.random()
    assert a.random.random() != c.random.random()


def test_a_superseded_epoch_enables_nothing():
    """Containment must be structural, not a property of one call site.

    Every ``AgentSession`` mutator addresses ``_epochs[-1]``, so today no session
    API can fire from a superseded epoch. That is one call site holding the line.
    A caller holding a direct reference to the old epoch — the plan's own
    falsifier list names "superseded POWL0 still enabling activities" — must not
    be handed a live step set for a plan that has been replaced.
    """
    session = _session([Action.up, Action.right, Action.down])
    old = session.open_epoch(_unordered("up", "right"))
    assert sorted(old.enabled()) == [(0,), (1,)], "live before the replan"

    session.replan(_unordered("right", "down"), preserves=("right",))

    superseded = session.epochs[0]
    assert superseded.standing is EpochStanding.SUPERSEDED
    assert superseded.enabled() == frozenset()
    assert (
        EpochStanding.SUPERSEDED in DecisionEpoch.TERMINAL_STANDINGS
    ), "SUPERSEDED must be a terminal standing, not a label"
    # the new epoch is unaffected
    assert session.epochs[-1].enabled()


def test_only_standing_closes_an_epoch_the_model_is_untouched():
    """The refusal is about standing, not about the plan: restore the standing
    and the same epoch object enables the same set again. This pins that the
    containment is a gate, not a mutation of the marking."""
    session = _session([Action.up, Action.right, Action.down])
    session.open_epoch(_unordered("up", "right"))
    session.replan(_unordered("right", "down"), preserves=("right",))

    superseded = session.epochs[0]
    assert superseded.enabled() == frozenset()
    revived = superseded.with_standing(EpochStanding.UNKNOWN)
    assert sorted(revived.enabled()) == [(0,), (1,)]
    assert revived.marking == superseded.marking
