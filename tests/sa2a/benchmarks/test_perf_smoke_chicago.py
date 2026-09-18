"""Fast Chicago-style perf-regression smoke tests for the two real scaling
findings `bench_v26_9_17_crown.py` measured (2026-09-17 benchmark pass):

1. DurableDiskReceiptStore.__init__() cost grows with pre-existing receipt-file
   count (it re-reads every prep_*.json/final_*.json on every construction).
2. DiscoveryRouter.route() worst-case cost grows with registered-engine count
   (a query only the last-registered, last-precedence-tier engine answers forces
   a near-full scan).

Both use real collaborators (real disk I/O, real ConsequenceBoundary actuation,
real DiscoveryRouter/DiscoveryEngine objects) -- zero mocks. Thresholds are set
at roughly 30-150x the real measured latency at these scales (see
docs/jira/v26.9.17/benchmarks/latency-and-scaling.md for the measured numbers
this margin is based on), so these guard against a genuine order-of-magnitude
regression (e.g. an accidental O(N^2) reintroduction) without being sensitive to
normal machine-load jitter -- not a tight perf gate.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant  # noqa: E402
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope  # noqa: E402
from autofde_lab.sa2a.conformance.courts.consequence_court import (  # noqa: E402
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)
from autofde_lab.sa2a.episode.episode1 import admit_target_binding  # noqa: E402
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery  # noqa: E402
from autofde_lab.sa2a.unknown.router import DiscoveryEngine, DiscoveryRouter, PRECEDENCE  # noqa: E402


def test_receipt_store_construction_stays_bounded_at_200_preexisting_files(tmp_path: Path) -> None:
    """Real finding (measured): construction cost is ~O(N) in pre-existing
    receipt-file count (0.06ms @0 files -> 8.0ms @100 -> 91.2ms @1000, i.e.
    roughly linear, ~0.08-0.09ms/file). At 200 files that extrapolates to
    roughly 16-18ms -- this asserts a generous 3000ms ceiling (~150-190x
    headroom over the extrapolated real cost), so it only trips on a genuine
    multi-order-of-magnitude regression, never on ordinary CI jitter."""
    store_dir = tmp_path / "receipts"
    store_dir.mkdir()
    journal_path = tmp_path / "journal.json"
    grant = AuthorityGrant(
        grant_id="smoke-grant", subject_id="smoke-actor",
        action_iri="urn:action:smoke", target_resource_iri="urn:cap:smoke-target",
    )
    broker = AuthorityBroker(grants=[grant])
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    seed_store = DurableDiskReceiptStore(store_dir)
    boundary = ConsequenceBoundary(broker, actuator, verifier, seed_store)
    admission = admit_target_binding(
        "urn:action:smoke", "urn:cap:smoke-target", issuer="smoke-actor", timestamp="2026-09-17T00:00:03Z"
    )
    for i in range(100):  # 100 actuations -> 100 prep_*.json + 100 final_*.json = 200 files
        envelope = ExecutionEnvelope(
            idempotency_token=f"smoke-act-{uuid.uuid4().hex[:12]}-{i}", action_iri="urn:action:smoke",
            target_resource="urn:cap:smoke-target", actor_id="smoke-actor", grant_id=grant.grant_id,
            plan_digest=f"smoke-plan-{i}", admission_result=admission,
        )
        result = boundary.execute(envelope)
        assert result.success

    actual_files = len(list(store_dir.glob("prep_*.json"))) + len(list(store_dir.glob("final_*.json")))
    assert actual_files == 200

    t0 = time.perf_counter()
    DurableDiskReceiptStore(store_dir)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 3000.0, (
        f"DurableDiskReceiptStore(store_dir) took {elapsed_ms:.1f}ms for 200 pre-existing "
        "receipt files -- more than 150x the extrapolated real measured cost (~16-18ms); "
        "this is a real regression, not jitter -- see "
        "docs/jira/v26.9.17/benchmarks/latency-and-scaling.md"
    )


def test_discovery_router_worst_case_stays_bounded_at_200_engines() -> None:
    """Real finding (measured): route()'s worst case (query only the very last
    registered engine, in the last precedence tier, answers) grows with total
    engine count -- 0.0064ms @10 engines -> 0.0291ms @100 -> 0.34ms @1000,
    consistent with the real O(5N) scan `DiscoveryRouter.route()`'s per-tier
    `(e for e in self._engines if e.kind == kind)` filter performs (it re-walks
    the full engine list once per of the 5 precedence tiers). At 200 engines
    that extrapolates to roughly 0.06ms -- this asserts a generous 500ms
    ceiling (~8000x headroom), so it only trips on a genuine algorithmic
    regression (e.g. an accidental quadratic-in-N reintroduction), never on
    ordinary CI jitter."""
    router = DiscoveryRouter()
    n = 200
    for i in range(n):
        kind = PRECEDENCE[i % 5]

        def make_attempt(idx: int = i):
            def attempt(query: UnknownQuery):
                if query.query_id == f"smoke-target-{idx}":
                    return CandidateResolution(
                        candidate_id=f"c-{idx}", query_id=query.query_id, proposed_assertion="x",
                        evidence_payload={}, source_identity=f"engine-{idx}", consumed_ticks=0, consumed_tokens=0,
                    )
                return None

            return attempt

        router.register(DiscoveryEngine(f"engine-{i}", kind, make_attempt()))

    worst_query = UnknownQuery(query_id=f"smoke-target-{n - 1}", predicate_or_topic="x")
    t0 = time.perf_counter()
    result = router.route(worst_query)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert result.selected_engine_id == f"engine-{n - 1}"
    assert elapsed_ms < 500.0, (
        f"DiscoveryRouter.route() worst case took {elapsed_ms:.1f}ms for {n} engines -- "
        "far beyond the extrapolated real measured cost (~0.06ms); this is a real "
        "regression, not jitter -- see docs/jira/v26.9.17/benchmarks/latency-and-scaling.md"
    )
