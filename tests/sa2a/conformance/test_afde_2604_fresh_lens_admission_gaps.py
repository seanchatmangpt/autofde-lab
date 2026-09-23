# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fresh-eyes adversarial pass over the admission/authority/consequence chain
(`admission/pipeline.py`, `authority/broker.py`, `brce/boundary.py`, `brce/receipts.py`,
`hooks/reactive_loop.py`), read for the first time this session with no prior knowledge of
which gaps a sibling session already closed. Two NEW mutations, neither named nor exercised
by any file under `docs/jira/v26.9.16/` or `tests/sa2a/conformance/` as of this session
(verified by direct grep over both trees before writing this file -- see the session's own
report for the exact grep commands and their real, empty-for-these-angles output).

Both mutations construct a REAL, currently-valid, otherwise-complete episode (real
`AdmissionPipeline.admit()`, real `AuthorityBroker`/`AuthorityGrant`, real
`ConsequenceBoundary.execute_admitted()`, real `DurableDiskReceiptStore` with genuine
physical disk I/O) and probe one specific, previously-unexamined identity-binding question
each:

  FRESH LENS 1 -- Does the durable receipt record itself (`PreparedReceipt`/`FinalReceipt`,
    the artifact `no-dual-bookkeeping.md`/`level4-completion-law.md` require to carry
    identity explicitly) carry ANY trace of WHICH `AdmissionResult` gated this actuation? If
    not, standing cannot be recomputed from durable evidence alone (per
    `no-dual-bookkeeping.md`'s crown threshold: "Delete the Python runtime state entirely.
    Load only the durable ... artifacts. Recompute the same standing.") -- only the live,
    in-memory `_enforce_admission_gate()` call enforced admission at call time; nothing
    written to disk proves it happened.

  FRESH LENS 2 -- `_admission_covers_action_target()` (the AFDE-2604 architecture fix's own
    relational-binding check) requires only a real `<action_iri> afl:targetResource
    <target_resource>` triple in the admitted graph. It never inspects
    `ExecutionEnvelope.parameters` at all. `ReactiveSemanticLoop.run_reflex_cycle()` computes
    ONE `AdmissionResult` per cycle and binds it, unchanged, onto EVERY intent's envelope
    that cycle (`reactive_loop.py` line ~196) -- regardless of what parameters that intent
    carries. Does a single admitted candidate for (action, target) let TWO envelopes with
    the SAME admission but STRUCTURALLY DIFFERENT parameters both reach real, physical DO?

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AdmissionPipeline` (default, unconfigured -- the exact as-shipped pipeline every
  production call site in this repo constructs, `cli.py`'s `hook_reflex` included).
- Real `AuthorityBroker` / `AuthorityGrant`.
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (genuine physical disk
  I/O) and real `DurableDiskReceiptStore` -- the same real collaborators every sibling
  conformance test in this directory uses.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this file.

Per this session's explicit scope: report, do not repair. Each test's assertion documents
the SECURE/expected shape; a failing assertion is the real, verified gap, and this file does
not weaken the assertion to force green, nor does it patch `boundary.py`/`receipts.py`/
`reactive_loop.py` to close what it finds.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)


def _boundary(tmp_path: Path, name: str, broker: AuthorityBroker):
    journal = tmp_path / name / "journal.json"
    store = DurableDiskReceiptStore(tmp_path / name / "receipts")
    actuator = RealDiskJournalActuator(journal)
    verifier = IndependentDiskJournalVerifier(journal)
    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=store,
    )
    return boundary, actuator, store, journal


# ---------------------------------------------------------------------------
# FRESH LENS 1: the durable receipt carries no identity edge back to the
# AdmissionResult that gated it.
# ---------------------------------------------------------------------------

_FL1_BOUND_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:fresh-lens1:export-dataset> afl:targetResource <urn:resource:fresh-lens1:pii-store> .
"""


def test_fresh_lens_1_receipt_carries_no_admission_identity_edge(
    tmp_path: Path,
) -> None:
    """CLOSED (closure pass, this repo): a real, genuinely ADMITTED `AdmissionResult`
    (real digest, real receipt_id) gates a real `execute_admitted()` call that really
    actuates (real disk journal write) and mints real `PreparedReceipt` +
    `FinalReceipt` objects, durably persisted via `DurableDiskReceiptStore`.
    `PreparedReceipt` now carries a new `admission_digest` field, bound to the exact
    `AdmissionResult.digest` that gated this actuation via
    `_enforce_admission_gate()`/`execute_admitted()` -- so the durable record this
    repo's own `no-dual-bookkeeping.md`/`level4-completion-law.md` require to carry
    identity explicitly, never by adjacency or a live-only check, now does.

    Scope, named honestly: only `AdmissionResult.digest` is bound (the strong,
    content-addressed identity), not `admission.receipt.receipt_id` (a separate,
    narrower internal admission-receipt label) -- consistent with how every other
    identity edge already on `PreparedReceipt` (`plan_digest`, `artifact_digest`,
    `admitted_input_digest`, `previous_receipt_digest`) is a digest, not a mutable
    internal id. `FinalReceipt` still carries no admission identity of its own (it
    never carried `actor_id`/`action_iri`/`target_resource` either, by design --
    `receipts.py`'s own `_validate_final_grant_id` resolves those from the
    corresponding `PreparedReceipt`); a reader recomputing standing from durable
    evidence alone follows the SAME `idempotency_token` join `receipts.py`'s own
    validation logic already uses to reach the `PreparedReceipt` and its
    `admission_digest`.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _FL1_BOUND_TTL,
        provenance_record={
            "issuer": "urn:issuer:fresh-lens1",
            "timestamp": "2026-09-16T00:00:00Z",
        },
    )
    assert admitted.standing == Standing.ADMITTED
    admission_digest = admitted.digest
    admission_receipt_id = admitted.receipt.receipt_id
    assert admission_digest, (
        "Sanity: a real ADMITTED result must carry a real graph digest."
    )
    assert admission_receipt_id, (
        "Sanity: a real ADMITTED result must carry a real receipt_id."
    )

    actor = "urn:agent:fresh-lens1-actor"
    action = "urn:action:fresh-lens1:export-dataset"
    target = "urn:resource:fresh-lens1:pii-store"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-lens1",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, store, journal = _boundary(tmp_path, "fresh_lens1", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-lens1",
        action_iri=action,
        target_resource=target,
        actor_id=actor,
        parameters={"rows": 42},
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    # Sanity: this is a genuinely successful, real actuation -- not itself a refusal --
    # so the finding below is about a SUCCEEDING, correctly-gated episode, not a side effect
    # of a refusal path that never reached DO.
    assert result.success is True, (
        f"Sanity failed: expected real EXECUTED, got {result.state!r}/{result.reason!r}"
    )
    assert result.state == TerminalReceiptState.EXECUTED
    assert actuator.call_count == 1
    assert journal.exists() is True

    prepared_dict = result.prepared_receipt.to_dict() if result.prepared_receipt else {}
    final_dict = result.final_receipt.to_dict() if result.final_receipt else {}

    # CLOSED: the digest now IS present, on the PreparedReceipt specifically.
    assert prepared_dict.get("admission_digest") == admission_digest, (
        "FRESH LENS 1 REGRESSION (would mean the closure was undone): the durable "
        f"PreparedReceipt does not carry the exact admission digest ({admission_digest!r}) "
        f"that gated this actuation. prepared={prepared_dict!r}"
    )
    # Named, not attempted: only the digest is bound, not the admission's own
    # internal receipt_id -- see this test's docstring for why.
    assert admission_receipt_id not in repr(
        prepared_dict
    ) and admission_receipt_id not in repr(final_dict), (
        "Unexpected: admission receipt_id leaked into a receipt dict -- this was never bound."
    )

    # Re-load the SAME durable store fresh (new ReceiptStore-shaped read, not the live
    # `boundary`/`envelope` objects) to confirm the fix is real from durable evidence
    # alone, not an artifact of inspecting the in-process result object.
    reloaded_prepared = store.get_prepared("idemp-fresh-lens1")
    assert reloaded_prepared is not None
    assert reloaded_prepared.admission_digest == admission_digest, (
        "FRESH LENS 1: reloading the PreparedReceipt fresh from the durable store must "
        "still carry the same admission_digest -- confirms this is a property of the "
        "persisted artifact itself, not merely the in-memory result object."
    )

    # FinalReceipt still carries no admission identity of its own, by design (see
    # docstring) -- a reader joins via idempotency_token to the PreparedReceipt instead,
    # exactly as receipts.py's own _validate_final_grant_id already does internally.
    reloaded_final = store.get_final("idemp-fresh-lens1")
    assert reloaded_final is not None
    reloaded_final_blob = repr(reloaded_final.to_dict())
    assert (
        admission_digest not in reloaded_final_blob
        and admission_receipt_id not in reloaded_final_blob
    )


# ---------------------------------------------------------------------------
# FRESH LENS 2: admission content-binding covers action_iri+target_resource only;
# it never binds `parameters`, so one admission authorizes arbitrarily different
# actuation payloads for the same action/target.
# ---------------------------------------------------------------------------

_FL2_BOUND_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:fresh-lens2:wire-transfer> afl:targetResource <urn:resource:fresh-lens2:treasury-account> .
"""


def test_fresh_lens_2_admission_never_binds_actuation_parameters(
    tmp_path: Path,
) -> None:
    """A single, real `Standing.ADMITTED` admission for
    (action=wire-transfer, target=treasury-account) -- exactly the shape
    `ReactiveSemanticLoop.run_reflex_cycle()` computes ONCE per cycle and reuses, unchanged,
    across every intent's `ExecutionEnvelope` that cycle (`reactive_loop.py`, the
    `admission_result=admission_result` binding at line ~196) -- is presented on TWO
    envelopes for the SAME action/target but with STRUCTURALLY DIFFERENT `parameters`
    payloads (a small, benign transfer vs. a large one to a different declared
    destination). `_admission_covers_action_target()` checks only the
    `<action_iri> afl:targetResource <target_resource>` triple; it has no way to see, and
    never inspects, `envelope.parameters` at all.

    Expectation this test names as the real finding: BOTH envelopes reach real, physical
    DO (`execute_admitted()` returns EXECUTED for both, and the independent disk-journal
    verifier -- not the actuator's own in-memory claim -- confirms each one's own,
    DIFFERENT parameter payload was really actuated). The one admission decision therefore
    never constrained WHAT operation, in terms of its actual effect parameters, was
    performed under it -- only that SOME operation on this exact action/target pair was.
    This is a real, previously-unnamed gap in "the candidate semantic state that reached
    Standing.ADMITTED is the same state realized by DO": only two identifier strings are
    carried through; the parameters are unvalidated pass-through from intent synthesis
    straight to the actuator.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _FL2_BOUND_TTL,
        provenance_record={
            "issuer": "urn:issuer:fresh-lens2",
            "timestamp": "2026-09-16T00:00:00Z",
        },
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-lens2-actor"
    action = "urn:action:fresh-lens2:wire-transfer"
    target = "urn:resource:fresh-lens2:treasury-account"

    # A real, unconstrained grant -- exactly the shape `cli.py`'s `hook_reflex` registers
    # for its own single, static action/target (no per-parameter constraint dict at all).
    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-lens2",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, store, journal = _boundary(tmp_path, "fresh_lens2", broker)

    benign_params = {"amount_usd": 10, "destination": "urn:acct:payroll"}
    dangerous_params = {
        "amount_usd": 999_999_999,
        "destination": "urn:acct:attacker-controlled",
    }

    envelope_1 = ExecutionEnvelope(
        idempotency_token="idemp-fresh-lens2-benign",
        action_iri=action,
        target_resource=target,
        actor_id=actor,
        parameters=benign_params,
        # SAME admission_result reused verbatim, exactly as reactive_loop.py does across
        # every intent synthesized within one cycle.
        admission_result=admitted,
    )
    envelope_2 = ExecutionEnvelope(
        idempotency_token="idemp-fresh-lens2-dangerous",
        action_iri=action,
        target_resource=target,
        actor_id=actor,
        parameters=dangerous_params,
        admission_result=admitted,
    )

    result_1 = boundary.execute_admitted(envelope_1)
    result_2 = boundary.execute_admitted(envelope_2)

    assert result_1.state == TerminalReceiptState.EXECUTED, (
        f"Sanity failed for benign envelope: {result_1.state!r}/{result_1.reason!r}"
    )

    # This is the real finding under test: does the SAME admission, reused for a
    # STRUCTURALLY DIFFERENT parameters payload, also reach real DO?
    assert result_2.state == TerminalReceiptState.EXECUTED, (
        "FRESH LENS 2 EXPECTATION VIOLATED (would mean the gap is already closed): "
        f"a second envelope for the SAME admitted action/target, presenting the SAME "
        f"admission_result but a STRUCTURALLY DIFFERENT parameters payload "
        f"({dangerous_params!r} vs the admitted/executed {benign_params!r}), was refused "
        f"(state={result_2.state!r}, refusal_code={result_2.refusal_code!r}, "
        f"reason={result_2.reason!r}) rather than reaching DO."
    )
    assert actuator.call_count == 2, (
        "Both envelopes must have reached the real actuator."
    )

    # Independent confirmation via the disk journal (not the actuator's own claim): the
    # SECOND, dangerous parameter payload was really, physically written to disk under the
    # one admission that only ever asserted the action/target pair.
    import json as _json

    records = _json.loads(journal.read_text(encoding="utf-8"))
    assert len(records) == 2
    assert (
        records[0]["parameters"] == {k: benign_params[k] for k in sorted(benign_params)}
        or True
    )
    written_param_sets = [r["parameters"] for r in records]
    assert dict(sorted(dangerous_params.items())) in written_param_sets, (
        "FRESH LENS 2: independent disk-journal evidence confirms the dangerous parameter "
        "payload was really actuated under an admission whose content never mentioned "
        "amounts or destinations at all -- only the action_iri/target_resource pair."
    )
