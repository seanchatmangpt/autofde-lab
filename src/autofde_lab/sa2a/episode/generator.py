"""Deterministic fresh-equivalent-candidate generator (v26.9.17 ARD §64 item 6).

SCOPE, named explicitly (not silently implied broader): this is a real,
deterministic, STRUCTURAL SUBSTITUTION generator -- it is NOT an LLM call and NOT
a general paraphraser. Given a seed `CandidateResolution` (e.g. the one Episode 1
admitted) and a selection `index`, it substitutes the subject noun-phrase for one
of a small, fixed, honestly-scoped pool of alternative subjects while preserving
the exact predicate/topic token `episode/equivalence.py`'s `topic_of()` extracts
(the final whitespace-delimited token of `proposed_assertion`). This is the
honest floor this module builds: real substitution over a bounded, explicit pool
-- never synthesis of novel subjects, never a trivial single-character edit, and
never a claim of general natural-language paraphrase.

Every field that ARD §64 item 6 requires be genuinely different IS different on
the returned candidate: `candidate_id`, `proposed_assertion` (subject text),
`source_identity`, and `evidence_payload`. `topic_of()` is always preserved,
which is exactly what makes the result topic-equivalent under
`episode/equivalence.py`'s `build_topic_equivalence_predicate()` and therefore
resolvable via `KnownRouteRegistry.lookup()` -- proven by a real Episode 1 run +
real lookup call in `tests/sa2a/episode/test_generator_chicago.py`, not asserted
by construction.
"""

from __future__ import annotations

import hashlib

from autofde_lab.sa2a.unknown.resolution import CandidateResolution

#: A small, fixed, honestly-scoped pool of alternative subject noun-phrases.
#: Deliberately not exhaustive, not learned, not LLM-generated -- see the module
#: docstring's scope note. Real strings a caller could plausibly ask about under
#: the same "service:<name> <predicate>" assertion shape this fixture's own
#: `requires-port` demonstration uses (cli.py `_requires_port_seed_candidate`),
#: but this module makes no assumption about WHICH shape of subject/topic it is
#: given beyond "at least two whitespace-delimited tokens" (`_split_subject_and_topic`).
SUBJECT_POOL: tuple[str, ...] = (
    "service:api-gateway",
    "service:billing-worker",
    "service:auth-proxy",
    "service:inventory-sync",
    "service:notification-relay",
    "service:payment-processor",
    "service:search-indexer",
    "service:webhook-dispatcher",
)


def _split_subject_and_topic(proposed_assertion: str) -> tuple[str, str]:
    """Split a `<subject...> <topic>` assertion into its subject prefix and its
    topic (the final whitespace-delimited token) -- exactly the same tokenization
    `episode/equivalence.py::topic_of()` uses, so preserving this split's second
    element always preserves `topic_of()`'s result.
    """
    tokens = proposed_assertion.strip().split()
    if len(tokens) < 2:
        raise ValueError(
            "generate_fresh_equivalent_candidate: cannot split subject/topic from "
            f"malformed proposed_assertion {proposed_assertion!r} -- need at least "
            "2 whitespace-delimited tokens (subject + topic)"
        )
    return " ".join(tokens[:-1]), tokens[-1]


def generate_fresh_equivalent_candidate(
    *, seed: CandidateResolution, index: int
) -> CandidateResolution:
    """Deterministically generate a fresh, topic-equivalent, textually-different
    `CandidateResolution` from `seed`, selecting an alternative subject by `index`.

    Real substitution, never a no-op: the returned candidate always carries a
    DIFFERENT `candidate_id`, `proposed_assertion` (subject swapped for a
    different pool entry -- never re-selects `seed`'s own subject), `source_identity`,
    and `evidence_payload` than `seed`. `topic_of(returned.proposed_assertion) ==
    topic_of(seed.proposed_assertion)` always holds, because only the subject
    prefix is substituted -- the topic token itself is carried over byte-for-byte.

    Two calls with different `index` values (mod the pool size minus the seed's
    own subject) select different pool entries, so consecutive distinct indices
    produce genuinely different `proposed_assertion` text while preserving the
    same topic -- exercised for real in
    `tests/sa2a/episode/test_generator_chicago.py`.
    """
    seed_subject, topic = _split_subject_and_topic(seed.proposed_assertion)

    # Exclude the seed's own subject so the result is always genuinely different
    # from the seed -- never accidentally re-selects it by unlucky modulus.
    alternatives = [s for s in SUBJECT_POOL if s != seed_subject]
    if not alternatives:
        # Only reachable if SUBJECT_POOL were reduced to a single entry that
        # happens to equal the seed's subject -- named explicitly rather than
        # silently returning a byte-identical subject.
        alternatives = [f"{seed_subject}-alt"]
    new_subject = alternatives[index % len(alternatives)]

    selection_digest = hashlib.sha256(
        f"{seed.candidate_id}:{index}:{new_subject}".encode("utf-8")
    ).hexdigest()[:12]

    return CandidateResolution(
        candidate_id=f"cand-generated-{selection_digest}",
        query_id=f"{seed.query_id}-generated-{index}",
        proposed_assertion=f"{new_subject} {topic}",
        evidence_payload={
            "source": "generator:episode2-fresh-equivalent",
            "generator_index": index,
            "seed_candidate_id": seed.candidate_id,
        },
        source_identity=f"generator:episode2-fresh-equivalent:{index}",
        consumed_ticks=0,
        consumed_tokens=0,
    )
