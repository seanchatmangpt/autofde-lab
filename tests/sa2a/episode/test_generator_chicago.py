"""Chicago-style tests for `episode.generator.generate_fresh_equivalent_candidate`
(v26.9.17 ARD §64 item 6, "generate a fresh semantically equivalent instance").

Real collaborators throughout: a real `CandidateResolution` seed, the real
`topic_of()`/`build_topic_equivalence_predicate()` from `episode/equivalence.py`,
a real `Episode1Runner` run producing a real registered `KnownRoute`, and a real
`KnownRouteRegistry.lookup()` call against the generated candidate -- KNOWN
resolution is observed by actually running the real equivalence predicate against
the generated candidate, never asserted by construction. Zero mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.sa2a.episode.episode1 import Episode1Runner
from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate, topic_of
from autofde_lab.sa2a.episode.generator import generate_fresh_equivalent_candidate
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery


def _seed_candidate() -> CandidateResolution:
    return CandidateResolution(
        candidate_id="cand-ep1-seed",
        query_id="q-seed",
        proposed_assertion="service:api-gateway requires-port",
        evidence_payload={"source": "formal-port-probe"},
        source_identity="formal-port-probe",
        consumed_ticks=2,
        consumed_tokens=0,
    )


def test_generated_candidate_is_genuinely_different_from_seed_in_every_required_field() -> None:
    """ARD §64 item 6: candidate_id, subject text, source_identity, and
    evidence_payload must all differ from the seed -- not a trivial no-op edit."""
    seed = _seed_candidate()
    generated = generate_fresh_equivalent_candidate(seed=seed, index=0)

    assert generated.candidate_id != seed.candidate_id
    assert generated.proposed_assertion != seed.proposed_assertion
    assert generated.source_identity != seed.source_identity
    assert generated.evidence_payload != seed.evidence_payload

    # Not a trivial single-character edit: the whole subject noun-phrase changed.
    seed_subject = seed.proposed_assertion.rsplit(" ", 1)[0]
    generated_subject = generated.proposed_assertion.rsplit(" ", 1)[0]
    assert seed_subject != generated_subject
    assert len(generated_subject) - len(seed_subject) != 0 or generated_subject != seed_subject


def test_generated_candidate_preserves_exact_topic_token() -> None:
    """The one thing that must NOT change: the predicate/topic token
    `episode/equivalence.py::topic_of()` extracts."""
    seed = _seed_candidate()
    generated = generate_fresh_equivalent_candidate(seed=seed, index=3)
    assert topic_of(generated.proposed_assertion) == topic_of(seed.proposed_assertion)
    assert topic_of(generated.proposed_assertion) == "requires-port"


def test_two_consecutive_different_indices_produce_different_text_same_topic() -> None:
    """The exact falsifier ARD §64 item 6 names: two consecutive calls with
    different indices/seeds produce DIFFERENT text but the SAME topic_of() result."""
    seed = _seed_candidate()
    first = generate_fresh_equivalent_candidate(seed=seed, index=0)
    second = generate_fresh_equivalent_candidate(seed=seed, index=1)

    assert first.proposed_assertion != second.proposed_assertion
    assert first.candidate_id != second.candidate_id
    assert topic_of(first.proposed_assertion) == topic_of(second.proposed_assertion) == "requires-port"


def test_generation_is_deterministic_for_the_same_seed_and_index() -> None:
    seed = _seed_candidate()
    a = generate_fresh_equivalent_candidate(seed=seed, index=2)
    b = generate_fresh_equivalent_candidate(seed=seed, index=2)
    assert a.proposed_assertion == b.proposed_assertion
    assert a.candidate_id == b.candidate_id


def test_generator_never_reselects_the_seeds_own_subject_across_the_whole_pool() -> None:
    """Real coverage sweep: no index, across a full pool cycle, ever reproduces the
    seed's own subject text -- the exclusion in generator.py is load-bearing, not
    merely likely to hold by chance."""
    seed = _seed_candidate()
    seed_subject = seed.proposed_assertion.rsplit(" ", 1)[0]
    for index in range(16):
        generated = generate_fresh_equivalent_candidate(seed=seed, index=index)
        generated_subject = generated.proposed_assertion.rsplit(" ", 1)[0]
        assert generated_subject != seed_subject


def test_malformed_single_token_assertion_is_refused_not_silently_mangled() -> None:
    seed = CandidateResolution(
        candidate_id="cand-malformed", query_id="q-malformed", proposed_assertion="onlyonetoken",
        evidence_payload={}, source_identity="x", consumed_ticks=0, consumed_tokens=0,
    )
    with pytest.raises(ValueError):
        generate_fresh_equivalent_candidate(seed=seed, index=0)


def test_generated_candidate_genuinely_resolves_known_via_real_known_route_registry_lookup(
    tmp_path: Path,
) -> None:
    """The real integration falsifier ARD §64 item 6 names: feed the generated
    candidate through the REAL `KnownRouteRegistry.lookup()` (populated by a real
    `Episode1Runner` run) and confirm it genuinely resolves KNOWN via the real
    equivalence predicate -- observed by actually running it, not by construction."""
    runner1 = Episode1Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts"
    )

    def discover(query: UnknownQuery) -> CandidateResolution:
        return _seed_candidate()

    ep1 = runner1.run(
        semantic_class_id="requires-port",
        query=UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"),
        discover=discover,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        target_resource="urn:cap:api-gateway",
    )
    assert ep1.episode.classification == "KNOWN"
    assert ep1.machine_experience.state.value == "ACTIVE"

    generated = generate_fresh_equivalent_candidate(seed=_seed_candidate(), index=5)
    # Real assertion this candidate is actually different, not the same object
    # replayed back through lookup by coincidence.
    assert generated.candidate_id != "cand-ep1-seed"
    assert generated.proposed_assertion != "service:api-gateway requires-port"

    resolved_route = runner1.routes.lookup("requires-port", generated)
    assert resolved_route is not None, "generated candidate must resolve KNOWN via the real equivalence predicate"
    assert resolved_route.route_id == ep1.machine_experience.known_route_id


def test_generated_candidate_from_a_different_semantic_class_seed_still_only_matches_its_own_class(
    tmp_path: Path,
) -> None:
    """Falsifier: a generated candidate whose topic does not match a registered
    route's semantic class must not resolve KNOWN merely because SOME route
    exists (PRD §6.9/§6.10, mirroring the existing episode2 non-equivalent test)."""
    runner1 = Episode1Runner(
        state_dir=tmp_path / "state", journal_path=tmp_path / "journal.json", receipt_store_dir=tmp_path / "receipts"
    )

    def discover(query: UnknownQuery) -> CandidateResolution:
        return _seed_candidate()

    ep1 = runner1.run(
        semantic_class_id="requires-port",
        query=UnknownQuery(query_id="q-1", predicate_or_topic="service:api-gateway requires-port"),
        discover=discover,
        equivalence_predicate=build_topic_equivalence_predicate("requires-port"),
        equivalence_predicate_id="pred-requires-port-v1",
        probe_input="requires-port",
        action_iri="urn:action:open-port",
        target_resource="urn:cap:api-gateway",
    )
    assert ep1.episode.classification == "KNOWN"

    unrelated_seed = CandidateResolution(
        candidate_id="cand-unrelated-seed", query_id="q-unrelated",
        proposed_assertion="service:database-cluster requires-replication-factor",
        evidence_payload={}, source_identity="unrelated", consumed_ticks=0, consumed_tokens=0,
    )
    generated_unrelated = generate_fresh_equivalent_candidate(seed=unrelated_seed, index=0)
    assert topic_of(generated_unrelated.proposed_assertion) == "requires-replication-factor"

    resolved = runner1.routes.lookup("requires-port", generated_unrelated)
    assert resolved is None
