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
    surviving hypotheses. Each step MUST copy one exact `capability_id` from the supplied
    capability catalog and shape `arguments` according to that capability's input_schema.
    Never invent a surface, tool name, capability ID, argument name, or benchmark fault
    category. Prefer observations whose possible outcomes falsify multiple competitors.
    Do not actuate. If prior candidates were refused, obey those typed refusals rather
    than repeating the same invalid process.
    """

    facts_json: str = dspy.InputField()
    hypotheses_json: str = dspy.InputField()
    obligations_json: str = dspy.InputField()
    capabilities_json: str = dspy.InputField()
    rejections_json: str = dspy.InputField()
    max_steps: int = dspy.InputField()
    process: ObservationProcessProposal = dspy.OutputField()


class CommitDiagnosis(dspy.Signature):
    """Describe the smallest causal explanation justified by externally computed
    epistemic standing. The input is already at causal closure; do not broaden it.
    Reference only supplied hypothesis IDs and admitted fact IDs.
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
    diagnosis. Each step MUST copy one exact `capability_id` from the supplied catalog
    and use only arguments admitted by that capability's input_schema. Consequential
    steps are explicit DO; verification is explicit VERIFY. Prefer reversible causal
    repairs. Never invent a capability, surface, tool name, or benchmark fault category.
    Do not execute.
    """

    diagnosis_json: str = dspy.InputField()
    facts_json: str = dspy.InputField()
    capabilities_json: str = dspy.InputField()
    max_processes: int = dspy.InputField()
    processes: list[MitigationProcessProposal] = dspy.OutputField()
