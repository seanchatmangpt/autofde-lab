# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real GymAct `EnvironmentProvider`/`Environment` bridge for the real
AzureGoat Module-1 privilege-escalation domain (`azuregoat_privesc.py`).

This is a real integration against the real, standalone `gymact` package
(installed as a real path dependency -- see `pyproject.toml`'s
`[tool.uv.sources]` and the `gymact` entry in `dependencies`), following
`~/gymact/docs/integrations/consumer-setup.md`'s checklist and structurally
matching `gymact.providers.MemoryProvider`/`MemoryEnvironment`, the reference
implementation documented there.

`materialize()` builds a real `AzureGoatPrivilegeEscalation` domain instance
and a real, C++-backed `Astar` solver (`autofde_lab.hub.solver.astar.astar.Astar`,
resolved the same way `tests/ecosystem/test_gymact_terragoat_bridge_chicago.py`
resolves it: `autofde_lab.utils.load_registered_solver("Astar")`), runs
`solver.solve()` for real, and replays the resulting policy from the real
initial state to derive a real, ordered 10-step plan -- exactly the manual's
documented step ordering (`ssh_login_vm` through `confirm_owner_role`), not a
hand-written sequence.

Every one of the ten `ATTACK_STEPS` is exposed as one `gymact.models.Capability`
classified `Consequence.DO`: each step is a real, world-changing actuation
against AzureGoat's documented attack surface (SSH login, `az login -i`,
rewriting and publishing an Owner-privileged runbook, starting it -- see that
module's own docstring), never `READ`. Per
`~/gymact/.claude/rules/actuation-authority.md` and this repo's own
consequence law (`request accepted != world changed != objective verified`),
`actuate()` refuses (raises `ActuationRefused`, never silently no-ops or
advances) any capability that is not the real solved plan's next step from
the real current state -- both the domain's own real precondition check
(`get_applicable_actions`) and the real plan cursor must agree, so neither an
inapplicable step nor an out-of-order-but-applicable step is silently
admitted.

`verify()` does NOT read `self._state` (the same in-process object `actuate()`
mutates) as its evidence -- that was a self-report bug, corrected 2026-08-12
per `docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` Correction 4 and this session's
own actor/verifier-independence ARD requirement. Instead `verify()`
independently replays the domain's real transition function
(`get_next_state`) over `self._action_log` -- an append-only record of every
step actually applied, written once by `actuate()` and never read back by it
-- starting from `get_initial_state()`, and cross-checks the replayed fact
set against `self._state.facts`, failing closed (returning `passed=False`
with the divergence detail) if the two disagree. This is a real, structurally
independent re-derivation, not a live external poll: no live Azure API is
reachable from this environment, so it cannot reach
`kubernetes_reconciliation.py`'s stronger "poll a live external system"
guarantee. It is documented here as a materially weaker but still genuinely
independent check, per this session's own no-overclaiming discipline --
future work with real Azure credentials should replace this with an actual
resource-state query. `checkpoint()`/`restore()` snapshot/restore the real
`(facts, plan_cursor, action_log)` triple. `teardown()` is a real, idempotent
no-op -- this domain holds no external resources (no subprocess, no network,
no filesystem handle) to release.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

from autofde_lab import utils

from .azuregoat_privesc import ATTACK_STEPS, GOAL_FACT, AzureGoatPrivilegeEscalation, State

AZUREGOAT_PRIVESC_CAPABILITIES: tuple[Capability, ...] = tuple(
    Capability(
        iri=f"urn:gymact:azuregoat-privesc:capability:{step.id}",
        title=f"{step.manual_step}: {step.description}",
        consequence=Consequence.DO,
        binding=step.id,
    )
    for step in ATTACK_STEPS
)


class ActuationRefused(RuntimeError):
    """Raised when `actuate()` is asked to run a capability that is not the
    real next applicable step of the real solved plan from the real current
    state -- never silently allowed, per
    `~/gymact/.claude/rules/actuation-authority.md`.
    """


class AzureGoatPrivescEnvironment:
    """One materialized instance of the real AzureGoat Module-1
    privilege-escalation domain, with a real solved plan and real internal
    fact-set state advanced by real, precondition-checked actuation.
    """

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:gymact:azuregoat-privesc:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._domain = AzureGoatPrivilegeEscalation()
        self._closed = False

        astar_cls = utils.load_registered_solver("Astar")
        plan: list[str] = []
        with astar_cls(domain_factory=lambda: self._domain) as solver:
            solver.solve()
            obs = self._domain.get_initial_state()
            for _ in range(len(self._domain.steps) + 1):
                if self._domain.is_goal(obs):
                    break
                action = solver.sample_action(obs)
                plan.append(action)
                obs = self._domain.get_next_state(obs, action)

        if not self._domain.is_goal(obs):
            raise RuntimeError(
                "real Astar solve did not reach the AzureGoat privesc goal "
                f"{GOAL_FACT!r}; computed partial plan: {plan}"
            )

        self._plan: tuple[str, ...] = tuple(plan)
        self._state: State = self._domain.get_initial_state()
        self._plan_cursor = 0
        # Append-only record of every step_id actually applied by actuate(),
        # in order. verify() replays the domain's transition function over
        # this log independently of `self._state` -- see module docstring
        # ("verify() does NOT read self._state...") for why this exists.
        self._action_log: list[str] = []

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return AZUREGOAT_PRIVESC_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {"facts": sorted(self._state.facts)}

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        step_id = capability.binding
        try:
            step = self._domain.describe_step(step_id)
        except KeyError:
            raise ActuationRefused(
                f"refused: {step_id!r} is not a real AzureGoat privesc attack step"
            ) from None

        applicable_ids = {
            a for a in self._domain.get_applicable_actions(self._state).get_elements()
        }
        if step_id not in applicable_ids:
            raise ActuationRefused(
                f"refused: {step_id!r} is not applicable from the real current state "
                f"{sorted(self._state.facts)!r} (preconditions "
                f"{sorted(step.preconditions)!r} unmet, or already established)"
            )

        expected_next = self._plan[self._plan_cursor] if self._plan_cursor < len(self._plan) else None
        if step_id != expected_next:
            raise ActuationRefused(
                f"refused: {step_id!r} is applicable but is not the real solved "
                f"plan's next step (expected {expected_next!r} at plan cursor "
                f"{self._plan_cursor})"
            )

        before = self._state
        next_state = self._domain.get_next_state(before, step_id)
        self._state = next_state
        self._plan_cursor += 1
        self._action_log.append(step_id)
        return {
            "before": {"facts": sorted(before.facts)},
            "after": {"facts": sorted(next_state.facts)},
            "capability": capability.iri,
            "manual_step": step.manual_step,
            "established": step.establishes,
        }

    def _replay_state_from_log(self) -> State:
        """Independently re-derive the current fact-set by replaying the
        domain's real transition function over `self._action_log` from a
        fresh `get_initial_state()` -- never reads `self._state` directly.
        This is what makes `verify()` a genuine re-derivation rather than a
        self-report of the same object `actuate()` mutated.
        """
        state = self._domain.get_initial_state()
        for step_id in self._action_log:
            state = self._domain.get_next_state(state, step_id)
        return state

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        replayed = self._replay_state_from_log()
        replayed_facts = sorted(replayed.facts)
        live_facts = sorted(self._state.facts)
        divergence = None if replayed_facts == live_facts else {
            "replayed_facts": replayed_facts,
            "live_state_facts": live_facts,
        }
        observed: dict[str, Any] = {"facts": replayed_facts, "action_log": list(self._action_log)}
        if divergence is not None:
            # Fail closed: the independently-replayed state disagrees with
            # the live in-process object. Never silently prefer one.
            observed["divergence"] = divergence
            return False, observed
        if "facts" in expected:
            expected_facts = set(expected["facts"])
            passed = expected_facts <= set(replayed_facts)
        else:
            passed = GOAL_FACT in replayed_facts
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "facts": sorted(self._state.facts),
            "plan_cursor": self._plan_cursor,
            "action_log": list(self._action_log),
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._state = State(facts=frozenset(checkpoint["facts"]))
        self._plan_cursor = int(checkpoint.get("plan_cursor", 0))
        self._action_log = list(checkpoint.get("action_log", []))

    async def teardown(self) -> None:
        # Real, idempotent no-op: this domain holds no external resource
        # (no subprocess, no network socket, no filesystem handle) that
        # needs releasing -- unlike e.g. gymact.gyms.kubernetes_reconciliation,
        # which tears down a real cluster object. Safe to call repeatedly.
        self._closed = True


class AzureGoatPrivescProvider:
    """Real `gymact.providers.EnvironmentProvider` that materializes the real
    AzureGoat Module-1 privilege-escalation domain (structurally matching
    `gymact.providers.MemoryProvider`, the documented reference shape).
    """

    name = "azuregoat_privesc"
    materialization_requires_authority = False

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.requires_authority = requires_authority

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> AzureGoatPrivescEnvironment:
        del scenario
        configured = config.get("requires_authority", self.requires_authority)
        if not isinstance(configured, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return AzureGoatPrivescEnvironment(requires_authority=configured)
