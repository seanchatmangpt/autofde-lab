# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `autofde_lab.reasoning.gymact_dspy_react`.

Real collaborators throughout:

- The real `autofde_lab.fabric.gymact_capability_gate.CapabilityGate`, real
  TOML parsing against the real, checked-in `gymact_capabilities.toml`.
- The real `dspy.ReAct` module and real `dspy.LM` (Groq-backed, live network
  call) for the end-to-end test -- named `skipif` on `GROQ_API_KEY`, never a
  mock substitute, per `.claude/rules/testing-chicago-style.md`.

The ONE test double is `_FakeSregymEnvironment`: a small, hand-written,
honest implementation of exactly the `actuate`/`teardown` surface this
module calls on its environment -- the same real-degraded-alternative
pattern `test_gymact_diagnosis_driver_chicago.py` uses (materializing a real
Kubernetes cluster + sregym conductor subprocess is genuinely infeasible in
a unit test). Every method really computes and returns real, deterministic
data; `call_log` records real, observable call order for state-based
assertions, never "was this called" interaction verification as the primary
check.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.
"""

from __future__ import annotations

import asyncio
import os

import dspy
import pytest

from autofde_lab.fabric.gymact_capability_gate import CapabilityGate, CapabilityRefused
from autofde_lab.reasoning.gymact_dspy_react import (
    DiagnosisResult,
    build_gated_react_tools,
    run_dspy_diagnosis,
)


class _FakeCapability:
    def __init__(self, binding: str) -> None:
        self.binding = binding


_FAKE_CAPABILITIES: tuple[_FakeCapability, ...] = (
    _FakeCapability("observe_cluster_state"),
    _FakeCapability("run_kubectl"),
    _FakeCapability("submit_diagnosis"),
    _FakeCapability("submit_mitigation"),
)


class _FakeSregymEnvironment:
    """Real, hand-written, honest fake of exactly the `actuate`/`teardown`
    surface `gymact_dspy_react.py` calls -- not gymact itself."""

    def __init__(self) -> None:
        self.call_log: list[str] = []
        self.kubectl_commands: list[str] = []
        self.torn_down = False
        self.last_diagnosis_payload: dict | None = None
        self.last_mitigation_payload: dict | None = None

    async def actuate(self, capability: _FakeCapability, payload: dict) -> dict:
        self.call_log.append(capability.binding)
        if capability.binding == "observe_cluster_state":
            return {"after": {"stage": "diagnosis"}}
        if capability.binding == "run_kubectl":
            command = payload.get("command", "")
            self.kubectl_commands.append(command)
            return {"result_text": [{"text": '{"items": [{"metadata": {"name": "api-0"}}]}'}]}
        if capability.binding == "submit_diagnosis":
            self.last_diagnosis_payload = dict(payload)
            return {"after": {"diagnosis": payload.get("diagnosis")}}
        if capability.binding == "submit_mitigation":
            self.last_mitigation_payload = dict(payload)
            return {"after": {"mitigation": payload.get("mitigation")}}
        raise AssertionError(f"unexpected real actuate() call for binding={capability.binding!r}")

    async def teardown(self) -> None:
        self.torn_down = True


# ---------------------------------------------------------------------------
# Structural: the gate really refuses an unlisted binding
# ---------------------------------------------------------------------------


def test_build_gated_react_tools_refuses_unlisted_capability(tmp_path) -> None:
    """A capability whose binding is missing from the manifest is really
    refused by the real CapabilityGate -- proving these tools are actually
    routed through the gate, not calling `environment.actuate` directly."""
    manifest = tmp_path / "capabilities.toml"
    manifest.write_text(
        '[gymact]\nenvironment = "sregym"\n\n'
        '[[capability]]\nname = "observe_cluster_state"\nconsequence = "READ"\nreason = "x"\n'
    )
    gate = CapabilityGate.from_toml(manifest)
    env = _FakeSregymEnvironment()
    tools = build_gated_react_tools(env, gate, _FAKE_CAPABILITIES, namespace="social-network")
    run_kubectl = next(t for t in tools if t.__name__ == "run_kubectl")

    with pytest.raises(CapabilityRefused):
        run_kubectl("get pods")

    # The refusal happened before any real actuate() call was made.
    assert env.call_log == []


# ---------------------------------------------------------------------------
# Structural: a real, allowed tool call really drives environment.actuate()
# ---------------------------------------------------------------------------


def test_build_gated_react_tools_run_kubectl_calls_real_actuate(tmp_path) -> None:
    manifest = tmp_path / "capabilities.toml"
    manifest.write_text(
        '[gymact]\nenvironment = "sregym"\n\n'
        '[[capability]]\nname = "run_kubectl"\nconsequence = "DO"\nreason = "x"\n'
    )
    gate = CapabilityGate.from_toml(manifest)
    env = _FakeSregymEnvironment()
    tools = build_gated_react_tools(env, gate, _FAKE_CAPABILITIES, namespace="social-network")
    run_kubectl = next(t for t in tools if t.__name__ == "run_kubectl")

    result_text = run_kubectl("get pods -o json")

    assert env.call_log == ["run_kubectl"]
    assert env.kubectl_commands == ["kubectl get pods -o json -n social-network"]
    assert "result_text" in result_text


def test_build_gated_react_tools_run_kubectl_respects_explicit_namespace(tmp_path) -> None:
    manifest = tmp_path / "capabilities.toml"
    manifest.write_text(
        '[gymact]\nenvironment = "sregym"\n\n'
        '[[capability]]\nname = "run_kubectl"\nconsequence = "DO"\nreason = "x"\n'
    )
    gate = CapabilityGate.from_toml(manifest)
    env = _FakeSregymEnvironment()
    tools = build_gated_react_tools(env, gate, _FAKE_CAPABILITIES, namespace="social-network")
    run_kubectl = next(t for t in tools if t.__name__ == "run_kubectl")

    run_kubectl("get pods -n other-namespace -o json")

    assert env.kubectl_commands == ["kubectl get pods -n other-namespace -o json"]


# ---------------------------------------------------------------------------
# Live Groq end-to-end: named skip, never a mock, when GROQ_API_KEY is unset
# ---------------------------------------------------------------------------

_GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

requires_real_groq_key = pytest.mark.skipif(
    not _GROQ_API_KEY,
    reason=(
        "GROQ_API_KEY is not set in this environment -- a real live Groq "
        "call is required for this test and no mock substitute is used "
        "per .claude/rules/testing-chicago-style.md."
    ),
)


@requires_real_groq_key
def test_live_groq_react_diagnosis_against_fake_environment() -> None:
    """Real end-to-end: a real dspy.ReAct loop, backed by a real Groq LM
    call, reasons over the gated tool surface against a real (fake-cluster)
    environment and produces a real submit_diagnosis call.

    The LM call is real and live (Groq); the Kubernetes cluster is the one
    real, named, infeasible-in-process exception
    (`_FakeSregymEnvironment`) -- exactly the same split
    `test_gymact_diagnosis_driver_chicago.py` uses.
    """
    lm = dspy.LM("groq/openai/gpt-oss-20b", api_key=_GROQ_API_KEY, cache=False)
    env = _FakeSregymEnvironment()

    result = asyncio.run(
        run_dspy_diagnosis(
            "wrong_dns_policy_social_network",
            mcp_server_port=0,
            api_port=0,
            namespace="social-network",
            max_iters=3,
            lm=lm,
            _environment_factory=lambda: _identity_async(env),
            _capabilities=_FAKE_CAPABILITIES,
        )
    )

    assert isinstance(result, DiagnosisResult)
    assert result.problem_id == "wrong_dns_policy_social_network"
    assert result.namespace == "social-network"
    assert result.diagnosis  # real, non-empty LM-produced text
    assert 0.0 <= result.confidence <= 1.0
    assert "submit_diagnosis" in env.call_log
    assert env.last_diagnosis_payload is not None
    assert env.last_diagnosis_payload["diagnosis"] == result.diagnosis
    assert env.torn_down is True
    # The real ReAct loop must have used at least one real tool call to
    # inspect the cluster before concluding -- not a zero-tool-call guess.
    assert any(binding in ("run_kubectl", "observe_cluster_state") for binding in env.call_log)


async def _identity_async(value):
    return value
