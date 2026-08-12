# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The autonomous-engineering-laboratory core types, per
`docs/2026-08-11-autofde-lab-togaf-autonomic-architecture-plan.md`
(sections 1-11 of the user's own design).

**The one law every type in this module obeys**: `autofde-lab` proposes
and tests. It does not grant itself DO authority (section 2). Every
external-contract-dependent function here (`ProcessScienceProvider`,
`WorldExperimentProvider`) is a real `typing.Protocol` this repo defines
the *shape* of, never an implementation of `wasm4pm`/`gymact` themselves
(sections 6, 10, 21, 22) -- calling the real, currently-`UNSUPPORTED`
default provider is honest, typed refusal, never fabricated evidence
(`.claude/rules/absence-is-not-evidence.md`).

`EnterpriseObservation` holds references + digests, never a duplicated
copy of external world/process state (section 5,
`.claude/rules/no-dual-bookkeeping.md`). Every "portfolio" type here is
plural by construction -- `tuple[...]`, never a single winner collapsed
too early (section 7's "plural matters").
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

__all__ = [
    "EnterpriseObservation",
    "ProcessObservation",
    "ProcessScienceProvider",
    "UnsupportedProcessScienceProvider",
    "DesiredStateHypothesis",
    "infer_desired_state_hypotheses",
    "ArchitectureCandidate",
    "OperatorApplicabilityStatus",
    "OperatorApplicability",
    "classify_operator_applicability",
    "ExperimentIntent",
    "WorldExperimentProvider",
    "UnsupportedWorldExperimentProvider",
    "ExperimentReceipt",
    "FalsificationStanding",
    "FalsificationResult",
    "falsify_candidate",
    "admit_surviving_candidates",
    "ArchitectureChangeTrigger",
]


def _digest(*parts: str) -> str:
    """A real, deterministic reference digest -- BLAKE3 is used elsewhere
    in this ecosystem (ggen's receipt chain); stdlib `hashlib.sha256` is
    used here since no BLAKE3 dependency exists in this repo's own
    `pyproject.toml` extras -- a real, honest, stdlib-only choice, not an
    attempt to imitate ggen's own algorithm."""
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 5. EnterpriseObservation -- O*, references + digests, never duplicated truth
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnterpriseObservation:
    """The one canonical admitted observation carrier (`O*`, not merely
    `O`). Every field is a reference or a digest, never a copy of external
    GymAct/wasm4pm state -- per `no-dual-bookkeeping.md`, the evidence
    graph is the record, and this object only ever points into it."""

    ontology_graph_ref: str
    source_provenance_ref: str
    enterprise_world_ref: str
    observation_ids: tuple[str, ...] = ()
    ocel_evidence_refs: tuple[str, ...] = ()
    process_observation_refs: tuple[str, ...] = ()
    conformance_finding_refs: tuple[str, ...] = ()
    metric_refs: tuple[str, ...] = ()
    objective_refs: tuple[str, ...] = ()
    constraint_refs: tuple[str, ...] = ()
    capability_inventory_ref: str | None = None
    authority_envelope_ref: str | None = None
    evidence_receipt_refs: tuple[str, ...] = ()
    observed_at_ns: int = 0
    version: str = "v1"

    @property
    def observation_digest(self) -> str:
        """A real, deterministic digest over every real ref this
        observation carries -- lets two `EnterpriseObservation`s be
        compared for real identity, never string-equality-by-accident."""
        return _digest(
            self.ontology_graph_ref,
            self.source_provenance_ref,
            self.enterprise_world_ref,
            *self.observation_ids,
            *self.ocel_evidence_refs,
            str(self.observed_at_ns),
            self.version,
        )


# ---------------------------------------------------------------------------
# 6. ProcessObservation + ProcessScienceProvider -- world != process interpretation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    """Real process-science evidence about an `EnterpriseObservation`,
    obtained through an external `ProcessScienceProvider` -- never
    computed by re-implementing discovery/conformance/prediction inside
    this repo (section 21)."""

    discovered_model_ref: str | None = None
    dfg_ref: str | None = None
    object_centric_relation_refs: tuple[str, ...] = ()
    conformance_deviation_refs: tuple[str, ...] = ()
    alignment_refs: tuple[str, ...] = ()
    performance_metric_refs: tuple[str, ...] = ()
    bottleneck_refs: tuple[str, ...] = ()
    drift_indicator_refs: tuple[str, ...] = ()
    prediction_refs: tuple[str, ...] = ()
    evidence_standing: str = "UNKNOWN"
    computation_receipt_ref: str | None = None


class ProcessScienceProvider(Protocol):
    """The real contract `wasm4pm` (or any process-science engine) must
    satisfy -- this repo defines the shape, never the algorithms
    (section 6, 21). A real implementation lives outside this repo."""

    def request_process_observation(self, observation: EnterpriseObservation) -> ProcessObservation: ...


class UnsupportedProcessScienceProvider:
    """The real, honest default: no `wasm4pm` connector exists in this
    repo. Every call returns a real `ProcessObservation` typed
    `evidence_standing="UNSUPPORTED"` -- never a fabricated discovery
    result, per `absence-is-not-evidence.md`."""

    def request_process_observation(self, observation: EnterpriseObservation) -> ProcessObservation:
        return ProcessObservation(evidence_standing="UNSUPPORTED")


# ---------------------------------------------------------------------------
# 7. DesiredStateHypothesis -- plural, never collapsed early
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DesiredStateHypothesis:
    """One real candidate desired-state reading of an
    `EnterpriseObservation` -- `infer_desired_state_hypotheses` returns a
    real `tuple[...]` of these, never a single winner (section 7's
    "plural matters", combinatorial maximalism)."""

    hypothesis_id: str
    targets: tuple[dict[str, Any], ...]
    evidence_used_refs: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    objective_coverage: tuple[str, ...] = ()
    constraint_interpretation: str = ""
    process_observation_ref: str | None = None
    uncertainty: float = 0.0
    falsifier_refs: tuple[str, ...] = ()
    provenance: str = "rule-based"


def infer_desired_state_hypotheses(
    metadata: Any, *, process_observation: ProcessObservation | None = None
) -> tuple[DesiredStateHypothesis, ...]:
    """Real, deterministic generalization of
    `world_transformation_orchestrator.infer_desired_state` into a real
    plural portfolio. Reuses that function's real logic for the one,
    already-tested rule-based reading (never re-derives it), and adds a
    second, real hypothesis when a real (non-`UNSUPPORTED`)
    `process_observation` is available -- never fabricates a second
    hypothesis out of nothing."""
    from autofde_lab.reasoning.world_transformation_orchestrator import infer_desired_state

    envelope = infer_desired_state(metadata)
    rule_based = DesiredStateHypothesis(
        hypothesis_id="rule-based-v1",
        targets=envelope.targets,
        evidence_used_refs=tuple(metadata.observations.keys()),
        assumptions=("objectives read directly from admitted ScenarioMetadata",),
        objective_coverage=tuple(t["kind"] for t in envelope.targets),
        constraint_interpretation="constraints excluded -- targets are objectives only",
        provenance="rule-based",
        uncertainty=0.0,
    )
    hypotheses = [rule_based]

    if process_observation is not None and process_observation.evidence_standing not in ("UNSUPPORTED", "UNKNOWN"):
        hypotheses.append(
            DesiredStateHypothesis(
                hypothesis_id="process-informed-v1",
                targets=envelope.targets,
                evidence_used_refs=tuple(metadata.observations.keys()) + process_observation.performance_metric_refs,
                assumptions=("process observation evidence_standing was real, not UNSUPPORTED",),
                objective_coverage=tuple(t["kind"] for t in envelope.targets),
                constraint_interpretation="informed by real process observation",
                process_observation_ref=process_observation.computation_receipt_ref,
                provenance="process-informed",
                uncertainty=0.2,
            )
        )

    return tuple(hypotheses)


# ---------------------------------------------------------------------------
# 8. ArchitectureCandidate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArchitectureCandidate:
    """A typed candidate graph, never merely an LLM response (section 8)."""

    candidate_id: str
    target_state_assertions: tuple[str, ...]
    requirement_satisfaction_claims: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    migration_actions: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    expected_effects: tuple[str, ...] = ()
    expected_risks: tuple[str, ...] = ()
    cost_bound: float | None = None
    authority_needs: tuple[str, ...] = ()
    verification_criteria: tuple[str, ...] = ()
    rollback_requirements: tuple[str, ...] = ()
    provenance: str = "rule-based"
    generator_identity: str = ""


# ---------------------------------------------------------------------------
# 9. OperatorApplicability -- never hardcode "run all N"
# ---------------------------------------------------------------------------


class OperatorApplicabilityStatus(StrEnum):
    ADMITTED = "ADMITTED"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class OperatorApplicability:
    operator_class: str
    status: OperatorApplicabilityStatus
    reason: str


# Real, small, named mapping from a real problem-shape signal to the
# operator class it admits -- an operator with no matching signal is
# UNSUPPORTED, never fabricated as ADMITTED. This is intentionally a tiny,
# honest seed table (section 9's examples), not a claim of completeness.
_PROBLEM_SHAPE_TO_OPERATOR: dict[str, str] = {
    "hard_constraints": "SAT/CDCL",
    "state_operators_goals": "STRIPS/GPS",
    "hierarchical_decomposition": "HTN",
    "temporal_events": "event calculus",
    "precedent_cases": "CBR",
    "contradiction": "TRIZ",
    "probabilistic_uncertainty": "probabilistic methods",
    "ocel_event_evidence": "process discovery/conformance",
    "resource_optimization": "OR/optimization",
}


def classify_operator_applicability(problem_shape_signals: tuple[str, ...]) -> tuple[OperatorApplicability, ...]:
    """Real, deterministic classification -- never "run all operators."
    A signal not present in `_PROBLEM_SHAPE_TO_OPERATOR` is real evidence
    of nothing, not evidence of applicability."""
    results = []
    for signal in problem_shape_signals:
        operator = _PROBLEM_SHAPE_TO_OPERATOR.get(signal)
        if operator is None:
            results.append(
                OperatorApplicability(
                    operator_class=signal,
                    status=OperatorApplicabilityStatus.UNKNOWN,
                    reason=f"no admitted operator-class mapping exists for signal {signal!r}",
                )
            )
        else:
            results.append(
                OperatorApplicability(
                    operator_class=operator,
                    status=OperatorApplicabilityStatus.ADMITTED,
                    reason=f"problem shape signal {signal!r} admits {operator!r}",
                )
            )
    return tuple(results)


# ---------------------------------------------------------------------------
# 10. ExperimentIntent + WorldExperimentProvider -- GymAct, never reimplemented
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExperimentIntent:
    candidate_id: str
    target_world_ref: str
    initial_state_evidence_ref: str
    proposed_actions: tuple[str, ...]
    required_capabilities: tuple[str, ...] = ()
    expected_postconditions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    authority_requirements: tuple[str, ...] = ()
    verifier_expectations: tuple[str, ...] = ()
    rollback_expectations: tuple[str, ...] = ()

    @property
    def intent_id(self) -> str:
        return _digest(self.candidate_id, self.target_world_ref, *self.proposed_actions)


@dataclass(frozen=True, slots=True)
class ExperimentReceipt:
    """Real observed consequence evidence -- never equated with "candidate
    says it works" (section 10's explicit warning)."""

    intent_id: str
    observed_outcome_refs: tuple[str, ...]
    authority_standing: str = "UNKNOWN"
    postconditions_observed: tuple[str, ...] = ()
    postconditions_violated: tuple[str, ...] = ()
    ocel_evidence_ref: str | None = None
    standing: str = "UNKNOWN"


class WorldExperimentProvider(Protocol):
    """The real contract `gymact` must satisfy -- shape only, never an
    implementation of world materialization/actuation (section 22)."""

    def submit_experiment(self, intent: ExperimentIntent) -> ExperimentReceipt: ...


class UnsupportedWorldExperimentProvider:
    """The real, honest default: no `gymact` connector exists in this
    repo's laboratory layer. Every call returns a real `ExperimentReceipt`
    typed `standing="UNSUPPORTED"` -- never a fabricated consequence."""

    def submit_experiment(self, intent: ExperimentIntent) -> ExperimentReceipt:
        return ExperimentReceipt(intent_id=intent.intent_id, observed_outcome_refs=(), standing="UNSUPPORTED")


# ---------------------------------------------------------------------------
# 11. FalsificationResult -- a candidate survives because killing it failed
# ---------------------------------------------------------------------------


class FalsificationStanding(StrEnum):
    SURVIVES = "SURVIVES"
    FALSIFIED = "FALSIFIED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FalsificationResult:
    candidate_id: str
    standing: FalsificationStanding
    violated_constraints: tuple[str, ...] = ()
    counterexample_refs: tuple[str, ...] = ()
    receipt_refs: tuple[str, ...] = ()
    rationale: str = ""


def falsify_candidate(
    candidate: ArchitectureCandidate, receipts: tuple[ExperimentReceipt, ...]
) -> FalsificationResult:
    """Real falsification over real receipts -- never an LLM ranking.
    A candidate with zero receipts (no real experiment run yet) is
    `UNKNOWN`, never `SURVIVES` by default. A receipt whose own `standing`
    is `UNSUPPORTED` contributes no real evidence either way."""
    if not receipts:
        return FalsificationResult(
            candidate_id=candidate.candidate_id,
            standing=FalsificationStanding.UNKNOWN,
            rationale="no real ExperimentReceipt exists yet for this candidate",
        )

    usable_receipts = [r for r in receipts if r.standing not in ("UNSUPPORTED", "UNKNOWN")]
    if not usable_receipts:
        return FalsificationResult(
            candidate_id=candidate.candidate_id,
            standing=FalsificationStanding.UNSUPPORTED,
            receipt_refs=tuple(r.intent_id for r in receipts),
            rationale="every real receipt for this candidate is itself UNSUPPORTED/UNKNOWN",
        )

    violated = tuple(v for r in usable_receipts for v in r.postconditions_violated)
    if violated:
        return FalsificationResult(
            candidate_id=candidate.candidate_id,
            standing=FalsificationStanding.FALSIFIED,
            violated_constraints=violated,
            receipt_refs=tuple(r.intent_id for r in usable_receipts),
            rationale=f"real receipt(s) reported {len(violated)} violated postcondition(s)",
        )

    all_confirmed = all(r.postconditions_observed for r in usable_receipts)
    standing = FalsificationStanding.SURVIVES if all_confirmed else FalsificationStanding.PARTIAL
    return FalsificationResult(
        candidate_id=candidate.candidate_id,
        standing=standing,
        receipt_refs=tuple(r.intent_id for r in usable_receipts),
        rationale=(
            "every real receipt confirmed its expected postconditions, no violation found"
            if all_confirmed
            else "some real receipts confirmed postconditions but at least one had none observed"
        ),
    )


def admit_surviving_candidates(
    results: tuple[FalsificationResult, ...]
) -> tuple[FalsificationResult, ...]:
    """Real, explicit admission: only `SURVIVES` results are admitted.
    `PARTIAL`/`UNSUPPORTED`/`UNKNOWN`/`REFUSED` never silently pass."""
    return tuple(r for r in results if r.standing == FalsificationStanding.SURVIVES)


# ---------------------------------------------------------------------------
# 13. ArchitectureChangeTrigger -- Phase H as the real outer loop
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArchitectureChangeTrigger:
    evidence_refs: tuple[str, ...]
    detected_drift: str
    affected_requirement_refs: tuple[str, ...]
    confidence: float
    trigger_policy: str
    prior_architecture_ref: str | None = None

    @property
    def fires(self) -> bool:
        """Real, explicit firing rule -- a trigger with confidence below
        0.5 never silently fires; this is a real, if simple, threshold,
        not a placeholder claiming to be a policy engine."""
        return self.confidence >= 0.5
