"""Chicago-style court for SA2A advice over the real FOND x HDDL product."""

from __future__ import annotations

import pytest

from autofde_lab.planning.fond_hddl_product import (
    HDDLDomain,
    Method,
    Outcome,
    PrimitiveAction,
    ProductState,
    Task,
    build_fond_problem,
)
from autofde_lab.planning.sa2a_advice import order_product_frontier
from autofde_lab.sa2a.computation import (
    ComputationArtifact,
    ComputationRuntime,
    PlanningAdvice,
    PlanningAdviceKind,
    ScoredCandidate,
)


def _subject():
    domain = HDDLDomain(
        tasks={
            "recover": Task("recover", primitive=False),
            "rollback": Task("rollback", primitive=True),
            "failover": Task("failover", primitive=True),
        },
        methods={
            "recover": (
                Method(
                    name="rollback-first",
                    task="recover",
                    preconditions=frozenset({"degraded"}),
                    subtasks=("rollback",),
                ),
                Method(
                    name="failover-first",
                    task="recover",
                    preconditions=frozenset({"degraded"}),
                    subtasks=("failover",),
                ),
            )
        },
        actions={
            "rollback": PrimitiveAction(
                name="rollback",
                preconditions=frozenset({"degraded"}),
                outcomes=frozenset({Outcome(add=frozenset({"healthy"}))}),
            ),
            "failover": PrimitiveAction(
                name="failover",
                preconditions=frozenset({"degraded"}),
                outcomes=frozenset({Outcome(add=frozenset({"healthy"}))}),
            ),
        },
    )
    initial = ProductState(world=frozenset({"degraded"}), tau=("recover",))
    reachability = build_fond_problem(
        domain,
        initial,
        lambda state: not state.tau and "healthy" in state.world,
    )
    return initial, reachability


def _artifact() -> ComputationArtifact:
    return ComputationArtifact(
        artifact_identity="sha256:qualified-model",
        capability_iri="https://schema.org/Action",
        runtime=ComputationRuntime.ONNX,
        input_schema_identity="sha256:planning-input",
        output_schema_identity="sha256:method-ranking",
        input_projection_identity="sha256:rdf-features",
        deterministic=True,
    )


def test_model_orders_exact_product_frontier_without_redefining_it() -> None:
    state, reachability = _subject()
    advice = PlanningAdvice(
        planning_subject_identity="sha256:world-subject",
        formal_projection_identity="sha256:fond-hddl-product",
        artifact=_artifact(),
        kind=PlanningAdviceKind.METHOD_ORDER,
        candidates=(
            ScoredCandidate(candidate_ref="not-a-formal-method", score=1.0),
            ScoredCandidate(candidate_ref="refine:rollback-first", score=0.91),
            ScoredCandidate(candidate_ref="refine:failover-first", score=0.42),
        ),
    )

    result = order_product_frontier(
        reachability=reachability,
        state=state,
        advice=advice,
        planning_subject_identity="sha256:world-subject",
        formal_projection_identity="sha256:fond-hddl-product",
    )

    assert result.formal_action_refs == (
        "refine:failover-first",
        "refine:rollback-first",
    )
    assert result.ordered_action_refs == (
        "refine:rollback-first",
        "refine:failover-first",
    )
    assert result.preserves_formal_frontier
    assert "not-a-formal-method" not in result.ordered_action_refs


def test_advice_for_another_subject_or_projection_is_refused() -> None:
    state, reachability = _subject()
    advice = PlanningAdvice(
        planning_subject_identity="sha256:other-subject",
        formal_projection_identity="sha256:fond-hddl-product",
        artifact=_artifact(),
        kind=PlanningAdviceKind.METHOD_ORDER,
        candidates=(),
    )

    with pytest.raises(ValueError, match="PLANNING_ADVICE_SUBJECT_IDENTITY_MISMATCH"):
        order_product_frontier(
            reachability=reachability,
            state=state,
            advice=advice,
            planning_subject_identity="sha256:world-subject",
            formal_projection_identity="sha256:fond-hddl-product",
        )

    correct_subject = PlanningAdvice(
        planning_subject_identity="sha256:world-subject",
        formal_projection_identity="sha256:other-product",
        artifact=_artifact(),
        kind=PlanningAdviceKind.METHOD_ORDER,
        candidates=(),
    )
    with pytest.raises(ValueError, match="PLANNING_ADVICE_FORMAL_PROJECTION_MISMATCH"):
        order_product_frontier(
            reachability=reachability,
            state=state,
            advice=correct_subject,
            planning_subject_identity="sha256:world-subject",
            formal_projection_identity="sha256:fond-hddl-product",
        )
