from autofde_lab.semantic_parts import (
    SubstitutionCase,
    evaluate_substitution_discovery,
)


def test_semantic_grounding_must_find_more_verified_substitutions_than_lexical():
    cases = [
        SubstitutionCase(
            subject_id="python:dijkstra",
            verified_equivalents=frozenset({"rust:dijkstra"}),
            lexical_candidates=("python:dijkstra-helper", "python:graph-search"),
            semantic_candidates=("rust:dijkstra", "go:dijkstra-unverified"),
        ),
        SubstitutionCase(
            subject_id="java:observer",
            verified_equivalents=frozenset({"elixir:pubsub-observer"}),
            lexical_candidates=("java:observer-utils", "java:event-listener"),
            semantic_candidates=("elixir:pubsub-observer",),
        ),
    ]

    result = evaluate_substitution_discovery(cases, k=2)

    assert result["lexical"]["discovery_rate"] == 0.0
    assert result["semantic"]["discovery_rate"] == 1.0
    assert result["discovery_rate_lift"] == 1.0
    assert result["falsifier_triggered"] is False
    assert result["authority"] == "NONE"


def test_equal_performance_triggers_the_falsifier():
    cases = [
        SubstitutionCase(
            subject_id="a",
            verified_equivalents=frozenset({"b"}),
            lexical_candidates=("b",),
            semantic_candidates=("b",),
        )
    ]

    result = evaluate_substitution_discovery(cases)

    assert result["discovery_rate_lift"] == 0.0
    assert result["falsifier_triggered"] is True


def test_oracle_cannot_self_verify_subject():
    try:
        SubstitutionCase(
            subject_id="a",
            verified_equivalents=frozenset({"a"}),
            lexical_candidates=(),
            semantic_candidates=(),
        )
    except ValueError as error:
        assert "cannot verify itself" in str(error)
    else:
        raise AssertionError("self-verification must be refused")
