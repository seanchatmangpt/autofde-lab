from __future__ import annotations

import pytest

from autofde_lab.sota_factory.autopilot import AutopilotPolicy, SOTAAutopilot
from autofde_lab.sota_factory.execution import (
    ExperimentExecutionPort,
    GymActExecutionProfile,
)
from autofde_lab.sota_factory.factory import SOTAFactory
from autofde_lab.sota_factory.models import (
    BasisChoice,
    BenchmarkTarget,
    BudgetPolicy,
    ExperimentPlan,
    FailureKind,
    TrialOutcome,
    TrialResult,
)
from autofde_lab.sota_factory.space import DecisionSpace


def _space() -> DecisionSpace:
    one = (BasisChoice("one"),)
    return DecisionSpace(
        models=one,
        planners=one,
        tool_policies=one,
        repair_policies=one,
        replanning_policies=one,
        verification_policies=one,
        projection_policies=one,
        memory_policies=one,
        budgets=(BudgetPolicy("one"),),
    )


def _factory() -> SOTAFactory:
    target = BenchmarkTarget(
        benchmark_id="urn:test:benchmark",
        revision="sha256:benchmark",
        published_sota=66.0,
        primary_metric="success-rate",
        task_ids=("t1", "t2", "t3"),
        expected_task_count=3,
        evaluator_ref="urn:test:evaluator",
        frontier_source_ref="urn:test:frontier",
    )
    return SOTAFactory(target=target, decision_space=_space())


class PassingExecutionPort:
    """Real deterministic implementation of the execution-port contract."""

    async def execute(self, plan: ExperimentPlan) -> TrialResult:
        return TrialResult(
            plan_id=plan.plan_id,
            benchmark_id=plan.benchmark_id,
            benchmark_revision=plan.benchmark_revision,
            task_id=plan.task_id,
            architecture_digest=plan.architecture_digest,
            outcome=TrialOutcome.PASS,
            primary_score=1.0,
            evidence_refs=(f"urn:test:receipt:{plan.plan_id}",),
        )


class BlockingExecutionPort:
    async def execute(self, plan: ExperimentPlan) -> TrialResult:
        return TrialResult(
            plan_id=plan.plan_id,
            benchmark_id=plan.benchmark_id,
            benchmark_revision=plan.benchmark_revision,
            task_id=plan.task_id,
            architecture_digest=plan.architecture_digest,
            outcome=TrialOutcome.BLOCKED,
            primary_score=0.0,
            failure_kind=FailureKind.DEPENDENCY,
            blocker="BLOCKED:DEPENDENCY_UNAVAILABLE",
            evidence_refs=(f"urn:test:blocker:{plan.plan_id}",),
        )


def test_execution_port_protocol_is_structural() -> None:
    assert isinstance(PassingExecutionPort(), ExperimentExecutionPort)


def test_execution_profile_cannot_encode_vacuous_verification() -> None:
    with pytest.raises(ValueError, match="non-empty verification oracle"):
        GymActExecutionProfile(provider="memory")


@pytest.mark.asyncio
async def test_autopilot_reaches_evidence_bound_definition_of_done() -> None:
    factory = _factory()
    run = await SOTAAutopilot(
        factory,
        PassingExecutionPort(),
        policy=AutopilotPolicy(batch_size=3, max_rounds=2, max_trials=3),
    ).run()

    assert run.terminal is True
    assert run.stop_reason == "DEFINITION_OF_DONE"
    assert len(run.results) == 3
    assert all(result.evidence_refs for result in run.results)
    assert factory.definition_of_done().done is True
    assert factory.scoreboard().champion is not None
    assert factory.scoreboard().champion.score == 100.0


@pytest.mark.asyncio
async def test_autopilot_is_bounded_by_trial_budget() -> None:
    factory = _factory()
    run = await SOTAAutopilot(
        factory,
        PassingExecutionPort(),
        policy=AutopilotPolicy(batch_size=3, max_rounds=4, max_trials=2),
    ).run()

    assert run.terminal is False
    assert run.stop_reason == "MAX_TRIALS_REACHED"
    assert len(run.results) == 2
    assert len(factory.results) == 2


@pytest.mark.asyncio
async def test_blockers_are_ingested_as_learning_signals_not_hidden() -> None:
    factory = _factory()
    run = await SOTAAutopilot(
        factory,
        BlockingExecutionPort(),
        policy=AutopilotPolicy(batch_size=1, max_rounds=1, max_trials=1),
    ).run()

    assert run.terminal is False
    assert run.results[0].outcome is TrialOutcome.BLOCKED
    assert run.results[0].failure_kind is FailureKind.DEPENDENCY
    assert factory.snapshot().learning_signals
