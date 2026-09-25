"""Pure calibration tests: the transcript state machine over REAL jar output.

Fixtures under ``tests/iec/fixtures/tlc/v1.7.4`` are real stdout captured from
the pinned tla2tools.jar by ``scripts/capture_tlc_fixtures.py``; MANIFEST.json
records the jar sha256, java version, argv and exit code of each capture. These
tests pin the message codes, exit codes and SANY behaviour the court relies on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autofde_lab.iec.tlc_court import (
    FINISHED,
    TLA2TOOLS_SHA256,
    TlcVerdict,
    classify_sany,
    classify_tlc,
    parse_tool_output,
)

FIXTURES = Path(__file__).parent / "fixtures" / "tlc" / "v1.7.4"
MANIFEST = json.loads((FIXTURES / "MANIFEST.json").read_text())
REPO = Path(__file__).resolve().parents[2]


def _fixture(name: str) -> tuple[str, int]:
    return (FIXTURES / f"{name}.stdout").read_text(), MANIFEST["fixtures"][name][
        "exit_code"
    ]


def test_manifest_binds_fixtures_to_the_pinned_jar() -> None:
    assert MANIFEST["jar_sha256"] == TLA2TOOLS_SHA256
    committed = (
        (REPO / "tools" / "tla" / "tla2tools-1.7.4.sha256").read_text().split()[0]
    )
    assert committed == TLA2TOOLS_SHA256
    toolchain = json.loads((REPO / "tools" / "tla" / "TOOLCHAIN.json").read_text())
    assert (
        toolchain["sha256"] == TLA2TOOLS_SHA256 and toolchain["size_bytes"] == 2274532
    )


@pytest.mark.parametrize(
    "name", ["tlc_reference_liveness_holds", "tlc_reference_invariant_holds"]
)
def test_success_transcripts_hold_in_bound(name: str) -> None:
    stdout, exit_code = _fixture(name)
    tr = parse_tool_output(stdout)
    assert exit_code == 0
    assert tr.outcome == "SUCCESS" and tr.final_phase == FINISHED
    assert tr.errors == () and tr.trace == ()
    assert tr.distinct_states == 10 and tr.left_on_queue == 0 and tr.depth == 10
    assert tr.tool_version == "2.19 of 08 August 2024 (rev: 5a47802)"
    assert classify_tlc(exit_code, tr) is TlcVerdict.PROPERTY_HOLDS_IN_BOUND


@pytest.mark.parametrize(
    ("name", "invariant", "last_action", "length"),
    [
        ("tlc_mutant_do_without_authority", "ExecutedRequiresAuthority", "Actuate", 6),
        ("tlc_mutant_duplicate_consequence", "AtMostOneConsequence", "RetryActuate", 8),
        (
            "tlc_mutant_standing_without_verify",
            "NoStandingWithoutVerification",
            "GrantStanding",
            9,
        ),
    ],
)
def test_invariant_counterexamples_parse_to_named_violation(
    name: str, invariant: str, last_action: str, length: int
) -> None:
    stdout, exit_code = _fixture(name)
    tr = parse_tool_output(stdout)
    assert exit_code == 12
    assert tr.outcome == "INVARIANT_VIOLATED" and tr.violated_invariant == invariant
    assert tr.trace[0].action == "Init" and tr.trace[-1].action == last_action
    assert len(tr.trace) == length and tr.loop is None and tr.errors == ()
    assert "VIOLATION" in tr.phases and "TRACE" in tr.phases
    assert (
        classify_tlc(exit_code, tr, expected_property=invariant)
        is TlcVerdict.COUNTEREXAMPLE_FOUND
    )
    # A verdict about a different property than the one asked for is not admitted.
    assert classify_tlc(exit_code, tr, expected_property="Other") is TlcVerdict.UNKNOWN


def test_liveness_counterexample_ends_in_stuttering() -> None:
    stdout, exit_code = _fixture("tlc_mutant_no_fairness")
    tr = parse_tool_output(stdout)
    assert exit_code == 13
    assert tr.outcome == "TEMPORAL_VIOLATED" and tr.loop == "STUTTERING"
    assert "STUTTER" in tr.phases and tr.errors == ()
    assert classify_tlc(exit_code, tr) is TlcVerdict.COUNTEREXAMPLE_FOUND


def test_deadlock_transcript_is_calibrated() -> None:
    stdout, exit_code = _fixture("tlc_reference_deadlock")
    tr = parse_tool_output(stdout)
    assert exit_code == 11 and tr.outcome == "DEADLOCK"
    assert tr.trace[-1].action == "GrantStanding"
    assert "-deadlock" not in MANIFEST["fixtures"]["tlc_reference_deadlock"]["argv"]


def test_config_error_is_tool_error_not_a_verdict() -> None:
    stdout, exit_code = _fixture("tlc_config_error")
    tr = parse_tool_output(stdout)
    assert exit_code == 151 and tr.outcome == "TOOL_ERROR"
    assert any(e.startswith("TLC_ERROR:2229") for e in tr.errors)
    assert classify_tlc(exit_code, tr) is TlcVerdict.TOOL_ERROR


def test_sany_semantic_error_exits_zero_but_is_refused() -> None:
    stdout, exit_code = _fixture("sany_semantic_error")
    assert (
        exit_code == 0
    )  # calibrated: SANY does not signal semantic errors by exit code
    verdict, errors = classify_sany(exit_code, stdout)
    assert verdict is TlcVerdict.MODEL_PARSE_REFUSED and "*** Errors:" in errors


def test_sany_parse_error_and_success() -> None:
    stdout, exit_code = _fixture("sany_parse_error")
    assert exit_code == 255
    assert classify_sany(exit_code, stdout)[0] is TlcVerdict.MODEL_PARSE_REFUSED
    stdout, exit_code = _fixture("sany_reference_ok")
    assert classify_sany(exit_code, stdout) == (TlcVerdict.MODEL_PARSE_ALIVE, ())


def test_truncated_transcript_is_unknown_never_success() -> None:
    stdout, _ = _fixture("tlc_reference_liveness_holds")
    cut = stdout[: stdout.index("@!@!@STARTMSG 2193")]
    tr = parse_tool_output(cut)
    assert tr.outcome == "INCOMPLETE" and tr.final_phase != FINISHED
    assert classify_tlc(0, tr) is TlcVerdict.UNKNOWN


def test_exit_zero_without_success_message_is_not_a_hold() -> None:
    stdout, _ = _fixture("tlc_reference_liveness_holds")
    start = stdout.index("@!@!@STARTMSG 2193")
    end = stdout.index("@!@!@ENDMSG 2193 @!@!@") + len("@!@!@ENDMSG 2193 @!@!@\n")
    tr = parse_tool_output(stdout[:start] + stdout[end:])
    assert tr.outcome == "INCOMPLETE"
    assert classify_tlc(0, tr) is TlcVerdict.UNKNOWN


def test_state_outside_violation_is_flagged() -> None:
    stdout, _ = _fixture("tlc_mutant_do_without_authority")
    start = stdout.index("@!@!@STARTMSG 2110")
    end = stdout.index("@!@!@ENDMSG 2110 @!@!@") + len("@!@!@ENDMSG 2110 @!@!@\n")
    tr = parse_tool_output(stdout[:start] + stdout[end:])
    assert "TRACE_WITHOUT_VIOLATION" in tr.errors or any(
        e.startswith("ILLEGAL_TRANSITION") for e in tr.errors
    )
    assert classify_tlc(12, tr) is not TlcVerdict.COUNTEREXAMPLE_FOUND
