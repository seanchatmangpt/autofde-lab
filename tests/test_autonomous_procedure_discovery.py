from __future__ import annotations

import pytest

from autofde_lab.hub.domain.gym_procedure.discovery import (
    DiscoveryChallenge,
    DiscoveryRefused,
    ProbeEvidence,
    discover_procedure,
)


@pytest.mark.asyncio
async def test_discovers_without_transition_model_and_preserves_failed_edges() -> None:
    challenge = DiscoveryChallenge(
        subject="held-out/task",
        initial_facts=frozenset({"start"}),
        goal_facts=frozenset({"done"}),
        action_ids=("opaque-b", "opaque-a"),
    )
    hidden = {
        "opaque-a": (frozenset({"start"}), frozenset({"middle"})),
        "opaque-b": (frozenset({"middle"}), frozenset({"done"})),
    }

    async def probe(prefix: tuple[str, ...], action_id: str) -> ProbeEvidence:
        state = frozenset({"start"})
        for prior in prefix:
            required, effect = hidden[prior]
            assert required <= state
            state |= effect
        required, effect = hidden[action_id]
        accepted = required <= state and not effect <= state
        after = state | effect if accepted else state
        return ProbeEvidence(
            action_id=action_id,
            prefix=prefix,
            accepted=accepted,
            before_facts=state,
            after_facts=after,
            standing="ALIVE" if accepted else "BLOCKED",
            receipt_ids=(f"receipt:{len(prefix)}:{action_id}",),
            reason=None if accepted else "PRECONDITION_REFUSED",
        )

    result = await discover_procedure(challenge, probe)
    assert result.plan == ("opaque-a", "opaque-b")
    assert challenge.goal_facts <= result.goal_state
    assert result.rejected_probes >= 1
    assert result.evidence_receipt_ids


@pytest.mark.asyncio
async def test_refuses_unreceipted_probe_evidence() -> None:
    challenge = DiscoveryChallenge(
        subject="held-out/task",
        initial_facts=frozenset({"start"}),
        goal_facts=frozenset({"done"}),
        action_ids=("opaque-a",),
    )

    async def probe(prefix: tuple[str, ...], action_id: str) -> ProbeEvidence:
        return ProbeEvidence(
            action_id=action_id,
            prefix=prefix,
            accepted=True,
            before_facts=frozenset({"start"}),
            after_facts=frozenset({"start", "done"}),
            standing="ALIVE",
            receipt_ids=(),
        )

    with pytest.raises(DiscoveryRefused, match="UNRECEIPTED_DISCOVERY_PROBE_REFUSED"):
        await discover_procedure(challenge, probe)
