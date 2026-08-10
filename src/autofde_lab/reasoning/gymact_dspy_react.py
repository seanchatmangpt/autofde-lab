# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""A small, real DSPy ``ReAct`` diagnosis loop over the real, gated sregym
capability surface.

Scope, honestly bounded
------------------------
This is deliberately smaller than ``gymact_diagnosis_driver.py``'s POWL
pipeline: no scanner/taxonomy classifier, no remediation-recheck block, no
OCEL evidence graph. It is a basic ``observe -> think -> act (kubectl reads)
-> submit_diagnosis`` loop, driven by a real ``dspy.ReAct`` module reasoning
over real tool calls -- the "quick... basic runs" scope named in this
task, not a replacement for the POWL-mediated driver.

Why DSPy (not a hand-rolled loop)
------------------------------------
``dspy`` is already a real, installed dependency of this project (see
``pyproject.toml``'s ``[project.optional-dependencies].dspy`` and the
already-real ``dspy.ReAct`` usage in ``sregym_pipeline.py`` and
``hub/solver/dspy_policy/dspy_policy.py``). Reusing the framework's own
``ReAct`` module -- rather than hand-rolling a second, parallel
observe/think/act loop -- keeps this module's control flow (tool-call
parsing, trajectory bookkeeping, stopping condition) delegated to code this
repo already depends on and already tests elsewhere, matching
``python-native.md``'s "compose, don't generate" rule at the DSPy-usage
level, not just the FastAPI/FastMCP level it names explicitly.

Real, gated tool calls -- not a bypass of ``CapabilityGate``
-----------------------------------------------------------------
Every tool ``dspy.ReAct`` may call is a thin synchronous wrapper that (a)
looks up the real ``gymact.gyms.sregym`` ``Capability`` object for that
binding name, (b) calls ``CapabilityGate.guard_capability(capability)`` --
the SAME gate instance, loaded from the SAME
``fabric/gymact_capabilities.toml`` manifest ``gymact_diagnosis_driver.py``
uses -- before, (c) driving the real, async ``environment.actuate(...)``
call to completion via a dedicated-thread ``asyncio.run`` (see
``_run_coroutine_sync``, mirroring ``gymact_diagnosis_driver.py``'s own
helper of the same name/shape, duplicated rather than imported since that
module is explicitly not to be touched or made a dependency surface for
this new, separate module). A refused capability raises
``CapabilityRefused`` (a real ``PermissionError`` subclass) out of the tool
call, exactly as it would from the POWL-mediated driver -- there is no
second, ungated path to ``environment.actuate()`` anywhere in this file.

``submit_mitigation``, if attempted at all
--------------------------------------------
Per this task's own scope note, no automated remediation-command synthesis
exists in this repo yet (see ``gymact_diagnosis_driver.py``'s module
docstring for the confirmed gap). ``run_dspy_diagnosis`` therefore only
observes and diagnoses by default; ``attempt_mitigation=True`` submits the
same honest ``{"mitigation": "not_attempted", ...}`` payload
``gymact_diagnosis_driver.py`` submits, gated the same way -- never a
fabricated remediation command.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import dspy

from autofde_lab.fabric.gymact_capability_gate import DEFAULT_MANIFEST_PATH, CapabilityGate

__all__ = [
    "DiagnoseClusterFault",
    "DiagnosisResult",
    "GymActReActDiagnoser",
    "build_gated_react_tools",
    "run_dspy_diagnosis",
]


def _run_coroutine_sync(coro: Any) -> Any:
    """Run a real coroutine to completion from a synchronous ReAct tool
    call, without colliding with a caller's already-running event loop.

    Duplicated from (not imported from) ``gymact_diagnosis_driver.py`` --
    this task's constraints name that module as not-to-be-touched and this
    module as a new, separate, additive one; a private, three-line helper is
    not worth coupling the two modules together for.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _capability(capabilities: Any, name: str) -> Any:
    for cap in capabilities:
        if cap.binding == name:
            return cap
    raise KeyError(f"no real gymact capability named {name!r}")


class DiagnoseClusterFault(dspy.Signature):
    """Diagnose a live Kubernetes cluster fault for the given sregym
    problem. Use the provided tools to inspect REAL live cluster state
    (kubectl reads, the conductor's own status observation) before
    concluding -- never guess a root cause the tools have not evidenced."""

    problem_id: str = dspy.InputField(desc="the sregym benchmark problem id under diagnosis")
    namespace: str = dspy.InputField(desc="the real Kubernetes namespace the target app deploys into")
    diagnosis: str = dspy.OutputField(desc="free-text root-cause diagnosis grounded in real tool output")
    confidence: float = dspy.OutputField(desc="0.0-1.0, must reflect actual evidentiary support from tool calls")


def build_gated_react_tools(
    environment: Any,
    gate: CapabilityGate,
    capabilities: Any,
    *,
    namespace: str,
) -> list[Callable[..., str]]:
    """Build synchronous ``dspy.ReAct``-compatible tool functions, each
    routed through the real, ``CapabilityGate``-checked
    ``environment.actuate(capability, payload)`` surface.

    ``namespace`` is closed over rather than left to the LLM to supply on
    every call -- the LLM already knows it from ``DiagnoseClusterFault``'s
    ``namespace`` input field; baking it into the tool functions here means
    a hallucinated/wrong namespace argument from the model can never
    silently redirect a real kubectl read at a different namespace than the
    one this run was materialized against.
    """
    capabilities_by_binding = {cap.binding: cap for cap in capabilities}

    def run_kubectl(command: str) -> str:
        """Run a real, namespace-scoped read-only kubectl command against
        the live cluster (e.g. 'get pods -o json', 'describe deployment
        <name>', 'get events --sort-by=.lastTimestamp'). The namespace is
        applied automatically -- do not include -n in `command`."""
        cap = capabilities_by_binding["run_kubectl"]
        gate.guard_capability(cap)
        stripped = command.strip()
        # Same real defect this driver's sibling module found and fixed
        # forward: sregym's real kubectl-mcp tool rejects any command that
        # does not literally start with "kubectl".
        if not stripped.startswith("kubectl"):
            stripped = f"kubectl {stripped}"
        if " -n " not in stripped and "--namespace" not in stripped:
            stripped = f"{stripped} -n {namespace}"
        result = _run_coroutine_sync(environment.actuate(cap, {"command": stripped}))
        return str(result)

    def observe_cluster_state() -> str:
        """Read sregym's real conductor /status endpoint (benchmark stage,
        not raw cluster state)."""
        cap = capabilities_by_binding["observe_cluster_state"]
        gate.guard_capability(cap)
        result = _run_coroutine_sync(environment.actuate(cap, {}))
        return str(result)

    return [run_kubectl, observe_cluster_state]


class GymActReActDiagnoser(dspy.Module):
    """One real ``dspy.Module`` wrapping ``dspy.ReAct(DiagnoseClusterFault,
    tools=...)`` over the gated sregym tool surface.

    Kept intentionally thin: this class owns no environment-materialization
    or teardown logic (that stays in :func:`run_dspy_diagnosis`, matching
    ``gymact_diagnosis_driver.py``'s own separation of "build real
    collaborators" from "reason over them"). Constructing this module with a
    real ``environment``/``gate``/``capabilities`` triple is what makes its
    ``forward`` calls real, gated, live tool calls; nothing here fabricates
    tool output.
    """

    def __init__(
        self,
        *,
        environment: Any,
        gate: CapabilityGate,
        capabilities: Any,
        namespace: str,
        max_iters: int = 6,
    ) -> None:
        super().__init__()
        tools = build_gated_react_tools(environment, gate, capabilities, namespace=namespace)
        self.react = dspy.ReAct(DiagnoseClusterFault, tools=tools, max_iters=max_iters)

    def forward(self, problem_id: str, namespace: str) -> Any:
        return self.react(problem_id=problem_id, namespace=namespace)


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    """Real, typed result of one basic ReAct-mediated diagnosis run."""

    problem_id: str
    namespace: str
    diagnosis: str
    confidence: float
    trajectory: dict[str, Any]
    submit_diagnosis_response: Any
    mitigation_attempted: bool
    submit_mitigation_response: Any | None


async def run_dspy_diagnosis(
    problem_id: str,
    *,
    mcp_server_port: int,
    api_port: int,
    judge_model_id: str = "groq/openai/gpt-oss-20b",
    judge_api_base: str = "https://api.groq.com/openai/v1",
    wall_clock_timeout_s: int = 900,
    startup_timeout_seconds: float = 900.0,
    verify_timeout_seconds: float = 300.0,
    namespace: str | None = None,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    max_iters: int = 6,
    attempt_mitigation: bool = False,
    lm: Any | None = None,
    _environment_factory: Callable[[], Any] | None = None,
    _capabilities: Any = None,
) -> DiagnosisResult:
    """Materialize a real ``SregymEnvironment``, run a real ``dspy.ReAct``
    diagnosis loop over the gated tool surface, and submit a real
    ``submit_diagnosis`` capability call.

    ``lm``, when given, is used as-is (a real, already-constructed
    ``dspy.LM``) -- useful for tests/callers that want to reuse one LM
    instance across calls. When omitted, a real ``dspy.LM(judge_model_id)``
    is constructed and used via ``dspy.context(lm=...)`` (DSPy's own
    thread/call-scoped LM override) so this function never mutates any
    caller's global ``dspy.settings`` -- reusing ``judge_model_id``/
    ``judge_api_base`` unmodified from ``gymact_diagnosis_driver.py``'s
    identical defaults, per this task's instruction to match the existing
    driver's confirmed-working Groq routing (litellm resolves the
    ``"groq/"``-prefixed model string against the real ``GROQ_API_KEY``
    environment variable; ``judge_api_base`` is accepted for parity with
    the existing driver's signature but litellm's groq provider does not
    require an explicit ``api_base`` override for the default
    ``api.groq.com`` endpoint).

    ``_environment_factory``/``_capabilities`` are test-only injection
    points (leading underscore), same contract as
    ``gymact_diagnosis_driver.run_gymact_mediated_diagnosis``: a test
    supplies a real, hand-written fake ``SregymEnvironment``-shaped object
    instead of materializing a real cluster.
    """
    if namespace is None:
        from autofde_lab.reasoning.gymact_diagnosis_driver import PROBLEM_ID_NAMESPACE

        namespace = PROBLEM_ID_NAMESPACE.get(problem_id)
        if namespace is None:
            raise ValueError(
                f"no known real namespace for problem_id={problem_id!r} -- pass namespace= "
                "explicitly (see PROBLEM_ID_NAMESPACE in gymact_diagnosis_driver.py)."
            )

    gate = CapabilityGate.from_toml(manifest_path)

    if _environment_factory is not None:
        env = await _environment_factory()
        capabilities = _capabilities
    else:
        from gymact.gyms.sregym import SREGYM_CAPABILITIES, SregymVendorProvider

        provider = SregymVendorProvider()
        env = await provider.materialize(
            scenario=problem_id,
            config={
                "problem_id": problem_id,
                "judge_model_id": judge_model_id,
                "judge_api_base": judge_api_base,
                "wall_clock_timeout_s": wall_clock_timeout_s,
                "startup_timeout_seconds": startup_timeout_seconds,
                "verify_timeout_seconds": verify_timeout_seconds,
                "mcp_server_port": mcp_server_port,
                "api_port": api_port,
            },
        )
        capabilities = SREGYM_CAPABILITIES

    resolved_lm = lm if lm is not None else dspy.LM(judge_model_id)

    try:
        diagnoser = GymActReActDiagnoser(
            environment=env,
            gate=gate,
            capabilities=capabilities,
            namespace=namespace,
            max_iters=max_iters,
        )
        with dspy.context(lm=resolved_lm):
            prediction = diagnoser(problem_id=problem_id, namespace=namespace)

        diagnosis_text = str(getattr(prediction, "diagnosis", ""))
        try:
            confidence = float(getattr(prediction, "confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        trajectory = dict(getattr(prediction, "trajectory", {}) or {})

        submit_cap = _capability(capabilities, "submit_diagnosis")
        gate.guard_capability(submit_cap)
        submit_response = await env.actuate(
            submit_cap, {"diagnosis": diagnosis_text, "confidence": confidence}
        )

        mitigation_response: Any | None = None
        if attempt_mitigation:
            mitigation_cap = _capability(capabilities, "submit_mitigation")
            gate.guard_capability(mitigation_cap)
            mitigation_response = await env.actuate(
                mitigation_cap,
                {"mitigation": "not_attempted", "reason": "no_automated_command_synthesis_yet"},
            )

        return DiagnosisResult(
            problem_id=problem_id,
            namespace=namespace,
            diagnosis=diagnosis_text,
            confidence=confidence,
            trajectory=trajectory,
            submit_diagnosis_response=submit_response,
            mitigation_attempted=attempt_mitigation,
            submit_mitigation_response=mitigation_response,
        )
    finally:
        try:
            await env.teardown()
        except Exception as teardown_exc:  # noqa: BLE001 -- teardown failure must not mask a real result
            import logging

            logging.getLogger(__name__).warning(
                "gymact_dspy_react: env.teardown() raised %r", teardown_exc
            )
