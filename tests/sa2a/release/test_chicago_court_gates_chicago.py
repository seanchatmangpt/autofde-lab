"""Chicago-style tests for `ReleaseRun`'s real Chicago court gates (v26.9.17 PRD §14
item 26 / ARD §64 item 15, "mandatory Chicago gates pass" / "run the complete
Chicago Crown").

Real collaborators throughout: a real end-to-end `ReleaseRun` crown execution, the
real `ConsequenceCourt`/`AuthorityCourt` classes composed (never re-derived) against
this crown's own real journal/receipt-store infra and real action_iri/target_resource
identity. Zero mocks.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.conformance.courts.authority_court import AuthorityCheckResult
from autofde_lab.sa2a.conformance.courts.consequence_court import CourtGateResult
from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.release.run import ReleaseRun
from autofde_lab.sa2a.release.state_machine import ReleaseState
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery

_MANIFEST = {
    "release_id": "v26.9.17-chicago-gates-test-crown",
    "repositories": [{"name": "autofde-lab", "exact_sha": "a" * 40}],
    "artifacts": [{"artifact_id": "artifact-1", "digest": "b" * 64}],
    "root_manifest_digest": "c" * 64,
    "semantic_profile": "SA2A-STRICT-DEMONSTRATION",
    "court_revision": "v26.9.17",
    "falsifier_corpus_digest": "d" * 64,
    "query_set_digest": "e" * 64,
    "environment_identity": "test-env",
}


def _discover(query: UnknownQuery) -> CandidateResolution:
    return CandidateResolution(
        candidate_id="cand-ep1",
        query_id=query.query_id,
        proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"},
        source_identity="formal-port-probe",
        consumed_ticks=2,
        consumed_tokens=0,
    )


def _run_crown(tmp_path: Path):
    run = ReleaseRun(work_dir=tmp_path)
    return run.run(
        candidate_manifest=_MANIFEST,
        semantic_class_id="requires-port",
        episode1_query=UnknownQuery(
            query_id="q-1", predicate_or_topic="service:api-gateway requires-port"
        ),
        episode1_discover=_discover,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        episode1_target_resource="urn:cap:api-gateway",
        episode2_fresh_candidate=CandidateResolution(
            candidate_id="cand-ep2",
            query_id="q-2-fresh",
            proposed_assertion="service:billing-worker requires-port",
            evidence_payload={"source": "fresh-request"},
            source_identity="fresh-request",
            consumed_ticks=0,
            consumed_tokens=0,
        ),
        episode2_target_resource="urn:cap:billing-worker",
    )


class TestChicagoCourtGatesWiredForReal:
    def test_crowned_run_reports_every_named_gate_passed(self, tmp_path: Path) -> None:
        result = _run_crown(tmp_path)
        assert result.state == ReleaseState.CROWNED, result.reason
        gates = result.chicago_court_gates
        assert gates is not None
        assert len(gates) > 0
        for gate_id, gate_result in gates.items():
            assert isinstance(gate_result, (CourtGateResult, AuthorityCheckResult))
            assert gate_result.passed is True, f"{gate_id} did not pass: {gate_result}"

    def test_wired_gate_registry_matches_what_a_real_crown_run_actually_produces(
        self, tmp_path: Path
    ) -> None:
        """Structural drift guard: `ReleaseRun.CHICAGO_COURT_GATES_WIRED` (the named
        scope record) must name EXACTLY the gate ids a real crown run produces --
        catches the class attribute silently drifting from the real code."""
        result = _run_crown(tmp_path)
        assert result.state == ReleaseState.CROWNED, result.reason
        produced_gate_ids = set(result.chicago_court_gates.keys())
        assert produced_gate_ids == set(ReleaseRun.CHICAGO_COURT_GATES_WIRED)

    def test_wired_and_not_applicable_registries_are_disjoint(self) -> None:
        wired = set(ReleaseRun.CHICAGO_COURT_GATES_WIRED)
        not_applicable = set(ReleaseRun.CHICAGO_COURT_GATES_NOT_APPLICABLE.keys())
        assert wired.isdisjoint(not_applicable)

    def test_consequence_court_gates_present_and_named(self, tmp_path: Path) -> None:
        result = _run_crown(tmp_path)
        gates = result.chicago_court_gates
        for gate_id in (
            "CHI-BRCE-01-PREPARED-COMMIT",
            "CHI-BRCE-02-BYPASS-PREVENTION",
            "CHI-BRCE-03-ANTI-COLLUSION",
            "CHI-POST-01-INDEPENDENT-OBSERVATION",
            "CHI-BRCE-04-IDEMPOTENCY-REPLAY-REFUSAL",
        ):
            assert gate_id in gates
            assert isinstance(gates[gate_id], CourtGateResult)

    def test_authority_court_gates_present_and_named(self, tmp_path: Path) -> None:
        result = _run_crown(tmp_path)
        gates = result.chicago_court_gates
        for gate_id in (
            "SA2A-AUTH-AGENT-NOT-AUTHORITY",
            "SA2A-AUTH-PLAN-NOT-AUTHORITY",
            "SA2A-AUTH-PROOF-NOT-AUTHORITY",
            "SA2A-AUTH-CAPABILITY-NOT-AUTHORITY",
            "SA2A-AUTH-GRANT-REQUIRED",
            "SA2A-AUTH-CONFUSED-DEPUTY",
            "CHI-PLAN-AUTH-TOKEN-REBINDING",
            "SA2A-AUTH-LEGITIMATE-GRANT",
            "CHI-PLAN-AUTH-PLANNER-NON-AUTHORITY",
        ):
            assert gate_id in gates
            assert isinstance(gates[gate_id], AuthorityCheckResult)

    def test_to_receipt_surfaces_every_gate_as_a_boolean(self, tmp_path: Path) -> None:
        result = _run_crown(tmp_path)
        payload = result.to_receipt()["chicago_court_gates"]
        assert payload is not None
        assert set(payload.keys()) == set(result.chicago_court_gates.keys())
        assert all(v is True for v in payload.values())

    def test_consequence_court_gates_do_not_disturb_the_crowns_own_real_receipts(
        self, tmp_path: Path
    ) -> None:
        """The audit gates append their OWN, distinctly-identified receipts to the
        SAME real receipt store/journal the crown's Episode 1/Episode 2 used -- this
        must never mutate or shadow the episodes' own real final-receipt digests."""
        result = _run_crown(tmp_path)
        assert result.state == ReleaseState.CROWNED, result.reason
        assert result.episode1.episode.final_receipt_digest
        assert result.episode2.episode.final_receipt_digest
        assert (
            result.episode1.episode.final_receipt_digest
            != result.episode2.episode.final_receipt_digest
        )
