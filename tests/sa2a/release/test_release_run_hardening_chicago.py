"""Adversarial hardening tests for `ReleaseRun`/`ReleaseState` (v26.9.17 PRD §12;
ARD §45, §50) -- QUALIFICATION-mode pass per
`~/.claude/rules/local-dfcm-manufacturing-engine.md`: attacking the already-working
crown built in this session, not re-testing its happy path (that's
`test_release_run_chicago.py`).

Real collaborators throughout: real `SubjectResolver`, `Episode1Runner`/
`Episode2Runner`, real `DiscoveryRouter`, `ReplayEngine`, and a REAL separate
subprocess for the fresh-consumer verifier. Zero mocks -- see
`.claude/rules/testing-chicago-style.md`.
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path

import pytest

from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.release.run import ReleaseRun, ReleaseRunResult
from autofde_lab.sa2a.release.state_machine import (
    LAWFUL_RELEASE_TRANSITIONS,
    ReleaseState,
)
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery
from autofde_lab.sa2a.unknown.router import (
    DiscoveryEngine,
    DiscoveryEngineKind,
    DiscoveryRouter,
)

_MANIFEST = {
    "release_id": "v26.9.17-hardening-crown",
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


def _episode2_candidate(query_id: str = "q-2-fresh") -> CandidateResolution:
    return CandidateResolution(
        candidate_id="cand-ep2",
        query_id=query_id,
        proposed_assertion="service:billing-worker requires-port",
        evidence_payload={"source": "fresh-request"},
        source_identity="fresh-request",
        consumed_ticks=0,
        consumed_tokens=0,
    )


def _base_kwargs(manifest: dict) -> dict:
    return dict(
        candidate_manifest=manifest,
        semantic_class_id="requires-port",
        episode1_query=UnknownQuery(
            query_id="q-1", predicate_or_topic="service:api-gateway requires-port"
        ),
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        episode1_target_resource="urn:cap:api-gateway",
        episode2_fresh_candidate=_episode2_candidate(),
        episode2_target_resource="urn:cap:billing-worker",
    )


# --- 1. Calling .run() twice on the same instance -------------------------------


def test_second_run_call_on_same_crowned_instance_is_refused_not_crashed(
    tmp_path: Path,
) -> None:
    """Pre-fix, live behaviour: a second `.run()` call after CROWNED reached the
    first `self._goto(ReleaseState.SUBJECT_FENCED)` inside `run()` and raised an
    uncaught `ValueError` from `validate_release_transition` (only
    `SubjectResolutionError` is caught in `run()`). Now it must return a clean typed
    ReleaseRunResult, leave `self.state`/`self.history` exactly as the first run left
    them (no silent reset -- that would erase the first run's real history), and
    never touch the filesystem for a second episode."""
    run = ReleaseRun(work_dir=tmp_path)
    result1 = run.run(**_base_kwargs(_MANIFEST), episode1_discover=_discover)
    assert result1.state == ReleaseState.CROWNED
    history_after_first_run = list(run.history)

    result2 = run.run(
        **_base_kwargs({**_MANIFEST, "release_id": "a-different-release"}),
        episode1_discover=_discover,
    )

    assert (
        result2.state == ReleaseState.CROWNED
    )  # unchanged -- reflects the FIRST run's real standing
    assert "ALREADY_RUN" in result2.reason
    assert (
        result2.episode1 is None and result2.episode2 is None
    )  # no second episode was ever attempted
    assert run.history == history_after_first_run  # history was not corrupted or reset


def test_second_run_call_after_a_refused_first_run_is_also_refused_not_crashed(
    tmp_path: Path,
) -> None:
    """The same defect reproduced from a non-terminal-looking-but-actually-terminal
    exit (REFUSED), not only from CROWNED -- REFUSED has zero lawful outgoing
    transitions too (state_machine.py), so this hit the identical uncaught
    ValueError pre-fix."""
    floating_manifest = {
        **_MANIFEST,
        "repositories": [{"name": "x", "exact_sha": "main"}],
    }
    run = ReleaseRun(work_dir=tmp_path)
    result1 = run.run(**_base_kwargs(floating_manifest), episode1_discover=_discover)
    assert result1.state == ReleaseState.REFUSED

    result2 = run.run(**_base_kwargs(_MANIFEST), episode1_discover=_discover)
    assert result2.state == ReleaseState.REFUSED
    assert "ALREADY_RUN" in result2.reason


# --- 2. Malformed candidate_manifest propagates cleanly end to end --------------


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param(
            {
                "release_id": "r1",
                "repositories": "not-a-list",
                "artifacts": [],
                "root_manifest_digest": "c" * 64,
            },
            id="repositories_is_a_string",
        ),
        pytest.param(
            {
                "release_id": "r1",
                "repositories": [],
                "artifacts": [42],
                "root_manifest_digest": "c" * 64,
            },
            id="artifact_entry_not_a_mapping",
        ),
        pytest.param(
            {
                "release_id": "r1",
                "repositories": [["a", "b"]],
                "artifacts": [],
                "root_manifest_digest": "c" * 64,
            },
            id="repository_entry_is_a_list",
        ),
        pytest.param(None, id="candidate_manifest_is_none"),
    ],
)
def test_malformed_candidate_manifest_yields_clean_refused_result_not_uncaught_exception(
    tmp_path: Path, manifest
) -> None:
    """Confirms `run.py`'s subject-fence `except SubjectResolutionError` really does
    catch every malformed-manifest shape the composition-layer's own fail-closed
    `SubjectResolver.resolve()` re-raises as that one typed exception -- run.py has
    no OTHER except clause, so if resolver.py ever regressed to a raw
    AttributeError/TypeError this would surface as an uncaught crash here."""
    run = ReleaseRun(work_dir=tmp_path)
    result = run.run(**_base_kwargs(manifest), episode1_discover=_discover)
    assert isinstance(result, ReleaseRunResult)
    assert result.state == ReleaseState.REFUSED
    assert "REFUSED_MALFORMED_MANIFEST" in result.reason
    assert run.history == [ReleaseState.CREATED, ReleaseState.REFUSED]


# --- 3. discover=None / discovery_router=None gap -------------------------------


def test_run_signature_now_exposes_discovery_router() -> None:
    """Confirms the real, worth-naming gap this pass found: `ReleaseRun.run()` used
    to have NO `discovery_router` parameter at all, even though `Episode1Runner.run()`
    accepts one -- now fixed additively (new Optional param, default None)."""
    params = inspect.signature(ReleaseRun.run).parameters
    assert "discovery_router" in params
    assert params["discovery_router"].default is None
    assert params["episode1_discover"].default is None  # now optional, not required


def test_neither_discover_nor_discovery_router_is_refused_before_any_state_transition(
    tmp_path: Path,
) -> None:
    """Pre-fix, live behaviour: passing `episode1_discover=None` with no way to
    supply a `discovery_router` (the parameter did not exist) crashed with an
    uncaught `ValueError` from `Episode1Runner.run()`'s own "exactly one of"
    invariant, leaving `run.state` stuck at EPISODE_1_RUNNING -- not a lawful
    terminal/exit state. Now this must be refused BEFORE subject fencing even
    starts (cheapest failure first, and no wasted SubjectResolver/episode work)."""
    run = ReleaseRun(work_dir=tmp_path)
    result = run.run(
        **_base_kwargs(_MANIFEST), episode1_discover=None, discovery_router=None
    )
    assert result.state == ReleaseState.CREATED  # no transition was attempted at all
    assert "DISCOVERY_CONFIGURATION" in result.reason
    assert run.history == [
        ReleaseState.CREATED
    ]  # untouched -- refused before subject fencing


def test_both_discover_and_discovery_router_simultaneously_is_also_refused(
    tmp_path: Path,
) -> None:
    """The other half of Episode1Runner's 'exactly one of' invariant -- supplying
    BOTH must be refused the same clean way, not silently prefer one."""
    router = DiscoveryRouter()
    run = ReleaseRun(work_dir=tmp_path)
    result = run.run(
        **_base_kwargs(_MANIFEST), episode1_discover=_discover, discovery_router=router
    )
    assert result.state == ReleaseState.CREATED
    assert "DISCOVERY_CONFIGURATION" in result.reason


def test_discovery_router_alone_reaches_crowned_end_to_end(tmp_path: Path) -> None:
    """Confirms the fix is not merely a guard but a REAL additive capability: a real
    DiscoveryRouter, with zero `discover=` callable, drives a full crown to CROWNED
    through ReleaseRun -- exercising the exact new `discovery_router=discovery_router`
    forwarding line added to `runner1.run(...)`."""

    def _candidate(engine_id: str, query: UnknownQuery) -> CandidateResolution:
        return CandidateResolution(
            candidate_id=f"cand-{engine_id}",
            query_id=query.query_id,
            proposed_assertion="service:api-gateway requires-port",
            evidence_payload={"engine": engine_id},
            source_identity=engine_id,
            consumed_ticks=1,
            consumed_tokens=0,
        )

    router = DiscoveryRouter()
    router.register(
        DiscoveryEngine(
            "exact-1",
            DiscoveryEngineKind.EXACT_REUSABLE_MACHINERY,
            lambda q: _candidate("exact-1", q),
        )
    )

    run = ReleaseRun(work_dir=tmp_path)
    result = run.run(**_base_kwargs(_MANIFEST), discovery_router=router)
    assert result.state == ReleaseState.CROWNED, result.reason
    assert result.episode1.episode.classification == "KNOWN"


# --- 4. fresh_consumer subprocess timeout ----------------------------------------


def test_fresh_consumer_subprocess_has_a_bounded_timeout_not_an_unbounded_hang(
    tmp_path: Path,
) -> None:
    """Pre-fix, live behaviour: `_run_fresh_consumer`'s `subprocess.run(...)` call
    carried NO `timeout=` at all -- a hung subprocess would hang `ReleaseRun.run()`
    forever. This exercises the REAL subprocess machinery (a real
    `python -m autofde_lab.sa2a.release.fresh_consumer` process actually starts) with
    a deliberately, absurdly tight timeout (real Python interpreter startup always
    exceeds it) to force the real `subprocess.TimeoutExpired` path deterministically,
    without needing to construct an artificial infinite hang."""
    t0 = time.monotonic()
    standing = ReleaseRun._run_fresh_consumer(
        tmp_path / "state", "ep1-x", "ep2-x", timeout=0.0001
    )
    elapsed = time.monotonic() - t0
    assert elapsed < 5.0, (
        "the call must return promptly once the timeout fires, not hang"
    )
    assert standing["verdict"].startswith("UNKNOWN:SUBPROCESS_TIMEOUT")


def test_fresh_consumer_default_timeout_is_generous_not_tight() -> None:
    """Pins the chosen default (30s) as a deliberate, named value -- not an
    arbitrary magic number that could silently drift to something too tight for a
    real (if slow) fresh_consumer.py invocation."""
    params = inspect.signature(ReleaseRun._run_fresh_consumer).parameters
    assert params["timeout"].default == 30.0


# --- 5. Two ReleaseRun instances with distinct work_dirs do not cross-contaminate


def test_two_release_runs_with_distinct_work_dirs_do_not_cross_contaminate(
    tmp_path: Path,
) -> None:
    work_dir_a = tmp_path / "run-a"
    work_dir_b = tmp_path / "run-b"
    run_a = ReleaseRun(work_dir=work_dir_a)
    run_b = ReleaseRun(work_dir=work_dir_b)

    result_a = run_a.run(
        **_base_kwargs({**_MANIFEST, "release_id": "release-A"}),
        episode1_discover=_discover,
    )
    result_b = run_b.run(
        **_base_kwargs({**_MANIFEST, "release_id": "release-B"}),
        episode1_discover=_discover,
    )

    assert result_a.state == ReleaseState.CROWNED
    assert result_b.state == ReleaseState.CROWNED
    assert result_a.episode1.episode.episode_id != result_b.episode1.episode.episode_id
    assert result_a.episode2.episode.episode_id != result_b.episode2.episode.episode_id
    assert result_a.exact_subject.release_id == "release-A"
    assert result_b.exact_subject.release_id == "release-B"

    state_a_names = {p.name for p in (work_dir_a / "state").glob("*.json")}
    state_b_names = {p.name for p in (work_dir_b / "state").glob("*.json")}
    ep1_id_b = result_b.episode1.episode.episode_id
    assert not any(ep1_id_b in name for name in state_a_names), (
        "work_dir A must not contain any trace of run B's episode"
    )
    assert (
        run_a.history
        == run_b.history
        == [
            ReleaseState.CREATED,
            ReleaseState.SUBJECT_FENCED,
            ReleaseState.PREFLIGHTED,
            ReleaseState.EPISODE_1_RUNNING,
            ReleaseState.EPISODE_1_VERIFIED,
            ReleaseState.EXPERIENCE_ADMITTED,
            ReleaseState.EPISODE_2_RUNNING,
            ReleaseState.EPISODE_2_VERIFIED,
            ReleaseState.CHICAGO_RUNNING,
            ReleaseState.EVIDENCE_VALIDATED,
            ReleaseState.CROWNED,
        ]
    )


# --- 6. LAWFUL_RELEASE_TRANSITIONS mutation-style completeness check ------------

_SIX_TYPED_EXITS = {
    ReleaseState.REFUSED,
    ReleaseState.BLOCKED,
    ReleaseState.BUILD_BROKEN,
    ReleaseState.UNSUPPORTED,
    ReleaseState.NONCONFORMANT,
    ReleaseState.UNKNOWN,
}


def test_every_release_state_has_a_transition_table_entry_no_keyerror_risk() -> None:
    """Confirmed ALREADY CORRECT: every member of the `ReleaseState` enum has an
    entry in `LAWFUL_RELEASE_TRANSITIONS` -- no state was added to the enum without
    being wired into `_MAIN_SEQUENCE` or `_LAWFUL_EXITS`, so `can_transition_release`/
    `validate_release_transition`'s `.get(current, set())` never silently defaults for
    a real state (it would only for a genuinely foreign value)."""
    missing = [s for s in ReleaseState if s not in LAWFUL_RELEASE_TRANSITIONS]
    assert missing == []
    assert set(LAWFUL_RELEASE_TRANSITIONS.keys()) == set(ReleaseState)


def test_every_non_crowned_state_can_reach_all_six_typed_exits_in_one_hop() -> None:
    """Confirmed ALREADY CORRECT: the dict-comprehension in state_machine.py ORs
    `_LAWFUL_EXITS` onto every main-sequence state except CROWNED, so every
    non-terminal state can reach ALL SIX typed exits directly, not just the 2-3
    ReleaseRun.run() currently triggers (see the finding test below)."""
    for state in ReleaseState:
        if state in _SIX_TYPED_EXITS or state is ReleaseState.CROWNED:
            continue
        reachable = LAWFUL_RELEASE_TRANSITIONS[state]
        missing_exits = _SIX_TYPED_EXITS - reachable
        assert not missing_exits, f"{state} cannot reach {missing_exits} in one hop"


def test_crowned_and_every_exit_are_terminal_with_zero_outgoing_transitions() -> None:
    assert LAWFUL_RELEASE_TRANSITIONS[ReleaseState.CROWNED] == set()
    for exit_state in _SIX_TYPED_EXITS:
        assert LAWFUL_RELEASE_TRANSITIONS[exit_state] == set()


def test_named_finding_build_broken_and_unsupported_and_unknown_are_declared_but_dead_in_release_run() -> (
    None
):
    """NAMED FINDING (not fixed -- explicitly out of this pass's scope per the task):
    `ReleaseState.BUILD_BROKEN`, `ReleaseState.UNSUPPORTED`, and `ReleaseState.UNKNOWN`
    are declared as lawful exits in `state_machine.py` and are reachable in the
    transition TABLE from every non-terminal state (confirmed by the test above) --
    but `ReleaseRun.run()` never actually calls `self._goto()` with any of the three.
    Only REFUSED (subject resolution failure), BLOCKED (dirty worktree), and
    NONCONFORMANT (episode/replay/fresh-consumer failure) are ever triggered by the
    real orchestrator. This pins that fact as an executable regression: if a future
    change silently starts (or stops) using one of these three, this test will flip,
    which is the intended signal to update this file's own claim rather than let it
    drift (`.claude/rules/absence-is-not-evidence.md`: a discovered gap is a result,
    not something to paper over silently). Wiring real triggering logic for
    BUILD_BROKEN/UNSUPPORTED (what actual condition should distinguish a build
    failure or missing capability from a generic NONCONFORMANT/REFUSED?) is a real
    design decision left to a future pass, not a bug this adversarial pass fixes."""
    source = inspect.getsource(ReleaseRun.run)
    triggered = {
        state
        for state in ReleaseState
        if f"self._goto(ReleaseState.{state.name})" in source
    }
    assert triggered == {
        ReleaseState.SUBJECT_FENCED,
        ReleaseState.REFUSED,
        ReleaseState.BLOCKED,
        ReleaseState.PREFLIGHTED,
        ReleaseState.EPISODE_1_RUNNING,
        ReleaseState.NONCONFORMANT,
        ReleaseState.EPISODE_1_VERIFIED,
        ReleaseState.EXPERIENCE_ADMITTED,
        ReleaseState.EPISODE_2_RUNNING,
        ReleaseState.EPISODE_2_VERIFIED,
        ReleaseState.CHICAGO_RUNNING,
        ReleaseState.EVIDENCE_VALIDATED,
        ReleaseState.CROWNED,
    }
    dead_exits = _SIX_TYPED_EXITS - triggered
    assert dead_exits == {
        ReleaseState.BUILD_BROKEN,
        ReleaseState.UNSUPPORTED,
        ReleaseState.UNKNOWN,
    }
