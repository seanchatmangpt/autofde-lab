"""Chicago-style regression tests for the 2026-09-17 hardening pass over the
v26.9.17 composition/release/episode/experience/discovery-router layer.

Each test pins ONE real bug found by close reading (not fuzzing) and fixed the
same session: a malformed-input or raising-collaborator path that used to crash
with an unhandled exception, now degrades to a typed refusal/UNKNOWN outcome.
Zero mocks throughout -- every "raising collaborator" is a real Python callable
that genuinely raises, not a mock configured to raise.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.composition.resolver import (
    REFUSED_MALFORMED_MANIFEST,
    SubjectResolutionError,
    SubjectResolver,
)
from autofde_lab.sa2a.episode.episode1 import Episode1Runner
from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.experience.compiler import ArtifactRegistry, EpisodeEvidence, ExperienceCompiler
from autofde_lab.sa2a.experience.admission import ExperienceAdmissionGate
from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry
from autofde_lab.sa2a.experience.qualification import ExperienceQualifier
from autofde_lab.sa2a.release.fresh_consumer import verify
from autofde_lab.sa2a.unknown.resolution import AdmissionReceipt, CandidateResolution, EpistemicState, UnknownQuery
from autofde_lab.sa2a.unknown.router import DiscoveryEngine, DiscoveryEngineKind, DiscoveryRouter

_VALID_MANIFEST = {
    "release_id": "v26.9.17-hardening-test",
    "root_manifest_digest": "c" * 64,
}


def test_subject_resolver_refuses_string_where_repositories_list_expected() -> None:
    try:
        SubjectResolver().resolve({**_VALID_MANIFEST, "repositories": "not-a-list"})
        assert False, "must refuse cleanly, never crash with AttributeError"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_MALFORMED_MANIFEST


def test_subject_resolver_refuses_non_dict_repository_entries() -> None:
    try:
        SubjectResolver().resolve({**_VALID_MANIFEST, "repositories": [123, "x", None]})
        assert False, "must refuse cleanly, never crash with AttributeError"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_MALFORMED_MANIFEST


def test_subject_resolver_refuses_non_mapping_manifest() -> None:
    try:
        SubjectResolver().resolve(["not", "a", "mapping"])  # type: ignore[arg-type]
        assert False, "must refuse cleanly, never crash"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_MALFORMED_MANIFEST


def test_fresh_consumer_reports_corrupt_not_absent_for_truncated_checkpoint(tmp_path: Path) -> None:
    (tmp_path / "ep1.json").write_text(
        '{"episode_id": "ep1", "experience_id": "exp1", "known_route_id": "r1", '
        '"classification": "KNOWN", "actuation_identity": "a1"}'
    )
    (tmp_path / "ep1.ocel2.json").write_text('{"events": []}')
    (tmp_path / "ep2.json").write_text("{not valid json")
    (tmp_path / "ep2.ocel2.json").write_text('{"events": []}')

    standing = verify(tmp_path, "ep1", "ep2")
    assert standing.verdict() == "UNKNOWN:ARTIFACTS_CORRUPT:ep2_checkpoint"
    assert standing.artifacts_corrupt == ("ep2_checkpoint",)
    # Distinguishable from genuine absence -- a different failure class.
    assert standing.artifacts_absent == ()


def test_fresh_consumer_reports_corrupt_for_json_that_is_not_an_object(tmp_path: Path) -> None:
    """A file that parses as valid JSON but isn't a dict (e.g. a bare list or
    number) is still not a usable checkpoint -- must not crash on the first
    `.get()` call downstream."""
    (tmp_path / "ep1.json").write_text("[1, 2, 3]")
    (tmp_path / "ep1.ocel2.json").write_text('{"events": []}')
    (tmp_path / "ep2.json").write_text('{"episode_id": "ep2"}')
    (tmp_path / "ep2.ocel2.json").write_text('{"events": []}')

    standing = verify(tmp_path, "ep1", "ep2")
    assert standing.verdict() == "UNKNOWN:ARTIFACTS_CORRUPT:ep1_checkpoint"


def test_known_route_registry_lookup_survives_a_raising_predicate() -> None:
    routes = KnownRouteRegistry()
    compiler = ExperienceCompiler()
    candidate = CandidateResolution(
        candidate_id="c1", query_id="q1", proposed_assertion="service:x requires-port",
        evidence_payload={"source": "probe"}, source_identity="probe", consumed_ticks=1, consumed_tokens=0,
    )
    receipt = AdmissionReceipt(
        receipt_id="r1", candidate_hash=candidate.candidate_hash, admitted=True,
        epistemic_standing=EpistemicState.KNOWN, reasons=("OK",), admitted_assertion=candidate.proposed_assertion,
    )
    experience = compiler.compile(
        semantic_class_id="requires-port", admitted_solution=candidate, admission_receipt=receipt,
        episode_evidence=EpisodeEvidence(episode_id="ep1", discovery_identity="probe", discovery_resource_receipt="r"),
        equivalence_predicate_id="raising-predicate",
    )
    admitted = ExperienceAdmissionGate(compiler.artifact_registry).admit(experience)
    assert admitted.admitted

    def raising_predicate(_candidate: object) -> bool:
        raise RuntimeError("this predicate is broken")

    qualifier = ExperienceQualifier(compiler.artifact_registry, routes)
    result = qualifier.qualify(admitted.experience, equivalence_predicate=raising_predicate, probe_input="requires-port")
    assert result.qualified

    # lookup() must not propagate the predicate's RuntimeError -- it must
    # gracefully report UNKNOWN (None) instead of crashing the caller.
    found = routes.lookup("requires-port", "anything")
    assert found is None


def test_discovery_router_survives_a_raising_engine_and_falls_through() -> None:
    router = DiscoveryRouter()

    def broken(query: UnknownQuery):
        raise RuntimeError("engine internal failure")

    def working(query: UnknownQuery) -> CandidateResolution:
        return CandidateResolution(
            candidate_id="c1", query_id=query.query_id, proposed_assertion="resolved",
            evidence_payload={}, source_identity="working-engine", consumed_ticks=1, consumed_tokens=0,
        )

    router.register(DiscoveryEngine("broken-1", DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY, broken))
    router.register(DiscoveryEngine("working-1", DiscoveryEngineKind.FORMAL_PLANNER_OR_SOLVER, working))

    result = router.route(UnknownQuery(query_id="q1", predicate_or_topic="anything"))
    assert result.selected_engine_id == "working-1"
    assert result.errored_engine_ids == ("broken-1",)


def test_episode1_runner_survives_a_raising_discover_callable(tmp_path: Path) -> None:
    def broken_discover(query: UnknownQuery):
        raise RuntimeError("this discover callable is broken")

    runner = Episode1Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts"
    )
    result = runner.run(
        semantic_class_id="requires-port",
        query=UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"),
        discover=broken_discover,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-1", probe_input="requires-port",
        action_iri="urn:action:open-port", target_resource="urn:cap:api-gateway",
    )
    assert result.episode.classification == "UNKNOWN"
    assert result.machine_experience.refusal_code == "REFUSED_DISCOVER_CALLABLE_RAISED"
    # The episode still reaches a durable checkpoint -- crash recovery is not lost
    # just because discovery itself failed.
    assert (tmp_path / "state" / f"{result.episode.episode_id}.json").exists()
