"""Real, measured performance benchmark for the v26.9.17 SA2A crown machinery
(QUALIFICATION-mode script, not a pytest suite -- run directly).

Every number this script prints is a real `time.perf_counter()` measurement around
a call to the ACTUAL production classes (`Episode1Runner`, `Episode2Runner`,
`ReleaseRun`, `KnownRouteRegistry`, `DiscoveryRouter`, `DurableDiskReceiptStore`) --
zero mocks, zero estimates. This script imports from `src/autofde_lab/sa2a/` but
does not modify it; it is a read-only consumer of the real public API, exactly the
way `tests/sa2a/release/test_release_run_chicago.py` and
`tests/sa2a/test_v26_9_17_hardening_chicago.py` already exercise these classes.

Usage:
    .venv/bin/python tests/sa2a/benchmarks/bench_v26_9_17_crown.py [--full]

`--full` also runs the N=10000 KnownRouteRegistry tier and the N=1000
DurableDiskReceiptStore tier, both of which take real wall-clock minutes because
they perform that many real AdmissionPipeline/rdflib parses or real disk actuations
-- omitted by default so a routine run stays under ~30s.

Findings this script exists to surface (see docs/jira/v26.9.17/benchmarks/
latency-and-scaling.md for the numbers a real run produced):

1. Per-stage latency breakdown for Episode1Runner, Episode2Runner, and a full
   ReleaseRun crown (including the real fresh_consumer subprocess spawn).
2. KnownRouteRegistry.lookup() scaling as route count grows.
3. DiscoveryRouter.route() scaling as engine count grows, best case (first tier
   answers) vs. worst case (falls through to the last-registered engine).
4. DurableDiskReceiptStore.__init__() cost as a function of how many prep_*.json/
   final_*.json files already exist in store_dir -- __init__ calls
   `_sync_from_disk()`, which reads and json.loads()'s EVERY file on every
   construction, and Episode1Runner/Episode2Runner each construct a FRESH
   DurableDiskReceiptStore per run() call.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from autofde_lab.sa2a.authority.broker import (  # noqa: E402
    AuthorityBroker,
    AuthorityGrant,
)
from autofde_lab.sa2a.brce.boundary import (  # noqa: E402
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.conformance.courts.consequence_court import (  # noqa: E402
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.episode.episode1 import (  # noqa: E402
    Episode1Runner,
    admit_target_binding,
)
from autofde_lab.sa2a.episode.episode2 import Episode2Runner  # noqa: E402
from autofde_lab.sa2a.episode.equivalence import (
    build_topic_equivalence_predicate,  # noqa: E402
)
from autofde_lab.sa2a.episode.types import ExplorationMeter  # noqa: E402
from autofde_lab.sa2a.experience.admission import ExperienceAdmissionGate  # noqa: E402
from autofde_lab.sa2a.experience.compiler import (  # noqa: E402
    ArtifactRegistry,
    EpisodeEvidence,
    ExperienceCompiler,
)
from autofde_lab.sa2a.experience.known_route import (  # noqa: E402
    KnownRoute,
    KnownRouteRegistry,
)
from autofde_lab.sa2a.experience.qualification import ExperienceQualifier  # noqa: E402
from autofde_lab.sa2a.release.run import ReleaseRun  # noqa: E402
from autofde_lab.sa2a.unknown.allocator import (  # noqa: E402
    CMCACandidateAllocator,
    ExplorationBudget,
)
from autofde_lab.sa2a.unknown.resolution import (  # noqa: E402
    CandidateResolution,
    UnknownQuery,
    UnknownResolutionPipeline,
)
from autofde_lab.sa2a.unknown.router import (  # noqa: E402
    PRECEDENCE,
    DiscoveryEngine,
    DiscoveryRouter,
)

RESULTS: dict[str, object] = {}


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 4)


def _time_it(fn: Callable[[], object], reps: int) -> tuple[float, float, float]:
    """Run `fn` `reps` times, return (mean_ms, min_ms, max_ms) over real
    time.perf_counter() deltas -- one call per rep, no batching."""
    samples: list[float] = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        samples.append(t1 - t0)
    return _ms(statistics.mean(samples)), _ms(min(samples)), _ms(max(samples))


def _report(
    label: str, mean_ms: float, min_ms: float, max_ms: float, reps: int
) -> None:
    print(f"  {label}: mean={mean_ms}ms min={min_ms}ms max={max_ms}ms (n={reps})")


# ---------------------------------------------------------------------------
# 1. Single-run latency breakdown
# ---------------------------------------------------------------------------


def _discover(query: UnknownQuery) -> CandidateResolution:
    return CandidateResolution(
        candidate_id=f"cand-{uuid.uuid4().hex[:8]}",
        query_id=query.query_id,
        proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"},
        source_identity="formal-port-probe",
        consumed_ticks=2,
        consumed_tokens=0,
    )


def bench_episode1_stage_breakdown(reps: int = 5) -> dict[str, float]:
    """Replicates Episode1Runner.run()'s internal call sequence by hand, calling
    the SAME real sub-pipeline pieces it composes, so each stage can be timed
    separately with time.perf_counter() (per-stage timing is not observable from
    outside a single Episode1Runner.run() call)."""
    print(
        "\n=== 1a. Episode1 stage breakdown (manual replication of Episode1Runner.run()) ==="
    )
    stage_totals: dict[str, list[float]] = {}

    for i in range(reps):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            meter = ExplorationMeter()
            routes = KnownRouteRegistry()
            artifacts = ArtifactRegistry()
            allocator = CMCACandidateAllocator()
            resolution = UnknownResolutionPipeline(allocator=allocator)
            compiler = ExperienceCompiler(artifacts)
            admission_gate = ExperienceAdmissionGate(artifacts)
            qualifier = ExperienceQualifier(artifacts, routes)

            episode_id = f"ep1-bench-{i}"
            query = UnknownQuery(
                query_id=f"q-{i}",
                predicate_or_topic="service:api-gateway requires-port",
            )
            budget = ExplorationBudget(
                max_compute_ticks=64, max_tokens=4096, max_experiments=4
            )

            t0 = time.perf_counter()
            resolution.route_unknown_to_frontier(
                [query], budget, plan_id=f"{episode_id}-frontier"
            )
            t1 = time.perf_counter()

            candidate = _discover(query)
            t2 = time.perf_counter()

            admission_receipt = resolution.admit_candidate(candidate)
            t3 = time.perf_counter()

            experience = compiler.compile(
                semantic_class_id="requires-port",
                admitted_solution=candidate,
                admission_receipt=admission_receipt,
                episode_evidence=EpisodeEvidence(
                    episode_id=episode_id,
                    discovery_identity=candidate.source_identity,
                    discovery_resource_receipt="budget:64:4096",
                ),
                equivalence_predicate_id="pred-requires-port-v1",
            )
            t4 = time.perf_counter()

            admit_result = admission_gate.admit(experience)
            t5 = time.perf_counter()

            qual_result = qualifier.qualify(
                admit_result.experience,
                equivalence_predicate=build_topic_equivalence_predicate(
                    "requires-port"
                ),
                probe_input="requires-port",
            )
            t6 = time.perf_counter()

            grant = AuthorityGrant(
                grant_id=f"grant-{i}",
                subject_id="bench-actor",
                action_iri="urn:action:open-port",
                target_resource_iri="urn:cap:api-gateway",
            )
            broker = AuthorityBroker(grants=[grant])
            actuator = RealDiskJournalActuator(tmp / "journal.json")
            verifier = IndependentDiskJournalVerifier(tmp / "journal.json")
            receipt_store = DurableDiskReceiptStore(tmp / "receipts")
            boundary = ConsequenceBoundary(broker, actuator, verifier, receipt_store)
            admission_for_action = admit_target_binding(
                "urn:action:open-port",
                "urn:cap:api-gateway",
                issuer="bench-actor",
                timestamp="2026-09-17T00:00:00Z",
            )
            envelope = ExecutionEnvelope(
                idempotency_token=f"act-bench-{i}",
                action_iri="urn:action:open-port",
                target_resource="urn:cap:api-gateway",
                actor_id="bench-actor",
                grant_id=grant.grant_id,
                plan_digest=qual_result.experience.digest,
                admission_result=admission_for_action,
            )
            t7 = time.perf_counter()
            boundary_result = boundary.execute(envelope)
            t8 = time.perf_counter()
            assert boundary_result.success, "benchmark fixture must actually succeed"

            stages = {
                "route_unknown_to_frontier": t1 - t0,
                "discover": t2 - t1,
                "admit_candidate": t3 - t2,
                "compile_experience": t4 - t3,
                "admit_experience": t5 - t4,
                "qualify_experience": t6 - t5,
                "boundary_setup_and_admit_target_binding": t7 - t6,
                "brce_execute": t8 - t7,
                "TOTAL": t8 - t0,
            }
            for k, v in stages.items():
                stage_totals.setdefault(k, []).append(v)

    result: dict[str, float] = {}
    for stage, samples in stage_totals.items():
        mean_ms = _ms(statistics.mean(samples))
        result[stage] = mean_ms
        print(
            f"  {stage}: mean={mean_ms}ms (n={reps}) min={_ms(min(samples))}ms max={_ms(max(samples))}ms"
        )
    return result


def bench_episode1_runner_end_to_end(reps: int = 5) -> tuple[float, float, float]:
    print(
        "\n=== 1b. Episode1Runner.run() end-to-end (single call, for cross-check against 1a's TOTAL) ==="
    )

    def _one(i: int) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            runner = Episode1Runner(
                state_dir=tmp / "state",
                journal_path=tmp / "journal.json",
                receipt_store_dir=tmp / "receipts",
            )
            result = runner.run(
                semantic_class_id="requires-port",
                query=UnknownQuery(
                    query_id=f"q1-{i}",
                    predicate_or_topic="service:api-gateway requires-port",
                ),
                discover=_discover,
                equivalence_predicate=build_topic_equivalence_predicate(
                    "requires-port"
                ),
                equivalence_predicate_id="pred-requires-port-v1",
                probe_input="requires-port",
                action_iri="urn:action:open-port",
                target_resource="urn:cap:api-gateway",
            )
            assert result.episode.classification == "KNOWN"

    i = [0]

    def runner() -> None:
        _one(i[0])
        i[0] += 1

    mean_ms, min_ms, max_ms = _time_it(runner, reps)
    _report("Episode1Runner.run() total", mean_ms, min_ms, max_ms, reps)
    return mean_ms, min_ms, max_ms


def bench_episode2_runner(reps: int = 5) -> dict[str, float]:
    print(
        "\n=== 1c. Episode2Runner.run() (isolated from its Episode1/KnownRoute setup) ==="
    )

    def _setup_known_route(
        tmp: Path,
    ) -> tuple[KnownRouteRegistry, ArtifactRegistry, dict]:
        routes = KnownRouteRegistry()
        artifacts = ArtifactRegistry()
        runner1 = Episode1Runner(
            state_dir=tmp / "state1",
            journal_path=tmp / "journal1.json",
            receipt_store_dir=tmp / "receipts1",
            known_route_registry=routes,
            artifact_registry=artifacts,
        )
        ep1 = runner1.run(
            semantic_class_id="requires-port",
            query=UnknownQuery(
                query_id="q-setup",
                predicate_or_topic="service:api-gateway requires-port",
            ),
            discover=_discover,
            equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
            equivalence_predicate_id="pred-requires-port-v1",
            probe_input="requires-port",
            action_iri="urn:action:open-port",
            target_resource="urn:cap:api-gateway",
        )
        assert ep1.episode.classification == "KNOWN"
        experience_store = {
            ep1.machine_experience.experience_id: ep1.machine_experience
        }
        return routes, artifacts, experience_store

    isolated_samples: list[float] = []
    combined_samples: list[float] = []
    for i in range(reps):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            t0 = time.perf_counter()
            routes, artifacts, experience_store = _setup_known_route(tmp)
            t1 = time.perf_counter()
            runner2 = Episode2Runner(
                state_dir=tmp / "state2",
                journal_path=tmp / "journal2.json",
                receipt_store_dir=tmp / "receipts2",
                known_route_registry=routes,
                artifact_registry=artifacts,
                experience_store=experience_store,
            )
            result = runner2.run(
                semantic_class_id="requires-port",
                fresh_candidate=CandidateResolution(
                    candidate_id=f"cand-ep2-{i}",
                    query_id=f"q2-{i}",
                    proposed_assertion="service:billing-worker requires-port",
                    evidence_payload={"source": "fresh-request"},
                    source_identity="fresh-request",
                    consumed_ticks=0,
                    consumed_tokens=0,
                ),
                probe_input="requires-port",
                action_iri="urn:action:open-port",
                target_resource="urn:cap:billing-worker",
            )
            t2 = time.perf_counter()
            assert result.episode.classification == "KNOWN"
            isolated_samples.append(t2 - t1)
            combined_samples.append(t2 - t0)

    iso_mean, iso_min, iso_max = (
        _ms(statistics.mean(isolated_samples)),
        _ms(min(isolated_samples)),
        _ms(max(isolated_samples)),
    )
    comb_mean, comb_min, comb_max = (
        _ms(statistics.mean(combined_samples)),
        _ms(min(combined_samples)),
        _ms(max(combined_samples)),
    )
    _report(
        "Episode2Runner.run() ISOLATED (setup excluded)",
        iso_mean,
        iso_min,
        iso_max,
        reps,
    )
    _report(
        "Episode1-setup + Episode2Runner.run() COMBINED",
        comb_mean,
        comb_min,
        comb_max,
        reps,
    )
    return {
        "episode2_isolated_mean_ms": iso_mean,
        "episode2_isolated_min_ms": iso_min,
        "episode2_isolated_max_ms": iso_max,
        "episode1_setup_plus_episode2_combined_mean_ms": comb_mean,
    }


_MANIFEST = {
    "release_id": "v26.9.17-bench-crown",
    "repositories": [{"name": "autofde-lab", "exact_sha": "a" * 40}],
    "artifacts": [{"artifact_id": "artifact-1", "digest": "b" * 64}],
    "root_manifest_digest": "c" * 64,
    "semantic_profile": "SA2A-STRICT-BENCHMARK",
    "court_revision": "v26.9.17",
    "falsifier_corpus_digest": "d" * 64,
    "query_set_digest": "e" * 64,
    "environment_identity": "bench-env",
}


def bench_release_run_crown(reps: int = 3) -> dict[str, float]:
    print(
        "\n=== 1d. Full ReleaseRun.run() crown (includes real fresh_consumer subprocess) ==="
    )
    totals: list[float] = []
    subprocess_only: list[float] = []

    for i in range(reps):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = ReleaseRun(work_dir=tmp)

            t0 = time.perf_counter()
            result = run.run(
                candidate_manifest=_MANIFEST,
                semantic_class_id="requires-port",
                episode1_query=UnknownQuery(
                    query_id=f"q-crown-{i}",
                    predicate_or_topic="service:api-gateway requires-port",
                ),
                episode1_discover=_discover,
                equivalence_predicate=build_topic_equivalence_predicate(
                    "requires-port"
                ),
                equivalence_predicate_id="pred-requires-port-v1",
                probe_input="requires-port",
                action_iri="urn:action:open-port",
                episode1_target_resource="urn:cap:api-gateway",
                episode2_fresh_candidate=CandidateResolution(
                    candidate_id=f"cand-ep2-crown-{i}",
                    query_id=f"q2-crown-{i}",
                    proposed_assertion="service:billing-worker requires-port",
                    evidence_payload={"source": "fresh-request"},
                    source_identity="fresh-request",
                    consumed_ticks=0,
                    consumed_tokens=0,
                ),
                episode2_target_resource="urn:cap:billing-worker",
            )
            t1 = time.perf_counter()
            assert result.state.value == "CROWNED", result.reason
            totals.append(t1 - t0)

            # Isolate the fresh_consumer subprocess overhead specifically, by
            # invoking the EXACT command ReleaseRun._run_fresh_consumer() runs,
            # against the already-produced state_dir -- a clean, separate
            # measurement of real process-spawn + interpreter-startup cost.
            state_dir = tmp / "state"
            t2 = time.perf_counter()
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autofde_lab.sa2a.release.fresh_consumer",
                    str(state_dir),
                    result.episode1.episode.episode_id,
                    result.episode2.episode.episode_id,
                ],
                capture_output=True,
                text=True,
                timeout=30.0,
                cwd=str(REPO_ROOT),
            )
            t3 = time.perf_counter()
            assert proc.returncode == 0, proc.stderr
            subprocess_only.append(t3 - t2)

    total_mean = _ms(statistics.mean(totals))
    total_min = _ms(min(totals))
    total_max = _ms(max(totals))
    sub_mean = _ms(statistics.mean(subprocess_only))
    sub_min = _ms(min(subprocess_only))
    sub_max = _ms(max(subprocess_only))
    _report(
        "ReleaseRun.run() full crown (TOTAL, includes its own internal fresh_consumer call)",
        total_mean,
        total_min,
        total_max,
        reps,
    )
    _report(
        "fresh_consumer subprocess spawn (isolated, re-invoked after the run)",
        sub_mean,
        sub_min,
        sub_max,
        reps,
    )
    print(
        f"  fresh_consumer subprocess as % of total crown latency: {round(100 * sub_mean / total_mean, 1)}%"
    )
    return {
        "release_run_total_mean_ms": total_mean,
        "release_run_total_min_ms": total_min,
        "release_run_total_max_ms": total_max,
        "fresh_consumer_subprocess_mean_ms": sub_mean,
        "fresh_consumer_subprocess_min_ms": sub_min,
        "fresh_consumer_subprocess_max_ms": sub_max,
    }


# ---------------------------------------------------------------------------
# 2. KnownRouteRegistry.lookup() scaling
# ---------------------------------------------------------------------------


def _build_known_route_registry(
    n: int, num_classes: int = 50
) -> tuple[KnownRouteRegistry, list[KnownRoute]]:
    registry = KnownRouteRegistry()
    routes: list[KnownRoute] = []
    for i in range(n):
        cls = f"class-{i % num_classes}"
        pred_id = f"pred-{i}"

        def make_pred(target: int = i) -> Callable[[object], bool]:
            return lambda candidate: candidate == target

        registry.register_predicate(pred_id, make_pred())
        route = KnownRoute(
            route_id=f"route-{i}",
            semantic_class_id=cls,
            experience_id=f"exp-{i}",
            equivalence_predicate_id=pred_id,
            required_preconditions=(),
            planner_or_policy_identity="bench",
            manufacturer_identity="bench",
            expected_capabilities=(),
            resource_envelope={},
            qualification_receipt=f"qual-{i}",
        )
        registry.register_route(route)
        routes.append(route)
    return registry, routes


def bench_known_route_registry_scaling(
    sizes: list[int], lookup_reps: int = 500
) -> dict[int, dict[str, float]]:
    print("\n=== 2. KnownRouteRegistry.lookup() scaling ===")
    print(
        f"  (routes spread across 50 semantic_class_id values; N/50 routes per class on average)"
    )
    out: dict[int, dict[str, float]] = {}
    for n in sizes:
        registry, routes = _build_known_route_registry(n)
        last = routes[
            -1
        ]  # deterministically the LAST route appended to ITS class's list too
        class_size = n // 50 + (1 if n % 50 else 0)

        # Worst case within a class: candidate matches only the class's last-registered
        # route, forcing lookup() to scan (and reject) every earlier ACTIVE route in
        # that same class before it hits.
        worst_mean, worst_min, worst_max = _time_it(
            lambda: registry.lookup(last.semantic_class_id, n - 1), lookup_reps
        )
        # Best case: candidate matches the FIRST route registered for ITS class.
        first_in_class = next(r for r in routes if r.semantic_class_id == "class-0")
        first_index = int(first_in_class.route_id.removeprefix("route-"))
        best_mean, best_min, best_max = _time_it(
            lambda: registry.lookup("class-0", first_index), lookup_reps
        )
        # Real miss: no route in the class accepts this candidate -> full class scan, no hit.
        miss_mean, miss_min, miss_max = _time_it(
            lambda: registry.lookup(last.semantic_class_id, -999), lookup_reps
        )

        print(f"  N={n} (approx {class_size} routes/class):")
        _report(
            "    best case (first-in-class hit)",
            best_mean,
            best_min,
            best_max,
            lookup_reps,
        )
        _report(
            "    worst case (last-in-class hit)",
            worst_mean,
            worst_min,
            worst_max,
            lookup_reps,
        )
        _report(
            "    miss (full class scan, no match)",
            miss_mean,
            miss_min,
            miss_max,
            lookup_reps,
        )
        out[n] = {
            "best_case_mean_ms": best_mean,
            "worst_case_mean_ms": worst_mean,
            "miss_mean_ms": miss_mean,
            "approx_routes_per_class": class_size,
        }
    return out


# ---------------------------------------------------------------------------
# 3. DiscoveryRouter.route() scaling
# ---------------------------------------------------------------------------


def _build_discovery_router(n: int) -> DiscoveryRouter:
    router = DiscoveryRouter()
    for i in range(n):
        kind = PRECEDENCE[i % 5]

        def make_attempt(idx: int = i):
            def attempt(query: UnknownQuery):
                if query.query_id == f"target-{idx}":
                    return CandidateResolution(
                        candidate_id=f"c-{idx}",
                        query_id=query.query_id,
                        proposed_assertion="x",
                        evidence_payload={},
                        source_identity=f"engine-{idx}",
                        consumed_ticks=0,
                        consumed_tokens=0,
                    )
                return None

            return attempt

        router.register(DiscoveryEngine(f"engine-{i}", kind, make_attempt()))
    return router


def bench_discovery_router_scaling(
    sizes: list[int], route_reps: int = 500
) -> dict[int, dict[str, float]]:
    print("\n=== 3. DiscoveryRouter.route() scaling ===")
    print("  (N engines round-robin across the 5 DiscoveryEngineKind precedence tiers)")
    out: dict[int, dict[str, float]] = {}
    for n in sizes:
        assert n % 5 == 0, (
            "benchmark sizes must be multiples of 5 for deterministic best/worst engine placement"
        )
        router = _build_discovery_router(n)
        best_query = UnknownQuery(
            query_id="target-0", predicate_or_topic="x"
        )  # engine-0, tier 1, position 0
        worst_query = UnknownQuery(
            query_id=f"target-{n - 1}", predicate_or_topic="x"
        )  # engine-(n-1), tier 5, last position

        best_mean, best_min, best_max = _time_it(
            lambda: router.route(best_query), route_reps
        )
        worst_mean, worst_min, worst_max = _time_it(
            lambda: router.route(worst_query), route_reps
        )
        miss_query = UnknownQuery(query_id="target-nonexistent", predicate_or_topic="x")
        miss_mean, miss_min, miss_max = _time_it(
            lambda: router.route(miss_query), route_reps
        )

        print(f"  N={n} engines:")
        _report(
            "    best case (engine-0, tier 1, first position)",
            best_mean,
            best_min,
            best_max,
            route_reps,
        )
        _report(
            "    worst case (engine-(N-1), tier 5, last position)",
            worst_mean,
            worst_min,
            worst_max,
            route_reps,
        )
        _report(
            "    miss (no engine answers, all N tried)",
            miss_mean,
            miss_min,
            miss_max,
            route_reps,
        )
        out[n] = {
            "best_case_mean_ms": best_mean,
            "worst_case_mean_ms": worst_mean,
            "miss_mean_ms": miss_mean,
        }
    return out


# ---------------------------------------------------------------------------
# 4. DurableDiskReceiptStore construction cost vs. pre-existing file count
# ---------------------------------------------------------------------------


def _populate_receipt_store(store_dir: Path, target_file_count: int) -> None:
    """Perform real ConsequenceBoundary.execute() calls (real disk actuation, real
    AdmissionPipeline/rdflib parse, real PreparedReceipt+FinalReceipt commit) until
    store_dir holds `target_file_count` real prep_*.json + final_*.json files --
    each successful execute() writes exactly one of each, so target_file_count must
    be even."""
    assert target_file_count % 2 == 0
    n_actuations = target_file_count // 2
    store_dir.mkdir(parents=True, exist_ok=True)
    journal_path = store_dir.parent / "seed_journal.json"
    grant = AuthorityGrant(
        grant_id="seed-grant",
        subject_id="seed-actor",
        action_iri="urn:action:seed",
        target_resource_iri="urn:cap:seed-target",
    )
    broker = AuthorityBroker(grants=[grant])
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    receipt_store = DurableDiskReceiptStore(store_dir)
    boundary = ConsequenceBoundary(broker, actuator, verifier, receipt_store)
    admission_for_action = admit_target_binding(
        "urn:action:seed",
        "urn:cap:seed-target",
        issuer="seed-actor",
        timestamp="2026-09-17T00:00:02Z",
    )
    for i in range(n_actuations):
        envelope = ExecutionEnvelope(
            idempotency_token=f"seed-act-{uuid.uuid4().hex[:12]}-{i}",
            action_iri="urn:action:seed",
            target_resource="urn:cap:seed-target",
            actor_id="seed-actor",
            grant_id=grant.grant_id,
            plan_digest=f"seed-plan-{i}",
            admission_result=admission_for_action,
        )
        result = boundary.execute(envelope)
        assert result.success, (
            f"seeding actuation {i} failed to succeed: {result.state}"
        )


def bench_receipt_store_construction_scaling(
    sizes: list[int],
) -> dict[int, dict[str, float]]:
    print(
        "\n=== 4. DurableDiskReceiptStore.__init__() cost vs. pre-existing file count ==="
    )
    print(
        "  (__init__ calls _sync_from_disk(), which globs + json.loads()'s EVERY file)"
    )
    out: dict[int, dict[str, float]] = {}
    for n in sizes:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            store_dir = tmp / "receipts"
            if n > 0:
                t_seed0 = time.perf_counter()
                _populate_receipt_store(store_dir, n)
                t_seed1 = time.perf_counter()
                print(
                    f"  N={n}: seeding {n} real receipt files took {_ms(t_seed1 - t_seed0)}ms (not part of the measured construction cost)"
                )
            else:
                store_dir.mkdir(parents=True, exist_ok=True)

            actual_files = len(list(store_dir.glob("prep_*.json"))) + len(
                list(store_dir.glob("final_*.json"))
            )
            assert actual_files == n, (
                f"seeding produced {actual_files} files, expected {n}"
            )

            reps = 10 if n <= 100 else 3
            mean_ms, min_ms, max_ms = _time_it(
                lambda: DurableDiskReceiptStore(store_dir), reps
            )
            _report(
                f"  N={n} pre-existing files -> DurableDiskReceiptStore(store_dir)",
                mean_ms,
                min_ms,
                max_ms,
                reps,
            )
            out[n] = {
                "mean_ms": mean_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "reps": reps,
            }
    return out


def main() -> None:
    full = "--full" in sys.argv
    print(f"v26.9.17 crown benchmark -- repo={REPO_ROOT} full={full}")
    print(f"python={sys.version.split()[0]} platform={sys.platform}")

    RESULTS["episode1_stage_breakdown_ms"] = bench_episode1_stage_breakdown(reps=5)
    ep1_mean, ep1_min, ep1_max = bench_episode1_runner_end_to_end(reps=5)
    RESULTS["episode1_runner_total_ms"] = {
        "mean": ep1_mean,
        "min": ep1_min,
        "max": ep1_max,
    }
    RESULTS["episode2_runner_ms"] = bench_episode2_runner(reps=5)
    RESULTS["release_run_crown"] = bench_release_run_crown(reps=3)

    known_route_sizes = [10, 100, 1000, 10000] if full else [10, 100, 1000]
    RESULTS["known_route_registry_scaling"] = bench_known_route_registry_scaling(
        known_route_sizes
    )

    RESULTS["discovery_router_scaling"] = bench_discovery_router_scaling(
        [10, 100, 1000]
    )

    receipt_store_sizes = [0, 10, 100, 1000] if full else [0, 10, 100]
    RESULTS["receipt_store_construction_scaling"] = (
        bench_receipt_store_construction_scaling(receipt_store_sizes)
    )

    print("\n=== RAW JSON RESULTS ===")
    print(json.dumps(RESULTS, indent=2, default=str))


if __name__ == "__main__":
    main()
