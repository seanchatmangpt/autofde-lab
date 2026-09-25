"""TLC court against the REAL pinned tla2tools.jar and a real JVM.

No doubles: every verdict here comes from a real SANY/TLC subprocess. Where the
toolchain is absent the tests skip with a visible typed reason
(``UNSUPPORTED:TLC_TOOLCHAIN_ABSENT``); with ``AUTOFDE_TLC_REQUIRED=1`` (set in
CI) that skip becomes a failure, so absence can never pass as green.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from autofde_lab.iec.brce_mutants import EXPECTED_VIOLATION, BrceMutant, brce_mutant
from autofde_lab.iec.brce_reference import brce_reference_system
from autofde_lab.iec.cli import main as iec_main
from autofde_lab.iec.formal import FormalResult, make_tlc_intent
from autofde_lab.iec.tlc_court import (
    DEADLOCK_EXEMPTION_REASON,
    FORMAL_PROOF_UNSUPPORTED,
    TLA2TOOLS_SHA256,
    TlaToolchain,
    TlcVerdict,
    ToolchainUnavailable,
    court,
    to_formal_evidence,
)

_DISCOVERED = TlaToolchain.discover()


@pytest.fixture(scope="module")
def tc() -> TlaToolchain:
    if isinstance(_DISCOVERED, TlaToolchain):
        return _DISCOVERED
    reason = (
        f"UNSUPPORTED:TLC_TOOLCHAIN_ABSENT ({_DISCOVERED.code}: {_DISCOVERED.reason})"
    )
    if os.environ.get("AUTOFDE_TLC_REQUIRED") == "1":
        pytest.fail(f"AUTOFDE_TLC_REQUIRED=1 but {reason}")
    pytest.skip(reason)


def _court(system, tc: TlaToolchain, tmp_path: Path, tag: str):
    return court(
        system,
        tc,
        workdir=tmp_path / tag,
        deadlock_check=False,
        deadlock_reason=DEADLOCK_EXEMPTION_REASON,
    )


def test_reference_model_holds_every_property_in_bound(
    tc: TlaToolchain, tmp_path: Path
) -> None:
    receipt = _court(brce_reference_system(), tc, tmp_path, "ref")
    p = receipt.payload
    assert p["parse"]["verdict"] == TlcVerdict.MODEL_PARSE_ALIVE.value
    assert p["model_check"] == TlcVerdict.MODEL_CHECK_ALIVE.value
    assert set(receipt.verdicts.values()) == {TlcVerdict.PROPERTY_HOLDS_IN_BOUND.value}
    assert set(receipt.verdicts) == {
        "NoStandingWithoutReceipt",
        "NoStandingWithoutVerification",
        "AtMostOneConsequence",
        "ExecutedRequiresAuthority",
        "AdmittedEventuallyTerminal",
    }
    assert {prop["distinct_states"] for prop in p["properties"]} == {10}
    assert p["jar_sha256"] == TLA2TOOLS_SHA256
    assert p["java_version"] == tc.java_version
    assert p["tool_version"] == "2.19 of 08 August 2024 (rev: 5a47802)"
    assert p["formal_proof"] == {
        "verdict": "UNSUPPORTED",
        "reason": FORMAL_PROOF_UNSUPPORTED,
    }
    assert p["authority"] == "NONE"
    assert p["bounds"]["deadlock_exemption_reason"] == DEADLOCK_EXEMPTION_REASON
    assert p["bounds"]["fairness"] == ["WF_vars(Next)"]
    assert all(prop["counterexample"] is None for prop in p["properties"])
    assert receipt.ocel_logs == {}


@pytest.mark.parametrize("kind", list(BrceMutant))
def test_each_mutant_is_refuted_on_its_named_property(
    kind: BrceMutant, tc: TlaToolchain, tmp_path: Path
) -> None:
    receipt = _court(brce_mutant(kind), tc, tmp_path, kind.value)
    prop = EXPECTED_VIOLATION[kind]
    assert receipt.payload["model_check"] == TlcVerdict.MODEL_CHECK_ALIVE.value
    assert receipt.verdicts[prop] == TlcVerdict.COUNTEREXAMPLE_FOUND.value
    entry = next(p for p in receipt.payload["properties"] if p["name"] == prop)
    cx = entry["counterexample"]
    assert cx["property"] == prop and cx["length"] >= 2
    assert cx["actions"][0] == "Init"
    log = receipt.ocel_logs[prop]
    assert log.validate() is log
    assert cx["ocel_digest"] == "sha256:" + log.digest()
    activities = [e.activity for e in log.events]
    assert activities.count("StateVisited") == cx["length"]
    assert "PropertyViolated" in activities
    if kind is BrceMutant.NO_FAIRNESS:
        assert activities[-1] == "Stuttering" and cx["loop"] == "STUTTERING"
    object_types = {o.object_type for o in log.objects}
    assert object_types == {"TlcRun", "TlaState", "TlaProperty"}


def test_replay_identity_is_deterministic(tc: TlaToolchain, tmp_path: Path) -> None:
    system = brce_mutant(BrceMutant.DUPLICATE_CONSEQUENCE)
    first = _court(system, tc, tmp_path, "a")
    second = _court(system, tc, tmp_path, "b")
    assert first.replay_identity == second.replay_identity
    assert first.verdicts == second.verdicts
    # receipt_digest also covers raw stdout digests, which carry wall-clock
    # timestamps; they are byte witnesses, not replay identity.
    for a, b in zip(first.runs, second.runs):
        assert a.transcript.trace_digest == b.transcript.trace_digest


def test_tampered_jar_is_refused(tc: TlaToolchain, tmp_path: Path) -> None:
    tampered = tmp_path / "tla2tools.jar"
    shutil.copyfile(tc.jar_path, tampered)
    with tampered.open("ab") as handle:
        handle.write(b"\x00")
    result = TlaToolchain.discover(tampered)
    assert isinstance(result, ToolchainUnavailable)
    assert result.code == "JAR_DIGEST_MISMATCH" and result.refused
    missing = TlaToolchain.discover(tmp_path / "absent.jar")
    assert isinstance(missing, ToolchainUnavailable) and not missing.refused


def test_disabling_deadlock_check_requires_reason(
    tc: TlaToolchain, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="requires a recorded reason"):
        court(brce_reference_system(), tc, workdir=tmp_path, deadlock_check=False)


def test_bridge_into_formal_result_contract(tc: TlaToolchain, tmp_path: Path) -> None:
    receipt = _court(
        brce_mutant(BrceMutant.STANDING_WITHOUT_VERIFY), tc, tmp_path, "bridge"
    )
    from autofde_lab.iec.tla_projection import render_tla

    intent = make_tlc_intent(
        render_tla(brce_mutant(BrceMutant.STANDING_WITHOUT_VERIFY)),
        tool_version=receipt.payload["tool_version"],
        executable_digest="sha256:" + receipt.payload["jar_sha256"],
        module_path="BRCEMutantStandingWithoutVerify.tla",
        config_path="x.cfg",
        jar_path="tla2tools.jar",
    )
    by_name = {run.property_name: run for run in receipt.runs}
    bad = to_formal_evidence(receipt, by_name["NoStandingWithoutVerification"], intent)
    assert bad.result is FormalResult.COUNTEREXAMPLE and bad.counterexample is not None
    good = to_formal_evidence(receipt, by_name["NoStandingWithoutReceipt"], intent)
    assert good.result is FormalResult.PASS and good.exit_code == 0


def test_cli_writes_receipt_and_ocel(tc: TlaToolchain, tmp_path: Path, capsys) -> None:
    out = tmp_path / "cli"
    code = iec_main(
        [
            "tlc-court",
            "--model",
            "mutant:DO_WITHOUT_AUTHORITY",
            "--out",
            str(out),
            "--jar",
            str(tc.jar_path),
        ]
    )
    assert code == 0
    assert (out / "receipt.json").is_file()
    assert (out / "counterexample.ExecutedRequiresAuthority.ocel.json").is_file()
    assert "COUNTEREXAMPLE_FOUND" in capsys.readouterr().out


def test_cli_refuses_tampered_jar(tmp_path: Path, tc: TlaToolchain) -> None:
    tampered = tmp_path / "t.jar"
    tampered.write_bytes(tc.jar_path.read_bytes() + b"!")
    code = iec_main(
        [
            "tlc-court",
            "--model",
            "brce",
            "--out",
            str(tmp_path / "o"),
            "--jar",
            str(tampered),
        ]
    )
    assert code == 3
    assert (
        '"code":"JAR_DIGEST_MISMATCH"' in (tmp_path / "o" / "receipt.json").read_text()
    )
