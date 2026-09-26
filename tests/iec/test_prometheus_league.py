"""SWE-Prometheus league comparability and aggregation falsifiers."""

from __future__ import annotations

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.prometheus import CASE_SCHEMA, DIMENSIONS
from autofde_lab.iec.crowns.prometheus_league import build_league


def case(
    subject: str,
    *,
    model: str,
    scaffold: str,
    gate: str = "detected",
    behavior: str = "preserved",
    clean: str = "PASS",
    replay: str = "PASS",
    base: int = 2,
    treated: int = 4,
) -> dict:
    repository, commit = subject.split("@", maxsplit=1)
    return {
        "schema": CASE_SCHEMA,
        "repository": repository,
        "base_commit": commit,
        "patch_digest": f"sha256:{model}-{commit}",
        "behavior": behavior,
        "gate_strength": gate,
        "mutation_receipt_id": (
            f"sha256:mutation-{model}-{commit}"
            if gate == "detected"
            else None
        ),
        "clean_environment": {
            "verdict": clean,
            "receipt_id": f"sha256:clean-{model}-{commit}",
        },
        "replay": {
            "verdict": replay,
            "receipt_id": f"sha256:replay-{model}-{commit}",
        },
        "dimensions": {
            dimension: {
                "base": base,
                "treated": treated,
                "evidence_status": "pass",
            }
            for dimension in DIMENSIONS
        },
        "model": model,
        "scaffold": scaffold,
    }


def test_full_comparability_when_subject_sets_are_exact() -> None:
    documents = [
        case("org/a@a1", model="MACHINE", scaffold="ggen"),
        case("org/b@b1", model="MACHINE", scaffold="ggen"),
        case("org/a@a1", model="LLM", scaffold="agent"),
        case("org/b@b1", model="LLM", scaffold="agent"),
    ]
    result = build_league(documents)
    assert result["comparability"]["standing"] == "FULL"
    assert result["comparability"]["common_subjects"] == [
        "git:org/a@a1",
        "git:org/b@b1",
    ]
    assert result["systems"]["MACHINE::ggen"]["all_observed"]["runs"] == 2
    assert result["systems"]["LLM::agent"]["common_subjects_only"]["runs"] == 2


def test_partial_comparability_never_silently_uses_union() -> None:
    documents = [
        case("org/a@a1", model="A", scaffold="s"),
        case("org/b@b1", model="A", scaffold="s"),
        case("org/a@a1", model="B", scaffold="s"),
    ]
    result = build_league(documents)
    assert result["comparability"]["standing"] == "PARTIAL"
    assert result["comparability"]["common_subjects"] == ["git:org/a@a1"]
    assert result["systems"]["A::s"]["all_observed"]["runs"] == 2
    assert result["systems"]["A::s"]["common_subjects_only"]["runs"] == 1
    assert result["systems"]["B::s"]["common_subjects_only"]["runs"] == 1


def test_strict_comparability_refuses_missing_subjects() -> None:
    documents = [
        case("org/a@a1", model="A", scaffold="s"),
        case("org/b@b1", model="A", scaffold="s"),
        case("org/a@a1", model="B", scaffold="s"),
    ]
    with pytest.raises(
        IECRefusal,
        match="REFUSED_INCOMPARABLE_SUBJECT_SETS",
    ):
        build_league(documents, require_common_subjects=True)


def test_duplicate_system_subject_is_refused_even_if_patch_differs() -> None:
    first = case("org/a@a1", model="A", scaffold="s")
    second = case("org/a@a1", model="A", scaffold="s")
    second["patch_digest"] = "sha256:another"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_DUPLICATE_BENCHMARK_SUBJECT",
    ):
        build_league([first, second])


def test_metrics_separate_ngi_from_admitted_vgg() -> None:
    documents = [
        case("org/a@a1", model="A", scaffold="s"),
        case(
            "org/b@b1",
            model="A",
            scaffold="s",
            gate="blind",
        ),
    ]
    result = build_league(documents)
    metrics = result["systems"]["A::s"]["all_observed"]
    assert metrics["runs"] == 2
    assert metrics["detected_gate_rate"] == 0.5
    assert metrics["alive_rate"] == 0.5
    assert metrics["vgg_admission_rate"] == 0.5
    assert metrics["mean_ngi"] == pytest.approx(2 / 3)
    assert metrics["mean_numeric_vgg"] == pytest.approx(2 / 3)
    assert metrics["falsifiers"] == {
        "NON_DISCRIMINATIVE_BEHAVIOR_GATE": 1
    }


def test_dimension_stats_keep_regressions_visible() -> None:
    documents = [
        case("org/a@a1", model="A", scaffold="s"),
        case(
            "org/b@b1",
            model="A",
            scaffold="s",
            base=4,
            treated=3,
        ),
    ]
    result = build_league(documents)
    tests_ci = result["systems"]["A::s"]["all_observed"]["dimensions"][
        "tests_ci"
    ]
    assert tests_ci["scorable"] == 2
    assert tests_ci["regressions"] == 1
    assert tests_ci["mean_delta"] == pytest.approx(0.5)


def test_empty_league_is_refused() -> None:
    with pytest.raises(
        IECRefusal,
        match="REFUSED_INVALID_PROMETHEUS_LEAGUE",
    ):
        build_league([])
