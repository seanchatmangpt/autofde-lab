from pathlib import Path

import dspy

from autofde_lab.sregym_sota import SIGNATURE_REVISION
from autofde_lab.sregym_sota.signatures import (
    ChallengeDiagnosis,
    CommitDiagnosis,
    ConstructDiscriminationProcess,
    ConstructMitigationProcesses,
    GenerateHypotheses,
    OrientIncident,
    RelateEvidence,
)


def test_signature_revision_is_explicit() -> None:
    assert SIGNATURE_REVISION == "SRE-SIG-002"


def test_exact_signature_surface() -> None:
    signatures = {
        OrientIncident,
        GenerateHypotheses,
        RelateEvidence,
        ConstructDiscriminationProcess,
        CommitDiagnosis,
        ChallengeDiagnosis,
        ConstructMitigationProcesses,
    }
    assert len(signatures) == 7
    assert all(issubclass(signature, dspy.Signature) for signature in signatures)


def test_cognition_source_contains_no_gepa_or_prompt_compiler() -> None:
    package = Path(__file__).parents[2] / "src" / "autofde_lab" / "sregym_sota"
    text = "\n".join(path.read_text() for path in sorted(package.glob("*.py"))).lower()
    assert "dspy.gepa" not in text
    assert "dspy.mipro" not in text
    assert "bootstrapfewshot" not in text


def test_core_contains_no_sregym_problem_ids_or_fault_taxonomy_keys() -> None:
    package = Path(__file__).parents[2] / "src" / "autofde_lab" / "sregym_sota"
    text = "\n".join(path.read_text() for path in sorted(package.glob("*.py")))
    forbidden = (
        "target_port",
        "incorrect_image",
        "network_policy_block",
        "duplicate_pvc",
        "fault_id",
        "fault_type",
    )
    assert not any(token in text for token in forbidden)


def test_discriminator_requires_exact_capability_identity_and_rejection_feedback() -> None:
    inputs = ConstructDiscriminationProcess.input_fields
    assert "capabilities_json" in inputs
    assert "rejections_json" in inputs
    doc = ConstructDiscriminationProcess.__doc__ or ""
    assert "capability_id" in doc
    assert "input_schema" in doc
