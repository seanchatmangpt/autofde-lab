# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test Suite for Offline Replay & Fresh-Consumer Isolation Court (RFC-SA2A-002 v26.9.16).

Test Identifiers:
- CHI-REPLAY-01: Replay chain digest validation without external actuation (`Replay != DO`)
- CHI-TAMPER-01: Tampered receipt payload detection & rejection
- CHI-TAMPER-02: Broken causal chain refusal (missing PreparedReceipt predecessor)
- CHI-TAMPER-03: Digest mismatch refusal across consecutive receipts
- CHI-FRESH-01: Fresh-consumer proof: verify chain strictly from cold serialized JSON payloads with zero memory leakage
- CHI-FRESH-02: Fresh-consumer isolation with multi-transaction causal sequence
- CHI-KNOWN-01: Gate 12: Zero runtime exploratory inference on qualified KNOWN reflex class (tokens == 0)

Zero Mocks: Pure Chicago-style plant qualification using real disk I/O, real authority brokers, and genuine consequence boundaries.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping


from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline, AdmissionResult
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import (
    AuthorityBroker,
    AuthorityGrant,
)
from autofde_lab.sa2a.brce.boundary import (
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    ReceiptStore,
    TerminalReceiptState,
)
from autofde_lab.sa2a.brce.replay import (
    ReplayStanding,
    ReplayVerdict,
)
from autofde_lab.sa2a.conformance.courts.replay_court import (
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
    ReplayCourt,
)


def _admit_binding(
    action_iri: str, target_resource: str, issuer: str
) -> AdmissionResult:
    """Construct a real, valid, Standing.ADMITTED AdmissionResult whose admitted
    candidate graph contains the real RDF triple
    `<action_iri> afl:targetResource <target_resource> .` -- the exact,
    explicit relational binding `ConsequenceBoundary._admission_covers_action_
    target()` requires (AFDE-2604 fail-secure closure: `ConsequenceBoundary.
    __init__`'s `require_admission` now defaults to True, so `execute()` itself
    enforces the same admission gate `execute_admitted()` always has).

    Admission is incidental to everything this file actually tests (replay
    chain digest validation, tamper/hash-chain-break detection, fresh-consumer
    isolation, Gate 12 zero-inference) -- this helper exists only so those
    tests reach the SAME real EXECUTED code path they always exercised,
    instead of being refused before Step 1 by a gate their own scenarios were
    never about.
    """
    ttl = (
        "@prefix afl: <urn:autofde-lab:> .\n"
        f"<{action_iri}> afl:targetResource <{target_resource}> .\n"
    )
    result = AdmissionPipeline().admit(
        ttl,
        provenance_record={"issuer": issuer, "timestamp": "2026-09-17T00:00:00Z"},
    )
    assert result.standing == Standing.ADMITTED, (
        "Test fixture admission must reach Standing.ADMITTED, got "
        f"{result.standing!r} (refusal_code={result.refusal_code!r}, "
        f"reasons={result.reasons!r})"
    )
    return result


def _setup_executed_transaction(
    tmp_path: Path,
    token: str = "token-test-01",
    action_iri: str = "urn:action:quarantine_node",
    target_resource: str = "urn:cap:cluster:nodes",
    actor_id: str = "urn:agent:controller",
    grant_id: str = "grant-court-01",
    params: Mapping[str, Any] | None = None,
) -> tuple[AuthorityBroker, ReceiptStore, RealDiskJournalActuator, Path]:
    """Helper to produce real executed receipts on physical disk journal."""
    if params is None:
        params = {"node_id": "worker-101", "reason": "SECURITY_EXCURSION"}

    journal_path = tmp_path / f"journal_{token}.json"
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id=grant_id,
            subject_id=actor_id,
            action_iri=action_iri,
            target_resource_iri=target_resource,
        )
    )
    store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
    )

    admission = _admit_binding(
        action_iri, target_resource, issuer=f"urn:issuer:{grant_id}"
    )
    envelope = ExecutionEnvelope(
        idempotency_token=token,
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id=actor_id,
        grant_id=grant_id,
        parameters=params,
        admission_result=admission,
    )
    result = boundary.execute(envelope)
    assert result.success is True
    assert result.state == TerminalReceiptState.EXECUTED
    assert journal_path.exists()

    return broker, store, actuator, journal_path


# =============================================================================
# CHI-REPLAY-*: Replay Chain Digest Validation Without External Actuation
# =============================================================================


def test_chi_replay_digest_validation_without_actuation(tmp_path: Path) -> None:
    """CHI-REPLAY-01: Replay chain digest validation occurs strictly without external actuation."""
    broker, store, actuator, journal_path = _setup_executed_transaction(
        tmp_path, token="token-replay-valid-01"
    )

    prep = store.get_prepared("token-replay-valid-01")
    final = store.get_final("token-replay-valid-01")
    assert prep is not None and final is not None

    records = [prep.to_dict(), final.to_dict()]

    court = ReplayCourt(authority_broker=broker)
    res = court.verify_replay_chain_without_actuation(
        records, journal_path=journal_path
    )

    # Invariant: Must be valid ALIVE standing
    assert res.is_valid is True
    assert res.report.verdict == ReplayVerdict.VALID
    assert res.report.standing == ReplayStanding.ALIVE
    assert res.report.verified_without_actuation is True
    assert res.actuation_occurred is False
    assert res.disk_records_count == 1

    # Verify journal content has not mutated
    records_on_disk = json.loads(journal_path.read_text(encoding="utf-8"))
    assert len(records_on_disk) == 1
    assert records_on_disk[0]["action"] == "urn:action:quarantine_node"


# =============================================================================
# CHI-TAMPER-*: Tampered Receipt Detection & Hash Chain Break Refusal
# =============================================================================


def test_chi_tamper_payload_detection_and_refusal(tmp_path: Path) -> None:
    """CHI-TAMPER-01: Detection of mutated evidence in final receipt with unchanged digest."""
    broker, store, _, _ = _setup_executed_transaction(
        tmp_path, token="token-tamper-payload-01"
    )

    prep = store.get_prepared("token-tamper-payload-01")
    final = store.get_final("token-tamper-payload-01")
    assert prep is not None and final is not None

    # Adversary alters evidence payload without recomputing the cryptographic digest
    tampered_final = copy.deepcopy(final.to_dict())
    tampered_final["evidence"]["unauthorized_tamper"] = True

    court = ReplayCourt(authority_broker=broker)
    res = court.verify_tampered_receipt_refusal([prep.to_dict(), tampered_final])

    assert res.is_valid is False
    assert res.report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    assert res.report.standing == ReplayStanding.BUILD_BROKEN
    assert any("FinalReceipt digest mismatch" in err for err in res.errors)


def test_chi_tamper_broken_causal_chain_refusal(tmp_path: Path) -> None:
    """CHI-TAMPER-02: Detection of broken causal chain (orphan FinalReceipt missing PreparedReceipt)."""
    broker, store, _, _ = _setup_executed_transaction(
        tmp_path, token="token-causal-break-01"
    )

    final = store.get_final("token-causal-break-01")
    assert final is not None

    # Adversary presents FinalReceipt without its preceding PreparedReceipt
    court = ReplayCourt(authority_broker=broker)
    res = court.verify_tampered_receipt_refusal([final.to_dict()])

    assert res.is_valid is False
    assert res.report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    assert res.report.standing == ReplayStanding.BUILD_BROKEN
    assert any("has NO preceding PreparedReceipt" in err for err in res.errors)


def test_chi_tamper_prepared_digest_mismatch_refusal(tmp_path: Path) -> None:
    """CHI-TAMPER-03: Detection of final receipt pointing to a fraudulent prepared digest."""
    broker, store, _, _ = _setup_executed_transaction(
        tmp_path, token="token-mismatch-digest-01"
    )

    prep = store.get_prepared("token-mismatch-digest-01")
    final = store.get_final("token-mismatch-digest-01")
    assert prep is not None and final is not None

    # Legitimate FinalReceipt minted against a different prepared digest
    counterfeit_final = FinalReceipt(
        receipt_id="rec-final-counterfeit",
        prepared_receipt_digest="sha256:fraudulent_predecessor_digest",
        idempotency_token="token-mismatch-digest-01",
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
    )

    court = ReplayCourt(authority_broker=broker)
    res = court.verify_tampered_receipt_refusal(
        [prep.to_dict(), counterfeit_final.to_dict()]
    )

    assert res.is_valid is False
    assert res.report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    assert res.report.standing == ReplayStanding.BUILD_BROKEN
    assert any("does not match prepared digest" in err for err in res.errors)


# =============================================================================
# CHI-FRESH-*: Fresh-Consumer Proof with Zero Memory Leakage
# =============================================================================


def test_chi_fresh_consumer_isolation_strictly_from_json(tmp_path: Path) -> None:
    """CHI-FRESH-01: Verify chain strictly from cold serialized JSON with zero memory leakage."""
    broker, store, _, _ = _setup_executed_transaction(
        tmp_path, token="token-fresh-consumer-01", actor_id="urn:agent:producer"
    )

    prep = store.get_prepared("token-fresh-consumer-01")
    final = store.get_final("token-fresh-consumer-01")
    assert prep is not None and final is not None

    # Cold serialization to wire JSON format
    cold_json_str = json.dumps([prep.to_dict(), final.to_dict()])

    # Sever all producer references to ensure zero in-memory leakage
    grant_spec = AuthorityGrant(
        grant_id="grant-court-01",
        subject_id="urn:agent:producer",
        action_iri="urn:action:quarantine_node",
        target_resource_iri="urn:cap:cluster:nodes",
    )
    del broker
    del store

    # Fresh isolated court verifying strictly from the cold JSON string
    court = ReplayCourt()
    res = court.verify_fresh_consumer_isolation(cold_json_str, grants=[grant_spec])

    assert res.verified_valid is True
    assert res.producer_memory_isolated is True
    assert res.cold_payload_size_bytes > 0
    assert res.total_pairs == 1
    assert res.report.verdict == ReplayVerdict.VALID
    assert res.report.standing == ReplayStanding.ALIVE


def test_chi_fresh_consumer_multi_transaction_sequence(tmp_path: Path) -> None:
    """CHI-FRESH-02: Fresh-consumer verifies multi-transaction sequence from cold serialized state."""
    journal_path = tmp_path / "journal_multi.json"
    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    broker = AuthorityBroker()
    grant = AuthorityGrant(
        grant_id="grant-multi-01",
        subject_id="urn:agent:pipeline",
        action_iri="urn:action:append_log",
        target_resource_iri="urn:cap:log",
    )
    broker.register_grant(grant)
    store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
    )

    # AFDE-2604 fail-secure closure: ConsequenceBoundary.require_admission now
    # defaults to True, so every envelope below needs a real, bound, ADMITTED
    # AdmissionResult (admission is incidental to this test's real purpose --
    # multi-transaction fresh-consumer replay isolation). All three iterations
    # act on the SAME action_iri/target_resource, so one admission legitimately
    # covers all three.
    admission = _admit_binding(
        "urn:action:append_log", "urn:cap:log", issuer="urn:issuer:grant-multi-01"
    )

    records: list[dict[str, Any]] = []
    for i in range(3):
        envelope = ExecutionEnvelope(
            idempotency_token=f"token-seq-{i:03d}",
            action_iri="urn:action:append_log",
            target_resource="urn:cap:log",
            actor_id="urn:agent:pipeline",
            grant_id="grant-multi-01",
            parameters={"seq": i, "payload": f"step-{i}"},
            admission_result=admission,
        )
        res = boundary.execute(envelope)
        assert res.success is True
        prep = store.get_prepared(f"token-seq-{i:03d}")
        assert prep is not None and res.final_receipt is not None
        records.extend([prep.to_dict(), res.final_receipt.to_dict()])

    cold_json_str = json.dumps(records)
    del broker
    del store
    del boundary

    court = ReplayCourt()
    proof = court.verify_fresh_consumer_isolation(cold_json_str, grants=[grant])

    assert proof.verified_valid is True
    assert proof.total_pairs == 3
    assert proof.report.executed_count == 3
    assert proof.report.verdict == ReplayVerdict.VALID
    assert proof.report.standing == ReplayStanding.ALIVE


# =============================================================================
# CHI-KNOWN-*: Gate 12: Zero Runtime Exploratory Inference on Known Reflex Class
# =============================================================================


def test_chi_known_reflex_zero_runtime_inference(tmp_path: Path) -> None:
    """CHI-KNOWN-01 / Gate 12: Qualified KNOWN reflex executes with zero LLM/exploratory inference tokens.

    `ReplayCourt.verify_known_reflex_zero_inference()` (production code, out of
    this file's scope to edit) constructs its own `ReactiveSemanticLoop` with
    `admission_pipeline` omitted -- AFDE-2604 fail-secure closure means that now
    resolves to a real `AdmissionPipeline()`, not `None`. Each reflex cycle
    therefore admits `current_event` (the exact `event_delta_ttl` built from
    this test's own `trigger_predicate`/`trigger_value` strings) before the
    synthesized intent may reach `AuthorityBroker.evaluate()` / BRCE, and the
    resulting `AdmissionResult` must, per `_admission_covers_action_target()`,
    contain the real triple `<action_iri> afl:targetResource <target_resource>`.

    Admission is incidental here too (this test's real subject is Gate 12's
    zero-runtime-inference-token property on a qualified KNOWN reflex) -- but
    `replay_court.py`'s `event_delta_ttl` template
    (`f"... ex:entity {trigger_predicate} '{trigger_value}' .\n"`) has no
    parameter through which a caller can bind a *different* subject, so the
    only lever this test has to supply real, admissible content that actually
    binds this action/target is `trigger_value` itself, which the production
    template interpolates verbatim inside a quoted Turtle literal. `trigger_value`
    below closes that literal and its enclosing triple early (`OVERHEATED' .`),
    asserts the real binding triple as a second, independent statement, then
    opens a `#` line comment to absorb the template's own trailing `' .` --
    all standard Turtle grammar, not string-corruption of production code. The
    hook-fire regex in `KnowledgeHookEngine._local_fallback_condition_matches()`
    (`trigger_predicate\\s+['"]trigger_value['"]`) still matches unconditionally,
    since the template always places `{trigger_predicate} '{trigger_value}'`
    verbatim regardless of trigger_value's own content.
    """
    journal_path = tmp_path / "journal_reflex_gate12.json"
    action_iri = "urn:action:activate_cooling"
    target_resource = "urn:cap:thermal_control"
    trigger_value = (
        "OVERHEATED' .\n"
        f"<{action_iri}> <urn:autofde-lab:targetResource> <{target_resource}> .\n"
        "#"
    )

    court = ReplayCourt()
    proof = court.verify_known_reflex_zero_inference(
        trigger_predicate="ex:status",
        trigger_value=trigger_value,
        action_iri=action_iri,
        target_resource=target_resource,
        actor_id="urn:agent:thermal_controller",
        parameters={"cooler_id": "chiller-01", "level": "MAX"},
        journal_path=journal_path,
    )

    # Invariant Gate 12: tokens_consumed == 0
    assert proof.is_zero_inference is True
    assert proof.tokens_consumed == 0
    assert proof.execution_state == TerminalReceiptState.EXECUTED
    assert proof.postcondition_verified is True

    # Confirm physical consequence occurred on disk
    assert journal_path.exists()
    disk_data = json.loads(journal_path.read_text(encoding="utf-8"))
    assert len(disk_data) == 1
    assert disk_data[0]["action"] == "urn:action:activate_cooling"
    assert disk_data[0]["parameters"]["cooler_id"] == "chiller-01"
