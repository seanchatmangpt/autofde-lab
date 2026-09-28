"""GALL courts for synthetic training provenance and learner demotion."""

from __future__ import annotations

from autofde_lab.sa2a.learning import (
    LearnerQualification,
    LearnerTier,
    TrainingExample,
    TrainingOrigin,
    select_least_complex_qualifying,
)


def test_ggen_training_example_preserves_synthetic_evidence_class() -> None:
    example = TrainingExample(
        generator_identity="sha256:ggen-igniter",
        source_ontology_identity="sha256:ontology",
        graph_identity="sha256:world",
        labeling_court="fond-hddl-exact-solver",
        court_version="v26.9.18",
        label_receipt="sha256:solver-receipt",
        origin=TrainingOrigin.GGEN_MANUFACTURED,
        features={"branching": 8, "repair_paths": 3},
        label={"best_method": "rollback"},
        seed=17,
        mutation_identity="sha256:mutation",
    )

    assert example.origin is TrainingOrigin.GGEN_MANUFACTURED
    assert len(example.example_identity) == 64


def test_gall_selects_least_complex_learner_that_closes_same_formal_court() -> None:
    results = (
        LearnerQualification(
            tier=LearnerTier.LINEAR,
            artifact_identity="sha256:linear",
            court_identity="sha256:court",
            passed=True,
            utility_gain=2.0,
            training_seconds=0.1,
            inference_milliseconds=0.01,
            formal_solution_preserved=True,
        ),
        LearnerQualification(
            tier=LearnerTier.GRADIENT_BOOSTING,
            artifact_identity="sha256:hgb",
            court_identity="sha256:court",
            passed=True,
            utility_gain=15.0,
            training_seconds=2.0,
            inference_milliseconds=0.05,
            formal_solution_preserved=True,
        ),
        LearnerQualification(
            tier=LearnerTier.GNN,
            artifact_identity="sha256:gnn",
            court_identity="sha256:court",
            passed=True,
            utility_gain=40.0,
            training_seconds=8.0,
            inference_milliseconds=0.2,
            formal_solution_preserved=True,
        ),
    )

    selected = select_least_complex_qualifying(results, minimum_utility_gain=10.0)

    assert selected is not None
    assert selected.artifact_identity == "sha256:hgb"
    assert selected.tier is LearnerTier.GRADIENT_BOOSTING


def test_speed_never_admits_a_learner_that_changes_formal_solution() -> None:
    unsafe_fast_model = LearnerQualification(
        tier=LearnerTier.NEAREST_NEIGHBORS,
        artifact_identity="sha256:unsafe",
        court_identity="sha256:court",
        passed=True,
        utility_gain=100.0,
        training_seconds=0.0,
        inference_milliseconds=0.001,
        formal_solution_preserved=False,
    )
    safe_gnn = LearnerQualification(
        tier=LearnerTier.GNN,
        artifact_identity="sha256:safe-gnn",
        court_identity="sha256:court",
        passed=True,
        utility_gain=20.0,
        training_seconds=5.0,
        inference_milliseconds=0.2,
        formal_solution_preserved=True,
    )

    selected = select_least_complex_qualifying(
        (unsafe_fast_model, safe_gnn),
        minimum_utility_gain=10.0,
    )

    assert selected == safe_gnn
