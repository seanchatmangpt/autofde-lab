"""Tests for Novelty Ingestion from production typed refusals."""

from __future__ import annotations

import pytest
from autofde_lab.sa2a.brce.receipts import FinalReceipt, TerminalReceiptState
from autofde_lab.sa2a.unknown.allocator import UnknownCandidate
from autofde_lab.sa2a.unknown.novelty_ingest import NoveltyIngestionGateway


def test_novelty_ingestion_from_refusal_receipt():
    gateway = NoveltyIngestionGateway()
    refusal_receipt = FinalReceipt(
        receipt_id="rec-refused-test-01",
        prepared_receipt_digest="prep-digest-123",
        idempotency_token="idemp-novelty-1",
        state=TerminalReceiptState.REFUSED,
        postcondition_verified=False,
        refusal_code="REFUSED_NO_GRANT",
        reason="No authority grant for action urn:action:restart_pod",
        evidence={"pod_name": "worker-42", "node": "k8s-node-3"},
    )

    candidate = gateway.ingest_refusal_receipt(
        refusal_receipt,
        action_iri="urn:action:restart_pod",
        target_resource="urn:cap:cluster:pods",
        observed_state_ttl="@prefix ex: <http://example.org/> . ex:pod ex:status 'CRASH_LOOP' .",
    )

    assert isinstance(candidate, UnknownCandidate)
    assert candidate.item_id.startswith("novelty-")
    assert candidate.option_entropy >= 1.0
    assert candidate.metadata is not None
    assert candidate.metadata["refusal_code"] == "REFUSED_NO_GRANT"
    assert candidate.metadata["action_iri"] == "urn:action:restart_pod"
    assert candidate.metadata["parameters"]["pod_name"] == "worker-42"


def test_novelty_ingestion_rejects_non_refused_receipt():
    gateway = NoveltyIngestionGateway()
    executed_receipt = FinalReceipt(
        receipt_id="rec-exec-test-02",
        prepared_receipt_digest="prep-digest-456",
        idempotency_token="idemp-ok",
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
    )

    with pytest.raises(ValueError, match="Only REFUSED receipts represent novelty"):
        gateway.ingest_refusal_receipt(executed_receipt)
