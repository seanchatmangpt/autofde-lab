"""Named BRCE mutants: each one must be refuted by the TLC court.

A mutant is the reference BRCE transition system with exactly one law broken.
The first three follow section 8 of the BRCE TLA+ adapter specification
(ggen_igniter ``docs/integrations/brce/tla-plus-adapter.md``); the fourth
removes fairness so the liveness obligation fails by stuttering.

These are anti-vacuity witnesses for the court: a court that reports
PROPERTY_HOLDS_IN_BOUND for a mutant is vacuous (``admission_vacuous``).
"""

from __future__ import annotations

import dataclasses
from enum import Enum

from .brce_reference import brce_reference_system
from .protocol_ir import Invariant, TransitionAction, TransitionSystem, make_action


class BrceMutant(str, Enum):
    DO_WITHOUT_AUTHORITY = "DO_WITHOUT_AUTHORITY"
    DUPLICATE_CONSEQUENCE = "DUPLICATE_CONSEQUENCE"
    STANDING_WITHOUT_VERIFY = "STANDING_WITHOUT_VERIFY"
    NO_FAIRNESS = "NO_FAIRNESS"


#: The property each mutant must violate, and the TLC verdict class.
EXPECTED_VIOLATION: dict[BrceMutant, str] = {
    BrceMutant.DO_WITHOUT_AUTHORITY: "ExecutedRequiresAuthority",
    BrceMutant.DUPLICATE_CONSEQUENCE: "AtMostOneConsequence",
    BrceMutant.STANDING_WITHOUT_VERIFY: "NoStandingWithoutVerification",
    BrceMutant.NO_FAIRNESS: "AdmittedEventuallyTerminal",
}


def _replace_action(
    system: TransitionSystem, name: str, action: TransitionAction
) -> tuple[TransitionAction, ...]:
    return tuple(action if item.name == name else item for item in system.actions)


def brce_mutant(kind: BrceMutant | str) -> TransitionSystem:
    kind = BrceMutant(kind)
    base = brce_reference_system()
    if kind is BrceMutant.DO_WITHOUT_AUTHORITY:
        # Declaring authority_required is not enforcing it: the guard no
        # longer reads the authority variable and skips Authorize.
        actuate = make_action(
            "Actuate",
            guard='phase = "CONSTRUCTED"',
            updates={
                "phase": '"EXECUTED"',
                "consequenceCount": "consequenceCount + 1",
            },
            consequence=True,
            authority_required=True,
        )
        return dataclasses.replace(
            base,
            name="BRCEMutantDoWithoutAuthority",
            actions=_replace_action(base, "Actuate", actuate),
        )
    if kind is BrceMutant.DUPLICATE_CONSEQUENCE:
        retry = make_action(
            "RetryActuate",
            guard='phase = "EXECUTED" /\\ authority',
            updates={"consequenceCount": "consequenceCount + 1"},
            consequence=True,
            authority_required=True,
        )
        return dataclasses.replace(
            base,
            name="BRCEMutantDuplicateConsequence",
            actions=base.actions + (retry,),
            state_constraints=(Invariant("ConsequenceBound", "consequenceCount <= 2"),),
        )
    if kind is BrceMutant.STANDING_WITHOUT_VERIFY:
        grant = make_action(
            "GrantStanding",
            guard='phase = "RECEIPTED" /\\ receipt',
            updates={"phase": '"STANDING"', "standing": "TRUE"},
        )
        return dataclasses.replace(
            base,
            name="BRCEMutantStandingWithoutVerify",
            actions=_replace_action(base, "GrantStanding", grant),
        )
    if kind is BrceMutant.NO_FAIRNESS:
        return dataclasses.replace(base, name="BRCEMutantNoFairness", fairness=())
    raise AssertionError(f"unhandled mutant {kind}")  # pragma: no cover


__all__ = ["BrceMutant", "EXPECTED_VIOLATION", "brce_mutant"]
