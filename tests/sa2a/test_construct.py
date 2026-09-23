r"""Unit tests for CONSTRUCT and Ephemeral Projection Engine (RFC-SA2A-001 v26.9.16).

Validates:
1. Deterministic manufacturing of artifacts from admitted semantics O* ($A = \mu(O*)$).
2. ConstructionReceipt creation, integrity, and binding.
3. Ephemeral software lifecycle: $O* \to G \to C_t \to \text{Verify} \to \text{Run} \to \text{Discard}$.
4. Fundamental projection boundary: $GeneratedCode \neq SemanticTruth$. Modifying projected
   artifacts leaves canonical state $O*$ untouched and fails verification.
"""

from __future__ import annotations

import pytest

from autofde_lab.sa2a.construct.constructor import (
    AdmittedSemantics,
    ArtifactManufacturer,
    TargetProfile,
)
from autofde_lab.sa2a.construct.ephemeral import (
    EphemeralLifecycleRunner,
    EphemeralProjectionWrapper,
    EphemeralState,
)


@pytest.fixture
def sample_admitted_semantics() -> AdmittedSemantics:
    """Fixture providing admitted canonical semantics O*."""
    return AdmittedSemantics(
        ontology_id="https://seanchatman.dev/ontology/sa2a/core",
        canonical_triples=(
            "<urn:agent:1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <urn:agent:Class>",
            "<urn:agent:1> <urn:action:canExecute> <urn:task:verify>",
            "<urn:task:verify> <urn:status> <urn:status:ALIVE>",
        ),
        semantic_version="v26.9.16",
        provenance_hash="7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        metadata=(("author", "Agent 7"), ("rfc", "RFC-SA2A-001")),
    )


def test_deterministic_manufacture(
    sample_admitted_semantics: AdmittedSemantics,
) -> None:
    r"""Test that manufacturing A = \mu(O*) is completely deterministic."""
    manufacturer = ArtifactManufacturer(
        manufacturer_identity="urn:autofde:sa2a:constructor",
        manufacturer_version="26.9.16",
    )

    artifact_1 = manufacturer.manufacture(
        sample_admitted_semantics, TargetProfile.PYTHON_EPHEMERAL
    )
    artifact_2 = manufacturer.manufacture(
        sample_admitted_semantics, TargetProfile.PYTHON_EPHEMERAL
    )

    assert artifact_1.artifact_digest == artifact_2.artifact_digest
    assert artifact_1.source_code == artifact_2.source_code
    assert artifact_1.receipt.receipt_id == artifact_2.receipt.receipt_id
    assert (
        artifact_1.receipt.admitted_input_digest
        == sample_admitted_semantics.canonical_digest()
    )


def test_construction_receipt_binding(
    sample_admitted_semantics: AdmittedSemantics,
) -> None:
    """Validate that ConstructionReceipt binds admitted input, manufacturer, profile, and artifact."""
    manufacturer = ArtifactManufacturer()
    artifact = manufacturer.manufacture(
        sample_admitted_semantics, TargetProfile.PYTHON_EPHEMERAL
    )

    receipt = artifact.receipt
    assert receipt.admitted_input_digest == sample_admitted_semantics.canonical_digest()
    assert receipt.output_artifact_digest == artifact.artifact_digest
    assert receipt.target_profile == TargetProfile.PYTHON_EPHEMERAL
    assert receipt.verify(sample_admitted_semantics, artifact) is True

    # Tampered O* should fail receipt verification
    different_semantics = AdmittedSemantics(
        ontology_id="https://seanchatman.dev/ontology/sa2a/core",
        canonical_triples=("<urn:agent:mutated> <urn:status> <urn:status:BLOCKED>",),
    )
    assert receipt.verify(different_semantics, artifact) is False


def test_different_target_profiles(
    sample_admitted_semantics: AdmittedSemantics,
) -> None:
    """Test manufacturing projections across different target profiles."""
    manufacturer = ArtifactManufacturer()

    profiles = [
        TargetProfile.PYTHON_EPHEMERAL,
        TargetProfile.JSON_SCHEMA,
        TargetProfile.BASH_DISPATCH,
        TargetProfile.BEAM_ATOMVM,
    ]

    for profile in profiles:
        artifact = manufacturer.manufacture(
            sample_admitted_semantics, target_profile=profile
        )
        assert artifact.target_profile == profile
        assert artifact.receipt.verify(sample_admitted_semantics, artifact) is True
        assert len(artifact.source_code) > 0


def test_ephemeral_lifecycle(sample_admitted_semantics: AdmittedSemantics) -> None:
    """Validate full ephemeral software lifecycle (§27): O* -> G -> C_t -> Verify -> Run -> Discard."""
    manufacturer = ArtifactManufacturer()
    artifact = manufacturer.manufacture(
        sample_admitted_semantics, TargetProfile.PYTHON_EPHEMERAL
    )

    wrapper = EphemeralProjectionWrapper(sample_admitted_semantics, artifact)
    assert wrapper.state == EphemeralState.GENERATED

    wrapper.compile()
    assert wrapper.state == EphemeralState.COMPILED

    verified = wrapper.verify()
    assert verified is True
    assert wrapper.state == EphemeralState.VERIFIED

    result = wrapper.execute({"param": 42})
    assert result.verified is True
    assert result.state == EphemeralState.EXECUTED
    assert result.output["status"] == "ALIVE"
    assert result.output["triples_count"] == 3
    assert result.output["inputs"] == {"param": 42}

    wrapper.discard()
    assert wrapper.state == EphemeralState.DISCARDED

    # Compilation or execution after discard should fail
    with pytest.raises(RuntimeError, match="discarded"):
        wrapper.compile()


def test_ephemeral_lifecycle_runner(
    sample_admitted_semantics: AdmittedSemantics,
) -> None:
    """Validate end-to-end EphemeralLifecycleRunner helper."""
    runner = EphemeralLifecycleRunner()
    res = runner.run_lifecycle(
        sample_admitted_semantics, TargetProfile.PYTHON_EPHEMERAL, {"key": "val"}
    )

    assert res.verified is True
    assert res.output["status"] == "ALIVE"
    assert res.output["inputs"] == {"key": "val"}


def test_projection_cannot_mutate_canonical_semantics(
    sample_admitted_semantics: AdmittedSemantics,
) -> None:
    """Validate that GeneratedCode != SemanticTruth.

    Modifying projected code:
    1. Produces an invalid receipt check.
    2. Leaves canonical O* completely untouched.
    """
    manufacturer = ArtifactManufacturer()
    artifact = manufacturer.manufacture(
        sample_admitted_semantics, TargetProfile.PYTHON_EPHEMERAL
    )
    original_digest = sample_admitted_semantics.canonical_digest()

    wrapper = EphemeralProjectionWrapper(sample_admitted_semantics, artifact)

    tampered_code = artifact.source_code.replace(
        "'status': 'ALIVE'", "'status': 'MUTATED_AUTHORITY'"
    )
    tampered_artifact = wrapper.mutate_code_attempt(tampered_code)

    # Canonical semantics O* remains strictly unchanged
    assert sample_admitted_semantics.canonical_digest() == original_digest
    assert wrapper.canonical_semantics.canonical_digest() == original_digest

    # Tampered artifact fails receipt verification
    tampered_wrapper = EphemeralProjectionWrapper(
        sample_admitted_semantics, tampered_artifact
    )
    tampered_wrapper.compile()
    assert tampered_wrapper.verify() is False
    assert tampered_wrapper.state == EphemeralState.TAMPERED

    with pytest.raises(RuntimeError, match="Integrity verification failed"):
        tampered_wrapper.execute()


def test_custom_renderer(sample_admitted_semantics: AdmittedSemantics) -> None:
    """Test custom projection renderer function."""
    manufacturer = ArtifactManufacturer()

    def custom_renderer(admitted: AdmittedSemantics) -> tuple[str, str]:
        code = (
            f"# Custom projection for {admitted.ontology_id}\n"
            f"def custom_main(arg):\n"
            f"    return f'processed_{{arg}}'\n"
        )
        return code, "custom_main"

    artifact = manufacturer.manufacture(
        sample_admitted_semantics,
        target_profile=TargetProfile.PYTHON_EPHEMERAL,
        custom_renderer=custom_renderer,
    )

    assert artifact.entrypoint == "custom_main"
    assert artifact.receipt.verify(sample_admitted_semantics, artifact) is True

    wrapper = EphemeralProjectionWrapper(sample_admitted_semantics, artifact)
    wrapper.compile()
    wrapper.verify()
    result = wrapper.execute("payload")
    assert result.output == "processed_payload"
