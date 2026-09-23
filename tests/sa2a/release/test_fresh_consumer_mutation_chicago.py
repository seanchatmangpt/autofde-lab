"""Mutation tests for the fresh-consumer trust-anchor verifier (v26.9.17 hardening pass,
2026-09-17; ARD §45; `.claude/rules/level4-completion-law.md`'s mutation law).

`fresh_consumer.py` is the "trust anchor" standing verifier: a real, separate-process
consumer that reads ONLY the durable JSON checkpoint + OCEL files `Episode1Runner`/
`Episode2Runner` write, and recomputes standing across `REQUIRED_CHAIN`'s 7 typed
object-to-object edges. Per `level4-completion-law.md`: "for every required relation R,
construct an otherwise-complete episode, mutate exactly R's identity, and require
admission to produce a typed non-ALIVE evidence object." Functional (happy-path) coverage
already exists in `tests/sa2a/release/test_release_run_chicago.py` -- this file is the
adversarial complement: for each of the 7 edges, build a real CONFORMANT pair (via the
real `ReleaseRun` -> `Episode1Runner`/`Episode2Runner` pipeline, never hand-written JSON,
so a hand-authored fixture cannot silently paper over a real schema mismatch), corrupt
exactly that edge's identity in the durable files on disk, and assert the verifier
degrades to a typed `UNKNOWN:CHAIN_INCOMPLETE:<edge>` verdict rather than staying
CONFORMANT or blaming an unrelated edge.

Real collaborators throughout, zero mocks: real `Episode1Runner`/`Episode2Runner` via the
real `ReleaseRun` orchestrator, real files on disk, mutated with real `json`
read/modify/write, and (for at least one baseline case and one mutation case, per this
pass's own instruction) the real, separate-process subprocess invocation
`ReleaseRun._run_fresh_consumer` itself uses in production.

Isolation note (read before "fixing" a test that looks like it is failing wrong): six of
the seven edges (`episode1_ocel->experience`, `episode2->same_route`,
`episode2_ocel->route`, `episode2->fresh_identity`, `episode2->frontier_clean_recomputed`,
`episode2->anti_vacuity`) can each be broken by mutating exactly one raw field that no
other edge's formula reads -- confirmed empirically below, and each of those six tests
asserts `unestablished == [<that edge only>]`, strictly. The seventh,
`episode1->experience`, cannot be isolated that way: `episode2->same_route`'s own formula
in `fresh_consumer.verify()` is `bool(ep1_active) and ep2_experience_id == ep1_experience_id
and ep2_route_id == ep1_route_id` -- it ANDs directly on `episode1->experience`'s own
boolean, so any mutation that breaks `episode1->experience` necessarily also breaks
`episode2->same_route`. This is the chain correctly refusing to let Episode 2 claim
"the same route Episode 1 produced" when Episode 1 never actually produced one -- a real,
intended coupling, not a chain-anchoring bug -- and `test_edge0_...` below asserts exactly
that two-edge failure while also asserting the five unrelated edges remain established (so
a genuine wrong-edge-blamed bug, e.g. edge 0's mutation instead flipping `fresh_identity`,
would still be caught).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.release import fresh_consumer as fc
from autofde_lab.sa2a.release.run import ReleaseRun
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery

_MANIFEST = {
    "release_id": "v26.9.17-mutation-test-crown",
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


def _build_conformant_pair(work_dir: Path) -> tuple[Path, str, str]:
    """Runs a REAL Episode1Runner -> Episode2Runner pair (via the real ReleaseRun
    orchestrator, exactly as production does) and returns (state_dir, episode1_id,
    episode2_id) for a pair that independently verifies as CONFORMANT before any
    mutation is applied. Never hand-writes checkpoint/OCEL JSON."""
    run = ReleaseRun(work_dir=work_dir)
    result = run.run(
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
    assert result.episode1 is not None and result.episode2 is not None, (
        "prerequisite real crown run did not reach Episode 2"
    )
    state_dir = work_dir / "state"
    ep1_id = result.episode1.episode.episode_id
    ep2_id = result.episode2.episode.episode_id
    sanity = fc.verify(state_dir, ep1_id, ep2_id)
    assert sanity.verdict() == "CONFORMANT_EVIDENCE_RECONSTRUCTED", (
        f"prerequisite real pair must be CONFORMANT before mutation; got {sanity.verdict()} ({sanity.report()})"
    )
    return state_dir, ep1_id, ep2_id


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_subprocess_verify(state_dir: Path, ep1_id: str, ep2_id: str) -> dict[str, Any]:
    """Invokes fresh_consumer exactly as `ReleaseRun._run_fresh_consumer` does in
    production: a real, separate OS process, never an in-process import."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "autofde_lab.sa2a.release.fresh_consumer",
            str(state_dir),
            ep1_id,
            ep2_id,
        ],
        capture_output=True,
        text=True,
    )
    assert proc.stdout, f"subprocess produced no stdout; stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------------------
# Baseline sanity: the real pair really is CONFORMANT, both in-process and via the real
# subprocess boundary -- establishing this is a precondition for every mutation test
# below meaning anything (a mutation "fixing" an already-broken baseline proves nothing).
# --------------------------------------------------------------------------------------


def test_real_conformant_pair_verifies_in_process(tmp_path: Path) -> None:
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert standing.verdict() == "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert standing.unestablished() == []
    assert all(edge.established for edge in standing.edges)
    assert len(standing.edges) == len(fc.REQUIRED_CHAIN) == 7


def test_real_conformant_pair_verifies_via_real_subprocess(tmp_path: Path) -> None:
    """At least one confirmation via the real, separate-process invocation path
    (`ReleaseRun._run_fresh_consumer`'s exact subprocess call), not just in-process."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    standing = _run_subprocess_verify(state_dir, ep1_id, ep2_id)
    assert standing["verdict"] == "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert all(edge["established"] for edge in standing["edges"])


# --------------------------------------------------------------------------------------
# Mutation law: one test per REQUIRED_CHAIN edge (level4-completion-law.md).
# --------------------------------------------------------------------------------------


def test_edge0_episode1_to_experience_mutated_via_classification(
    tmp_path: Path,
) -> None:
    """Mutate episode1's own claim of having produced an ACTIVE experience (flip
    `classification` away from KNOWN) -- confirmed CAUGHT ON THE FIRST ATTEMPT, no fix
    needed. See module docstring: this legitimately cascades into
    `episode2->same_route` (whose own formula ANDs on this edge's boolean) -- asserted
    explicitly here, alongside the five OTHER edges staying established, so a bug that
    made an unrelated edge fail instead would still be caught."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep1_path = state_dir / f"{ep1_id}.json"
    ep1 = _load(ep1_path)
    assert ep1["classification"] == "KNOWN"
    ep1["classification"] = "REFUSED"
    _save(ep1_path, ep1)

    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert standing.verdict() != "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert standing.verdict().startswith("UNKNOWN:CHAIN_INCOMPLETE:")
    unestablished = set(standing.unestablished())
    assert unestablished == {"episode1->experience", "episode2->same_route"}, (
        f"expected exactly the intended edge plus its necessary dependent, got {unestablished}"
    )
    still_established = {e.name for e in standing.edges if e.established}
    assert still_established == {
        "episode1_ocel->experience",
        "episode2_ocel->route",
        "episode2->fresh_identity",
        "episode2->frontier_clean_recomputed",
        "episode2->anti_vacuity",
    }


def test_edge1_episode1_ocel_to_experience_mutated_via_ocel_relationship_swap(
    tmp_path: Path,
) -> None:
    """Mutate ONLY episode1's own OCEL relationships (swap the experience_id linked
    by the real Episode1Completed event for a forged different id) -- checkpoint files
    untouched. Confirmed CAUGHT ON THE FIRST ATTEMPT, no fix needed: this is the exact
    scenario the task's own worked example named. Verified via BOTH the in-process call
    and the real separate-process subprocess boundary."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep1 = _load(state_dir / f"{ep1_id}.json")
    real_experience_id = ep1["experience_id"]
    assert real_experience_id

    ocel_path = state_dir / f"{ep1_id}.ocel2.json"
    ocel = _load(ocel_path)
    swapped = 0
    for event in ocel["events"]:
        if event["type"] != "Episode1Completed":
            continue
        for rel in event["relationships"]:
            if rel["objectId"] == real_experience_id:
                rel["objectId"] = "exp-FORGED-DIFFERENT-ID"
                swapped += 1
    assert swapped == 1, (
        "fixture assumption broke: expected exactly one experience_id relationship to swap"
    )
    _save(ocel_path, ocel)

    in_process = fc.verify(state_dir, ep1_id, ep2_id)
    assert in_process.verdict() == "UNKNOWN:CHAIN_INCOMPLETE:episode1_ocel->experience"
    assert in_process.unestablished() == ["episode1_ocel->experience"]

    via_subprocess = _run_subprocess_verify(state_dir, ep1_id, ep2_id)
    assert (
        via_subprocess["verdict"]
        == "UNKNOWN:CHAIN_INCOMPLETE:episode1_ocel->experience"
    )
    broken = [e["name"] for e in via_subprocess["edges"] if not e["established"]]
    assert broken == ["episode1_ocel->experience"]


def test_edge2_episode2_same_route_mutated_via_experience_id_mismatch(
    tmp_path: Path,
) -> None:
    """Mutate ONLY episode2's own claimed `experience_id` (leave `known_route_id`
    intact, so `episode2_ocel->route` -- which reads only `known_route_id` -- is
    unaffected). Confirmed CAUGHT ON THE FIRST ATTEMPT, no fix needed; fully isolated."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep2_path = state_dir / f"{ep2_id}.json"
    ep2 = _load(ep2_path)
    assert ep2["experience_id"]
    ep2["experience_id"] = "exp-FORGED-DIFFERENT-ID"
    _save(ep2_path, ep2)

    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert standing.verdict() == "UNKNOWN:CHAIN_INCOMPLETE:episode2->same_route"
    assert standing.unestablished() == ["episode2->same_route"]


def test_edge3_episode2_ocel_to_route_mutated_via_ocel_relationship_swap(
    tmp_path: Path,
) -> None:
    """Mutate ONLY episode2's own OCEL relationships (swap the route_id linked by the
    real Episode2Completed event) -- checkpoint files untouched. Confirmed CAUGHT ON
    THE FIRST ATTEMPT, no fix needed; fully isolated."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep2 = _load(state_dir / f"{ep2_id}.json")
    real_route_id = ep2["known_route_id"]
    assert real_route_id

    ocel_path = state_dir / f"{ep2_id}.ocel2.json"
    ocel = _load(ocel_path)
    swapped = 0
    for event in ocel["events"]:
        if event["type"] != "Episode2Completed":
            continue
        for rel in event["relationships"]:
            if rel["objectId"] == real_route_id:
                rel["objectId"] = "route-FORGED-DIFFERENT-ID"
                swapped += 1
    assert swapped == 1, (
        "fixture assumption broke: expected exactly one route_id relationship to swap"
    )
    _save(ocel_path, ocel)

    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert standing.verdict() == "UNKNOWN:CHAIN_INCOMPLETE:episode2_ocel->route"
    assert standing.unestablished() == ["episode2_ocel->route"]


def test_edge4_episode2_fresh_identity_mutated_via_actuation_identity_reuse(
    tmp_path: Path,
) -> None:
    """Mutate episode2's `actuation_identity` to REUSE episode1's -- the exact PRD
    §6.11 violation `Episode2Runner`'s own docstring names as the thing a fresh
    actuation identity structurally rules out. Confirmed CAUGHT ON THE FIRST ATTEMPT,
    no fix needed; fully isolated."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep1 = _load(state_dir / f"{ep1_id}.json")
    ep2_path = state_dir / f"{ep2_id}.json"
    ep2 = _load(ep2_path)
    assert ep1["actuation_identity"] and ep2["actuation_identity"]
    assert ep1["actuation_identity"] != ep2["actuation_identity"]
    ep2["actuation_identity"] = ep1["actuation_identity"]
    _save(ep2_path, ep2)

    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert standing.verdict() == "UNKNOWN:CHAIN_INCOMPLETE:episode2->fresh_identity"
    assert standing.unestablished() == ["episode2->fresh_identity"]


def test_edge5_frontier_clean_recomputed_mutated_via_stored_value_flip(
    tmp_path: Path,
) -> None:
    """Mutate ONLY the STORED `frontier_clean` boolean on episode2's checkpoint (flip
    it away from what the raw `intelligence_usage` counters actually recompute to),
    leaving every counter and every other field untouched. Confirmed CAUGHT ON THE
    FIRST ATTEMPT, no fix needed; fully isolated -- this is precisely the "producer's
    claim not trusted" mismatch this edge exists to catch."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep2_path = state_dir / f"{ep2_id}.json"
    ep2 = _load(ep2_path)
    assert ep2["frontier_clean"] is True
    ep2["frontier_clean"] = False
    _save(ep2_path, ep2)

    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert (
        standing.verdict()
        == "UNKNOWN:CHAIN_INCOMPLETE:episode2->frontier_clean_recomputed"
    )
    assert standing.unestablished() == ["episode2->frontier_clean_recomputed"]
    edge = next(
        e for e in standing.edges if e.name == "episode2->frontier_clean_recomputed"
    )
    assert "MISMATCH" in edge.basis


def test_edge6_anti_vacuity_mutated_via_blanked_final_receipt_digest(
    tmp_path: Path,
) -> None:
    """Mutate ONLY episode2's `final_receipt_digest` (blank it), leaving
    classification/route_executed/required_postcondition_verified/frontier_clean
    untouched -- simulating a route that classified KNOWN and claims execution but
    never actually produced a receipt. Confirmed CAUGHT ON THE FIRST ATTEMPT, no fix
    needed; fully isolated."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep2_path = state_dir / f"{ep2_id}.json"
    ep2 = _load(ep2_path)
    assert ep2["final_receipt_digest"]
    ep2["final_receipt_digest"] = ""
    _save(ep2_path, ep2)

    standing = fc.verify(state_dir, ep1_id, ep2_id)
    assert standing.verdict() == "UNKNOWN:CHAIN_INCOMPLETE:episode2->anti_vacuity"
    assert standing.unestablished() == ["episode2->anti_vacuity"]


# --------------------------------------------------------------------------------------
# Adversarial malformed-but-valid-JSON shapes: valid JSON, wrong structure. Per the
# module's own docstring ("Never raises -- this verifier is the trust anchor and must
# degrade to a typed UNKNOWN verdict on any malformed input, never crash"), none of
# these may raise out of `verify()`.
# --------------------------------------------------------------------------------------


def test_malformed_shape_experience_id_is_a_list_not_a_string(tmp_path: Path) -> None:
    """A checkpoint with `experience_id` as a list instead of a string -- confirmed
    live: degrades gracefully to a typed UNKNOWN (no crash). `bool([...])` is True for
    a non-empty list, so `episode1->experience` itself is NOT flagged (a real, narrow
    gap this test pins rather than hides: a non-string truthy `experience_id` is not
    independently rejected by that one boolean check) -- but the list can never
    string-equality-match the OCEL's string object ids or episode2's string
    `experience_id`, so the chain still correctly fails at the two edges that actually
    compare identity, and the overall verdict is correctly non-CONFORMANT."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep1_path = state_dir / f"{ep1_id}.json"
    ep1 = _load(ep1_path)
    ep1["experience_id"] = [ep1["experience_id"]]
    _save(ep1_path, ep1)

    standing = fc.verify(state_dir, ep1_id, ep2_id)  # must not raise
    assert standing.verdict() != "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert standing.verdict().startswith("UNKNOWN:CHAIN_INCOMPLETE:")
    assert set(standing.unestablished()) == {
        "episode1_ocel->experience",
        "episode2->same_route",
    }


def test_malformed_shape_intelligence_usage_missing_entirely(tmp_path: Path) -> None:
    """A checkpoint with `intelligence_usage` absent entirely (not `{}`, not present
    at all) -- confirmed live: degrades gracefully. `verify()`'s `ep2.get(
    "intelligence_usage", {}) or {}` yields `{}`, and every counter read then falls
    back to its own `-1`/`-1.0` sentinel default, which never equals the required `0`/
    `0.0` -- so `frontier_clean_recomputed` fails closed rather than silently reading
    zero counters as clean."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ep2_path = state_dir / f"{ep2_id}.json"
    ep2 = _load(ep2_path)
    assert "intelligence_usage" in ep2
    del ep2["intelligence_usage"]
    _save(ep2_path, ep2)

    standing = fc.verify(state_dir, ep1_id, ep2_id)  # must not raise
    assert (
        standing.verdict()
        == "UNKNOWN:CHAIN_INCOMPLETE:episode2->frontier_clean_recomputed"
    )
    assert standing.unestablished() == ["episode2->frontier_clean_recomputed"]


@pytest.mark.parametrize(
    "corrupt_events",
    [
        pytest.param("not-a-list", id="events_is_a_string"),
        pytest.param([1, 2, 3], id="events_is_a_list_of_non_dict_items"),
    ],
)
def test_malformed_shape_ocel_events_wrong_type(
    tmp_path: Path, corrupt_events: Any
) -> None:
    """A real bug found and fixed by this pass: `_ocel_event_objects()` previously
    called `.get(...)` directly on every item of `events` and every item of an event's
    `relationships` with no type check, so a valid-JSON-but-wrong-shape `events` field
    (a string, or a list of non-dict items) raised `AttributeError` OUT OF `verify()`
    itself -- the exact crash this module's own docstring says the trust anchor must
    never produce. Confirmed live before the fix: both shapes below raised
    `AttributeError: '<type>' object has no attribute 'get'`. Fixed in
    `_ocel_event_objects()` (module-level type guards on `events` and each event's
    `relationships`, skipping non-conforming entries instead of indexing into them);
    re-verified here that both shapes now degrade to a typed UNKNOWN with no exception."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ocel_path = state_dir / f"{ep1_id}.ocel2.json"
    ocel = _load(ocel_path)
    ocel["events"] = corrupt_events
    _save(ocel_path, ocel)

    standing = fc.verify(
        state_dir, ep1_id, ep2_id
    )  # must not raise (this is the regression)
    assert standing.verdict() != "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert standing.verdict().startswith("UNKNOWN:CHAIN_INCOMPLETE:")
    assert "episode1_ocel->experience" in standing.unestablished()

    # Also confirmed not to raise across the real subprocess boundary -- a crash caught
    # in-process but not there would still leave the production path exposed.
    via_subprocess = _run_subprocess_verify(state_dir, ep1_id, ep2_id)
    assert via_subprocess["verdict"] != "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert via_subprocess["verdict"].startswith("UNKNOWN:CHAIN_INCOMPLETE:")


def test_malformed_shape_ocel_relationships_is_a_string_not_a_list(
    tmp_path: Path,
) -> None:
    """A third malformed-but-valid-JSON shape: an individual event's `relationships`
    field is a string instead of a list. Same class of bug as the parametrized `events`
    case above (`for r in relationships: r.get(...)` would iterate over characters and
    raise) -- covered by the same fix. Confirmed live: no longer raises."""
    state_dir, ep1_id, ep2_id = _build_conformant_pair(tmp_path)
    ocel_path = state_dir / f"{ep1_id}.ocel2.json"
    ocel = _load(ocel_path)
    ocel["events"][0]["relationships"] = "oops-not-a-list"
    _save(ocel_path, ocel)

    standing = fc.verify(
        state_dir, ep1_id, ep2_id
    )  # must not raise (this is the regression)
    assert standing.verdict() != "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert standing.verdict().startswith("UNKNOWN:CHAIN_INCOMPLETE:")
    assert "episode1_ocel->experience" in standing.unestablished()


# --------------------------------------------------------------------------------------
# episode1_id == episode2_id (the same episode id passed twice).
# --------------------------------------------------------------------------------------


def test_same_episode_id_passed_for_both_arguments_degrades_sensibly(
    tmp_path: Path,
) -> None:
    """What happens if a caller passes the SAME episode id as both `episode1_id` and
    `episode2_id`? Confirmed live, no crash: `verify()` reads episode1's own checkpoint
    and OCEL file under BOTH roles. `episode2->same_route` reports established=True --
    trivially true, since "episode2's" claimed experience/route literally IS episode1's
    own claimed experience/route in this degenerate case -- but the overall verdict
    still correctly refuses CONFORMANT, because:
      - `episode2_ocel->route` fails: episode1's OCEL file contains an
        `Episode1Completed` event, never an `Episode2Completed` event, so the
        "episode2" OCEL lookup for `Episode2Completed` finds nothing.
      - `episode2->fresh_identity` fails: episode1's own `actuation_identity` trivially
        equals itself, so the required `ep1_actuation != ep2_actuation` is false.
    This is the "presumably fail the fresh_identity check" outcome named in this pass's
    own task, confirmed by running it for real rather than assumed."""
    state_dir, ep1_id, _ep2_id = _build_conformant_pair(tmp_path)

    standing = fc.verify(state_dir, ep1_id, ep1_id)  # must not raise

    assert standing.verdict() != "CONFORMANT_EVIDENCE_RECONSTRUCTED"
    assert standing.verdict().startswith("UNKNOWN:CHAIN_INCOMPLETE:")
    unestablished = set(standing.unestablished())
    assert "episode2->fresh_identity" in unestablished, "reused identity must be caught"
    assert "episode2_ocel->route" in unestablished, (
        "episode1's OCEL has no Episode2Completed event"
    )
    # episode1's own genuine edges (which don't depend on which id was passed as
    # "episode2") remain correctly established -- this is not a wholesale crash or a
    # blanket refusal, it is the specific edges that legitimately cannot hold.
    established = {e.name for e in standing.edges if e.established}
    assert "episode1->experience" in established
    assert "episode1_ocel->experience" in established
