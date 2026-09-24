"""Observed evidence returned from executing a VerificationCommandIntent."""

from __future__ import annotations

from dataclasses import dataclass

from .model import digest
from .verification_intent import VerificationCommandIntent, VerifierSet


@dataclass(frozen=True, slots=True)
class CommandObservation:
    intent_id: str
    exit_code: int
    stdout_digest: str
    stderr_digest: str
    started_at: str | None = None
    completed_at: str | None = None
    environment_digest: str | None = None

    @property
    def observation_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class VerifierSetEvidence:
    verifier_set_id: str
    observations: tuple[CommandObservation, ...]
    passed: bool
    missing_intent_ids: tuple[str, ...]
    unexpected_intent_ids: tuple[str, ...]

    @property
    def evidence_id(self) -> str:
        return digest(self)


def reconcile_verifier_set(
    verifier_set: VerifierSet,
    observations: tuple[CommandObservation, ...],
) -> VerifierSetEvidence:
    expected = {intent.intent_id: intent for intent in verifier_set.intents}
    observed = {observation.intent_id: observation for observation in observations}

    if len(observed) != len(observations):
        raise ValueError("duplicate command observation identity")

    missing = tuple(sorted(set(expected) - set(observed)))
    unexpected = tuple(sorted(set(observed) - set(expected)))

    passed = not missing and not unexpected
    if passed:
        for intent_id, intent in expected.items():
            observation = observed[intent_id]
            if observation.exit_code not in intent.expected_exit_codes:
                passed = False
                break
            if (
                intent.environment_digest is not None
                and observation.environment_digest != intent.environment_digest
            ):
                passed = False
                break

    return VerifierSetEvidence(
        verifier_set_id=verifier_set.verifier_set_id,
        observations=tuple(sorted(observations, key=lambda item: item.intent_id)),
        passed=passed,
        missing_intent_ids=missing,
        unexpected_intent_ids=unexpected,
    )
