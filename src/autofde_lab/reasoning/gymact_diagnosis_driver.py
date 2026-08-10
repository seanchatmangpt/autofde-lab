# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The real gymact-mediated diagnosis driver, wired through
:func:`autofde_lab.powl.runner.run_pipeline` -- the answer
``scripts/run_gymact_mediated_trial.py`` (a real, deliberately-kept
throwaway spike, not deleted by this module) named as still missing: "never
actually wired despite runner.py's docstring naming it."

What changed relative to the spike
------------------------------------
The spike drives ``observe -> kubectl reads -> scan -> phi -> classify ->
submit_diagnosis -> (no remediation synthesis yet) -> submit_mitigation ->
verify`` with hand-ordered ``await`` calls in a linear script. This module
builds the exact same real collaborators (real ``SregymEnvironment`` via
``SregymVendorProvider().materialize()``, the real
``autofde_lab_planner.scanner.registry.scan`` /
``autofde_lab_planner.scanner.taxonomy.classify`` sequence, the real
``CapabilityGate``-gated ``env.actuate()`` calls) but never calls them
directly in this module's own control flow. Instead:

1. :func:`autofde_lab.powl.runner.build_pipeline_powl_node` builds the real
   POWL pipeline tree, whose five terminal ``gymact_*`` Atom labels
   (``ALLOWED_ACTUATION_BINDING_LABELS`` in that module) are the real
   actuation-class labels this driver binds to.
2. Each of the five labels is bound to a real
   :class:`~autofde_lab.powl.runner.GatedCapabilityBinding` -- a closure over
   the one materialized ``env``, wrapping a real ``CapabilityGate``-checked
   gymact capability name -- never a bare callable (``run_pipeline`` itself
   refuses a bare callable for these five labels; see that module).
3. :func:`autofde_lab.powl.runner.run_pipeline` is called exactly once. THAT
   call is what fires each bound closure, in the order the real POWL tree's
   structural replay enables them -- this module's own code never calls
   ``env.observe()``/``env.actuate()``/``env.verify()`` directly; it only
   constructs the tree and the bindings and hands both to ``run_pipeline``.

Why bindings run each coroutine in a dedicated thread, not ``asyncio.run``
----------------------------------------------------------------------------
``sregym_pipeline.py``'s ReAct tools call ``asyncio.run(coro)`` directly
because a ``dspy.ReAct`` tool call happens with no event loop already
running. This driver is different: ``run_gymact_mediated_diagnosis`` is
itself ``async def`` (this task's own required signature), so by the time
``run_pipeline`` (a plain synchronous function) invokes a bound closure
synchronously, a real event loop IS already running for the driver's own
coroutine -- ``asyncio.run()`` inside that closure would raise
``RuntimeError: asyncio.run() cannot be called from a running event loop``.
``_run_coroutine_sync`` below runs each closure's coroutine to completion in
a short-lived dedicated thread with its own fresh event loop instead --
still a real, unmocked ``asyncio.run`` underneath, just executed off the
driver's own running loop so the two never collide.

Real remediation synthesis: not built yet, named honestly
-------------------------------------------------------------
Per the spike's own step [6/7] comment: automated mitigation-command
synthesis from a real ``Anomaly`` is real, unbuilt scope. The
``gymact_actuate_remediate`` binding therefore performs a real, non-mutating
``run_kubectl`` re-read (never a fabricated "fix" command) -- a real
``env.actuate()`` call through the real gated capability, honestly scoped to
"confirm current state before mitigation", not to a remediation this repo
cannot yet synthesize. ``submit_mitigation`` reports
``mitigation="not_attempted"`` for the same reason the spike does.

``verify`` is not a gymact ``Capability``
--------------------------------------------
``SregymEnvironment.verify()`` is a plain coroutine, never wired into
``actuate()``'s dispatch table (see ``gymact_capability_gate.py``'s module
docstring) -- so the ``gymact_verify`` binding calls ``env.verify()``
directly, not through ``env.actuate()``, and takes a bare ``ActionBinding``
rather than a ``GatedCapabilityBinding``: there is no real gymact
``Capability`` behind it to gate against. An earlier pass in this session
added a fictitious ``"verify"`` entry to ``gymact_capabilities.toml`` just to
satisfy the (incorrect) requirement that every actuation-class label be
capability-gated; ``CapabilityGate.stale_entries()`` correctly caught it as
drift (no real ``SREGYM_CAPABILITIES`` entry named ``"verify"`` exists), and
it was removed. Fixed forward in both ``runner.py`` (``gymact_verify`` moved
to its own ``ALLOWED_ACTUATION_ORACLE_LABELS`` set, bare-binding-only, not
required by the default completeness check) and here.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from autofde_lab.case_library.outcome_predicate import OracleVerdict, OutcomeVerdict, evaluate_outcome
from autofde_lab.fabric.gymact_capability_gate import DEFAULT_MANIFEST_PATH, CapabilityGate
from autofde_lab.ocel.log import OcelLog
from autofde_lab.powl.runner import (
    GYMACT_ACTUATE_REMEDIATE_LABEL,
    GYMACT_OBSERVE_LABEL,
    GYMACT_SUBMIT_DIAGNOSIS_LABEL,
    GYMACT_SUBMIT_MITIGATION_LABEL,
    GYMACT_VERIFY_LABEL,
    GatedCapabilityBinding,
    PipelineStallResult,
    build_pipeline_powl_node,
    run_pipeline,
)
from autofde_lab_planner.scanner.registry import ClusterState, scan
from autofde_lab_planner.scanner.taxonomy import classify

__all__ = [
    "GymactMediatedDiagnosisResult",
    "run_gymact_mediated_diagnosis",
]


def _run_coroutine_sync(coro: Any) -> Any:
    """Run a real coroutine to completion from a synchronous binding
    closure, without colliding with the driver's own already-running event
    loop -- see this module's docstring for why plain ``asyncio.run`` cannot
    be used here. A real ``asyncio.run`` call still happens, just inside a
    dedicated worker thread with its own fresh loop."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _capability(capabilities: Any, name: str) -> Any:
    for cap in capabilities:
        if cap.binding == name:
            return cap
    raise KeyError(f"no real gymact capability named {name!r}")


@dataclass(frozen=True, slots=True)
class GymactMediatedDiagnosisResult:
    """Real, typed result of one gymact-mediated diagnosis run.

    ``ocel_log``/``stall`` are exactly what ``run_pipeline`` returned for
    this run's real structural replay. ``verdict``/``confirmed_via`` are
    :func:`autofde_lab.case_library.outcome_predicate.evaluate_outcome`'s
    real output, computed from the real ``env.verify()`` oracle call fired
    by the ``gymact_verify`` binding -- never a self-certified re-scan.
    """

    problem_id: str
    ocel_log: OcelLog
    stall: PipelineStallResult
    verdict: OutcomeVerdict
    confirmed_via: str
    verify_observed: dict[str, Any]


async def run_gymact_mediated_diagnosis(
    problem_id: str,
    *,
    mcp_server_port: int,
    api_port: int,
    judge_model_id: str = "groq/openai/gpt-oss-20b",
    judge_api_base: str = "https://api.groq.com/openai/v1",
    wall_clock_timeout_s: int = 900,
    startup_timeout_seconds: float = 900.0,
    namespace: str = "social-network",
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    _environment_factory: Callable[[], Any] | None = None,
    _capabilities: Any = None,
) -> GymactMediatedDiagnosisResult:
    """Materialize a real ``SregymEnvironment``, build the real POWL
    pipeline tree extended with the five ``gymact_*`` actuation Atoms, bind
    each to a real, capability-gated closure over that one environment, and
    call ``run_pipeline`` exactly once -- the runner's own structural replay
    is what triggers each real call, in tree order, not this function.

    ``startup_timeout_seconds`` defaults to 900s, not gymact's own 120s
    default: a real trial this session hit
    ``RuntimeError: sregym conductor API ... did not become ready within
    120.0s`` -- confirmed live, the full observability+app deploy this
    problem set requires genuinely takes 5-15+ real minutes (measured this
    session, multiple live attempts), so the 120s default was never
    sufficient for this workload, not a transient flake.

    ``_environment_factory``/``_capabilities`` are test-only injection
    points (leading underscore -- not part of the public contract): when
    omitted, this function materializes the one real environment via
    ``gymact.gyms.sregym.SregymVendorProvider().materialize()`` against the
    real ``SREGYM_CAPABILITIES`` tuple, exactly as
    ``scripts/run_gymact_mediated_trial.py`` does. A test supplies a real,
    hand-written fake ``SregymEnvironment``-shaped object instead (see
    ``tests/reasoning/test_gymact_diagnosis_driver_chicago.py``) so it can
    assert the runner -- not this function's own code -- is what triggers
    each call, without materializing a real subprocess/cluster.
    """
    gate = CapabilityGate.from_toml(manifest_path)

    if _environment_factory is not None:
        env = await _environment_factory()
        SREGYM_CAPABILITIES = _capabilities
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
                "mcp_server_port": mcp_server_port,
                "api_port": api_port,
            },
        )

    # Mutable closure state -- carries the diagnosis/anomaly found by
    # gymact_observe across to the later gymact_submit_diagnosis /
    # gymact_actuate_remediate / gymact_verify bindings, exactly the way a
    # real diagnosing pipeline's steps depend on each other's real output.
    diagnosis_state: dict[str, Any] = {}

    async def _kubectl_json(command: str) -> Any:
        cap = _capability(SREGYM_CAPABILITIES, "run_kubectl")
        gate.guard_capability(cap)
        result = await env.actuate(cap, {"command": command})
        text_blocks = result.get("result_text", []) if isinstance(result, dict) else []
        raw = "".join(b.get("text", "") for b in text_blocks if isinstance(b, dict))
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}

    async def _observe() -> dict[str, Any]:
        obs_cap = _capability(SREGYM_CAPABILITIES, "observe_cluster_state")
        gate.guard_capability(obs_cap)
        status = await env.actuate(obs_cap, {})

        deployments = await _kubectl_json(f"get deployments -n {namespace} -o json")
        pods = await _kubectl_json(f"get pods -n {namespace} -o json")
        services = await _kubectl_json(f"get services -n {namespace} -o json")

        state: ClusterState = {
            "deployments": deployments,
            "pods": pods,
            "services": services,
        }
        anomalies = scan(state)
        diagnosis_state["anomalies"] = anomalies
        if anomalies:
            top = anomalies[0]
            diagnosis_state["top_anomaly"] = top
            diagnosis_state["label"] = classify(top)
        else:
            diagnosis_state["top_anomaly"] = None
            diagnosis_state["label"] = "no_anomaly_detected"
        return {"status": status, "anomaly_count": len(anomalies), "label": diagnosis_state["label"]}

    async def _submit_diagnosis() -> Any:
        cap = _capability(SREGYM_CAPABILITIES, "submit_diagnosis")
        gate.guard_capability(cap)
        top = diagnosis_state.get("top_anomaly")
        label = diagnosis_state.get("label", "no_anomaly_detected")
        payload: dict[str, Any] = {
            "diagnosis": label,
            "confidence": 0.8 if top is not None else 0.0,
        }
        if top is not None:
            payload["anomaly"] = {
                "kind": top.kind,
                "object_name": top.object_name,
                "namespace": top.namespace,
                "field": top.field,
            }
        return await env.actuate(cap, payload)

    async def _actuate_remediate() -> Any:
        # No automated remediation-command synthesis from an Anomaly exists
        # yet (see this module's docstring) -- a real, non-mutating
        # run_kubectl re-read, honestly scoped as a re-confirm, not a
        # fabricated fix.
        return await _kubectl_json(f"get pods -n {namespace} -o json")

    async def _submit_mitigation() -> Any:
        cap = _capability(SREGYM_CAPABILITIES, "submit_mitigation")
        gate.guard_capability(cap)
        payload = {"mitigation": "not_attempted", "reason": "no_automated_command_synthesis_yet"}
        return await env.actuate(cap, payload)

    async def _verify() -> dict[str, Any]:
        label = diagnosis_state.get("label", "no_anomaly_detected")
        passed, observed = await env.verify({"stage": "complete", "diagnosis": label})
        diagnosis_state["verify_passed"] = passed
        diagnosis_state["verify_observed"] = observed if isinstance(observed, dict) else {"raw": observed}
        return {"passed": passed, "observed": diagnosis_state["verify_observed"]}

    def _binding(coro_factory: Callable[[], Any]) -> Callable[[dict[str, Any]], Any]:
        def _call(_atom_attrs: dict[str, Any]) -> Any:
            return _run_coroutine_sync(coro_factory())

        return _call

    action_bindings = {
        GYMACT_OBSERVE_LABEL: GatedCapabilityBinding(
            capability_name="observe_cluster_state",
            callable_=_binding(_observe),
            gate=gate,
        ),
        GYMACT_SUBMIT_DIAGNOSIS_LABEL: GatedCapabilityBinding(
            capability_name="submit_diagnosis",
            callable_=_binding(_submit_diagnosis),
            gate=gate,
        ),
        GYMACT_ACTUATE_REMEDIATE_LABEL: GatedCapabilityBinding(
            capability_name="run_kubectl",
            callable_=_binding(_actuate_remediate),
            gate=gate,
        ),
        GYMACT_SUBMIT_MITIGATION_LABEL: GatedCapabilityBinding(
            capability_name="submit_mitigation",
            callable_=_binding(_submit_mitigation),
            gate=gate,
        ),
        # gymact_verify takes a bare ActionBinding, not a GatedCapabilityBinding:
        # SregymEnvironment.verify() is a plain coroutine, never a real gymact
        # Capability, never wired into actuate()'s dispatch table -- there is no
        # real capability name to gate it against. Fixed forward this session
        # after CapabilityGate.stale_entries() caught a fictitious "verify"
        # manifest entry that had been added just to satisfy the (incorrect)
        # requirement that every actuation-class label be capability-gated.
        GYMACT_VERIFY_LABEL: _binding(_verify),
    }

    try:
        model = build_pipeline_powl_node()
        ocel_log, stall = run_pipeline(
            model,
            session_id=f"gymact-mediated-{problem_id}",
            action_bindings=action_bindings,
            allow_partial_bindings=True,
        )

        verify_passed = bool(diagnosis_state.get("verify_passed", False))
        verify_observed = diagnosis_state.get("verify_observed", {})
        verdict, confirmed_via = evaluate_outcome(
            structural_passed=verify_passed,
            oracle=OracleVerdict(present=True, passed=verify_passed),
        )

        result = GymactMediatedDiagnosisResult(
            problem_id=problem_id,
            ocel_log=ocel_log,
            stall=stall,
            verdict=verdict,
            confirmed_via=confirmed_via,
            verify_observed=verify_observed,
        )
    finally:
        # Real bug found and fixed forward this session: `finally:
        # await env.teardown()` with no exception handling meant a
        # teardown-only failure (e.g. a real MCP client disconnect race,
        # confirmed live -- `httpx.ReadError` inside `_kubectl_client
        # .__aexit__`) silently discarded an already-successful `result`
        # from the `try` block, since Python replaces a `return`'s value
        # with any exception raised in the matching `finally`. Cleanup
        # failing must never destroy a real, already-computed diagnosis
        # result -- log it as a real, named, non-fatal teardown warning
        # instead.
        try:
            await env.teardown()
        except Exception as teardown_exc:  # noqa: BLE001 -- intentionally broad: any teardown failure must not mask `result`
            import logging

            logging.getLogger(__name__).warning(
                "gymact_diagnosis_driver: env.teardown() raised %r after a "
                "real diagnosis result was already computed -- the result "
                "is still returned; this is a real resource-cleanup gap, "
                "not a diagnosis failure.",
                teardown_exc,
            )

    return result
