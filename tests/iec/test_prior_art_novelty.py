"""Tests for the prior-art novelty court."""

import unittest

from autofde_lab.iec.prior_art import (
    NoveltyRefusal,
    PriorArtCandidate,
    PriorArtDisposition,
    PriorArtVerdict,
    assert_novelty_receipt,
    classify_prior_art,
)


def candidate(identifier: str, *semantics: str) -> PriorArtCandidate:
    return PriorArtCandidate(
        id=identifier,
        semantics=frozenset(semantics),
        provenance=f"https://example.invalid/{identifier}",
        exact_subject="fixture",
    )


class PriorArtNoveltyCourtTest(unittest.TestCase):
    def test_reuses_existing_formalism(self):
        verdict = classify_prior_art(
            {"hierarchical-planning", "task-decomposition"},
            [
                candidate(
                    "prior:hddl",
                    "hierarchical-planning",
                    "task-decomposition",
                    "methods",
                ),
                candidate("prior:pddl", "classical-planning"),
            ],
        )
        self.assertEqual(verdict.disposition, PriorArtDisposition.REUSE)
        self.assertEqual(verdict.selected, ("prior:hddl",))
        self.assertEqual(verdict.residual, ())
        self.assertEqual(verdict.standing, "NONE")

    def test_composes_existing_formalisms_before_invention(self):
        verdict = classify_prior_art(
            {"transition-system", "execution-observation"},
            [
                candidate("prior:tla-plus", "transition-system", "safety"),
                candidate("prior:ocel2", "execution-observation", "object-centric-events"),
            ],
        )
        self.assertEqual(verdict.disposition, PriorArtDisposition.COMPOSE)
        self.assertEqual(set(verdict.selected), {"prior:tla-plus", "prior:ocel2"})
        self.assertEqual(verdict.residual, ())

    def test_extension_exposes_only_irreducible_residual(self):
        verdict = classify_prior_art(
            {"ontology", "typed-functions", "authority-receipt"},
            [
                candidate("prior:owl2", "ontology"),
                candidate("prior:shacl", "graph-constraints"),
            ],
        )
        self.assertEqual(verdict.disposition, PriorArtDisposition.EXTEND)
        self.assertEqual(
            verdict.residual,
            ("authority-receipt", "typed-functions"),
        )

    def test_novel_gap_requires_search_and_discharge(self):
        verdict = classify_prior_art(
            {"semantic-that-no-candidate-has"},
            [
                candidate("prior:hddl", "hierarchical-planning"),
                candidate("prior:ocel2", "execution-observation"),
            ],
        )
        self.assertEqual(verdict.disposition, PriorArtDisposition.NOVEL_GAP)
        self.assertEqual(verdict.selected, ())
        assert_novelty_receipt(verdict)

    def test_no_candidates_is_failed_research_not_novelty(self):
        with self.assertRaisesRegex(NoveltyRefusal, "PRIOR_ART_SEARCH_MISSING"):
            classify_prior_art({"new-semantics"}, [])

    def test_forged_novelty_receipt_is_refused(self):
        verdict = PriorArtVerdict(
            required_semantics=("x",),
            searched=("prior:hddl",),
            selected=(),
            disposition=PriorArtDisposition.NOVEL_GAP,
            residual=("x",),
            failures=(),
        )
        with self.assertRaisesRegex(NoveltyRefusal, "SEARCH_NOT_DISCHARGED"):
            assert_novelty_receipt(verdict)


if __name__ == "__main__":
    unittest.main()
