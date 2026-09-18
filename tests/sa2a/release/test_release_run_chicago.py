"""Chicago-style tests for ReleaseRun / ReleaseState (v26.9.17 PRD §12; ARD §45, §50).

Real collaborators throughout: real SubjectResolver, Episode1Runner/Episode2Runner,
ReplayEngine, and a REAL separate subprocess for the fresh-consumer verifier
(invoked exactly the way `ReleaseRun._run_fresh_consumer` invokes it in production
-- `subprocess.run([sys.executable, "-m", ...])`). Zero mocks.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.release.run import ReleaseRun, ReleaseRunResult
from autofde_lab.sa2a.release.state_machine import ReleaseState, can_transition_release
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery

_MANIFEST = {
    "release_id": "v26.9.17-test-crown",
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
        candidate_id="cand-ep1", query_id=query.query_id, proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"}, source_identity="formal-port-probe",
        consumed_ticks=2, consumed_tokens=0,
    )


def _run(tmp_path: Path, manifest: dict) -> tuple[ReleaseRun, ReleaseRunResult]:
    run = ReleaseRun(work_dir=tmp_path)
    result = run.run(
        candidate_manifest=manifest,
        semantic_class_id="requires-port",
        episode1_query=UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"),
        episode1_discover=_discover,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        episode1_target_resource="urn:cap:api-gateway",
        episode2_fresh_candidate=CandidateResolution(
            candidate_id="cand-ep2", query_id="q-2-fresh", proposed_assertion="service:billing-worker requires-port",
            evidence_payload={"source": "fresh-request"}, source_identity="fresh-request",
            consumed_ticks=0, consumed_tokens=0,
        ),
        episode2_target_resource="urn:cap:billing-worker",
    )
    return run, result


def test_full_crown_reaches_crowned_through_every_required_predecessor(tmp_path: Path) -> None:
    run, result = _run(tmp_path, _MANIFEST)
    assert result.state == ReleaseState.CROWNED
    assert run.history == [
        ReleaseState.CREATED, ReleaseState.SUBJECT_FENCED, ReleaseState.PREFLIGHTED,
        ReleaseState.EPISODE_1_RUNNING, ReleaseState.EPISODE_1_VERIFIED, ReleaseState.EXPERIENCE_ADMITTED,
        ReleaseState.EPISODE_2_RUNNING, ReleaseState.EPISODE_2_VERIFIED, ReleaseState.CHICAGO_RUNNING,
        ReleaseState.EVIDENCE_VALIDATED, ReleaseState.CROWNED,
    ]
    assert result.exact_subject is not None
    assert result.replay_report is not None
    assert result.replay_report.standing.value == "ALIVE"
    assert result.fresh_consumer_standing is not None
    assert result.fresh_consumer_standing["verdict"] == "CONFORMANT_EVIDENCE_RECONSTRUCTED"


def test_episode_2_receives_the_real_composition_digest_not_an_empty_string(tmp_path: Path) -> None:
    """Regression (tag-readiness audit, 2026-09-17): ReleaseRun.run() used to omit
    exact_subject_digest= on its Episode2Runner.run() call, even though
    Episode2Runner.run() accepts it -- Episode 1's own record carried the real
    composition digest while Episode 2's silently carried "". PRD §14 item 28
    ("one composition receipt binds the COMPLETE exact subject") requires both."""
    _, result = _run(tmp_path, _MANIFEST)
    assert result.episode1 is not None and result.episode2 is not None
    assert result.exact_subject is not None
    assert result.episode1.episode.exact_subject_digest == result.exact_subject.composition_digest
    assert result.episode2.episode.exact_subject_digest == result.exact_subject.composition_digest
    assert result.episode2.episode.exact_subject_digest != ""


def test_both_episodes_carry_a_real_manufacture_digest(tmp_path: Path) -> None:
    """Regression (tag-readiness audit, 2026-09-17): Episode.manufacture_digest was
    defined and serialized but had zero assignment sites anywhere -- every crown run
    emitted an empty string for PRD §14 item 12 ("real manufacture where required")
    despite a real CompiledDeterministicRule genuinely being manufactured and
    evaluated by both episodes."""
    _, result = _run(tmp_path, _MANIFEST)
    assert result.episode1 is not None and result.episode2 is not None
    assert result.episode1.episode.manufacture_digest != ""
    assert result.episode2.episode.manufacture_digest != ""
    # Both episodes evaluate the SAME compiled artifact Episode 1 manufactured.
    assert result.episode1.episode.manufacture_digest == result.episode2.episode.manufacture_digest

    receipt = result.to_receipt()
    assert receipt["standing"] == "CROWNED"
    assert receipt["composition_digest"] == result.exact_subject.composition_digest
    assert receipt["episode_2"]["frontier_clean"] is True


def test_dirty_worktree_subject_is_blocked_before_episode1_ever_runs(tmp_path: Path) -> None:
    """ARD §61: a dirty worktree SHALL prevent final release standing -- and no
    episode work should be attempted for a subject that will never crown."""
    dirty_manifest = {**_MANIFEST, "repositories": [{"name": "autofde-lab", "exact_sha": f"dirty:{'a' * 40}"}]}
    run, result = _run(tmp_path, dirty_manifest)
    assert result.state == ReleaseState.BLOCKED
    assert "DIRTY_WORKTREE" in result.reason
    assert result.episode1 is None
    assert run.history == [ReleaseState.CREATED, ReleaseState.SUBJECT_FENCED, ReleaseState.BLOCKED]


def test_floating_repository_ref_refuses_before_subject_fenced(tmp_path: Path) -> None:
    floating_manifest = {**_MANIFEST, "repositories": [{"name": "x", "exact_sha": "main"}]}
    run, result = _run(tmp_path, floating_manifest)
    assert result.state == ReleaseState.REFUSED
    assert result.exact_subject is None
    assert run.history == [ReleaseState.CREATED, ReleaseState.REFUSED]


def test_state_machine_refuses_skipping_a_required_predecessor() -> None:
    """PRD §12: 'No transition may skip a required predecessor.'"""
    assert not can_transition_release(ReleaseState.CREATED, ReleaseState.EPISODE_1_RUNNING)
    assert not can_transition_release(ReleaseState.CREATED, ReleaseState.CROWNED)
    assert can_transition_release(ReleaseState.CREATED, ReleaseState.SUBJECT_FENCED)


def test_terminal_states_have_no_further_lawful_transitions() -> None:
    """CROWNED in particular: a crowned run cannot retroactively become REFUSED."""
    for terminal in (ReleaseState.CROWNED, ReleaseState.REFUSED, ReleaseState.BLOCKED, ReleaseState.NONCONFORMANT):
        assert not can_transition_release(terminal, ReleaseState.CREATED)
        assert not can_transition_release(terminal, ReleaseState.EPISODE_1_RUNNING)
    assert not can_transition_release(ReleaseState.CROWNED, ReleaseState.REFUSED)
    assert not can_transition_release(ReleaseState.CROWNED, ReleaseState.NONCONFORMANT)


def test_fresh_consumer_is_a_genuinely_separate_process_not_an_in_process_call(tmp_path: Path) -> None:
    """The exact regression this pass caught and fixed: `release/__init__.py` must
    not transitively import the producing runtime, or a subprocess invocation of
    `fresh_consumer` would fail its own independence self-check."""
    import subprocess
    import sys

    _, result = _run(tmp_path, _MANIFEST)
    assert result.episode1 is not None and result.episode2 is not None
    state_dir = tmp_path / "state"

    proc = subprocess.run(
        [sys.executable, "-m", "autofde_lab.sa2a.release.fresh_consumer", str(state_dir),
         result.episode1.episode.episode_id, result.episode2.episode.episode_id],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    import json

    standing = json.loads(proc.stdout)
    assert standing["verdict"] == "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert all(edge["established"] for edge in standing["edges"])
