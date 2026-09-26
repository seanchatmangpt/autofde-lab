"""Real TLC court for the delegation/admission transition law."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autofde_lab.iec.delegation_admission_formal import (
    EXPECTED_VIOLATION,
    DelegationAdmissionMutant,
    delegation_admission_mutant,
    delegation_admission_system,
)
from autofde_lab.iec.tlc_court import (
    DEADLOCK_EXEMPTION_REASON,
    TlaToolchain,
    TlcVerdict,
    court,
)

_DISCOVERED = TlaToolchain.discover()


@pytest.fixture(scope="module")
def tc() -> TlaToolchain:
    if isinstance(_DISCOVERED, TlaToolchain):
        return _DISCOVERED
    reason = (
        "UNSUPPORTED:TLC_TOOLCHAIN_ABSENT "
        f"({_DISCOVERED.code}: {_DISCOVERED.reason})"
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


def test_delegation_reference_holds_all_capacity_invariants(
    tc: TlaToolchain,
    tmp_path: Path,
) -> None:
    receipt = _court(delegation_admission_system(), tc, tmp_path, "reference")
    assert receipt.payload["model_check"] == TlcVerdict.MODEL_CHECK_ALIVE.value
    assert set(receipt.verdicts.values()) == {
        TlcVerdict.PROPERTY_HOLDS_IN_BOUND.value
    }
    assert set(receipt.verdicts) == {
        "NoDelegationBeyondExplain",
        "NoDelegationBeyondVerify",
        "NoDelegationBeyondModify",
        "NoDelegationBeyondAccount",
        "VerificationRequiresIndependence",
        "ModificationRequiresChangedRequirement",
        "StandingRequiresAdmissionCapacity",
    }
    assert receipt.payload["authority"] == "NONE"


@pytest.mark.parametrize("mutant", list(DelegationAdmissionMutant))
def test_each_delegation_mutant_has_a_real_tlc_counterexample(
    mutant: DelegationAdmissionMutant,
    tc: TlaToolchain,
    tmp_path: Path,
) -> None:
    receipt = _court(
        delegation_admission_mutant(mutant),
        tc,
        tmp_path,
        mutant.value.lower(),
    )
    expected = EXPECTED_VIOLATION[mutant]
    assert receipt.payload["model_check"] == TlcVerdict.MODEL_CHECK_ALIVE.value
    assert receipt.verdicts[expected] == TlcVerdict.COUNTEREXAMPLE_FOUND.value
    counterexample = next(
        prop["counterexample"]
        for prop in receipt.payload["properties"]
        if prop["name"] == expected
    )
    assert counterexample is not None
    assert counterexample["length"] >= 2
    assert counterexample["actions"][0] == "Init"


def test_formal_projection_is_deterministic() -> None:
    first = delegation_admission_system()
    second = delegation_admission_system()
    assert first.system_id == second.system_id
    assert first.authority_gaps() == ()
