"""Chicago-style tests for the real, callable falsifier-corpus runner (v26.9.17
PRD §14 item 27 / ARD §64 item 15, "zero mandatory falsifiers survive").

Real collaborators throughout: the real `FalsifierSuite` (admission/falsifiers.py)
against real adversarial RDF fixtures parsed by real rdflib, and the real
`SubjectResolver` (composition/resolver.py) against real deliberately-malformed
candidate manifests. Zero mocks.
"""

from __future__ import annotations

from rdflib import Graph

from autofde_lab.sa2a.admission.falsifier_corpus import (
    FalsifierCorpusVerdict,
    FalsifierTrialResult,
    _COMPOSITION_FENCE_FIXTURES,
    _SPARQL_FIXTURES,
    compute_falsifier_corpus_digest,
    run_falsifier_corpus,
)
from autofde_lab.sa2a.admission.falsifiers import FalsifierSuite
from autofde_lab.sa2a.composition.resolver import SubjectResolver


class TestRunFalsifierCorpus:
    """`run_falsifier_corpus()` actually runs every mandatory falsifier against a
    real fixture and reports zero survivors -- PRD §14 item 27's own claim,
    verified live, not asserted."""

    def test_all_mandatory_falsifiers_are_caught(self) -> None:
        verdict = run_falsifier_corpus()
        assert isinstance(verdict, FalsifierCorpusVerdict)
        assert verdict.all_mandatory_caught, (
            f"mandatory falsifier(s) survived: {verdict.survived_falsifier_ids}"
        )
        assert verdict.survived_falsifier_ids == ()

    def test_corpus_runs_exactly_the_named_mandatory_falsifiers(self) -> None:
        verdict = run_falsifier_corpus()
        ran_ids = {t.falsifier_id for t in verdict.trials}
        expected_ids = set(_SPARQL_FIXTURES) | set(_COMPOSITION_FENCE_FIXTURES)
        assert ran_ids == expected_ids
        # At minimum: the 5 SPARQL ASK falsifiers already in admission/falsifiers.py
        # PLUS the composition-identity-fence checks (this pass's own instructions).
        assert len(expected_ids) >= 5 + 2

    def test_every_trial_names_which_falsifier_and_a_real_detail(self) -> None:
        verdict = run_falsifier_corpus()
        for trial in verdict.trials:
            assert isinstance(trial, FalsifierTrialResult)
            assert trial.falsifier_id
            assert trial.detail  # a real finding, not an empty placeholder


class TestFalsifierCorpusDigest:
    """`corpus_digest` is real and deterministic -- computed from the corpus's own
    content, never a hardcoded placeholder (unlike the pre-existing `"d" * 64`
    literal in the crown's manifest fixtures, which this module does not touch)."""

    def test_digest_is_deterministic_across_calls(self) -> None:
        first = compute_falsifier_corpus_digest()
        second = compute_falsifier_corpus_digest()
        assert first == second
        assert len(first) == 64  # sha256 hex

    def test_digest_is_not_the_pre_existing_placeholder_literal(self) -> None:
        assert compute_falsifier_corpus_digest() != "d" * 64

    def test_run_falsifier_corpus_digest_matches_standalone_computation(self) -> None:
        verdict = run_falsifier_corpus()
        assert verdict.corpus_digest == compute_falsifier_corpus_digest()

    def test_digest_is_insensitive_to_trial_outcomes(self) -> None:
        """Running the corpus twice (independent real executions) must yield the
        SAME corpus_digest -- the digest identifies corpus content/version, not a
        particular run's pass/fail outcome."""
        first = run_falsifier_corpus()
        second = run_falsifier_corpus()
        assert first.corpus_digest == second.corpus_digest


class TestFalsifierCorpusVerdictAggregation:
    """Real, direct assertions on the typed verdict's own aggregation logic (a real
    dataclass with real behavior -- not a mock of a collaborator)."""

    def test_all_mandatory_caught_is_false_when_any_trial_survived(self) -> None:
        verdict = FalsifierCorpusVerdict(
            corpus_digest="irrelevant-for-this-check",
            trials=(
                FalsifierTrialResult(falsifier_id="A", description="d", survived=False, detail="caught"),
                FalsifierTrialResult(falsifier_id="B", description="d", survived=True, detail="NOT caught"),
            ),
        )
        assert verdict.all_mandatory_caught is False
        assert verdict.survived_falsifier_ids == ("B",)
        assert verdict.caught_falsifier_ids == ("A",)

    def test_all_mandatory_caught_is_true_when_zero_trials_survived(self) -> None:
        verdict = FalsifierCorpusVerdict(
            corpus_digest="irrelevant-for-this-check",
            trials=(
                FalsifierTrialResult(falsifier_id="A", description="d", survived=False, detail="caught"),
                FalsifierTrialResult(falsifier_id="B", description="d", survived=False, detail="caught"),
            ),
        )
        assert verdict.all_mandatory_caught is True
        assert verdict.survived_falsifier_ids == ()


class TestAdversarialFixturesAreGenuinelyAdversarial:
    """Sanity/no-false-positive control: each fixture triggers its falsifier
    specifically because it contains the bad pattern, not universally -- a SAFE
    counterpart must NOT trigger, and a WELL-FORMED manifest must NOT be refused."""

    def test_safe_consequence_action_with_authority_does_not_trigger(self) -> None:
        suite = FalsifierSuite(include_defaults=False)
        fdef = FalsifierSuite(include_defaults=True).get_falsifier("FALSIFIER_CONSEQUENCE_WITHOUT_AUTHORITY")
        suite.register(name=fdef.name, query=fdef.query, description=fdef.description, falsifier_id=fdef.falsifier_id)
        safe_ttl = (
            "@prefix afl: <urn:autofde-lab:> .\n"
            'afl:action-safe afl:consequenceClass "DESTRUCTIVE" ; afl:requiresAuthority afl:auth-safe .\n'
        )
        graph = Graph()
        graph.parse(data=safe_ttl, format="turtle")
        assert suite.evaluate(graph) == []

    def test_safe_projection_without_canonical_claim_does_not_trigger(self) -> None:
        suite = FalsifierSuite(include_defaults=False)
        fdef = FalsifierSuite(include_defaults=True).get_falsifier("FALSIFIER_PROJECTION_AS_CANONICAL")
        suite.register(name=fdef.name, query=fdef.query, description=fdef.description, falsifier_id=fdef.falsifier_id)
        safe_ttl = "@prefix afl: <urn:autofde-lab:> .\nafl:projection-safe a afl:Projection .\n"
        graph = Graph()
        graph.parse(data=safe_ttl, format="turtle")
        assert suite.evaluate(graph) == []

    def test_well_formed_manifest_is_not_refused_by_subject_resolver(self) -> None:
        good_manifest = {
            "release_id": "falsifier-corpus-sanity-well-formed",
            "repositories": [{"name": "repo-safe", "exact_sha": "a" * 40}],
            "artifacts": [{"artifact_id": "artifact-safe", "digest": "b" * 64}],
            "root_manifest_digest": "c" * 64,
        }
        exact_subject = SubjectResolver().resolve(good_manifest)
        assert exact_subject.release_id == "falsifier-corpus-sanity-well-formed"
