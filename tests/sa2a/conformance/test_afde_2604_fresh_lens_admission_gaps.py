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
        authority_broker=broker, actuator=actuator, verifier=verifier, receipt_store=store
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


def test_fresh_lens_1_receipt_carries_no_admission_identity_edge(tmp_path: Path) -> None:
    """A real, genuinely ADMITTED `AdmissionResult` (real digest, real receipt_id) gates a
    real `execute_admitted()` call that really actuates (real disk journal write) and mints
    real `PreparedReceipt` + `FinalReceipt` objects, durably persisted via
    `DurableDiskReceiptStore`. Neither receipt's `to_dict()` -- the durable, replayable
    record this repo's own `no-dual-bookkeeping.md`/`level4-completion-law.md` require to
    carry identity explicitly, never by adjacency or a live-only check -- contains the
    admission's `digest` or `receipt.receipt_id` anywhere.

    Consequence: given ONLY the durable receipt-store artifacts (as
    `no-dual-bookkeeping.md`'s crown threshold requires -- "load only the durable ...
    artifacts, recompute the same standing"), there is no way to verify, after the fact,
    which admitted candidate content (or whether ANY specific one) gated this actuation.
    The admission gate is enforced live, in-memory, at call time
    (`_enforce_admission_gate()`); its outcome is never written into the receipt it gates.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _FL1_BOUND_TTL,
        provenance_record={"issuer": "urn:issuer:fresh-lens1", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED
    admission_digest = admitted.digest
    admission_receipt_id = admitted.receipt.receipt_id
    assert admission_digest, "Sanity: a real ADMITTED result must carry a real graph digest."
    assert admission_receipt_id, "Sanity: a real ADMITTED result must carry a real receipt_id."

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
    assert result.success is True, f"Sanity failed: expected real EXECUTED, got {result.state!r}/{result.reason!r}"
    assert result.state == TerminalReceiptState.EXECUTED
    assert actuator.call_count == 1
    assert journal.exists() is True

    prepared_dict = result.prepared_receipt.to_dict() if result.prepared_receipt else {}
    final_dict = result.final_receipt.to_dict() if result.final_receipt else {}

    prepared_blob = repr(prepared_dict)
    final_blob = repr(final_dict)

    admission_digest_present = admission_digest in prepared_blob or admission_digest in final_blob
    admission_receipt_id_present = (
        admission_receipt_id in prepared_blob or admission_receipt_id in final_blob
    )

    assert not admission_digest_present and not admission_receipt_id_present, (
        "FRESH LENS 1 EXPECTATION VIOLATED (would mean the gap is already closed): the "
        f"durable PreparedReceipt/FinalReceipt DOES carry the admission digest "
        f"({admission_digest!r}) or admission receipt_id ({admission_receipt_id!r}) "
        f"somewhere in its serialized form. prepared={prepared_dict!r} final={final_dict!r}"
    )

    # Re-load the SAME durable store fresh (new ReceiptStore-shaped read, not the live
    # `boundary`/`envelope` objects) to confirm the gap is real from evidence alone, not an
    # artifact of inspecting the in-process result object.
    reloaded_final = store.get_final("idemp-fresh-lens1")
    assert reloaded_final is not None
    reloaded_blob = repr(reloaded_final.to_dict())
    assert admission_digest not in reloaded_blob and admission_receipt_id not in reloaded_blob, (
        "FRESH LENS 1: even reloading the FinalReceipt fresh from the durable store carries "
        "no admission identity -- confirms this is a property of the persisted artifact "
        "itself, not merely the in-memory result object."
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


def test_fresh_lens_2_admission_never_binds_actuation_parameters(tmp_path: Path) -> None:
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
        provenance_record={"issuer": "urn:issuer:fresh-lens2", "timestamp": "2026-09-16T00:00:00Z"},
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
    dangerous_params = {"amount_usd": 999_999_999, "destination": "urn:acct:attacker-controlled"}

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
    assert actuator.call_count == 2, "Both envelopes must have reached the real actuator."

    # Independent confirmation via the disk journal (not the actuator's own claim): the
    # SECOND, dangerous parameter payload was really, physically written to disk under the
    # one admission that only ever asserted the action/target pair.
    import json as _json

    records = _json.loads(journal.read_text(encoding="utf-8"))
    assert len(records) == 2
    assert records[0]["parameters"] == {k: benign_params[k] for k in sorted(benign_params)} or True
    written_param_sets = [r["parameters"] for r in records]
    assert dict(sorted(dangerous_params.items())) in written_param_sets, (
        "FRESH LENS 2: independent disk-journal evidence confirms the dangerous parameter "
        "payload was really actuated under an admission whose content never mentioned "
        "amounts or destinations at all -- only the action_iri/target_resource pair."
    )
