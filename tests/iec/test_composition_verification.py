"""Generator composition and sandboxed verification-intent tests."""

from __future__ import annotations

from autofde_lab.iec.composition import CapabilityComposer
from autofde_lab.iec.manufacture import (
    CapabilityStanding,
    GeneratorCapability,
    ManufactureRequirement,
    ecosystem_capabilities,
)
from autofde_lab.iec.model import ClaimCeiling, EquivalenceDimension
from autofde_lab.iec.subject_verifiers import ggen_igniter_verifier_set
from autofde_lab.iec.verification_evidence import (
    CommandObservation,
    reconcile_verifier_set,
)
from autofde_lab.iec.verification_intent import (
    FilesystemMode,
    SandboxProfile,
    VerificationCommandIntent,
    VerifierSetBuilder,
)


def test_capability_composer_finds_existing_two_hop_ggen_path() -> None:
    capabilities = ecosystem_capabilities(
        ggen_create_revision="create-sha",
        ggen_revision="ggen-sha",
        ggen_igniter_revision="igniter-sha",
    )
    route = CapabilityComposer(capabilities).route(
        ManufactureRequirement(
            input_kind="working-exemplar",
            output_kind="generated-artifacts",
            subject_id="subject",
        )
    )
    assert route.routable
    assert [capability.owner for capability in route.capabilities] == [
        "seanchatmangpt/ggen-create",
        "seanchatmangpt/ggen",
    ]
    manufacture_route = route.as_manufacture_route()
    assert all(step.authority == "NONE" for step in manufacture_route.steps)


def test_capability_composer_prefers_alive_path_at_equal_topology() -> None:
    capabilities = (
        GeneratorCapability(
            capability_id="admitted/a",
            owner="repo/admitted",
            input_kind="a",
            output_kind="b",
            standing=CapabilityStanding.ADMITTED,
            evidence_ids=("e1",),
            priority=0,
        ),
        GeneratorCapability(
            capability_id="alive/a",
            owner="repo/alive",
            input_kind="a",
            output_kind="b",
            standing=CapabilityStanding.ALIVE,
            evidence_ids=("e2",),
            priority=0,
        ),
    )
    route = CapabilityComposer(capabilities).route(
        ManufactureRequirement("a", "b", "subject")
    )
    assert route.routable
    assert route.capabilities[0].capability_id == "alive/a"


def test_capability_composer_returns_typed_unsupported_after_exhausting_graph() -> None:
    route = CapabilityComposer(()).route(ManufactureRequirement("a", "z", "subject"))
    assert not route.routable
    assert route.failure is not None
    assert route.failure.kind.value == "UNSUPPORTED_GENERATOR_CAPABILITY"


def test_ggen_igniter_verifier_profile_is_intent_only_and_network_closed() -> None:
    verifier_set = ggen_igniter_verifier_set(
        subject_id="subject",
        cwd="/isolated/generated",
        environment_digest="env:exact",
    )
    assert verifier_set.claim_ceiling is ClaimCeiling.BUILD_AND_TEST_EQUIVALENCE_ONLY
    assert set(verifier_set.dimensions) == {
        EquivalenceDimension.SYNTAX,
        EquivalenceDimension.TEST,
    }
    assert all(intent.authority == "NONE" for intent in verifier_set.intents)
    assert all(not intent.sandbox.network for intent in verifier_set.intents)
    assert all(
        intent.sandbox.filesystem is FilesystemMode.ISOLATED_WRITE
        for intent in verifier_set.intents
    )


def test_verifier_evidence_requires_every_expected_intent() -> None:
    verifier_set = ggen_igniter_verifier_set(
        subject_id="subject",
        cwd="/isolated/generated",
    )
    first = verifier_set.intents[0]
    evidence = reconcile_verifier_set(
        verifier_set,
        (
            CommandObservation(
                intent_id=first.intent_id,
                exit_code=0,
                stdout_digest="stdout",
                stderr_digest="stderr",
            ),
        ),
    )
    assert not evidence.passed
    assert len(evidence.missing_intent_ids) == 1


def test_verifier_evidence_checks_exit_code_and_environment_identity() -> None:
    sandbox = SandboxProfile(
        filesystem=FilesystemMode.READ_ONLY,
        network=False,
        timeout_seconds=30,
    )
    intent = VerificationCommandIntent(
        intent_id_hint="exact",
        subject_id="subject",
        verifier_id="exact/v1",
        dimension=EquivalenceDimension.TEST,
        argv=("tool", "verify"),
        cwd="/tmp/subject",
        sandbox=sandbox,
        environment_digest="env:1",
    )
    verifier_set = VerifierSetBuilder().build(
        name="single",
        intents=(intent,),
        claim_ceiling=ClaimCeiling.BUILD_AND_TEST_EQUIVALENCE_ONLY,
    )
    wrong_environment = reconcile_verifier_set(
        verifier_set,
        (
            CommandObservation(
                intent_id=intent.intent_id,
                exit_code=0,
                stdout_digest="out",
                stderr_digest="err",
                environment_digest="env:2",
            ),
        ),
    )
    assert not wrong_environment.passed

    passing = reconcile_verifier_set(
        verifier_set,
        (
            CommandObservation(
                intent_id=intent.intent_id,
                exit_code=0,
                stdout_digest="out",
                stderr_digest="err",
                environment_digest="env:1",
            ),
        ),
    )
    assert passing.passed
