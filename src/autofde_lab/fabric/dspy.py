# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""DSPy compiler for natural-language jobs into typed decision requests."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from autofde_lab.fabric.models import (
    DecisionCatalog,
    DecisionRefusal,
    DecisionRequest,
    RefusalCode,
)

# The one deliberate, narrow bridge between this repo's fabric layer and its
# sa2a/unknown/ candidate-frontier substrate -- AFDE-2611
# (docs/jira/v26.9.16/AFDE-2611-shllm-bounded-local-tier.md) found these two
# subsystems real, independently tested, and completely unwired: nothing
# reachable from fabric/dspy.py's sole local-compile call site ever
# constructed `AllocationStanding.EXHAUSTED`, so the enum member was dead
# decoration and an unbounded/unretried compile call had no typed budget
# result to report. This import exists to fix exactly that gap and nothing
# more: only `AllocationStanding` (a plain, dependency-free str-Enum with no
# admission/authority/consequence semantics of its own) is imported here --
# never `autofde_lab.sa2a.authority` (AuthorityBroker) or
# `autofde_lab.sa2a.brce` (ConsequenceBoundary) or
# `autofde_lab.sa2a.unknown.resolution`/`novelty_ingest` (the admission
# court / candidate pipeline). A locally-compiled `DecisionRequest` is still
# never passed into any admission, authority, or consequence-boundary call
# anywhere in this module -- only this module's *own* bounded-compile
# outcome is reported using the same typed budget-standing vocabulary the
# allocator already uses elsewhere in this repo, so a real local-model call
# and the rest of `sa2a/unknown/`'s budget standing speak one language
# instead of two unconnected ones.
from autofde_lab.sa2a.unknown.allocator import AllocationStanding


class DecisionCompiler(Protocol):
    """Compiler boundary used by A2A and optional MCP projections."""

    def compile(self, job: str, catalog: DecisionCatalog) -> DecisionRequest: ...


class DSPyDecisionCompiler:
    """Compile a user job into a validated scikit-decide request.

    DSPy and its LM are only used at the novelty frontier. JSON requests,
    exact cache hits, registry matching, planning, and rollout remain outside
    the language-model path.
    """

    def __init__(self, program: Any | None = None) -> None:
        try:
            import dspy
        except ImportError as error:
            raise DecisionRefusal(
                RefusalCode.DEPENDENCY_UNAVAILABLE,
                "DSPy is unavailable; install the agentic requirements",
                details={"dependency": "dspy"},
            ) from error

        if program is None:

            class JobToDecision(dspy.Signature):
                """Map a job to one registered domain and compatible solver.

                Return strict JSON objects for constructor arguments. Use AUTO
                when solver selection should be delegated to scikit-decide.
                """

                job: str = dspy.InputField()
                domains: str = dspy.InputField()
                solvers: str = dspy.InputField()
                domain: str = dspy.OutputField()
                solver: str = dspy.OutputField()
                domain_arguments_json: str = dspy.OutputField()
                solver_arguments_json: str = dspy.OutputField()
                max_steps: int = dspy.OutputField()

            program = dspy.Predict(JobToDecision)
        self._program = program

    def compile(self, job: str, catalog: DecisionCatalog) -> DecisionRequest:
        """Compile and validate one natural-language job."""
        try:
            prediction = self._program(
                job=job,
                domains=json.dumps(catalog.domains),
                solvers=json.dumps(catalog.solvers),
            )
            domain = str(prediction.domain).strip()
            solver_text = str(prediction.solver).strip()
            solver = (
                None if solver_text.upper() in {"", "AUTO", "NONE"} else solver_text
            )
            domain_arguments = _json_object(
                str(prediction.domain_arguments_json), "domain_arguments_json"
            )
            solver_arguments = _json_object(
                str(prediction.solver_arguments_json), "solver_arguments_json"
            )
            max_steps = int(prediction.max_steps)
        except DecisionRefusal:
            raise
        except Exception as error:
            raise DecisionRefusal(
                RefusalCode.NATURAL_LANGUAGE_COMPILATION_FAILED,
                "DSPy failed to compile the job into a decision request",
                details={"error": str(error)},
            ) from error

        if domain not in catalog.domains:
            raise DecisionRefusal(
                RefusalCode.NATURAL_LANGUAGE_COMPILATION_FAILED,
                "DSPy selected an unregistered domain",
                details={"domain": domain},
            )
        if solver is not None and solver not in catalog.solvers:
            raise DecisionRefusal(
                RefusalCode.NATURAL_LANGUAGE_COMPILATION_FAILED,
                "DSPy selected an unregistered solver",
                details={"solver": solver},
            )
        return DecisionRequest(
            domain=domain,
            solver=solver,
            domain_arguments=domain_arguments,
            solver_arguments=solver_arguments,
            max_steps=max_steps,
        )


# Defaults for the local-compile budget ceiling. Deliberately small and
# named here (never re-derived at each call site): three attempts, thirty
# wall-clock seconds total across all of them.
DEFAULT_COMPILE_MAX_ATTEMPTS = 3
DEFAULT_COMPILE_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class BoundedCompileResult:
    """Typed outcome of one budget-bounded local-compile attempt sequence.

    `standing` is drawn from the real, shared
    `autofde_lab.sa2a.unknown.allocator.AllocationStanding` vocabulary --
    `ADMITTED` when a candidate `DecisionRequest` was produced within the
    attempt/time ceiling, `EXHAUSTED` when the ceiling was spent without
    producing one. This is the fix for AFDE-2611's Law 4 gap finding: the
    call site this wraps previously had no way to report budget exhaustion
    as anything other than letting the underlying exception propagate.
    """

    standing: AllocationStanding
    request: DecisionRequest | None
    attempts_used: int
    elapsed_seconds: float
    last_error: str | None = None


def bounded_compile(
    compile_fn: Callable[[str, DecisionCatalog], DecisionRequest],
    job: str,
    catalog: DecisionCatalog,
    *,
    max_attempts: int = DEFAULT_COMPILE_MAX_ATTEMPTS,
    timeout_seconds: float = DEFAULT_COMPILE_TIMEOUT_SECONDS,
) -> BoundedCompileResult:
    """Call `compile_fn(job, catalog)` under an explicit attempt/time ceiling.

    This is the fix for the real gap AFDE-2611 names precisely: the sole
    local-compile call site in this repo's fabric layer
    (`compile_request_text`, below) had no retry loop, no timeout, and no
    budget bound of any kind -- an exception from `compile_fn` propagated
    completely unbounded, and nothing anywhere reachable from that call site
    ever constructed `AllocationStanding.EXHAUSTED`.

    `bounded_compile` never retries past `max_attempts` and never keeps
    calling once `timeout_seconds` of wall-clock time has elapsed (checked
    before each attempt begins -- a cooperative ceiling, not a preemptive
    one: it will not forcibly interrupt a single `compile_fn` call that
    itself hangs past the remaining budget, the same non-preemptive bound
    ordinary retry/backoff libraries use). On exhaustion it returns a typed
    `BoundedCompileResult` carrying `AllocationStanding.EXHAUSTED` instead
    of raising the last underlying exception -- the caller decides what a
    typed exhaustion result means for it (see `compile_request_text`,
    which turns it into a `DecisionRefusal`). It never falls back to a
    different, unbounded provider: `compile_fn` is the only callable ever
    invoked, on every attempt, with the same `job`/`catalog` arguments.
    """
    if max_attempts <= 0:
        raise ValueError("max_attempts must be strictly positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be strictly positive")

    start = time.monotonic()
    attempts_used = 0
    last_error: str | None = None

    for _ in range(max_attempts):
        if (time.monotonic() - start) >= timeout_seconds:
            break
        attempts_used += 1
        try:
            request = compile_fn(job, catalog)
        except Exception as error:  # noqa: BLE001 -- typed exhaustion below
            last_error = f"{type(error).__name__}: {error}"
            continue
        return BoundedCompileResult(
            standing=AllocationStanding.ADMITTED,
            request=request,
            attempts_used=attempts_used,
            elapsed_seconds=time.monotonic() - start,
        )

    return BoundedCompileResult(
        standing=AllocationStanding.EXHAUSTED,
        request=None,
        attempts_used=attempts_used,
        elapsed_seconds=time.monotonic() - start,
        last_error=last_error,
    )


def compile_request_text(
    text: str,
    catalog: DecisionCatalog,
    compiler: DecisionCompiler | None = None,
    *,
    max_attempts: int = DEFAULT_COMPILE_MAX_ATTEMPTS,
    timeout_seconds: float = DEFAULT_COMPILE_TIMEOUT_SECONDS,
) -> DecisionRequest:
    """Prefer deterministic JSON; invoke DSPy only for natural language.

    The DSPy compile call is bounded by `bounded_compile` (see above): a
    finite attempt ceiling and a finite wall-clock ceiling, never an
    unbounded retry loop and never a silent fallback to a different
    provider. Exhaustion is a typed `DecisionRefusal`
    (`NATURAL_LANGUAGE_COMPILATION_EXHAUSTED`) carrying the real
    `AllocationStanding.EXHAUSTED` value in its details, not an unbounded
    exception propagating from whatever the underlying compiler last raised.
    """
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise DecisionRefusal(
                RefusalCode.INVALID_ARGUMENTS,
                "decision request JSON is malformed",
                details={"error": error.msg},
            ) from error
        if not isinstance(payload, dict):
            raise DecisionRefusal(
                RefusalCode.INVALID_ARGUMENTS,
                "decision request must be a JSON object",
            )
        return DecisionRequest.from_dict(payload)
    if compiler is None:
        raise DecisionRefusal(
            RefusalCode.NATURAL_LANGUAGE_COMPILER_UNAVAILABLE,
            "natural-language requests require an explicitly configured DSPy compiler",
        )

    result = bounded_compile(
        compiler.compile,
        stripped,
        catalog,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
    )
    if result.standing is AllocationStanding.EXHAUSTED:
        raise DecisionRefusal(
            RefusalCode.NATURAL_LANGUAGE_COMPILATION_EXHAUSTED,
            "DSPy compile exhausted its attempt/time budget without "
            "producing a candidate decision request",
            details={
                "standing": AllocationStanding.EXHAUSTED.value,
                "attempts_used": result.attempts_used,
                "elapsed_seconds": result.elapsed_seconds,
                "max_attempts": max_attempts,
                "timeout_seconds": timeout_seconds,
                "last_error": result.last_error,
            },
        )
    assert result.request is not None  # ADMITTED always carries a request
    return result.request


def _json_object(value: str, field: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except json.JSONDecodeError as error:
        raise DecisionRefusal(
            RefusalCode.NATURAL_LANGUAGE_COMPILATION_FAILED,
            f"{field} is not valid JSON",
            details={"error": error.msg},
        ) from error
    if not isinstance(decoded, dict):
        raise DecisionRefusal(
            RefusalCode.NATURAL_LANGUAGE_COMPILATION_FAILED,
            f"{field} must be a JSON object",
        )
    return decoded
