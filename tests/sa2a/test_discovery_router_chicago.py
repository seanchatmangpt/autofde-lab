"""Chicago-style tests for DiscoveryRouter (v26.9.17 PRD §6.6, ARD §14-15).

Real collaborators: real UnknownQuery/CandidateResolution objects, real registered
engine callables. Zero mocks.
"""

from __future__ import annotations

from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery
from autofde_lab.sa2a.unknown.router import DiscoveryEngine, DiscoveryEngineKind, DiscoveryRouter


def _candidate(engine_id: str, query: UnknownQuery) -> CandidateResolution:
    return CandidateResolution(
        candidate_id=f"cand-{engine_id}", query_id=query.query_id,
        proposed_assertion=f"resolved-by:{engine_id}", evidence_payload={"engine": engine_id},
        source_identity=engine_id, consumed_ticks=1, consumed_tokens=0,
    )


def test_precedence_prefers_exact_reusable_machinery_over_general_exploratory() -> None:
    """ARD §15: exact reusable machinery is tried BEFORE general exploratory
    intelligence, even when both are registered and both would produce a candidate."""
    router = DiscoveryRouter()
    calls: list[str] = []

    def exact(query: UnknownQuery):
        calls.append("exact")
        return _candidate("exact", query)

    def general(query: UnknownQuery):
        calls.append("general")
        return _candidate("general", query)

    router.register(DiscoveryEngine("general-1", DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE, general))
    router.register(DiscoveryEngine("exact-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, exact))

    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="anything"))
    assert result.selected_engine_id == "exact-1"
    assert result.selected_kind == DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY
    assert not result.used_general_exploratory_intelligence
    assert "general" not in calls, "general exploratory intelligence must not be invoked when exact machinery already answered"


def test_falls_through_precedence_when_earlier_engines_cannot_handle_the_query() -> None:
    router = DiscoveryRouter()
    router.register(DiscoveryEngine("exact-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: None))
    router.register(DiscoveryEngine("formal-1", DiscoveryEngineKind.FORMAL_PLANNER_OR_SOLVER, lambda q: None))
    router.register(
        DiscoveryEngine("general-1", DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE, lambda q: _candidate("general-1", q))
    )
    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="anything"))
    assert result.selected_engine_id == "general-1"
    assert result.used_general_exploratory_intelligence
    assert result.attempted_engine_ids == ("exact-1", "formal-1", "general-1")


def test_no_engine_can_handle_yields_no_candidate_never_a_fabricated_one() -> None:
    router = DiscoveryRouter()
    router.register(DiscoveryEngine("exact-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: None))
    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="anything"))
    assert result.candidate is None
    assert result.selected_engine_id is None
    assert result.attempted_engine_ids == ("exact-1",)


def test_duplicate_engine_id_is_refused() -> None:
    router = DiscoveryRouter()
    router.register(DiscoveryEngine("dup", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: None))
    try:
        router.register(DiscoveryEngine("dup", DiscoveryEngineKind.FORMAL_PLANNER_OR_SOLVER, lambda q: None))
        assert False, "must refuse a second engine registered under an already-used engine_id"
    except ValueError:
        pass


def test_returned_candidate_carries_no_standing_field() -> None:
    """Structural proof of the candidate-only boundary: CandidateResolution has no
    admitted/standing field at all -- a discovery engine cannot self-admit even if
    it wanted to, because the type it returns has nowhere to put that claim."""
    router = DiscoveryRouter()
    router.register(DiscoveryEngine("e1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: _candidate("e1", q)))
    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="anything"))
    assert not hasattr(result.candidate, "admitted")
    assert not hasattr(result.candidate, "standing")
