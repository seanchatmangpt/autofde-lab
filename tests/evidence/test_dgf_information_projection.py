import json
from pathlib import Path

import pytest

from autofde_lab.evidence.dgf_information_projection import (
    audit_dgf_projection,
    build_dgf_decision_cases,
    dotted_get,
    route_signature,
    search_min_cost_sufficient_projection,
    search_sufficient_dgf_projections,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _case(
    dataset: Path,
    name: str,
    *,
    public_kind: str,
    signing_authority: bool,
    disposition: str,
) -> Path:
    case_dir = dataset / name
    _write_json(
        case_dir / "01_route_manifest.json",
        {
            "occurrences": [
                {
                    "occurrence_id": f"{name}-01",
                    "gate": "legal",
                    "phase": "design",
                    "position": 1,
                }
            ]
        },
    )
    _write_json(
        case_dir / "99_hidden_ground_truth.json",
        {
            "case_id": name,
            "canonical_truth": {
                "public": {"kind": public_kind},
                "legal": {"signing_authority": signing_authority},
            },
            "reference_decisions": [
                {
                    "occurrence_id": f"{name}-01",
                    "position": 1,
                    "gate": "legal",
                    "phase": "design",
                    "disposition": disposition,
                }
            ],
        },
    )
    return case_dir


def test_dotted_get_reads_mappings_and_lists_without_defaulting_missing() -> None:
    payload = {"a": {"b": [{"c": 7}]}}
    assert dotted_get(payload, "a.b.0.c") == 7

    with pytest.raises(KeyError):
        dotted_get(payload, "a.missing")


def test_route_signature_is_stable_and_position_sensitive() -> None:
    rows = [
        {
            "position": 1,
            "gate": "legal",
            "phase": "design",
            "disposition": "GO",
        }
    ]
    assert route_signature(rows) == route_signature([dict(rows[0])])
    assert "legal" in route_signature(rows)


def test_public_projection_exposes_information_obstruction(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _case(
        dataset,
        "left",
        public_kind="same",
        signing_authority=True,
        disposition="GO",
    )
    _case(
        dataset,
        "right",
        public_kind="same",
        signing_authority=False,
        disposition="NO_GO",
    )

    audit = audit_dgf_projection(
        dataset,
        observation_paths=("public.kind",),
    )

    assert audit.sufficient is False
    assert audit.report.obstruction_count == 1
    assert audit.report.collision_class_count == 1


def test_adding_decisive_fact_removes_information_obstruction(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _case(
        dataset,
        "left",
        public_kind="same",
        signing_authority=True,
        disposition="GO",
    )
    _case(
        dataset,
        "right",
        public_kind="same",
        signing_authority=False,
        disposition="NO_GO",
    )

    audit = audit_dgf_projection(
        dataset,
        observation_paths=("public.kind", "legal.signing_authority"),
    )

    assert audit.sufficient is True
    assert audit.report.obstruction_count == 0


def test_search_finds_minimal_sufficient_projection_width(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _case(
        dataset,
        "left",
        public_kind="same",
        signing_authority=True,
        disposition="GO",
    )
    _case(
        dataset,
        "right",
        public_kind="same",
        signing_authority=False,
        disposition="NO_GO",
    )

    audits = search_sufficient_dgf_projections(
        dataset,
        candidate_paths=("public.kind", "legal.signing_authority"),
        max_width=2,
    )

    assert [audit.observation_paths for audit in audits] == [
        ("legal.signing_authority",)
    ]
    assert all(audit.sufficient for audit in audits)


def test_search_returns_empty_when_candidate_vocabulary_cannot_distinguish(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _case(
        dataset,
        "left",
        public_kind="same",
        signing_authority=True,
        disposition="GO",
    )
    _case(
        dataset,
        "right",
        public_kind="same",
        signing_authority=False,
        disposition="NO_GO",
    )

    assert (
        search_sufficient_dgf_projections(
            dataset,
            candidate_paths=("public.kind",),
            max_width=1,
        )
        == ()
    )


def test_min_cost_search_chooses_cheapest_sufficient_surface(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    left = _case(
        dataset,
        "left",
        public_kind="same",
        signing_authority=True,
        disposition="GO",
    )
    right = _case(
        dataset,
        "right",
        public_kind="same",
        signing_authority=False,
        disposition="NO_GO",
    )

    for case_dir, copy_value in ((left, True), (right, False)):
        hidden = json.loads((case_dir / "99_hidden_ground_truth.json").read_text())
        hidden["canonical_truth"]["legal"]["signing_authority_copy"] = copy_value
        _write_json(case_dir / "99_hidden_ground_truth.json", hidden)

    plan = search_min_cost_sufficient_projection(
        dataset,
        candidate_costs={
            "public.kind": 0.1,
            "legal.signing_authority": 5.0,
            "legal.signing_authority_copy": 2.0,
        },
        max_width=2,
    )

    assert plan is not None
    assert plan.observation_paths == ("legal.signing_authority_copy",)
    assert plan.total_cost == 2.0
    assert plan.audit.sufficient is True


def test_min_cost_search_refuses_invalid_costs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="DGF_CANDIDATE_COST_INVALID"):
        search_min_cost_sufficient_projection(
            tmp_path,
            candidate_costs={"public.kind": -1.0},
            max_width=1,
        )


def test_projection_refuses_duplicate_paths_and_empty_dataset(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="DGF_PROJECTION_PATHS_DUPLICATE"):
        build_dgf_decision_cases(
            tmp_path,
            observation_paths=("a", "a"),
        )

    with pytest.raises(ValueError, match="DGF_EMPTY_DATASET"):
        build_dgf_decision_cases(
            tmp_path,
            observation_paths=("a",),
        )
