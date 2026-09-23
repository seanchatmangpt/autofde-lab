"""Real OS-thread concurrency/race stress tests for the v26.9.17 crown machinery
(Episode1Runner/Episode2Runner sharing a journal/receipt-store/state directory, and
KnownRouteRegistry under concurrent access) -- QUALIFICATION-mode falsification, not
new feature work (~/.claude/rules/local-dfcm-manufacturing-engine.md).

Real Python `threading` (actual OS threads under the GIL), real filesystem I/O, real
`Episode1Runner`/`Episode2Runner`/`KnownRouteRegistry` objects -- zero mocks. This
single test function runs both stress scenarios end-to-end (deliberately ONE test,
not split across several relying on shared module state across pytest test-function
boundaries, which would silently break under a future `pytest-xdist` split) and
writes real captured findings to
`docs/jira/v26.9.17/benchmarks/concurrency-stress-findings.md` before asserting.

Scope note (read before "fixing" anything here): `RealDiskJournalActuator` and
`DurableDiskReceiptStore` are shared infrastructure used by 20+ other test files and
5+ other src/ modules (conformance courts, benchmarks, replay court) -- see this
file's own findings doc for the exact fan-out. A fix narrow enough to be safe here
(a lock scoped to one class this test owns, e.g. `KnownRouteRegistry`) is applied
directly, in-place, with a re-run proving the race is gone. A fix that would need to
touch `DurableDiskReceiptStore`/`RealDiskJournalActuator` internals is documented as
an open, confirmed-live finding instead, per `.claude/rules/absence-is-not-evidence.md`
("a discovered gap is a result, not something to paper over") and the AFDE-2604
Lens 4 R1/R2/R3 precedent (`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`).
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from autofde_lab.sa2a.episode.episode1 import Episode1Runner
from autofde_lab.sa2a.episode.episode2 import Episode2Runner
from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.experience.known_route import KnownRoute, KnownRouteRegistry
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery

N_THREADS = 8
N_TRIALS = 5


# -----------------------------------------------------------------------------
# Scenario 1: N=8 threads, own Episode1Runner+Episode2Runner, SHARED journal/receipt
# store/state dir -- the exact sharing pattern ReleaseRun.run() itself uses across
# episode1/episode2 within one run.
# -----------------------------------------------------------------------------


@dataclass
class ThreadOutcome:
    thread_index: int
    exception: Optional[str] = None
    ep1_classification: str = ""
    ep1_standing: str = ""
    ep1_boundary_attempted: bool = False
    ep1_boundary_success: bool = False
    ep1_final_digest: str = ""
    ep2_classification: str = ""
    ep2_boundary_attempted: bool = False
    ep2_boundary_success: bool = False
    ep2_final_digest: str = ""
    wrong_answer: str = ""  # non-empty names a specific silent-wrong-result finding


def _run_one_thread(
    i: int, state_dir: Path, journal_path: Path, receipt_store_dir: Path
) -> ThreadOutcome:
    outcome = ThreadOutcome(thread_index=i)
    semantic_class = f"stress-class-{i}"
    action_iri = f"urn:action:stress-{i}"
    target1 = f"urn:cap:stress-{i}:ep1"
    target2 = f"urn:cap:stress-{i}:ep2"

    def discover(query: UnknownQuery) -> CandidateResolution:
        return CandidateResolution(
            candidate_id=f"cand-{i}-ep1",
            query_id=query.query_id,
            proposed_assertion=f"service:node-{i} {semantic_class}",
            evidence_payload={"source": f"stress-probe-{i}"},
            source_identity=f"stress-probe-{i}",
            consumed_ticks=1,
            consumed_tokens=0,
        )

    try:
        runner1 = Episode1Runner(
            state_dir=state_dir,
            journal_path=journal_path,
            receipt_store_dir=receipt_store_dir,
        )
        ep1 = runner1.run(
            semantic_class_id=semantic_class,
            query=UnknownQuery(
                query_id=f"q-{i}-1",
                predicate_or_topic=f"service:node-{i} {semantic_class}",
            ),
            discover=discover,
            equivalence_predicate=build_topic_equivalence_predicate(semantic_class),
            equivalence_predicate_id=f"pred-{semantic_class}-v1",
            probe_input=semantic_class,
            action_iri=action_iri,
            target_resource=target1,
        )
        outcome.ep1_classification = ep1.episode.classification
        outcome.ep1_standing = ep1.episode.standing
        outcome.ep1_boundary_attempted = ep1.boundary_result is not None
        outcome.ep1_boundary_success = bool(
            ep1.boundary_result and ep1.boundary_result.success
        )
        outcome.ep1_final_digest = ep1.episode.final_receipt_digest

        if ep1.episode.classification != "KNOWN":
            return outcome

        experience_store = {
            ep1.machine_experience.experience_id: ep1.machine_experience
        }
        runner2 = Episode2Runner(
            state_dir=state_dir,
            journal_path=journal_path,
            receipt_store_dir=receipt_store_dir,
            known_route_registry=runner1.routes,
            artifact_registry=runner1.artifacts,
            experience_store=experience_store,
        )
        fresh_candidate = CandidateResolution(
            candidate_id=f"cand-{i}-ep2",
            query_id=f"q-{i}-2",
            proposed_assertion=f"service:node-{i}-fresh {semantic_class}",
            evidence_payload={"source": f"stress-fresh-{i}"},
            source_identity=f"stress-fresh-{i}",
            consumed_ticks=0,
            consumed_tokens=0,
        )
        ep2 = runner2.run(
            semantic_class_id=semantic_class,
            fresh_candidate=fresh_candidate,
            probe_input=semantic_class,
            action_iri=action_iri,
            target_resource=target2,
        )
        outcome.ep2_classification = ep2.episode.classification
        outcome.ep2_boundary_attempted = ep2.boundary_result is not None
        outcome.ep2_boundary_success = bool(
            ep2.boundary_result and ep2.boundary_result.success
        )
        outcome.ep2_final_digest = ep2.episode.final_receipt_digest

        # Silent-wrong-answer check: a successful ep1 and ep2 within the SAME thread
        # must never carry the SAME final receipt digest -- that would mean episode 2
        # silently reused episode 1's cached receipt (idempotency-token collision /
        # cross-episode receipt bleed) instead of minting its own fresh actuation.
        if (
            outcome.ep1_boundary_success
            and outcome.ep2_boundary_success
            and outcome.ep1_final_digest == outcome.ep2_final_digest
        ):
            outcome.wrong_answer = (
                "ep1_and_ep2_final_digest_identical_within_same_thread"
            )

    except Exception as exc:  # noqa: BLE001 -- deliberately capturing ANY exception for reporting
        outcome.exception = f"{type(exc).__name__}: {exc}"
    return outcome


def _run_episode_trial(
    tmp_path: Path, trial_index: int
) -> tuple[list[ThreadOutcome], dict]:
    trial_dir = tmp_path / f"trial-{trial_index}"
    state_dir = trial_dir / "state"
    journal_path = trial_dir / "journal.json"
    receipt_store_dir = trial_dir / "receipts"

    outcomes: list[Optional[ThreadOutcome]] = [None] * N_THREADS
    threads: list[threading.Thread] = []

    def target(i: int) -> None:
        outcomes[i] = _run_one_thread(i, state_dir, journal_path, receipt_store_dir)

    start = time.monotonic()
    for i in range(N_THREADS):
        threads.append(
            threading.Thread(target=target, args=(i,), name=f"stress-{trial_index}-{i}")
        )
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60.0)
    duration_s = time.monotonic() - start

    still_alive = [t.name for t in threads if t.is_alive()]

    # Ground-truth check: count real journal records on disk vs. how many
    # boundary.execute() calls actually attempted actuation (each such call invokes
    # RealDiskJournalActuator.actuate() exactly once before deciding success/failure
    # -- see brce/boundary.py execute(): `evidence = self._actuator.actuate(...)` is
    # unconditional once authority+admission pass and the token is fresh).
    attempted_actuations = sum(
        (1 if o.ep1_boundary_attempted else 0) + (1 if o.ep2_boundary_attempted else 0)
        for o in outcomes
        if o is not None
    )
    journal_records = 0
    journal_parse_error = ""
    if journal_path.exists():
        try:
            journal_records = len(json.loads(journal_path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            journal_parse_error = f"{type(exc).__name__}: {exc}"

    summary = {
        "trial_index": trial_index,
        "duration_s": round(duration_s, 3),
        "still_alive_threads": still_alive,
        "attempted_actuations": attempted_actuations,
        "journal_records_on_disk": journal_records,
        "journal_parse_error": journal_parse_error,
        "lost_journal_records": attempted_actuations - journal_records,
    }
    return [o for o in outcomes if o is not None], summary


# -----------------------------------------------------------------------------
# Scenario 2: KnownRouteRegistry direct concurrent register_route()/lookup() stress
# on ONE shared instance.
# -----------------------------------------------------------------------------


def _run_registry_trial(trial_index: int) -> dict:
    registry = KnownRouteRegistry()
    errors: list[str] = []
    errors_lock = threading.Lock()
    registered_ids: list[str] = []
    registered_lock = threading.Lock()

    def register_predicate_and_route(i: int) -> None:
        try:
            semantic_class = f"registry-stress-{trial_index}-{i}"
            pred_id = f"pred-{semantic_class}"
            registry.register_predicate(
                pred_id, build_topic_equivalence_predicate(semantic_class)
            )
            route = KnownRoute(
                route_id=f"route-{semantic_class}",
                semantic_class_id=semantic_class,
                experience_id=f"exp-{semantic_class}",
                equivalence_predicate_id=pred_id,
                required_preconditions=(),
                planner_or_policy_identity="stress-planner",
                manufacturer_identity="stress-manufacturer",
                expected_capabilities=(),
                resource_envelope={},
                qualification_receipt=f"qr-{semantic_class}",
            )
            registry.register_route(route)
            with registered_lock:
                registered_ids.append(route.route_id)
            # Interleave lookups against every thread's class (racing register_route()'s
            # dict mutation on other keys, and its own key's list append).
            for _ in range(20):
                for j in range(N_THREADS):
                    registry.lookup(
                        f"registry-stress-{trial_index}-{j}", f"x {semantic_class}"
                    )
        except Exception as exc:  # noqa: BLE001
            with errors_lock:
                errors.append(f"thread-{i}: {type(exc).__name__}: {exc}")

    threads = [
        threading.Thread(
            target=register_predicate_and_route,
            args=(i,),
            name=f"reg-{trial_index}-{i}",
        )
        for i in range(N_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    still_alive = [t.name for t in threads if t.is_alive()]
    total_routes_visible = sum(
        len(registry.routes_for_class(f"registry-stress-{trial_index}-{i}"))
        for i in range(N_THREADS)
    )
    return {
        "trial_index": trial_index,
        "errors": errors,
        "still_alive_threads": still_alive,
        "expected_routes": N_THREADS,
        "routes_actually_registered": len(registered_ids),
        "routes_visible_in_registry": total_routes_visible,
        "lost_registrations": N_THREADS - total_routes_visible,
    }


# -----------------------------------------------------------------------------
# Scenario 3: KnownRouteRegistry.register_route() (inserts a NEW key via
# setdefault()) racing KnownRouteRegistry.deactivate() (iterates
# self._routes_by_class.values()) -- the specific dict-resize-during-iteration
# hazard named (but not exercised) by Scenario 2. Higher trial count (30, vs. 5
# elsewhere) since this shape needs a thread switch to land inside a narrow
# iteration window to trigger -- a small trial count under-samples it.
# -----------------------------------------------------------------------------

N_REGISTRY_DEACTIVATE_TRIALS = 30
N_REGISTRY_DEACTIVATE_REGISTER_THREADS = 6


def _make_stress_route(i: int, trial: int) -> KnownRoute:
    cls = f"deact-race-{trial}-{i}"
    return KnownRoute(
        route_id=f"route-{cls}",
        semantic_class_id=cls,
        experience_id=f"exp-{cls}",
        equivalence_predicate_id=f"pred-{cls}",
        required_preconditions=(),
        planner_or_policy_identity="stress-planner",
        manufacturer_identity="stress-manufacturer",
        expected_capabilities=(),
        resource_envelope={},
        qualification_receipt="qr",
    )


def _run_registry_deactivate_trial(trial_index: int) -> dict:
    registry = KnownRouteRegistry()
    for i in range(
        3
    ):  # seed routes so deactivate() has something to iterate immediately
        registry.register_route(_make_stress_route(i, trial_index))

    errors: list[str] = []
    errors_lock = threading.Lock()

    def register_worker(i: int) -> None:
        try:
            registry.register_route(_make_stress_route(i + 100, trial_index))
        except Exception as exc:  # noqa: BLE001
            with errors_lock:
                errors.append(f"register[{i}]: {type(exc).__name__}: {exc}")

    def deactivate_worker() -> None:
        try:
            for _ in range(50):
                registry.deactivate(f"route-deact-race-{trial_index}-0")
        except Exception as exc:  # noqa: BLE001
            with errors_lock:
                errors.append(f"deactivate: {type(exc).__name__}: {exc}")

    threads = [
        threading.Thread(
            target=register_worker, args=(i,), name=f"deactreg-{trial_index}-{i}"
        )
        for i in range(N_REGISTRY_DEACTIVATE_REGISTER_THREADS)
    ]
    threads += [
        threading.Thread(target=deactivate_worker, name=f"deact-{trial_index}-{k}")
        for k in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    return {
        "trial_index": trial_index,
        "errors": errors,
        "still_alive_threads": [t.name for t in threads if t.is_alive()],
    }


# -----------------------------------------------------------------------------
# Single test: run all scenarios for real, write real findings, then assert.
# -----------------------------------------------------------------------------


def test_v26_9_17_concurrency_stress(tmp_path: Path) -> None:
    episode_summaries: list[dict] = []
    episode_outcomes: list[list[ThreadOutcome]] = []
    for trial in range(N_TRIALS):
        outcomes, summary = _run_episode_trial(tmp_path, trial)
        episode_outcomes.append(outcomes)
        episode_summaries.append(summary)

    registry_summaries = [_run_registry_trial(trial) for trial in range(N_TRIALS)]
    registry_deactivate_summaries = [
        _run_registry_deactivate_trial(trial)
        for trial in range(N_REGISTRY_DEACTIVATE_TRIALS)
    ]

    _write_findings_document(
        episode_outcomes,
        episode_summaries,
        registry_summaries,
        registry_deactivate_summaries,
    )

    # --- Hard assertions on what must NEVER happen, regardless of legitimate races ---
    for outcomes, summary in zip(episode_outcomes, episode_summaries):
        for o in outcomes:
            assert o.exception is None, (
                f"trial {summary['trial_index']} thread {o.thread_index} raised an "
                f"uncaught exception under concurrent load: {o.exception}"
            )
            assert not o.wrong_answer, (
                f"trial {summary['trial_index']} thread {o.thread_index} produced a "
                f"silent wrong-answer: {o.wrong_answer}"
            )
        assert not summary["still_alive_threads"], (
            f"trial {summary['trial_index']}: threads still alive after 60s join timeout: "
            f"{summary['still_alive_threads']}"
        )
        # The journal file, if written at all, must always be valid JSON -- a torn
        # concurrent write would show up here as a JSONDecodeError, which the atomic
        # os.replace() pattern is specifically supposed to prevent.
        assert not summary["journal_parse_error"], (
            f"trial {summary['trial_index']}: journal file failed to parse as JSON "
            f"after concurrent writes: {summary['journal_parse_error']}"
        )

    for summary in registry_summaries:
        assert not summary["still_alive_threads"], (
            f"trial {summary['trial_index']}: hung threads {summary['still_alive_threads']}"
        )
        assert not summary["errors"], (
            f"trial {summary['trial_index']}: errors {summary['errors']}"
        )
        assert summary["lost_registrations"] == 0, (
            f"trial {summary['trial_index']}: {summary['lost_registrations']} of "
            f"{summary['expected_routes']} registrations lost under concurrent access"
        )

    for summary in registry_deactivate_summaries:
        assert not summary["still_alive_threads"], (
            f"deactivate-race trial {summary['trial_index']}: hung threads {summary['still_alive_threads']}"
        )
        assert not summary["errors"], (
            f"deactivate-race trial {summary['trial_index']}: errors {summary['errors']}"
        )


def _write_findings_document(
    episode_outcomes: list[list[ThreadOutcome]],
    episode_summaries: list[dict],
    registry_summaries: list[dict],
    registry_deactivate_summaries: list[dict],
) -> None:
    findings_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "jira"
        / "v26.9.17"
        / "benchmarks"
        / "concurrency-stress-findings.md"
    )
    lines: list[str] = []
    lines.append("# v26.9.17 concurrency/race stress findings (real, this session)")
    lines.append("")
    lines.append(
        "Real Python `threading` (OS threads under the GIL), real filesystem I/O, real "
        "`Episode1Runner`/`Episode2Runner`/`KnownRouteRegistry` objects. Zero mocks. "
        "Produced by `tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py`, run this "
        "session with `.venv/bin/python -m pytest "
        "tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py -v`."
    )
    lines.append("")
    lines.append(
        f"N_THREADS={N_THREADS}, N_TRIALS={N_TRIALS} (5 independent trials, fresh work_dir each)."
    )
    lines.append("")
    lines.append(
        "## 1. Episode1Runner/Episode2Runner sharing journal_path/receipt_store_dir/state_dir"
    )
    lines.append("")
    lines.append(
        "Each thread constructs its OWN `Episode1Runner`/`Episode2Runner` (own "
        "`KnownRouteRegistry`, own `ArtifactRegistry`, own `ExplorationMeter`) but all "
        "8 threads in a trial point at the SAME `journal_path`/`receipt_store_dir`/"
        "`state_dir` -- the exact sharing pattern `ReleaseRun.run()` itself uses across "
        "episode1/episode2 within one run."
    )
    lines.append("")
    lines.append(
        "| trial | duration_s | attempted_actuations | journal_records_on_disk | "
        "lost_journal_records | journal_parse_error |"
    )
    lines.append("|---|---|---|---|---|---|")
    for s in episode_summaries:
        lines.append(
            f"| {s['trial_index']} | {s['duration_s']} | {s['attempted_actuations']} | "
            f"{s['journal_records_on_disk']} | {s['lost_journal_records']} | "
            f"{s['journal_parse_error'] or '(none)'} |"
        )
    lines.append("")

    total_attempted = sum(s["attempted_actuations"] for s in episode_summaries)
    total_on_disk = sum(s["journal_records_on_disk"] for s in episode_summaries)
    total_lost = sum(s["lost_journal_records"] for s in episode_summaries)
    trials_with_loss = sum(
        1 for s in episode_summaries if s["lost_journal_records"] > 0
    )

    lines.append(
        f"**Real numbers across all {N_TRIALS} trials**: {total_attempted} total "
        f"`boundary.execute()` calls that reached actuation (authority+admission passed, "
        f"fresh idempotency token), {total_on_disk} records actually present in the "
        f"shared journal file afterward, **{total_lost} lost journal records** "
        f"({trials_with_loss}/{N_TRIALS} trials showed at least one lost record)."
    )
    lines.append("")
    if total_lost > 0:
        lines.append(
            "**CONFIRMED, LIVE RACE**: `RealDiskJournalActuator.actuate()` "
            "(`src/autofde_lab/sa2a/conformance/courts/consequence_court.py`) performs an "
            "unsynchronized read-modify-write on the shared journal file: "
            "`records = json.loads(journal_path.read_text())` then `records.append(entry)` "
            "then atomic `os.replace()` of the whole file. The atomic `os.replace()` makes "
            "each INDIVIDUAL file write torn-write-safe (no partial/corrupt file is ever "
            "visible -- confirmed by `journal_parse_error` being empty in every trial above) "
            "but it does **not** make the READ-then-APPEND-then-WRITE sequence atomic as a "
            "whole. When two threads' `actuate()` calls interleave: both read the same "
            "N-record list, both independently append their own entry to their own "
            "in-memory copy, and whichever thread's `os.replace()` lands second silently "
            "overwrites the first thread's entry with a file that never contains it -- a "
            "classic lost-update race, invisible to both actuator calls (each returns "
            "`applied: True`, since neither ever inspects the other's write)."
        )
        lines.append("")
        lines.append(
            "**Consequence for correctness (not just availability)**: the LOST thread's own "
            "`IndependentDiskJournalVerifier.verify_postcondition()` call then reads the "
            "journal's `records[-1]` and finds a DIFFERENT thread's `action`/`target`/"
            "`payload_digest` there, so it correctly returns `False` -- the boundary reports "
            "`success=False` / `TerminalReceiptState.UNKNOWN_OUTCOME` for that thread's real, "
            "genuinely-happened actuation. This is fail-closed (no false `EXECUTED` was ever "
            "observed in these trials -- see the wrong-answer count below), but it is still a "
            "real defect: a durably-real disk mutation happened, and the system's own receipt "
            "for it reports a state that says it never verifiably happened, because the "
            "on-disk EVIDENCE of that mutation was overwritten by a concurrent writer before "
            "the verifier could observe it."
        )
    else:
        lines.append(
            "No lost journal records observed in this run (0 total across all trials). "
            "Given the unsynchronized read-modify-write pattern in "
            "`RealDiskJournalActuator.actuate()` (see source, and the reasoning above), this "
            "absence is most likely explained by low realized contention at N=8 threads on "
            "this machine (the GIL rarely interleaved two `actuate()` calls' read/write "
            "windows within the same shared journal at the SAME moment), not by the code "
            "being race-free by design -- there is no lock anywhere in "
            "`RealDiskJournalActuator`/`DurableDiskReceiptStore`, so the race is real even "
            "when a given run does not happen to trigger it."
        )
    lines.append("")

    any_wrong_answer = [
        (s["trial_index"], o.thread_index, o.wrong_answer)
        for s, trial in zip(episode_summaries, episode_outcomes)
        for o in trial
        if o.wrong_answer
    ]
    any_exception = [
        (s["trial_index"], o.thread_index, o.exception)
        for s, trial in zip(episode_summaries, episode_outcomes)
        for o in trial
        if o.exception
    ]
    known_executed = sum(
        1
        for trial in episode_outcomes
        for o in trial
        if o.ep1_classification == "KNOWN" and o.ep1_standing == "EXECUTED"
    )
    ep1_boundary_failed = sum(
        1
        for trial in episode_outcomes
        for o in trial
        if o.ep1_boundary_attempted and not o.ep1_boundary_success
    )
    total_threads_run = N_THREADS * N_TRIALS

    lines.append(
        f"**Per-episode outcome counts across {total_threads_run} total thread-runs "
        f"({N_TRIALS} trials x {N_THREADS} threads)**: {known_executed} reached "
        f"Episode 1 KNOWN/EXECUTED; {ep1_boundary_failed} attempted actuation but the "
        f"boundary reported failure (the lost-journal-record consequence above, when "
        f"nonzero); {len(any_exception)} raised an uncaught exception; "
        f"{len(any_wrong_answer)} silent wrong-answer(s) (cross-episode receipt digest "
        f"collision) observed."
    )
    lines.append("")
    if any_exception:
        lines.append(
            "Exceptions observed (new bugs, distinct from the known journal race):"
        )
        for trial_idx, thread_idx, exc in any_exception:
            lines.append(f"- trial {trial_idx} thread {thread_idx}: `{exc}`")
        lines.append("")
    if any_wrong_answer:
        lines.append("Silent wrong-answers observed (the dangerous category):")
        for trial_idx, thread_idx, why in any_wrong_answer:
            lines.append(f"- trial {trial_idx} thread {thread_idx}: `{why}`")
        lines.append("")

    lines.append("## 2. KnownRouteRegistry concurrent register_route()/lookup() stress")
    lines.append("")
    lines.append(
        "ONE shared `KnownRouteRegistry` instance per trial, N=8 threads each registering "
        "a route under its OWN distinct semantic class while ALL 8 threads concurrently "
        "call `.lookup()` against every other thread's class (20 lookup passes per "
        "thread) -- direct pressure on the plain, unlocked `dict`/`list` structures in "
        "`register_route()`/`lookup()`."
    )
    lines.append("")
    lines.append(
        "| trial | errors | routes_registered | routes_visible | lost_registrations |"
    )
    lines.append("|---|---|---|---|---|")
    for s in registry_summaries:
        lines.append(
            f"| {s['trial_index']} | {len(s['errors'])} | {s['routes_actually_registered']} | "
            f"{s['routes_visible_in_registry']} | {s['lost_registrations']} |"
        )
    lines.append("")

    total_reg_errors = sum(len(s["errors"]) for s in registry_summaries)
    total_lost_reg = sum(s["lost_registrations"] for s in registry_summaries)
    if total_reg_errors == 0 and total_lost_reg == 0:
        lines.append(
            f"**No RuntimeError and no lost registration observed across all {N_TRIALS} "
            f"trials x {N_THREADS} threads for the register_route()/lookup() access "
            "pattern.**"
        )
    else:
        lines.append(
            f"**{total_reg_errors} errors, {total_lost_reg} lost registrations observed** "
            "-- see pytest's captured stdout/the raw test run for exact exception text."
        )
    lines.append("")

    lines.append(
        "## 3. KnownRouteRegistry.register_route() racing .deactivate() (dict-resize-during-iteration hazard)"
    )
    lines.append("")
    lines.append(
        f"`deactivate()`'s `for routes in self._routes_by_class.values(): ...` iterates the "
        "SAME outer dict `register_route()`'s `setdefault()` can insert a brand-new key "
        "into -- the textbook shape for CPython's `RuntimeError: dictionary changed size "
        f"during iteration`. {N_REGISTRY_DEACTIVATE_TRIALS} independent trials (higher count "
        "than scenarios 1-2, since this shape needs a thread switch to land inside a narrow "
        f"iteration window): {N_REGISTRY_DEACTIVATE_REGISTER_THREADS} threads each calling "
        "`register_route()` under a brand-new semantic class while 2 threads concurrently "
        "call `deactivate()` 50x each against an already-seeded route."
    )
    lines.append("")
    total_deact_errors = sum(len(s["errors"]) for s in registry_deactivate_summaries)
    if total_deact_errors == 0:
        lines.append(
            f"**Zero errors observed across all {N_REGISTRY_DEACTIVATE_TRIALS} trials** "
            "(current state: `KnownRouteRegistry` now holds a `threading.RLock` guarding "
            "every method -- see 'Fix applied' below). This scenario was ALSO run before "
            "the lock was added (same code, same trial count, via a throwaway scratchpad "
            "script) and likewise produced zero errors -- so this result does not, by "
            "itself, prove the lock closed a live bug; it is consistent with either "
            "'the lock works' or 'this shape needs more contention than 6+2 threads on "
            "this machine to trigger under the GIL,' and this findings document does not "
            "overclaim which. The lock is retained as correctness-by-construction "
            "(no test-scale-dependent race window at all, rather than an empirically "
            "unobserved one) since it is a narrow, single-file, low-risk change."
        )
    else:
        lines.append(
            f"**{total_deact_errors} errors observed** -- see pytest's captured stdout for "
            "exact exception text. If any are `RuntimeError: dictionary changed size "
            "during iteration`, this CONFIRMS the hazard live; the lock fix below should "
            "make a re-run of this exact scenario show zero."
        )
    lines.append("")

    lines.append("## Fix applied vs. left open")
    lines.append("")
    lines.append(
        "- **`KnownRouteRegistry` (`src/autofde_lab/sa2a/experience/known_route.py`)**: "
        "FIXED. Added a `threading.RLock` (`self._lock`) guarding `register_predicate()`, "
        "`register_route()`, `deactivate()`, `lookup()`, and `routes_for_class()` -- every "
        "method that reads or writes `_routes_by_class`/`_predicates`. `lookup()` snapshots "
        "the candidate route list and predicate dict under the lock, then releases it before "
        "calling any caller-supplied `predicate(candidate)` (foreign code must never run "
        "while holding this registry's own lock). Owned single-file class, no fan-out to "
        "other callers' internals -- re-verified safe against the full `tests/sa2a` suite "
        "(`.venv/bin/python -m pytest tests/sa2a -q`, exit 0, all passing) after the change."
    )
    lines.append(
        "- **`RealDiskJournalActuator`/`DurableDiskReceiptStore` "
        "(`src/autofde_lab/sa2a/conformance/courts/consequence_court.py`): left open, "
        "NOT fixed**, per this task's explicit scope guidance. `RealDiskJournalActuator` "
        "is constructed at call sites across 5 `src/` modules (`consequence_court.py`, "
        "`episode1.py`, `episode2.py`, `conformance/benchmarks/harness.py`, "
        "`conformance/runner.py`, `conformance/courts/replay_court.py`) and imported by "
        "20 test files; `DurableDiskReceiptStore` similarly by 4 `src/` modules and 18 "
        'test files (full list: `grep -rln "RealDiskJournalActuator\\|DurableDiskReceiptStore" '
        "src/ tests/`). A lock added inside `actuate()`/`_sync_from_disk()`/`save_prepared`/"
        "`save_final` would need to be keyed by the resolved `journal_path`/`store_dir` "
        "(since separate instances currently share no Python-level state at all -- each "
        "`Episode1Runner.run()`/`Episode2Runner.run()` call constructs a brand-new "
        "`DurableDiskReceiptStore`/`RealDiskJournalActuator` instance) to actually close "
        "this race, which is exactly the kind of shared-infrastructure internals change "
        "this task's ownership boundary excludes. This mirrors the reasoning the AFDE-2604 "
        "Lens 4 R1/R2/R3 TOCTOU findings were deliberately left SURVIVED/open for "
        "(`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`: \"Lens 4's "
        "R1/R2/R3 (TOCTOU/concurrency) deliberately left SURVIVED, verified not "
        'accidentally masked"). Named here as a NEWLY CONFIRMED instance of that same '
        "open concurrency-safety gap, now reproduced against the v26.9.17 crown path "
        "specifically (Episode1Runner/Episode2Runner sharing a journal across real OS "
        "threads), not just against the older RFC-SA2A-001/AFDE-2604 courts."
    )
    lines.append("")
    lines.append("## Reproduction")
    lines.append("")
    lines.append("```bash")
    lines.append(
        ".venv/bin/python -m pytest tests/sa2a/test_v26_9_17_concurrency_stress_chicago.py -v"
    )
    lines.append("```")
    lines.append("")

    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
