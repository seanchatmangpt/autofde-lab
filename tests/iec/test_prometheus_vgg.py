"""SWE-Prometheus / VGG court falsifiers."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.prometheus import evaluate_case, main

DIMS = [
    "tests_ci",
    "quality_gates",
    "docs_collaboration",
    "structure_maintainability",
    "reproducible_environment",
    "dependency_security",
]


def case(
    *,
    gate: str = "detected",
    behavior: str = "preserved",
    clean: str = "PASS",
    replay: str = "PASS",
    base: int = 2,
    treated: int = 4,
) -> dict:
    return {
        "schema": "autofde-lab.swe-prometheus-case/1",
        "repository": "seanchatmangpt/example",
        "base_commit": "0123456789abcdef",
        "patch_digest": "sha256:patch",
        "behavior": behavior,
        "gate_strength": gate,
        "mutation_receipt_id": "sha256:mut" if gate == "detected" else None,
        "clean_environment": {"verdict": clean, "receipt_id": "sha256:clean"},
        "replay": {"verdict": replay, "receipt_id": "sha256:replay"},
        "dimensions": {
            dimension: {
                "base": base,
                "treated": treated,
                "evidence_status": "pass",
            }
            for dimension in DIMS
        },
    }


def test_detected_gate_reaches_alive_and_recomputes_ngi() -> None:
    result = evaluate_case(case())
    assert result["paper"]["ngi"] == pytest.approx(2 / 3)
    assert result["vgg"]["standing"] == "ALIVE"
    assert result["vgg"]["value"] == pytest.approx(2 / 3)
    assert result["gate"] == "PASS"


@pytest.mark.parametrize(
    ("gate", "standing"),
    [
        ("blind", "PARTIAL_ALIVE"),
        ("vacuous", "PARTIAL_ALIVE"),
        ("none", "UNKNOWN"),
    ],
)
def test_weak_gate_reports_paper_ngi_but_cannot_crown_vgg(
    gate: str,
    standing: str,
) -> None:
    result = evaluate_case(case(gate=gate))
    assert result["paper"]["ngi"] == pytest.approx(2 / 3)
    assert result["vgg"]["standing"] == standing
    assert result["vgg"]["value"].startswith("UNREPRESENTABLE")
    assert "NON_DISCRIMINATIVE_BEHAVIOR_GATE" in result["falsifiers"]


def test_behavior_break_dominates_positive_governance_scores() -> None:
    result = evaluate_case(case(behavior="broken"))
    assert result["paper"]["ngi"] == pytest.approx(2 / 3)
    assert result["paper"]["behavior_valid"] is False
    assert result["vgg"]["standing"] == "BUILD_BROKEN"
    assert result["gate"] == "COUNTEREXAMPLE"


def test_base_five_gets_no_improvement_reward_but_regression_is_retained() -> None:
    payload = case()
    for dimension in DIMS:
        payload["dimensions"][dimension] = {
            "base": 5,
            "treated": 5,
            "evidence_status": "pass",
        }
    payload["dimensions"]["tests_ci"] = {
        "base": 5,
        "treated": 4,
        "evidence_status": "pass",
    }
    result = evaluate_case(payload)
    assert result["paper"]["ngi"] is None
    assert result["paper"]["regressions"] == ["tests_ci"]
    assert "GOVERNANCE_REGRESSION" in result["falsifiers"]
    assert "NO_NGI_DENOMINATOR" in result["falsifiers"]


def test_non_applicable_dimension_is_explicit_not_zero() -> None:
    payload = case()
    payload["dimensions"]["dependency_security"] = {
        "evidence_status": "not_applicable"
    }
    result = evaluate_case(payload)
    assert result["dimensions"]["dependency_security"]["scorable"] is False
    assert len(result["paper"]["scorable_dimensions"]) == 5
    assert result["paper"]["ngi"] == pytest.approx(2 / 3)


def test_detected_gate_requires_mutation_receipt() -> None:
    payload = case()
    payload["mutation_receipt_id"] = None
    with pytest.raises(IECRefusal, match="REFUSED_UNBOUNDED_EQUIVALENCE"):
        evaluate_case(payload)


def test_clean_or_replay_failure_caps_standing() -> None:
    assert (
        evaluate_case(case(clean="UNSUPPORTED"))["vgg"]["standing"]
        == "PARTIAL_ALIVE"
    )
    assert (
        evaluate_case(case(replay="COUNTEREXAMPLE"))["vgg"]["standing"]
        == "PARTIAL_ALIVE"
    )


def test_cli_receipt_is_byte_deterministic(tmp_path) -> None:
    input_path = tmp_path / "case.json"
    output_path = tmp_path / "out.json"
    input_path.write_text(json.dumps(case()), encoding="utf-8")

    assert main([str(input_path), str(output_path), "--gate"]) == 0
    first = output_path.read_bytes()
    assert main([str(input_path), str(output_path)]) == 0
    assert output_path.read_bytes() == first
