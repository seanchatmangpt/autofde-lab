"""Formal transition systems for delegation/admission capacity.

The executable JSON court evaluates one evidence snapshot. These transition
systems model the reachable-state law: delegation can grow only after all four
evidence capacities cover the next unit, verification capacity can grow only
after independent verification is observed, and modification capacity can grow
only after a changed-requirement probe is observed.

They are deliberately bounded to capacity 3 for explicit-state model checking.
That bound qualifies the transition law, not production scale.
"""

from __future__ import annotations

from enum import Enum

from .protocol_ir import Invariant, StateVariable, TransitionSystem, make_action

__all__ = [
    "DelegationAdmissionMutant",
    "EXPECTED_VIOLATION",
    "delegation_admission_system",
    "delegation_admission_mutant",
]


class DelegationAdmissionMutant(str, Enum):
    UNBOUNDED_DELEGATION = "UNBOUNDED_DELEGATION"
    SELF_VERIFICATION = "SELF_VERIFICATION"
    MODIFY_WITHOUT_CHANGE = "MODIFY_WITHOUT_CHANGE"
    STANDING_WITHOUT_CAPACITY = "STANDING_WITHOUT_CAPACITY"


EXPECTED_VIOLATION = {
    DelegationAdmissionMutant.UNBOUNDED_DELEGATION: "NoDelegationBeyondExplain",
    DelegationAdmissionMutant.SELF_VERIFICATION: "VerificationRequiresIndependence",
    DelegationAdmissionMutant.MODIFY_WITHOUT_CHANGE: (
        "ModificationRequiresChangedRequirement"
    ),
    DelegationAdmissionMutant.STANDING_WITHOUT_CAPACITY: (
        "StandingRequiresAdmissionCapacity"
    ),
}


def _variables() -> tuple[StateVariable, ...]:
    return (
        StateVariable("delegation", "0"),
        StateVariable("explainCap", "0"),
        StateVariable("verifyCap", "0"),
        StateVariable("modifyCap", "0"),
        StateVariable("accountCap", "0"),
        StateVariable("independent", "FALSE", ("FALSE", "TRUE")),
        StateVariable("changeObserved", "FALSE", ("FALSE", "TRUE")),
        StateVariable("standing", "FALSE", ("FALSE", "TRUE")),
    )


def _invariants() -> tuple[Invariant, ...]:
    return (
        Invariant("NoDelegationBeyondExplain", "delegation <= explainCap"),
        Invariant("NoDelegationBeyondVerify", "delegation <= verifyCap"),
        Invariant("NoDelegationBeyondModify", "delegation <= modifyCap"),
        Invariant("NoDelegationBeyondAccount", "delegation <= accountCap"),
        Invariant(
            "VerificationRequiresIndependence",
            "verifyCap = 0 \/ independent",
        ),
        Invariant(
            "ModificationRequiresChangedRequirement",
            "modifyCap = 0 \/ changeObserved",
        ),
        Invariant(
            "StandingRequiresAdmissionCapacity",
            (
                "~standing \/ "
                "(delegation <= explainCap /\ "
                "delegation <= verifyCap /\ "
                "delegation <= modifyCap /\ "
                "delegation <= accountCap)"
            ),
        ),
    )


def _actions(
    mutant: DelegationAdmissionMutant | None = None,
) -> tuple:
    delegate_guard = (
        "delegation < 3"
        if mutant is DelegationAdmissionMutant.UNBOUNDED_DELEGATION
        else (
            "delegation < 3 /\ "
            "delegation < explainCap /\ "
            "delegation < verifyCap /\ "
            "delegation < modifyCap /\ "
            "delegation < accountCap"
        )
    )
    verify_guard = (
        "verifyCap < 3"
        if mutant is DelegationAdmissionMutant.SELF_VERIFICATION
        else "verifyCap < 3 /\ independent"
    )
    modify_guard = (
        "modifyCap < 3"
        if mutant is DelegationAdmissionMutant.MODIFY_WITHOUT_CHANGE
        else "modifyCap < 3 /\ changeObserved"
    )
    standing_guard = (
        "TRUE"
        if mutant is DelegationAdmissionMutant.STANDING_WITHOUT_CAPACITY
        else (
            "~standing /\ delegation > 0 /\ "
            "delegation <= explainCap /\ "
            "delegation <= verifyCap /\ "
            "delegation <= modifyCap /\ "
            "delegation <= accountCap"
        )
    )

    standing_updates = {"standing": "TRUE"}
    if mutant is DelegationAdmissionMutant.STANDING_WITHOUT_CAPACITY:
        # Avoid a vacuous mutant: standing over delegation=0 still satisfies
        # every capacity inequality. Force one unsupported delegated unit.
        standing_updates["delegation"] = "1"

    return (
        make_action(
            "ExplainEvidence",
            guard="explainCap < 3",
            updates={"explainCap": "explainCap + 1"},
        ),
        make_action(
            "ObserveIndependentVerifier",
            guard="~independent",
            updates={"independent": "TRUE"},
        ),
        make_action(
            "VerifyEvidence",
            guard=verify_guard,
            updates={"verifyCap": "verifyCap + 1"},
        ),
        make_action(
            "ObserveChangedRequirement",
            guard="~changeObserved",
            updates={"changeObserved": "TRUE"},
        ),
        make_action(
            "ModifyEvidence",
            guard=modify_guard,
            updates={"modifyCap": "modifyCap + 1"},
        ),
        make_action(
            "AccountEvidence",
            guard="accountCap < 3",
            updates={"accountCap": "accountCap + 1"},
        ),
        make_action(
            "DelegateOne",
            guard=delegate_guard,
            updates={"delegation": "delegation + 1"},
        ),
        make_action(
            "GrantStanding",
            guard=standing_guard,
            updates=standing_updates,
        ),
    )


def delegation_admission_system() -> TransitionSystem:
    """Reference bounded transition system."""
    return TransitionSystem(
        name="DelegationAdmission",
        variables=_variables(),
        actions=_actions(),
        invariants=_invariants(),
    )


def delegation_admission_mutant(
    mutant: DelegationAdmissionMutant,
) -> TransitionSystem:
    """One-edge mutant used to calibrate TLC falsification."""
    suffix = "".join(part.title() for part in mutant.value.lower().split("_"))
    return TransitionSystem(
        name=f"DelegationAdmissionMutant{suffix}",
        variables=_variables(),
        actions=_actions(mutant),
        invariants=_invariants(),
    )
