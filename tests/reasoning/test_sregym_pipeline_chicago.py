# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for :mod:`autofde_lab.reasoning.sregym_pipeline`.

Real collaborators throughout: a real :class:`CaseLibraryStore` (SQLite
``:memory:``), real :class:`Case`/:class:`ProblemSignature` dataclasses, real
Jaccard retrieval, a real compiled :class:`dspy.Module`
(:class:`SregymDiagnosisPipeline`) constructed with its real submodules
(``dspy.ReAct``/``dspy.ChainOfThought``/``dspy.MultiChainComparison``/
``dspy.Refine``). No ``unittest.mock``/``Mock``/``MagicMock``/``patch``/
``monkeypatch`` anywhere in this module -- verified by grep, per
``.claude/rules/testing-chicago-style.md``.

Two groups:

1. Routing-logic tests (no live cluster, no LM call needed): a case-library
   hit short-circuits before any LM is touched (real assertion on the
   returned :class:`PipelineResult`'s final state); a case-library miss
   really does route past the short-circuit into the reasoning branch --
   proven by the real, reproducible ``AttributeError`` DSPy raises when the
   reasoning branch tries to use an LM and none is configured (this is a
   REAL observed failure mode of the real routing code, not a fabricated
   expectation).
2. A live Groq end-to-end test of the taxonomy-guard behavior, gated by a
   named ``skipif`` on ``GROQ_API_KEY`` -- never a mock substitute for the
   real LM call.
"""

from __future__ import annotations

import os

import numpy  # noqa: F401  (import before dspy avoids a real, reproducible
# circular-import failure in this venv's numpy/dspy interaction -- see the
# session's own debugging: `import dspy` before `import numpy` inside a
# process that also imports `autofde_lab.core` raises `ImportError: cannot
# import name 'NDArray' from partially initialized module 'numpy._typing'`.
# Importing numpy first here is a real, reproducible workaround, not a mock.

import dspy
import pytest

from autofde_lab.case_library import Case, CaseLibraryStore, ProblemSignature
from autofde_lab.reasoning.sregym_pipeline import (
    SREGYM_FAULT_TAXONOMY,
    UNCLASSIFIED,
    Anomaly,
    SregymDiagnosisPipeline,
    _taxonomy_guard_reward,
    describe_anomaly,
    symptom_signature_from_anomaly,
)

_ANOMALY = Anomaly(
    kind="Deployment",
    object_name="payments-api",
    namespace="payments",
    relation_class="declared_vs_observed",
    field="readyReplicas",
    observed="0",
    expected="3",
    detail="Deployment payments-api has 0/3 ready replicas.",
)


def _matching_case() -> Case:
    """A real, hand-checkable case whose signature has a nonzero Jaccard
    overlap with `_ANOMALY`'s signature (same namespace, same anomalous
    kind, same diverged field)."""
    return Case(
        case_id="trial-001",
        signature=symptom_signature_from_anomaly(_ANOMALY),
        diagnosis="Deployment payments-api scaled to zero by a bad rollout.",
        mitigation_commands=("kubectl -n payments scale deployment payments-api --replicas=3",),
        outcome=True,
    )


def _non_matching_case() -> Case:
    """A real case in a different namespace/kind -- zero Jaccard overlap
    with `_ANOMALY`'s signature."""
    return Case(
        case_id="trial-999",
        signature=ProblemSignature(
            namespace="unrelated-namespace",
            anomalous_kinds=frozenset({"ConfigMap"}),
            diverged_fields=frozenset({"ConfigMap.data=drifted"}),
        ),
        diagnosis="Unrelated ConfigMap drift.",
        mitigation_commands=("kubectl -n unrelated-namespace apply -f configmap.yaml",),
        outcome=True,
    )


# ---------------------------------------------------------------------------
# Pure-function unit tests -- no LM, no cluster
# ---------------------------------------------------------------------------


def test_symptom_signature_from_anomaly_is_a_real_problem_signature() -> None:
    signature = symptom_signature_from_anomaly(_ANOMALY)
    assert signature.namespace == "payments"
    assert signature.anomalous_kinds == frozenset({"Deployment"})
    assert signature.diverged_fields == frozenset({"Deployment.readyReplicas=0"})


def test_describe_anomaly_renders_every_field() -> None:
    text = describe_anomaly(_ANOMALY)
    assert "payments-api" in text
    assert "readyReplicas" in text
    assert "observed='0'" in text
    assert "expected='3'" in text


def test_taxonomy_is_real_and_finite() -> None:
    assert len(SREGYM_FAULT_TAXONOMY) == len(set(SREGYM_FAULT_TAXONOMY))
    assert "inject_scale_pods_to_zero" in SREGYM_FAULT_TAXONOMY
    # The fabricated category from this session's real prior failed trial
    # must never appear in the real taxonomy.
    assert "inject_image_pull_secret" not in SREGYM_FAULT_TAXONOMY
    assert "imagePullSecret" not in SREGYM_FAULT_TAXONOMY


def test_taxonomy_guard_rejects_off_taxonomy_category() -> None:
    reward_fn = _taxonomy_guard_reward(SREGYM_FAULT_TAXONOMY)
    fabricated = dspy.Prediction(category="imagePullSecret", confidence=0.9)
    assert reward_fn({}, fabricated) == 0.0


def test_taxonomy_guard_accepts_real_category_within_confidence_ceiling() -> None:
    reward_fn = _taxonomy_guard_reward(SREGYM_FAULT_TAXONOMY)
    real = dspy.Prediction(category="inject_scale_pods_to_zero", confidence=0.4)
    assert reward_fn({"confidence_ceiling": 0.5}, real) == 1.0


def test_taxonomy_guard_rejects_confidence_above_evidentiary_ceiling() -> None:
    reward_fn = _taxonomy_guard_reward(SREGYM_FAULT_TAXONOMY)
    overclaiming = dspy.Prediction(category="inject_scale_pods_to_zero", confidence=0.9)
    # A case-library similarity score of 0.3 (or ensemble agreement of 0.3)
    # cannot license a 0.9 confidence claim.
    assert reward_fn({"confidence_ceiling": 0.3}, overclaiming) == 0.0


def test_taxonomy_guard_accepts_unclassified() -> None:
    reward_fn = _taxonomy_guard_reward(SREGYM_FAULT_TAXONOMY)
    honest_refusal = dspy.Prediction(category=UNCLASSIFIED, confidence=0.1)
    assert reward_fn({}, honest_refusal) == 1.0


# ---------------------------------------------------------------------------
# Routing-logic tests: case-library hit vs. miss
# ---------------------------------------------------------------------------


def test_case_library_hit_short_circuits_before_any_lm_call() -> None:
    """A real case-library hit returns the real stored diagnosis/mitigation
    directly -- no LM configured, no LM call attempted, no exception."""
    store = CaseLibraryStore(":memory:")
    store.put(_matching_case())
    pipeline = SregymDiagnosisPipeline(store, environment=None, ensemble_n=2)

    result = pipeline(_ANOMALY)

    assert result.source == "case_library"
    assert result.case_id == "trial-001"
    assert result.diagnosis == "Deployment payments-api scaled to zero by a bad rollout."
    assert result.mitigation_commands == (
        "kubectl -n payments scale deployment payments-api --replicas=3",
    )
    assert result.taxonomy_category is None
    assert result.confidence == pytest.approx(1.0)


def test_case_library_miss_routes_past_short_circuit_into_reasoning_branch() -> None:
    """With no matching case and no LM configured, the pipeline must NOT
    silently fall back to the case-library branch -- it must actually reach
    the reasoning branch and fail there, for the real reason DSPy fails
    without a configured LM. This is a real, reproducible failure of the
    real routing code, asserted on directly (not a mock substitution for
    "and then it calls the LM")."""
    store = CaseLibraryStore(":memory:")
    store.put(_non_matching_case())
    pipeline = SregymDiagnosisPipeline(store, environment=None, ensemble_n=2)

    assert dspy.settings.lm is None  # precondition: no LM configured anywhere in this process

    with pytest.raises(AttributeError):
        pipeline(_ANOMALY)


def test_case_library_miss_with_empty_store_also_routes_to_reasoning() -> None:
    store = CaseLibraryStore(":memory:")
    pipeline = SregymDiagnosisPipeline(store, environment=None, ensemble_n=2)

    with pytest.raises(AttributeError):
        pipeline(_ANOMALY)


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def test_retain_persists_only_on_confirmed_or_disputed_verdict() -> None:
    """Exercises all three real :class:`OutcomeVerdict` retention paths
    against a real :class:`CaseLibraryStore` (SQLite ``:memory:``), using
    the real :func:`evaluate_outcome` decision function to produce each
    verdict rather than constructing ``OutcomeVerdict`` members by hand --
    so this test proves the pipeline's ``retain`` wiring, not just its own
    understanding of the enum.
    """
    from autofde_lab.case_library.outcome_predicate import OracleVerdict, evaluate_outcome
    from autofde_lab.reasoning.sregym_pipeline import PipelineResult

    store = CaseLibraryStore(":memory:")
    pipeline = SregymDiagnosisPipeline(store, environment=None, ensemble_n=2)
    result = PipelineResult(
        source="reasoning",
        diagnosis="Deployment payments-api scaled to zero.",
        mitigation_commands=(),
        taxonomy_category="inject_scale_pods_to_zero",
        confidence=0.7,
    )
    mitigation = ("kubectl -n payments scale deployment payments-api --replicas=3",)

    # UNCONFIRMED: structural re-check itself failed -- refuse to retain.
    unconfirmed_verdict, unconfirmed_via = evaluate_outcome(
        structural_passed=False, oracle=OracleVerdict(present=False)
    )
    refused = pipeline.retain(
        _ANOMALY,
        result,
        mitigation_commands=mitigation,
        verdict=unconfirmed_verdict,
        confirmed_via=unconfirmed_via,
    )
    assert refused is None
    assert len(store) == 0

    # DISPUTED: structural re-check passed, but a present oracle disagreed --
    # retained as its own tagged artifact, never discarded and never
    # coerced into a boolean outcome.
    disputed_verdict, disputed_via = evaluate_outcome(
        structural_passed=True, oracle=OracleVerdict(present=True, passed=False)
    )
    disputed = pipeline.retain(
        _ANOMALY,
        result,
        mitigation_commands=mitigation,
        verdict=disputed_verdict,
        confirmed_via=disputed_via,
        case_id="trial-disputed-001",
    )
    assert disputed is not None
    assert disputed.outcome is None
    assert disputed.confirmed_via == "disputed"
    assert len(store) == 1
    reloaded_disputed = store.get("trial-disputed-001")
    assert reloaded_disputed is not None
    assert reloaded_disputed.outcome is None
    assert reloaded_disputed.confirmed_via == "disputed"

    # CONFIRMED via structural check alone (no oracle consulted).
    confirmed_verdict, confirmed_via = evaluate_outcome(
        structural_passed=True, oracle=OracleVerdict(present=False)
    )
    assert confirmed_via == "structural_only"
    retained = pipeline.retain(
        _ANOMALY,
        result,
        mitigation_commands=mitigation,
        verdict=confirmed_verdict,
        confirmed_via=confirmed_via,
        case_id="trial-retained-001",
    )
    assert retained is not None
    assert retained.case_id == "trial-retained-001"
    assert retained.outcome is True
    assert retained.confirmed_via == "structural_only"
    assert len(store) == 2

    reloaded = store.get("trial-retained-001")
    assert reloaded is not None
    assert reloaded.diagnosis == "Deployment payments-api scaled to zero."
    assert reloaded.mitigation_commands == mitigation
    assert reloaded.outcome is True
    assert reloaded.confirmed_via == "structural_only"

    # CONFIRMED via structural check AND oracle agreement.
    confirmed_oracle_verdict, confirmed_oracle_via = evaluate_outcome(
        structural_passed=True, oracle=OracleVerdict(present=True, passed=True)
    )
    assert confirmed_oracle_via == "structural_and_oracle"
    retained_with_oracle = pipeline.retain(
        _ANOMALY,
        result,
        mitigation_commands=mitigation,
        verdict=confirmed_oracle_verdict,
        confirmed_via=confirmed_oracle_via,
        case_id="trial-retained-002",
    )
    assert retained_with_oracle is not None
    assert retained_with_oracle.outcome is True
    assert retained_with_oracle.confirmed_via == "structural_and_oracle"
    assert len(store) == 3


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
def test_live_groq_taxonomy_guard_rejects_fabricated_category() -> None:
    """Real end-to-end: a real Groq LM call classifies a deliberately
    fabricated-looking anomaly, and the dspy.Refine taxonomy guard must
    either land on a real taxonomy category (or UNCLASSIFIED) -- never an
    invented label -- proving the guard actually constrains a real LM
    output, not a scripted one."""
    lm = dspy.LM("groq/openai/gpt-oss-20b", api_key=_GROQ_API_KEY, cache=True)
    dspy.configure(lm=lm)
    try:
        store = CaseLibraryStore(":memory:")
        pipeline = SregymDiagnosisPipeline(store, environment=None, ensemble_n=2)

        fabricated_looking_anomaly = Anomaly(
            kind="Secret",
            object_name="ghost-registry-cred",
            namespace="nonexistent-ns-zzz",
            relation_class="dangling_reference",
            field="spec.imagePullSecrets[0].name",
            observed="does-not-exist-anywhere",
            expected=None,
            detail=(
                "Pod references imagePullSecret 'does-not-exist-anywhere' which "
                "is not present in any namespace; this symptom does not match "
                "any known SREGym fault-injector signature."
            ),
        )

        result = pipeline(fabricated_looking_anomaly)

        assert result.source == "reasoning"
        assert result.taxonomy_category in set(SREGYM_FAULT_TAXONOMY) | {UNCLASSIFIED}
        assert 0.0 <= result.confidence <= 1.0
    finally:
        dspy.configure(lm=None)
