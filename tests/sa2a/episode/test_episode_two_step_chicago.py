"""Chicago-style tests for Episode1Runner -> Episode2Runner (v26.9.17 PRD §6.11-6.13,
§7; ARD §5.9-5.10, §16, §20-23).

Real collaborators throughout: real UnknownResolutionPipeline/CMCACandidateAllocator/
AuthorityBroker/ConsequenceBoundary, the real disk actuator/verifier/receipt-store
already built for the Chicago conformance courts, real filesystem I/O (tmp_path), real
state-based assertions on the returned Episode objects. Zero mocks.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.episode.episode1 import Episode1Result, Episode1Runner
from autofde_lab.sa2a.episode.episode2 import Episode2Runner
from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.episode.types import EpisodeKind
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery


def _discover_port_requirement(query: UnknownQuery) -> CandidateResolution:
    return CandidateResolution(
        candidate_id="cand-ep1", query_id=query.query_id,
        proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"}, source_identity="formal-port-probe",
        consumed_ticks=2, consumed_tokens=0,
    )


def _run_episode1(tmp_path: Path) -> tuple[Episode1Runner, Episode1Result]:
    runner1 = Episode1Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts"
    )
    result = runner1.run(
        semantic_class_id="requires-port",
        query=UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"),
        discover=_discover_port_requirement,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        target_resource="urn:cap:api-gateway",
    )
    return runner1, result


def test_episode1_solves_a_genuine_unknown_and_reaches_active_experience(tmp_path: Path) -> None:
    runner1, result = _run_episode1(tmp_path)
    assert result.episode.kind == EpisodeKind.UNKNOWN_DISCOVERY
    assert result.episode.classification == "KNOWN"
    assert result.episode.standing == "EXECUTED"
    assert result.episode.route_executed is True
    assert result.episode.intelligence_usage.explore_unknown_invocations == 1
    assert result.machine_experience.state.value == "ACTIVE"
    assert result.episode.known_route_id == result.machine_experience.known_route_id
    # A real receipt digest was minted, not an empty placeholder.
    assert result.episode.prepared_receipt_digest
    assert result.episode.final_receipt_digest


def test_episode1_checkpoints_intermediate_state_for_crash_recovery(tmp_path: Path) -> None:
    """ARD §16: 'SHALL persist intermediate state for crash recovery/diagnosis.'"""
    runner1, result = _run_episode1(tmp_path)
    snapshot_path = (tmp_path / "state") / f"{result.episode.episode_id}.json"
    assert snapshot_path.exists()
    import json

    snapshot = json.loads(snapshot_path.read_text())
    assert snapshot["last_completed_stage"] == "complete"
    assert snapshot["episode_id"] == result.episode.episode_id


def test_episode2_fresh_equivalent_request_resolves_known_with_zero_exploration(tmp_path: Path) -> None:
    """The core v26.9.17 claim: a FRESH, textually-different-but-semantically-
    equivalent Episode 2 request routes through KNOWN machinery with zero
    equivalent exploratory inference (PRD §6.13, ARD §22-23)."""
    runner1, ep1 = _run_episode1(tmp_path)

    experience_store = {ep1.machine_experience.experience_id: ep1.machine_experience}
    runner2 = Episode2Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts",
        known_route_registry=runner1.routes, artifact_registry=runner1.artifacts, experience_store=experience_store,
    )
    fresh_candidate = CandidateResolution(
        candidate_id="cand-ep2-different", query_id="q-2-fresh",
        proposed_assertion="service:billing-worker requires-port",  # same topic, different subject/text
        evidence_payload={"source": "fresh-request"}, source_identity="fresh-request",
        consumed_ticks=0, consumed_tokens=0,
    )
    ep2 = runner2.run(
        semantic_class_id="requires-port", fresh_candidate=fresh_candidate, probe_input="requires-port",
        action_iri="urn:action:open-port", target_resource="urn:cap:billing-worker",
    )

    assert ep2.episode.kind == EpisodeKind.KNOWN_REPLAY
    assert ep2.episode.classification == "KNOWN"
    assert ep2.episode.route_executed is True
    assert ep2.episode.required_postcondition_verified is True
    assert ep2.episode.frontier_clean is True

    usage = ep2.episode.intelligence_usage
    assert usage.explore_unknown_invocations == 0
    assert usage.frontier_model_calls == 0
    assert usage.local_discovery_model_calls == 0
    assert usage.worker_allocations == 0

    # PRD §6.11: fresh actuation identity, never Episode 1's.
    assert ep2.episode.actuation_identity != ep1.episode.actuation_identity
    assert ep2.episode.request_identity != ep1.episode.request_identity
    assert ep2.episode.episode_id != ep1.episode.episode_id
    # Distinct receipts too -- Episode 2 minted its own, never returned Episode 1's
    # cached receipt via idempotency-token replay.
    assert ep2.episode.final_receipt_digest != ep1.episode.final_receipt_digest
    assert ep2.episode.prepared_receipt_digest != ep1.episode.prepared_receipt_digest


def test_episode2_non_equivalent_candidate_is_unknown_not_a_false_known(tmp_path: Path) -> None:
    """Falsifier for PRD §6.9/§6.10: a candidate outside the semantic class must
    never resolve KNOWN merely because SOME route exists for that class."""
    runner1, ep1 = _run_episode1(tmp_path)
    experience_store = {ep1.machine_experience.experience_id: ep1.machine_experience}
    runner2 = Episode2Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts",
        known_route_registry=runner1.routes, artifact_registry=runner1.artifacts, experience_store=experience_store,
    )
    unrelated_candidate = CandidateResolution(
        candidate_id="cand-unrelated", query_id="q-unrelated",
        proposed_assertion="service:database-cluster requires-replication-factor",
        evidence_payload={}, source_identity="unrelated", consumed_ticks=0, consumed_tokens=0,
    )
    ep2 = runner2.run(
        semantic_class_id="requires-port", fresh_candidate=unrelated_candidate, probe_input="requires-port",
        action_iri="urn:action:open-port", target_resource="urn:cap:database-cluster",
    )
    assert ep2.episode.classification == "UNKNOWN"
    assert ep2.known_route is None
    assert ep2.boundary_result is None


def test_episode2_before_any_episode1_is_unknown_not_a_crash(tmp_path: Path) -> None:
    """No KnownRouteRegistry entries exist yet -- Episode 2 must classify UNKNOWN
    cleanly rather than error, and must not attempt any consequence."""
    from autofde_lab.sa2a.experience.compiler import ArtifactRegistry
    from autofde_lab.sa2a.experience.known_route import KnownRouteRegistry

    runner2 = Episode2Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts",
        known_route_registry=KnownRouteRegistry(), artifact_registry=ArtifactRegistry(), experience_store={},
    )
    candidate = CandidateResolution(
        candidate_id="cand-cold", query_id="q-cold", proposed_assertion="service:x requires-port",
        evidence_payload={}, source_identity="cold", consumed_ticks=0, consumed_tokens=0,
    )
    ep2 = runner2.run(
        semantic_class_id="requires-port", fresh_candidate=candidate, probe_input="requires-port",
        action_iri="urn:action:open-port", target_resource="urn:cap:x",
    )
    assert ep2.episode.classification == "UNKNOWN"
    assert ep2.episode.route_executed is False
    assert ep2.boundary_result is None
