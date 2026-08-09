from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from .models import ExperimentPlan, FailureKind, TrialOutcome, TrialResult


@dataclass(frozen=True, slots=True)
class GymActExecutionProfile:
    """Pure-data lowering of one ExperimentPlan into a GymAct consequence request.

    The profile contains no execution grant and cannot authorize DO. Authority remains
    an external input consumed by GymAct/BRCE.
    """

    provider: str
    scenario: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)
    capability_ref: str | None = None
    capability_binding: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    expected: Mapping[str, Any] = field(default_factory=dict)
    authority_ref: str | None = None
    subject_revision: str | None = None
    action_ref: str | None = None
    input_schema: Mapping[str, Any] = field(default_factory=lambda: {"type": "object"})

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("execution profile provider must be non-empty")
        if self.capability_ref is not None and self.capability_binding is not None:
            raise ValueError("execution profile selects capability by ref OR binding")
        if not self.expected:
            raise ValueError(
                "execution profile requires a non-empty verification oracle"
            )


@runtime_checkable
class ExecutionProfileResolver(Protocol):
    """CONSTRUCT-only adapter from an experiment identity to executable request data."""

    def resolve(self, plan: ExperimentPlan) -> GymActExecutionProfile: ...


@runtime_checkable
class ExperimentExecutionPort(Protocol):
    """External consequence boundary consumed by the SELECT/LEARN SOTA factory."""

    async def execute(self, plan: ExperimentPlan) -> TrialResult: ...


_FAILURE_MAP = {
    "NONE": FailureKind.NONE,
    "CONFIGURATION": FailureKind.TOOL_POLICY,
    "AUTHORITY": FailureKind.AUTHORITY,
    "DEPENDENCY": FailureKind.DEPENDENCY,
    "CAPABILITY": FailureKind.TOOL_POLICY,
    "EXECUTION": FailureKind.EXECUTION,
    "VERIFICATION": FailureKind.VERIFICATION,
    "UNCERTAIN": FailureKind.EXECUTION,
}


def _map_outcome(standing: str, verified: bool) -> TrialOutcome:
    if standing == "ALIVE" and verified:
        return TrialOutcome.PASS
    if standing in {"BLOCKED", "STALE", "BUILD_BROKEN", "REQUIRES_CONFIGURATION"}:
        return TrialOutcome.BLOCKED
    if standing == "UNSUPPORTED":
        return TrialOutcome.UNSUPPORTED
    if standing == "REFUSED":
        return TrialOutcome.REFUSED
    return TrialOutcome.FAIL


class GymActExecutionPort:
    """Governed adapter from Lab ExperimentPlan to GymAct's autonomic BRCE plane.

    ``controller`` is injected by the caller and is expected to be a configured
    ``gymact.autonomic.AutonomicController``. The adapter deliberately does not create
    a runtime, authority resolver, GrantIssuer, or ExecutionGrant. This keeps Lab on
    SELECT/CONSTRUCT/LEARN while GymAct owns DO.
    """

    def __init__(self, controller: object, resolver: ExecutionProfileResolver) -> None:
        if not isinstance(resolver, ExecutionProfileResolver):
            raise TypeError("resolver does not satisfy ExecutionProfileResolver")
        self._controller = controller
        self._resolver = resolver

    async def execute(self, plan: ExperimentPlan) -> TrialResult:
        # Lazy import lets the Lab remain importable while GymAct's autonomic surface
        # is delivered independently through its own PR. Execution itself requires it.
        try:
            from gymact.autonomic import ConsequenceRequest
        except ImportError as exc:
            raise RuntimeError("GYMACT_AUTONOMIC_EXECUTION_REQUIRED") from exc

        run = getattr(self._controller, "run", None)
        if run is None:
            raise TypeError("controller must expose async run(ConsequenceRequest)")

        profile = self._resolver.resolve(plan)
        request = ConsequenceRequest(
            request_id=plan.plan_id,
            provider=profile.provider,
            scenario=profile.scenario,
            config=dict(profile.config),
            capability_ref=profile.capability_ref,
            capability_binding=profile.capability_binding,
            payload=dict(profile.payload),
            expected=dict(profile.expected),
            authority_ref=profile.authority_ref,
            subject_revision=profile.subject_revision or plan.benchmark_revision,
            action_ref=profile.action_ref,
            input_schema=dict(profile.input_schema),
            idempotency_key=plan.plan_id,
            require_verification=True,
        )
        result = await run(request)
        standing = str(result.standing)
        failure_name = str(result.knowledge.failure_class)
        outcome = _map_outcome(standing, bool(result.verified))
        failure_kind = (
            FailureKind.NONE
            if outcome is TrialOutcome.PASS
            else _FAILURE_MAP.get(failure_name, FailureKind.UNKNOWN)
        )
        return TrialResult(
            plan_id=plan.plan_id,
            benchmark_id=plan.benchmark_id,
            benchmark_revision=plan.benchmark_revision,
            task_id=plan.task_id,
            architecture_digest=plan.architecture_digest,
            outcome=outcome,
            primary_score=1.0 if outcome is TrialOutcome.PASS else 0.0,
            failure_kind=failure_kind,
            blocker="" if outcome is TrialOutcome.PASS else str(result.reason),
            evidence_refs=tuple(str(item) for item in result.receipt_ids),
        )
