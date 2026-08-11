from __future__ import annotations

import dspy

from .models import (
    DiagnosisCandidate,
    EpistemicObligation,
    EvidenceLinkProposal,
    HypothesisProposal,
    MitigationProcessProposal,
    ObservationProcessProposal,
)


class OrientIncident(dspy.Signature):
    """Orient to the observed operational system without assuming a fault taxonomy.
    Separate observed facts from assumptions and identify the smallest relevant boundary.
    """

    goal: str = dspy.InputField()
    facts_json: str = dspy.InputField()
    capabilities_json: str = dspy.InputField()
    focus: str = dspy.OutputField()
    open_questions: list[str] = dspy.OutputField()


class GenerateHypotheses(dspy.Signature):
    """Manufacture a diverse portfolio of falsifiable causal hypotheses.
    Do not use a predefined benchmark/fault taxonomy. Prefer mechanisms over symptoms,
    distinguish causes from victims, and give each hypothesis predictions and falsifiers.
    """

    goal: str = dspy.InputField()
    facts_json: str = dspy.InputField()
    prior_hypotheses_json: str = dspy.InputField()
    max_hypotheses: int = dspy.InputField()
    hypotheses: list[HypothesisProposal] = dspy.OutputField()


class RelateEvidence(dspy.Signature):
    """Propose relationships between admitted fact IDs and hypotheses.
    Never assign epistemic standing. Cite only fact IDs present in the input.
    """

    facts_json: str = dspy.InputField()
    hypotheses_json: str = dspy.InputField()
    links: list[EvidenceLinkProposal] = dspy.OutputField()
    obligations: list[EpistemicObligation] = dspy.OutputField()


class ConstructDiscriminationProcess(dspy.Signature):
    """Construct a bounded POWL-compatible observation process that partitions the
    surviving hypotheses. Every step must use a discovered capability. Prefer reads
    whose possible outcomes can falsify multiple competitors. Do not actuate.
    """

    facts_json: str = dspy.InputField()
    hypotheses_json: str = dspy.InputField()
    obligations_json: str = dspy.InputField()
    capabilities_json: str = dspy.InputField()
    max_steps: int = dspy.InputField()
    process: ObservationProcessProposal = dspy.OutputField()


class CommitDiagnosis(dspy.Signature):
    """Describe the smallest causal explanation justified by externally computed
    epistemic standing. The input is already at causal closure; do not broaden it.
    """

    facts_json: str = dspy.InputField()
    hypotheses_json: str = dspy.InputField()
    diagnosis: DiagnosisCandidate = dspy.OutputField()


class ChallengeDiagnosis(dspy.Signature):
    """Try to falsify the proposed diagnosis and return evidence obligations only.
    Check temporal behavior, victim-versus-cause errors, viable competitors, symptom
    coverage, and whether removing the cause predicts recovery. Do not assign standing.
    """

    diagnosis_json: str = dspy.InputField()
    facts_json: str = dspy.InputField()
    hypotheses_json: str = dspy.InputField()
    obligations: list[EpistemicObligation] = dspy.OutputField()


class ConstructMitigationProcesses(dspy.Signature):
    """Construct multiple lawful POWL-compatible recovery processes for the admitted
    diagnosis. Use only discovered capabilities. Consequential steps are explicit DO;
    verification is explicit VERIFY. Prefer reversible causal repairs. Do not execute.
    """

    diagnosis_json: str = dspy.InputField()
    facts_json: str = dspy.InputField()
    capabilities_json: str = dspy.InputField()
    max_processes: int = dspy.InputField()
    processes: list[MitigationProcessProposal] = dspy.OutputField()
