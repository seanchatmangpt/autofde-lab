"""Chicago-style tests for DiscoveryRouter (v26.9.17 PRD §6.6, ARD §14-15).

Real collaborators: real UnknownQuery/CandidateResolution objects, real registered
engine callables. Zero mocks.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

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


def test_wrong_type_return_from_attempt_is_rejected_not_propagated() -> None:
    """Adversarial hardening (2026-09-17, part 2): `attempt()`'s contract is 'a real
    `CandidateResolution`, or `None`' -- nothing else. Confirmed live pre-fix: a
    misbehaving engine returning a bare string made `DiscoveryRoutingResult.candidate`
    hold that string, and the first downstream read of a real `CandidateResolution`
    field (`Episode1Runner.run()`'s `candidate.consumed_tokens`) crashed with an
    uncaught `AttributeError`. `route()` must now validate the return type itself and
    treat a violation the same as a raising engine: fall through, record it in
    `errored_engine_ids`, never let the wrong-type value escape as `.candidate`."""
    router = DiscoveryRouter()
    router.register(DiscoveryEngine("string-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: "not a real candidate"))
    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="anything"))
    assert result.candidate is None
    assert result.selected_engine_id is None
    assert result.errored_engine_ids == ("string-1",)


def test_wrong_type_return_falls_through_to_a_later_valid_engine() -> None:
    router = DiscoveryRouter()
    router.register(DiscoveryEngine("int-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: 42))
    router.register(DiscoveryEngine("dict-1", DiscoveryEngineKind.COMPOSITION, lambda q: {}))
    router.register(
        DiscoveryEngine("formal-1", DiscoveryEngineKind.FORMAL_PLANNER_OR_SOLVER, lambda q: _candidate("formal-1", q))
    )
    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="anything"))
    assert result.selected_engine_id == "formal-1"
    assert result.candidate.candidate_id == "cand-formal-1"
    assert result.errored_engine_ids == ("int-1", "dict-1")


def test_wrong_type_return_never_reaches_episode1runner_as_a_fake_candidate(tmp_path) -> None:
    """Boundary-crossing confirmation (read-only import of episode1.py, not edited
    here -- episode/ is out of this agent's ownership): with the router-level fix in
    place, a wrong-typed engine return degrades to the SAME typed UNKNOWN/REFUSED
    outcome Episode1Runner already produces for 'no engine answered' -- never an
    uncaught AttributeError from `candidate.consumed_tokens` on a non-CandidateResolution
    value. This is the exact crash reproduced live before the router-level fix."""
    from autofde_lab.sa2a.episode.episode1 import Episode1Runner
    from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate

    router = DiscoveryRouter()
    router.register(DiscoveryEngine("bad-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, lambda q: "not a real candidate"))

    runner = Episode1Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts"
    )
    result = runner.run(
        semantic_class_id="requires-port",
        query=UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"),
        discovery_router=router,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-1", probe_input="requires-port",
        action_iri="urn:action:open-port", target_resource="urn:cap:api-gateway",
    )
    assert result.episode.classification == "UNKNOWN"
    assert result.machine_experience.refusal_code == "REFUSED_NO_DISCOVERY_ENGINE_PRODUCED_CANDIDATE"


def test_cli_requires_port_router_prefers_exact_machinery_for_the_demonstrated_query() -> None:
    """PRD §14 item 6 ('actual discovery execution'): `cli.py`'s real
    `_build_requires_port_discovery_router()` (2 engines, 2 precedence tiers) must
    select `EXACT_REUSABLE_MACHINERY` for the demonstrated `requires-port` query --
    the `GENERAL_EXPLORATORY_INTELLIGENCE` fallback must never even be invoked,
    proven by the real invocation log `route()` produces, not by construction."""
    from autofde_lab.sa2a.cli import _build_requires_port_discovery_router

    router, invocation_log = _build_requires_port_discovery_router()
    result = router.route(UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"))

    assert result.selected_engine_id == "exact-port-probe"
    assert result.selected_kind == DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY
    assert not result.used_general_exploratory_intelligence
    assert invocation_log == ["exact-port-probe"], "general fallback must not be invoked when exact machinery answers"


def test_cli_requires_port_router_falls_back_to_general_for_an_unrecognized_topic() -> None:
    """The same router genuinely falls through to GENERAL_EXPLORATORY_INTELLIGENCE
    for a query the exact engine does not recognize -- proving the exact engine's
    'not this one' answer is a real decision (returns None), not a stub that always
    matches."""
    from autofde_lab.sa2a.cli import _build_requires_port_discovery_router

    router, invocation_log = _build_requires_port_discovery_router()
    result = router.route(UnknownQuery(query_id="q-2", predicate_or_topic="service:x requires-replication-factor"))

    assert result.selected_engine_id == "general-exploratory-fallback"
    assert result.selected_kind == DiscoveryEngineKind.GENERAL_EXPLORATORY_INTELLIGENCE
    assert invocation_log == ["exact-port-probe", "general-exploratory-fallback"]


def test_crown_cli_command_actually_selects_exact_machinery_not_the_fallback(tmp_path) -> None:
    """End-to-end, real CLI invocation (typer.testing.CliRunner, matching this
    repo's existing test convention): the `crown` command's receipt carries the
    real discovery-routing proof, and the demonstrated query resolves through
    EXACT_REUSABLE_MACHINERY only."""
    from autofde_lab.sa2a.cli import app

    result = CliRunner().invoke(app, ["crown", "--work-dir", str(tmp_path / "crown")])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["standing"] == "CROWNED"
    assert payload["discovery_routing"]["engines_invoked"] == ["exact-port-probe"]
    assert payload["discovery_routing"]["exact_reusable_machinery_selected"] is True
    # Episode 2's candidate is machine-generated (ARD §64 item 6), not a second
    # hand-typed literal -- distinct from Episode 1's seed candidate_id.
    assert payload["episode2_generated_candidate"]["candidate_id"] != "cand-ep1"
    assert payload["episode2_generated_candidate"]["generated_from_seed_candidate_id"] == "cand-ep1"


def test_episode1_cli_command_actually_selects_exact_machinery_not_the_fallback(tmp_path) -> None:
    """Same real-CLI proof for the standalone `episode1` command, which the audit
    named as sharing the crown fixture's hardcoded-discover pattern."""
    from autofde_lab.sa2a.cli import app

    result = CliRunner().invoke(app, ["episode1", "--work-dir", str(tmp_path / "ep1")])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["classification"] == "KNOWN"
    assert payload["discovery_routing"]["engines_invoked"] == ["exact-port-probe"]
    assert payload["discovery_routing"]["exact_reusable_machinery_selected"] is True
