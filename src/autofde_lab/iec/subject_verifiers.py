"""Repository-native verifier intent profiles for initial IEC crown targets.

These profiles are candidate defaults. A live repository's own doctrine and
current task runner always outrank this module.
"""

from __future__ import annotations

from .model import ClaimCeiling, EquivalenceDimension
from .verification_intent import (
    FilesystemMode,
    SandboxProfile,
    VerificationCommandIntent,
    VerifierSet,
    VerifierSetBuilder,
)


def ggen_igniter_verifier_set(
    *,
    subject_id: str,
    cwd: str,
    environment_digest: str | None = None,
) -> VerifierSet:
    """Candidate verifier set derived from ggen_igniter's documented Mix rail."""

    sandbox = SandboxProfile(
        filesystem=FilesystemMode.ISOLATED_WRITE,
        network=False,
        timeout_seconds=900,
        cpu_limit=4.0,
        memory_mb=4096,
    )
    intents = (
        VerificationCommandIntent(
            intent_id_hint="ggen-igniter-format",
            subject_id=subject_id,
            verifier_id="mix-format-check/v1",
            dimension=EquivalenceDimension.SYNTAX,
            argv=("mix", "format", "--check-formatted"),
            cwd=cwd,
            sandbox=sandbox,
            environment_digest=environment_digest,
        ),
        VerificationCommandIntent(
            intent_id_hint="ggen-igniter-test",
            subject_id=subject_id,
            verifier_id="mix-test/v1",
            dimension=EquivalenceDimension.TEST,
            argv=("mix", "test"),
            cwd=cwd,
            sandbox=sandbox,
            environment_digest=environment_digest,
        ),
    )
    return VerifierSetBuilder().build(
        name="ggen-igniter/native-v1",
        intents=intents,
        claim_ceiling=ClaimCeiling.BUILD_AND_TEST_EQUIVALENCE_ONLY,
    )


def python_unit_verifier_set(
    *,
    subject_id: str,
    cwd: str,
    test_path: str,
    environment_digest: str | None = None,
) -> VerifierSet:
    sandbox = SandboxProfile(
        filesystem=FilesystemMode.ISOLATED_WRITE,
        network=False,
        timeout_seconds=600,
        cpu_limit=4.0,
        memory_mb=4096,
    )
    intent = VerificationCommandIntent(
        intent_id_hint="python-unit",
        subject_id=subject_id,
        verifier_id="pytest/v1",
        dimension=EquivalenceDimension.TEST,
        argv=("python", "-m", "pytest", test_path, "-q"),
        cwd=cwd,
        sandbox=sandbox,
        environment_digest=environment_digest,
    )
    return VerifierSetBuilder().build(
        name="python/unit-v1",
        intents=(intent,),
        claim_ceiling=ClaimCeiling.BUILD_AND_TEST_EQUIVALENCE_ONLY,
    )
