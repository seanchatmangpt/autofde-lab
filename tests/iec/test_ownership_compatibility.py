"""Ownership, compatibility, and native-parser intent tests."""

from __future__ import annotations

from autofde_lab.iec.compatibility import compare_python_api
from autofde_lab.iec.native_parser import (
    NativeParserCapability,
    NativeParserRegistry,
    ParserCapabilityStanding,
    candidate_native_parsers,
)
from autofde_lab.iec.ownership import (
    ArtifactOwnership,
    OwnershipEvidence,
    OwnershipEvidenceKind,
    OwnershipResolver,
    OwnershipStanding,
)
from autofde_lab.iec.python_api import extract_python_api


def evidence(
    producer: str,
    kind: OwnershipEvidenceKind,
    evidence_id: str,
) -> OwnershipEvidence:
    return OwnershipEvidence(
        artifact_id="artifact",
        producer=producer,
        kind=kind,
        evidence_id=evidence_id,
        exact_subject_id="subject",
    )


def test_ownership_resolver_preserves_conflicting_producers() -> None:
    result = OwnershipResolver().resolve(
        "artifact",
        (
            evidence("ggen", OwnershipEvidenceKind.EXPLICIT_MANIFEST, "m"),
            evidence("handwritten", OwnershipEvidenceKind.DOCUMENTED_DOCTRINE, "d"),
        ),
    )
    assert result.standing is OwnershipStanding.CONTRADICTED
    assert result.producer is None
    assert result.conflicting_producers == ("ggen", "handwritten")


def test_explicit_manifest_yields_observed_ownership() -> None:
    result = OwnershipResolver().resolve(
        "artifact",
        (
            evidence("ggen", OwnershipEvidenceKind.EXPLICIT_MANIFEST, "m"),
            evidence("ggen", OwnershipEvidenceKind.GENERATED_MARKER, "marker"),
        ),
    )
    assert result.standing is OwnershipStanding.OBSERVED
    assert result.producer == "ggen"


def test_no_ownership_evidence_stays_unknown() -> None:
    result = OwnershipResolver().resolve("artifact", ())
    assert result.standing is OwnershipStanding.UNKNOWN
    assert result.producer is None


def test_python_compatibility_delta_names_removed_changed_and_added_symbols() -> None:
    original = extract_python_api(
        """
def keep(x: int) -> int:
    return x

def remove_me() -> None:
    return None

def change_me(x: int) -> int:
    return x
""",
        module_name="example",
    )
    candidate = extract_python_api(
        """
def keep(x: int) -> int:
    return x

def change_me(x: str) -> int:
    return 1

def added() -> bool:
    return True
""",
        module_name="example",
    )
    delta = compare_python_api(original, candidate)
    assert delta.added == ("function:added",)
    assert delta.removed == ("function:remove_me",)
    assert delta.changed == ("function:change_me",)
    assert delta.breaking_candidate


def test_native_parser_candidates_are_not_silently_admitted() -> None:
    candidates = candidate_native_parsers()
    assert candidates
    assert all(
        capability.standing is ParserCapabilityStanding.CANDIDATE
        for capability in candidates
    )

    registry = NativeParserRegistry()
    for capability in candidates:
        registry.register(capability)

    # Candidate prior art is not execution admission.
    assert (
        registry.intent_for(
            suffix=".ex",
            subject_id="subject",
            source_path="lib/app.ex",
            source_digest="sha256:source",
        )
        is None
    )


def test_admitted_native_parser_creates_zero_authority_intent() -> None:
    registry = NativeParserRegistry()
    registry.register(
        NativeParserCapability(
            capability_id="elixir/parser",
            language="elixir",
            suffixes=(".ex",),
            tool_identity="Code.string_to_quoted",
            tool_revision="elixir:1.18",
            output_contract="quoted/v1",
            standing=ParserCapabilityStanding.ADMITTED,
            evidence_ids=("observed-tool",),
        )
    )
    intent = registry.intent_for(
        suffix=".ex",
        subject_id="subject",
        source_path="lib/app.ex",
        source_digest="sha256:source",
    )
    assert intent is not None
    assert intent.authority == "NONE"
    assert intent.tool_identity == "Code.string_to_quoted"
