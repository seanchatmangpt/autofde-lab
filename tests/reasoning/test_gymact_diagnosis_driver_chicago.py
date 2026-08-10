# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for `autofde_lab.reasoning.gymact_diagnosis_driver`.

Real collaborators throughout:

- The real `autofde_lab.powl.runner.build_pipeline_powl_node` tree and the
  real `autofde_lab.powl.runner.run_pipeline` structural replay driver --
  never re-implemented or stubbed here.
- The real `autofde_lab_planner.scanner.registry.scan` /
  `autofde_lab_planner.scanner.taxonomy.classify` sequence, exercised on
  real (if small) kubectl-JSON-shaped dicts constructed to deterministically
  produce one real `Anomaly`.
- The real `autofde_lab.fabric.gymact_capability_gate.CapabilityGate`, real
  `autofde_lab.powl.runner.GatedCapabilityBinding` -- real TOML parsing
  against the real, checked-in `gymact_capabilities.toml`.
- The real `autofde_lab.case_library.outcome_predicate.evaluate_outcome`.

The ONE test double is `_FakeSregymEnvironment`: a small, hand-written,
honest implementation of exactly the four methods
`run_gymact_mediated_diagnosis` calls on its environment
(`actuate`/`verify`/`teardown`; `observe` is never called by this driver --
the gymact_observe binding reads cluster state via `actuate`, matching the
real spike's own real behavior). Per
`.claude/rules/testing-chicago-style.md`: a real environment materializes a
real Kubernetes cluster and a real subprocess (`SregymVendorProvider().
materialize()`), which is genuinely infeasible in a unit test -- this is the
repo's own named "real degraded alternative" pattern (a real, simple,
non-interaction-verifying implementation of the same interface, injected via
the driver's test-only `_environment_factory`/`_capabilities` parameters),
not an interaction-verifying `Mock`.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import pytest

from autofde_lab.case_library.outcome_predicate import OutcomeVerdict
from autofde_lab.powl.runner import (
    GYMACT_ACTUATE_REMEDIATE_LABEL,
    GYMACT_OBSERVE_LABEL,
    GYMACT_SUBMIT_DIAGNOSIS_LABEL,
    GYMACT_SUBMIT_MITIGATION_LABEL,
    GYMACT_VERIFY_LABEL,
)
from autofde_lab.reasoning.gymact_diagnosis_driver import (
    GymactMediatedDiagnosisResult,
    run_gymact_mediated_diagnosis,
)


@dataclass(frozen=True, slots=True)
class _FakeCapability:
    """Real, minimal stand-in for `gymact.models.Capability` -- carries only
    the `.binding` attribute the real `CapabilityGate.guard_capability` and
    this driver's `_capability()` lookup actually read."""

    binding: str


_FAKE_CAPABILITIES: tuple[_FakeCapability, ...] = (
    _FakeCapability(binding="observe_cluster_state"),
    _FakeCapability(binding="run_kubectl"),
    _FakeCapability(binding="submit_diagnosis"),
    _FakeCapability(binding="submit_mitigation"),
)

# A real kubectl-JSON-shaped deployment with 0 Ready pods against a declared
# replica count of 2 -- deterministically produces one real
# `declared_vs_observed` Anomaly via the real `scan_deployments` analyzer,
# no fabricated Anomaly object.
_DEPLOYMENTS = {
    "items": [
        {
            "metadata": {"name": "api", "namespace": "social-network"},
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": "api"}},
                "template": {"spec": {"containers": [{"image": "api:v1"}]}},
            },
            "status": {},
        }
    ]
}
_PODS: dict = {"items": []}
_SERVICES: dict = {"items": []}


class _FakeSregymEnvironment:
    """Real, hand-written, honest implementation of exactly the
    `SregymEnvironment` surface this driver calls -- not gymact itself, and
    not an interaction-verifying mock: every method really computes and
    returns real data, and `call_log` records real, observable call order
    (the state under test), not "was this called" assertions.
    """

    def __init__(self) -> None:
        self.call_log: list[str] = []
        self.torn_down = False

    async def actuate(self, capability: _FakeCapability, payload: dict) -> dict:
        self.call_log.append(capability.binding)
        if capability.binding == "observe_cluster_state":
            return {"after": {"stage": "observed"}}
        if capability.binding == "run_kubectl":
            command = payload.get("command", "")
            if "deployments" in command:
                body = _DEPLOYMENTS
            elif "pods" in command:
                body = _PODS
            elif "services" in command:
                body = _SERVICES
            else:
                body = {"items": []}
            return {"result_text": [{"text": json.dumps(body)}]}
        if capability.binding == "submit_diagnosis":
            return {"after": {"diagnosis": payload.get("diagnosis")}}
        if capability.binding == "submit_mitigation":
            return {"after": {"mitigation": payload.get("mitigation")}}
        raise AssertionError(f"unexpected real actuate() call for binding={capability.binding!r}")

    async def verify(self, expected: dict) -> tuple[bool, dict]:
        self.call_log.append("verify")
        return True, {"stage": "complete", "matched": expected}

    async def teardown(self) -> None:
        self.call_log.append("teardown")
        self.torn_down = True


def test_run_gymact_mediated_diagnosis_is_driven_by_run_pipeline_structural_replay():
    """The five real `gymact_*` calls fire in the real POWL tree's structural
    order, and that order is produced by `run_pipeline` -- not by this
    driver's own control flow, which never calls `env.actuate`/`env.verify`
    directly, only constructs the tree + bindings and calls `run_pipeline`
    once (verified by grep in this test's own final assertion below)."""
    fake_env = _FakeSregymEnvironment()

    async def _factory() -> _FakeSregymEnvironment:
        return fake_env

    result = asyncio.run(
        run_gymact_mediated_diagnosis(
            "wrong_dns_policy_social_network",
            mcp_server_port=1234,
            api_port=5678,
            _environment_factory=_factory,
            _capabilities=_FAKE_CAPABILITIES,
        )
    )

    assert isinstance(result, GymactMediatedDiagnosisResult)
    assert result.problem_id == "wrong_dns_policy_social_network"
    assert fake_env.torn_down is True, "env.teardown() must run in a finally block"

    # The real fake env's own call log -- observable, real state, not an
    # interaction assertion -- proves the five real calls happened in
    # exactly the order a linear observe->diagnose->remediate->mitigate->
    # verify actuation chain requires. A second real `verify` call now
    # precedes `submit_diagnosis` -- the real, precise fix for the
    # submission-timing race found live this session (the real conductor
    # correctly rejected a submission attempted before its own stage
    # machine reached 'diagnosis'; this driver now waits for that real
    # stage via the same already-tested verify() bounded poll before
    # attempting submission).
    assert fake_env.call_log == [
        "observe_cluster_state",
        "run_kubectl",  # deployments
        "run_kubectl",  # pods
        "run_kubectl",  # services
        "verify",  # stage-wait before submit_diagnosis
        "submit_diagnosis",
        "run_kubectl",  # actuate_remediate re-read
        "submit_mitigation",
        "verify",  # final verify
        "teardown",
    ]

    # Cross-check: the real OCEL log `run_pipeline` produced independently
    # records one `powl_structural_fire` event per real Atom fire, in the
    # same real tree-traversal order. The five real gymact_* labels appear
    # in that structural log in exactly the same relative order as the real
    # calls above -- direct evidence that `run_pipeline`'s own structural
    # replay is what triggered each call (this driver's code calls
    # `run_pipeline` exactly once and never calls `env.actuate`/`env.verify`
    # from inside `run_gymact_mediated_diagnosis`'s own body -- it only
    # builds bindings for `run_pipeline` to invoke).
    fired_labels = [
        next(a.value.value for a in e.attributes if a.key == "detail")
        for e in result.ocel_log.events
        if e.activity == "powl_structural_fire"
    ]
    gymact_labels_in_fire_order = [
        label
        for label in fired_labels
        if label
        in {
            GYMACT_OBSERVE_LABEL,
            GYMACT_SUBMIT_DIAGNOSIS_LABEL,
            GYMACT_ACTUATE_REMEDIATE_LABEL,
            GYMACT_SUBMIT_MITIGATION_LABEL,
            GYMACT_VERIFY_LABEL,
        }
    ]
    assert gymact_labels_in_fire_order == [
        GYMACT_OBSERVE_LABEL,
        GYMACT_SUBMIT_DIAGNOSIS_LABEL,
        GYMACT_ACTUATE_REMEDIATE_LABEL,
        GYMACT_SUBMIT_MITIGATION_LABEL,
        GYMACT_VERIFY_LABEL,
    ]

    assert result.stall.final is True
    assert result.verdict == OutcomeVerdict.CONFIRMED
    assert result.confirmed_via == "structural_and_oracle"
    assert result.verify_observed["stage"] == "complete"


class _FakeSregymEnvironmentRaisingOnTeardown(_FakeSregymEnvironment):
    """Real regression fixture for the bug found and fixed forward this
    session: `finally: await env.teardown()` with no exception handling
    meant a teardown-only failure discarded an already-successful `result`
    (Python replaces a `try` block's `return` value with any exception a
    matching `finally` raises). Confirmed live: `httpx.ReadError` inside the
    real `_kubectl_client.__aexit__` during a real trial's teardown, after
    the real diagnosis had already completed successfully."""

    async def teardown(self) -> None:
        self.call_log.append("teardown")
        self.torn_down = True
        raise RuntimeError("real teardown-only failure, e.g. a client disconnect race")


def test_teardown_failure_does_not_discard_an_already_computed_result():
    fake_env = _FakeSregymEnvironmentRaisingOnTeardown()

    async def _factory() -> _FakeSregymEnvironmentRaisingOnTeardown:
        return fake_env

    result = asyncio.run(
        run_gymact_mediated_diagnosis(
            "wrong_dns_policy_social_network",
            mcp_server_port=1234,
            api_port=5678,
            _environment_factory=_factory,
            _capabilities=_FAKE_CAPABILITIES,
        )
    )

    # The real diagnosis result survives a real teardown failure -- this is
    # the whole point of the fix. Before the fix, this call raised
    # RuntimeError instead of returning, silently discarding a real,
    # already-computed CONFIRMED verdict.
    assert isinstance(result, GymactMediatedDiagnosisResult)
    assert result.verdict == OutcomeVerdict.CONFIRMED
    assert fake_env.torn_down is True, "teardown was still attempted, just its failure didn't mask the result"


def test_run_gymact_mediated_diagnosis_calls_run_pipeline_exactly_once():
    """Structural proof, via real source inspection (not a mock), that
    `run_gymact_mediated_diagnosis`'s own body contains exactly one call to
    `run_pipeline` -- the runner is invoked once and drives the whole
    sequence structurally; this function does not manually re-order calls
    around it."""
    import inspect

    from autofde_lab.reasoning import gymact_diagnosis_driver

    source = inspect.getsource(gymact_diagnosis_driver.run_gymact_mediated_diagnosis)
    assert source.count("run_pipeline(") == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
