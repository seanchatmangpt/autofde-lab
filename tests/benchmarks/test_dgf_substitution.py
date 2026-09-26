import json
from pathlib import Path

import pytest

from autofde_lab.evidence.dgf_substitution import (
    ResidualWorkInputs,
    residual_work_ratio,
    run_dgf_dataset,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fake_dgf_root(tmp_path: Path) -> Path:
    root = tmp_path / "dgf"
    root.mkdir()
    (root / "evaluator.py").write_text(
        """
def evaluate_route(case, occurrences):
    out = []
    for occurrence, decision in zip(occurrences, case["decisions"], strict=True):
        row = dict(decision)
        row["occurrence_id"] = occurrence["occurrence_id"]
        row["position"] = occurrence["position"]
        out.append(row)
    return out
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return root


def _case(dataset: Path, name: str, *, expected_disposition: str = "GO") -> Path:
    case_dir = dataset / name
    occurrence = {
        "occurrence_id": f"{name}-01",
        "gate": "general",
        "phase": "governance",
        "position": 1,
    }
    decision = {
        "gate": "general",
        "phase": "governance",
        "disposition": "GO",
        "occurrence_id": f"{name}-01",
        "position": 1,
    }
    _write_json(case_dir / "01_route_manifest.json", {"occurrences": [occurrence]})
    _write_json(
        case_dir / "99_hidden_ground_truth.json",
        {
            "case_id": name,
            "canonical_truth": {
                "decisions": [
                    {
                        "gate": "general",
                        "phase": "governance",
                        "disposition": "GO",
                    }
                ]
            },
            "reference_decisions": [
                {**decision, "disposition": expected_disposition}
            ],
        },
    )
    return case_dir


def test_dataset_reports_gate_and_route_success_separately(tmp_path: Path) -> None:
    dgf_root = _fake_dgf_root(tmp_path)
    dataset = tmp_path / "dataset"
    _case(dataset, "pass")
    _case(dataset, "fail", expected_disposition="NO_GO")

    scores, summary = run_dgf_dataset(dataset, dgf_root=dgf_root)

    assert [score.route_match for score in scores] == [False, True] or [
        score.route_match for score in scores
    ] == [True, False]
    assert summary.cases == 2
    assert summary.routes_passed == 1
    assert summary.gates == 2
    assert summary.gates_passed == 1
    assert summary.route_success_rate == 0.5
    assert summary.gate_success_rate == 0.5


def test_residual_work_ratio_matches_paper_equation() -> None:
    ratio = residual_work_ratio(
        ResidualWorkInputs(
            exception_share=0.20,
            exception_effort_multiplier=2.0,
            ordinary_review_multiplier=0.10,
            rework=0.05,
            automation_support=0.02,
            baseline_overhead=0.10,
        )
    )

    assert ratio == pytest.approx((0.20 * 2.0 + 0.80 * 0.10 + 0.05 + 0.02) / 1.10)


def test_residual_work_rejects_invalid_share() -> None:
    with pytest.raises(ValueError, match="exception_share"):
        residual_work_ratio(
            ResidualWorkInputs(
                exception_share=1.1,
                exception_effort_multiplier=1.0,
                ordinary_review_multiplier=0.0,
                rework=0.0,
                automation_support=0.0,
            )
        )
