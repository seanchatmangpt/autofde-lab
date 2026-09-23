"""Chicago-style tests for CompositionReceipt (v26.9.17 PRD §14 item 28 / ARD §64
item 16, "one composition receipt binds the complete exact subject").

Real collaborators throughout: the real `ExactSubject`/`SubjectResolver`, the real
`ReleaseRun` crown end-to-end (via the same fixture `test_release_run_chicago.py`
uses), and the real `CompositionReceipt`/`build_composition_receipt`. Zero mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.sa2a.composition.receipt import (
    build_composition_receipt,
)
from autofde_lab.sa2a.episode.equivalence import build_topic_equivalence_predicate
from autofde_lab.sa2a.release.run import ReleaseRun
from autofde_lab.sa2a.release.state_machine import ReleaseState
from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownQuery

_MANIFEST = {
    "release_id": "v26.9.17-composition-receipt-test-crown",
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


def _run_crown(tmp_path: Path):
    run = ReleaseRun(work_dir=tmp_path)
    return run.run(
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


class TestCompositionReceiptBuild:
    """A real end-to-end crown run binds a real CompositionReceipt at CROWNED."""

    def test_crowned_run_attaches_real_composition_receipt(
        self, tmp_path: Path
    ) -> None:
        result = _run_crown(tmp_path)
        assert result.state == ReleaseState.CROWNED, result.reason
        receipt = result.composition_receipt
        assert receipt is not None
        assert receipt.composition_digest == result.exact_subject.composition_digest
        assert (
            receipt.episode1_final_receipt_digest
            == result.episode1.episode.final_receipt_digest
        )
        assert (
            receipt.episode2_final_receipt_digest
            == result.episode2.episode.final_receipt_digest
        )
        assert receipt.episode1_ocel_digest == result.episode1.episode.ocel_digest
        assert receipt.episode2_ocel_digest == result.episode2.episode.ocel_digest
        # Every field is real (non-empty) evidence, not placeholder digests.
        assert receipt.episode1_final_receipt_digest
        assert receipt.episode2_final_receipt_digest
        assert receipt.episode1_ocel_digest
        assert receipt.episode2_ocel_digest

    def test_to_receipt_surfaces_composition_receipt(self, tmp_path: Path) -> None:
        result = _run_crown(tmp_path)
        assert result.state == ReleaseState.CROWNED, result.reason
        payload = result.to_receipt()["composition_receipt"]
        assert payload is not None
        assert (
            payload["composition_receipt_digest"]
            == result.composition_receipt.composition_receipt_digest
        )
        assert payload["composition_digest"] == result.exact_subject.composition_digest

    def test_non_crowned_run_has_no_composition_receipt(self, tmp_path: Path) -> None:
        """A run that never reaches CROWNED (Episode 1 discovery raises -> UNKNOWN)
        must never fabricate a CompositionReceipt for episodes that never completed."""
        run = ReleaseRun(work_dir=tmp_path)

        def _raising_discover(query: UnknownQuery) -> CandidateResolution:
            raise RuntimeError("deliberate discovery failure")

        result = run.run(
            candidate_manifest=_MANIFEST,
            semantic_class_id="requires-port",
            episode1_query=UnknownQuery(
                query_id="q-1", predicate_or_topic="service:api-gateway requires-port"
            ),
            episode1_discover=_raising_discover,
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
        assert result.state == ReleaseState.NONCONFORMANT
        assert result.composition_receipt is None


class TestCompositionReceiptDigestSensitivity:
    """The falsifier this pass was asked to write: two DIFFERENT crown runs'
    CompositionReceipts must have DIFFERENT digests even when they coincidentally
    share one sub-digest -- proving `composition_receipt_digest` is sensitive to
    ALL of its inputs, not merely one.
    """

    _BASE_KWARGS = dict(
        receipt_id="composition-receipt-fixed",
        release_id="release-fixed",
        composition_digest="comp" + "0" * 60,
        episode1_id="ep1-fixed",
        episode1_final_receipt_digest="e1f" + "1" * 61,
        episode1_ocel_digest="e1o" + "2" * 61,
        episode2_id="ep2-fixed",
        episode2_final_receipt_digest="e2f" + "3" * 61,
        episode2_ocel_digest="e2o" + "4" * 61,
    )

    def test_identical_inputs_produce_identical_digest(self) -> None:
        a = build_composition_receipt(**self._BASE_KWARGS)
        b = build_composition_receipt(**self._BASE_KWARGS)
        assert a.composition_receipt_digest == b.composition_receipt_digest

    @pytest.mark.parametrize(
        "varied_field,new_value",
        [
            ("composition_digest", "comp" + "9" * 60),
            ("episode1_final_receipt_digest", "e1f" + "9" * 61),
            ("episode1_ocel_digest", "e1o" + "9" * 61),
            ("episode2_final_receipt_digest", "e2f" + "9" * 61),
            ("episode2_ocel_digest", "e2o" + "9" * 61),
            ("episode1_id", "ep1-different"),
            ("episode2_id", "ep2-different"),
            ("release_id", "release-different"),
        ],
    )
    def test_varying_any_single_field_changes_the_digest(
        self, varied_field: str, new_value: str
    ) -> None:
        """Same `composition_digest` (or any other single shared sub-digest) is not
        enough for two receipts to collide -- every field is load-bearing."""
        baseline = build_composition_receipt(**self._BASE_KWARGS)
        varied_kwargs = dict(self._BASE_KWARGS)
        varied_kwargs[varied_field] = new_value
        varied = build_composition_receipt(**varied_kwargs)
        assert (
            baseline.composition_receipt_digest != varied.composition_receipt_digest
        ), (
            f"varying only {varied_field!r} did not change composition_receipt_digest -- "
            "the digest is not sensitive to this field"
        )

    def test_two_runs_sharing_composition_digest_but_different_episode_receipts_differ(
        self,
    ) -> None:
        """The exact scenario named in this pass's instructions: same
        composition_digest, different episode receipts -> different combined digest."""
        run_a = build_composition_receipt(
            receipt_id="r-a",
            release_id="shared-release",
            composition_digest="shared-comp-digest",
            episode1_id="ep1-a",
            episode1_final_receipt_digest="final-a-1",
            episode1_ocel_digest="ocel-a-1",
            episode2_id="ep2-a",
            episode2_final_receipt_digest="final-a-2",
            episode2_ocel_digest="ocel-a-2",
        )
        run_b = build_composition_receipt(
            receipt_id="r-b",
            release_id="shared-release",
            composition_digest="shared-comp-digest",
            episode1_id="ep1-b",
            episode1_final_receipt_digest="final-b-1",
            episode1_ocel_digest="ocel-b-1",
            episode2_id="ep2-b",
            episode2_final_receipt_digest="final-b-2",
            episode2_ocel_digest="ocel-b-2",
        )
        assert run_a.composition_digest == run_b.composition_digest
        assert run_a.composition_receipt_digest != run_b.composition_receipt_digest

    def test_real_crown_composition_receipt_differs_across_two_independent_runs(
        self, tmp_path: Path
    ) -> None:
        """Full end-to-end version of the same falsifier: two real, independent
        ReleaseRun crown executions against the SAME manifest (same declared
        composition_digest) must still produce DIFFERENT composition_receipt_digest
        values, because each run mints its own fresh episode/receipt/OCEL identity."""
        result_a = _run_crown(tmp_path / "run-a")
        result_b = _run_crown(tmp_path / "run-b")
        assert result_a.state == ReleaseState.CROWNED, result_a.reason
        assert result_b.state == ReleaseState.CROWNED, result_b.reason
        assert (
            result_a.exact_subject.composition_digest
            == result_b.exact_subject.composition_digest
        )
        assert (
            result_a.composition_receipt.composition_receipt_digest
            != result_b.composition_receipt.composition_receipt_digest
        )
