"""Reference BRCE transition system for formal projection experiments.

The model is deliberately abstract. It exists to qualify IEC's protocol IR and
TLA+ manufacture path, not to assert that a production BRCE implementation
already exists.
"""

from __future__ import annotations

from .protocol_ir import (
    Invariant,
    LivenessProperty,
    StateVariable,
    TransitionSystem,
    make_action,
)


def brce_reference_system() -> TransitionSystem:
    variables = (
        StateVariable("phase", '"RECEIVED"'),
        StateVariable("authority", "FALSE", ("FALSE", "TRUE")),
        StateVariable("receipt", "FALSE", ("FALSE", "TRUE")),
        StateVariable("verified", "FALSE", ("FALSE", "TRUE")),
        StateVariable("standing", "FALSE", ("FALSE", "TRUE")),
        StateVariable("consequenceCount", "0"),
    )

    actions = (
        make_action(
            "Parse",
            guard='phase = "RECEIVED"',
            updates={"phase": '"PARSED"'},
        ),
        make_action(
            "Route",
            guard='phase = "PARSED"',
            updates={"phase": '"ROUTED"'},
        ),
        make_action(
            "Admit",
            guard='phase = "ROUTED"',
            updates={"phase": '"ADMITTED"'},
        ),
        make_action(
            "Construct",
            guard='phase = "ADMITTED"',
            updates={"phase": '"CONSTRUCTED"'},
        ),
        make_action(
            "Authorize",
            guard='phase = "CONSTRUCTED"',
            updates={"phase": '"AUTHORIZED"', "authority": "TRUE"},
        ),
        make_action(
            "Actuate",
            guard='phase = "AUTHORIZED" /\\ authority',
            updates={
                "phase": '"EXECUTED"',
                "consequenceCount": "consequenceCount + 1",
            },
            consequence=True,
            authority_required=True,
        ),
        make_action(
            "Receipt",
            guard='phase = "EXECUTED"',
            updates={"phase": '"RECEIPTED"', "receipt": "TRUE"},
        ),
        make_action(
            "Verify",
            guard='phase = "RECEIPTED" /\\ receipt',
            updates={"phase": '"VERIFIED"', "verified": "TRUE"},
        ),
        make_action(
            "GrantStanding",
            guard='phase = "VERIFIED" /\\ receipt /\\ verified',
            updates={"phase": '"STANDING"', "standing": "TRUE"},
        ),
    )

    invariants = (
        Invariant(
            "NoStandingWithoutReceipt",
            "~standing \\/ receipt",
        ),
        Invariant(
            "NoStandingWithoutVerification",
            "~standing \\/ verified",
        ),
        Invariant(
            "AtMostOneConsequence",
            "consequenceCount <= 1",
        ),
        Invariant(
            "ExecutedRequiresAuthority",
            'phase # "EXECUTED" \\/ authority',
        ),
    )

    liveness = (
        LivenessProperty(
            "AdmittedEventuallyTerminal",
            'phase = "ADMITTED" ~> phase \\in {"RECEIPTED", "VERIFIED", "STANDING"}',
        ),
    )

    system = TransitionSystem(
        name="BRCEReference",
        variables=variables,
        actions=actions,
        invariants=invariants,
        liveness=liveness,
    )
    if system.authority_gaps():
        raise AssertionError(
            "reference BRCE contains consequence action without authority requirement"
        )
    return system
