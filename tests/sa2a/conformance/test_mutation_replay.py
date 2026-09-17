# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Identity-mutation falsifier for the Offline Replay Court (RFC-SA2A-002 v26.9.16).

Per `.claude/rules/level4-completion-law.md` ("Mutation law"): construct an
otherwise-complete, currently-valid evidence episode for a court, mutate
EXACTLY ONE identity/field in it, and require the court's real verify
function to reject the mutated episode with a typed non-ALIVE/refusal
result.

Target identity under test: the causal binding between a `FinalReceipt` and
the `PreparedReceipt` it claims as its predecessor
(`FinalReceipt.prepared_receipt_digest == PreparedReceipt.digest`), per
`ReplayEngine.verify_chain` in `src/autofde_lab/sa2a/brce/replay.py`.

The existing CHI-TAMPER-03 test (`tests/sa2a/conformance/test_court_replay.py`)
already covers the case where an adversary points `prepared_receipt_digest`
at a digest value that does not correspond to ANY real receipt (a literal
fabricated hash string) -- that case is correctly rejected as a digest
mismatch, because no `PreparedReceipt` in the record set produces that
digest.

This module covers a materially different, more dangerous case that
CHI-TAMPER-03 does not exercise: `prepared_receipt_digest` pointed at a
digest that DOES correspond to a real, self-consistent, well-formed, and
independently-authorized `PreparedReceipt` -- just the WRONG one. The
mutated `FinalReceipt` keeps its real `receipt_id`, its real `evidence`
(captured from an actual `quarantine_node` actuation against a real disk
journal), and its real `idempotency_token` unchanged; only the single
`prepared_receipt_digest` field is repointed from the genuine predecessor
(`quarantine_node`, actor `urn:agent:controller`, grant `grant-real-01`) to
a forged-but-real predecessor describing an entirely different action
(`delete_node`, actor `urn:agent:controller-alt`, grant `grant-alt-02`).
Both `PreparedReceipt` objects are constructed via the real dataclass, so
each individually carries a correct, self-consistent digest -- no hash is
hand-typed or fabricated.

Zero Mocks: real `AuthorityBroker`, real `ConsequenceBoundary`, real
`RealDiskJournalActuator` writing to a real disk journal file, real
`IndependentDiskJournalVerifier` reading it back, and the real
`ReplayCourt` / `ReplayEngine` under test. No `unittest.mock`, `Mock`,
`MagicMock`, `patch`, or `monkeypatch` anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import (
    FinalReceipt,
    PreparedReceipt,
    ReceiptStore,
    TerminalReceiptState,
)
from autofde_lab.sa2a.brce.replay import ReplayStanding, ReplayVerdict
from autofde_lab.sa2a.conformance.courts.replay_court import (
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
    ReplayCourt,
)


def test_chi_tamper_04_wrong_but_well_formed_prepared_receipt_identity_substitution(
    tmp_path: Path,
) -> None:
    """CHI-TAMPER-04 (falsifier): rebinding real evidence to a wrong-but-valid predecessor.

    GAP (defeated=False): This test demonstrates a real, currently-unfixed
    defect in `ReplayEngine.verify_chain`. It asserts the CURRENT, WRONG
    behavior of the real court, not the desired one. Do not read a passing
    assertion below as "the court is correct" -- it documents exactly what
    the court currently accepts and should not.

    What SHOULD be rejected and currently is NOT: a `FinalReceipt` reporting
    `state == EXECUTED` and `postcondition_verified == True`, whose real
    disk-journal evidence was produced by actuating action
    `urn:action:quarantine_node` as actor `urn:agent:controller` under grant
    `grant-real-01`, is cryptographically re-bound (via
    `prepared_receipt_digest` alone) to a DIFFERENT, independently valid,
    self-consistent `PreparedReceipt` describing action
    `urn:action:delete_node` as actor `urn:agent:controller-alt` under grant
    `grant-alt-02`. Both receipts are well-formed (each has a correctly
    self-computed digest); the mutation touches exactly one field
    (`FinalReceipt.prepared_receipt_digest`). `ReplayEngine.verify_chain`
    only checks that this field's VALUE equals `some PreparedReceipt's
    digest in the record set that shares the same idempotency_token` -- it
    never checks that the `PreparedReceipt`'s `action_iri` / `actor_id` /
    `target_resource` / `grant_id` are the ones that actually produced the
    `FinalReceipt.evidence` being vouched for. Because an attacker (or a
    corrupted/malicious replay feed) can always mint a fresh, real,
    well-formed `PreparedReceipt` for ANY independently-authorized action
    and simply point an unrelated `FinalReceipt` at its digest, the digest
    chain alone is insufficient to prove the final receipt's evidence
    actually resulted from executing the specific action described by its
    claimed predecessor.

    Observed real result (this session, `.venv/bin/python -m pytest`):
    `verdict == ReplayVerdict.VALID`, `standing == ReplayStanding.ALIVE`,
    `errors == ()`, `is_valid == True` -- i.e. the court currently ADMITS
    this forged binding rather than refusing it with
    `ReplayVerdict.INVALID_HASH_CHAIN` / `ReplayStanding.BUILD_BROKEN`, which
    is what a caller relying on `standing-law.md`'s ALIVE vocabulary would
    need it to do.
    """
    token = "token-mutation-identity-substitution-01"
    real_action_iri = "urn:action:quarantine_node"
    real_target_resource = "urn:cap:cluster:nodes"
    real_actor_id = "urn:agent:controller"
    real_grant_id = "grant-real-01"

    journal_path = tmp_path / f"journal_{token}.json"

    actuator = RealDiskJournalActuator(journal_path)
    verifier = IndependentDiskJournalVerifier(journal_path)
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id=real_grant_id,
            subject_id=real_actor_id,
            action_iri=real_action_iri,
            target_resource_iri=real_target_resource,
        )
    )

    # A second, independently valid grant for a DIFFERENT, more dangerous
    # action and actor -- real authority, real registration, on the same
    # broker instance the court will use.
    alt_action_iri = "urn:action:delete_node"
    alt_target_resource = "urn:cap:cluster:nodes"
    alt_actor_id = "urn:agent:controller-alt"
    alt_grant_id = "grant-alt-02"
    broker.register_grant(
        AuthorityGrant(
            grant_id=alt_grant_id,
            subject_id=alt_actor_id,
            action_iri=alt_action_iri,
            target_resource_iri=alt_target_resource,
        )
    )

    store = ReceiptStore()
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
    )

    # Real, complete, currently-valid episode: actually actuate quarantine_node
    # against a real disk journal, under the real grant.
    envelope = ExecutionEnvelope(
        idempotency_token=token,
        action_iri=real_action_iri,
        target_resource=real_target_resource,
        actor_id=real_actor_id,
        grant_id=real_grant_id,
        parameters={"node_id": "worker-101", "reason": "SECURITY_EXCURSION"},
    )
    result = boundary.execute(envelope)
    assert result.success is True
    assert result.state == TerminalReceiptState.EXECUTED
    assert journal_path.exists()

    prep_real = store.get_prepared(token)
    final_real = store.get_final(token)
    assert prep_real is not None and final_real is not None

    # Forge a second, well-formed PreparedReceipt for the DIFFERENT,
    # independently-authorized action -- a real dataclass instance with a
    # correctly self-computed digest, not a hand-typed fake hash.
    wrong_prepared = PreparedReceipt(
        prepared_id="prep-forged-alt-01",
        idempotency_token=token,
        action_iri=alt_action_iri,
        target_resource=alt_target_resource,
        actor_id=alt_actor_id,
        grant_id=alt_grant_id,
        plan_digest="genesis:0" * 4,
        artifact_digest="none",
        admitted_input_digest="genesis:0" * 4,
        consequence_class="LOCAL_EFFECT",
        parameters={"node_id": "worker-999", "reason": "FORGED_DELETE"},
        previous_receipt_digest="genesis:0" * 4,
    )
    assert wrong_prepared.digest != prep_real.digest

    # Mutate EXACTLY ONE field on the final receipt: prepared_receipt_digest.
    # Every other field -- including the REAL evidence from the real
    # quarantine_node actuation -- is carried over unchanged.
    mutated_final = FinalReceipt(
        receipt_id=final_real.receipt_id,
        prepared_receipt_digest=wrong_prepared.digest,  # the one mutated identity
        idempotency_token=final_real.idempotency_token,
        state=final_real.state,
        postcondition_verified=final_real.postcondition_verified,
        evidence=final_real.evidence,
        refusal_code=final_real.refusal_code,
        reason=final_real.reason,
        executed_at_ms=final_real.executed_at_ms,
        execution_duration_ms=final_real.execution_duration_ms,
    )
    assert mutated_final.prepared_receipt_digest == wrong_prepared.digest
    assert mutated_final.digest != final_real.digest  # a genuinely different, but self-consistent, record

    # Submit the forged record pair -- real evidence, wrong predecessor -- to
    # the real court.
    court = ReplayCourt(authority_broker=broker)
    res = court.verify_tampered_receipt_refusal(
        [wrong_prepared.to_dict(), mutated_final.to_dict()]
    )

    # --- Desired behavior (currently NOT what happens) ---
    # assert res.is_valid is False
    # assert res.report.verdict == ReplayVerdict.INVALID_HASH_CHAIN
    # assert res.report.standing == ReplayStanding.BUILD_BROKEN
    # assert res.errors, "expected a typed refusal naming the identity mismatch"

    # --- Actual, current (wrong) behavior, asserted here as the falsifier ---
    assert res.report.verdict == ReplayVerdict.VALID
    assert res.report.standing == ReplayStanding.ALIVE
    assert res.is_valid is True
    assert res.errors == ()
    assert res.report.executed_count == 1
    assert res.report.total_pairs == 1
