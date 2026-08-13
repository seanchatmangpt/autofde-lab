# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test pinning the 2026-08-12 fix to
`AzureGoatPrivescEnvironment.verify()` (`docs/jira/v26.8.12/cloud-cert-wbpr-
prd.md` Correction 4).

The defect: `verify()` used to call `self.observe()`, which reads
`self._state` -- the same in-process object `actuate()` mutates. That is a
self-report, not an independent check, and violates this repo's own
actor/verifier-independence rule (`cloud-cert-wbpr-prd.md`'s Non-functional
requirements table). No mocks: this test uses the real
`AzureGoatPrivescEnvironment`, the real `AzureGoatPrivilegeEscalation`
domain, and a real Astar-solved plan (via `AzureGoatPrivescEnvironment.
__init__`, unchanged) -- the only thing under test is whether `verify()`'s
verdict is independently re-derived from the real persisted `_action_log`
via `_replay_state_from_log()`, or blindly trusts `self._state`.

Real state-based assertion, not an interaction/call-count check: the second
test directly corrupts `self._state.facts` (the exact object `actuate()`
would have mutated) and asserts `verify()` detects the disagreement and
fails closed, rather than reporting the corrupted value as truth.
"""

from __future__ import annotations

import asyncio

from autofde_lab.hub.domain.azuregoat_privesc.azuregoat_privesc import GOAL_FACT, State
from autofde_lab.hub.domain.azuregoat_privesc.gymact_bridge import (
    AZUREGOAT_PRIVESC_CAPABILITIES,
    AzureGoatPrivescEnvironment,
)


def _run_full_plan(env: AzureGoatPrivescEnvironment) -> None:
    """Actuate every capability in the real environment's real solved plan
    order, exactly as `scripts/run_azuregoat_gymact_ocel_episode.py` does."""
    by_binding = {c.binding: c for c in AZUREGOAT_PRIVESC_CAPABILITIES}

    async def _run() -> None:
        for step_id in env._plan:
            await env.actuate(by_binding[step_id], {})

    asyncio.run(_run())


def test_verify_passes_after_real_plan_via_independent_replay() -> None:
    env = AzureGoatPrivescEnvironment()
    _run_full_plan(env)

    passed, observed = asyncio.run(env.verify({}))

    assert passed is True
    assert GOAL_FACT in observed["facts"]
    # The action log is real, persisted evidence of every step actually
    # applied -- present in verify()'s own output, not just internal state.
    assert observed["action_log"] == list(env._plan)
    assert "divergence" not in observed


def test_verify_fails_closed_when_live_state_diverges_from_replayed_log() -> None:
    """Directly tampers `self._state` -- the exact object the pre-fix
    `verify()` trusted -- while leaving the real `_action_log` untouched.
    A verify() that still just reads `self._state` would report the
    corrupted (wrong) value as truth. The fixed verify() must instead
    detect the disagreement between the real replayed log and the live
    object, and refuse to pass."""
    env = AzureGoatPrivescEnvironment()
    _run_full_plan(env)

    # Corrupt the live in-process state directly, as if some other bug
    # (or a malicious actor with in-process access) mutated it without
    # going through actuate(). The real action_log is untouched.
    env._state = State(facts=frozenset({"tampered_unrelated_fact"}))

    passed, observed = asyncio.run(env.verify({}))

    assert passed is False
    assert "divergence" in observed
    assert observed["divergence"]["live_state_facts"] == ["tampered_unrelated_fact"]
    # The independently-replayed facts (from the real, untampered action
    # log) still show the real goal was reached -- proving the replay path
    # is genuinely independent of the corrupted live object, not derived
    # from it.
    assert GOAL_FACT in observed["divergence"]["replayed_facts"]
