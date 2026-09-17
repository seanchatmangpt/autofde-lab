# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fresh adversarial falsifiers against the AFDE-2604 local admission-fencing closure
(`src/autofde_lab/sa2a/brce/boundary.py`, `src/autofde_lab/sa2a/hooks/reactive_loop.py`),
written by an independent qualification pass per `.claude/rules/level4-completion-law.md`'s
Mutation law: for every required relation, construct an otherwise-complete, currently-valid
episode and mutate exactly one identity/field, expecting refusal.

These are DELIBERATELY DIFFERENT mutations from the ones the fixing session's own tests
(`test_afde_2604_admission_fencing_closure.py`, `test_afde_2604_boundary_fences.py`,
`test_mutation_consequence.py`, `test_mutation_cross_court_identity.py`) already exercise:

  MUTATION A -- content-unbound admission reuse: a real, genuinely `Standing.ADMITTED`
    `AdmissionResult` produced by admitting one (harmless) candidate graph is reused
    VERBATIM on an `ExecutionEnvelope` for a completely unrelated, more sensitive
    action/target that the admitted candidate's content never mentioned at all. Neither
    `ExecutionEnvelope.admission_result` nor `ConsequenceBoundary.execute_admitted()`
    binds the admitted graph's digest/content to the actuated `action_iri`/
    `target_resource` -- `execute_admitted()` checks only `admission.standing`.

  MUTATION B -- cross-action idempotency-token substitution: the SAME actor, holding
    valid, independent grants for TWO DIFFERENT actions, executes action1 under token T
    (real actuation, real receipt), then replays the SAME token T with action2/target2
    substituted in. The AFDE-2604 fix's Step 1 re-authorization check evaluates authority
    for action2/target2 (correctly, and it is authorized) -- but then returns the STALE
    `existing_final` receipt that was minted for action1, with `success=True`, WITHOUT
    ever actuating action2. The returned receipt's identity (action1) does not match the
    request's identity (action2) -- a `no-dual-bookkeeping.md` object-identity violation.

  MUTATION C -- admission fence bypass via already-executed token replay: a token is
    first executed through `execute_admitted()` with a real ADMITTED admission_result
    (genuine actuation). The SAME token is then replayed through `execute_admitted()`
    a second time with `admission_result=None` (no admission presented at all this
    time). Because `execute_admitted()` only checks admission when
    `receipt_store.get_final(token) is None`, and a final receipt now exists from the
    first call, the admission gate is skipped entirely on the second call and control
    falls straight through to `execute()`'s replay path, which re-authorizes and
    returns `success=True` -- so the "strict, admission-gated entry point" does not, in
    fact, require admission on every call through it, only the first.

Chicago Zero-Mock Standard (per `.claude/rules/testing-chicago-style.md`):
- Real `AuthorityBroker` / `AuthorityGrant` / real `AdmissionPipeline.admit()`.
- Real `RealDiskJournalActuator` / `IndependentDiskJournalVerifier` (genuine physical
  disk I/O) and a real `DurableDiskReceiptStore`, the same real collaborators the
  fixing session's own tests use.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
  file.

Each test below asserts the SECURE/expected outcome (refusal, or an actuation-identity
match). A PASS means the fix genuinely defeats that mutation. A FAIL is the real,
verified gap -- the assertion failure message and the real disk/receipt state are the
falsifying evidence, and this file does not weaken the assertion to make the test green.

RESULT (this session's fix pass over `src/autofde_lab/sa2a/brce/boundary.py`; see
`docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md`'s closure update for
the full account): all three mutations are now DEFEATED = TRUE.

  MUTATION A -- FIXED via a new module-level helper,
    `_admission_covers_action_target(admission, action_iri, target_resource)`, called
    from `ConsequenceBoundary.execute_admitted()` whenever `admission.standing ==
    Standing.ADMITTED`: the admitted candidate graph itself (`AdmissionResult.graph`,
    the real rdflib.Graph that reached ADMITTED) must contain BOTH `action_iri` and
    `target_resource` as real RDF nodes, or the call is refused with the new typed code
    `REFUSED_ADMISSION_CONTENT_NOT_BOUND` -- before `AuthorityBroker.evaluate()` or
    actuation are ever reached. Binding is derived from the admitted CONTENT, never
    from a self-asserted field on the envelope (which an adversary controls exactly as
    freely as a legitimate caller), per `.claude/rules/no-dual-bookkeeping.md`.

  MUTATION B -- FIXED inside `ConsequenceBoundary.execute()` Step 1's
    `existing_final.state == TerminalReceiptState.EXECUTED` branch: BEFORE the existing
    fix-(2)/(3) re-authorization check, the token's bound identity (the `action_iri`/
    `target_resource` recorded on the `PreparedReceipt` minted at this token's first
    EXECUTED write -- always minted before actuation, per Step 4) is compared against
    the REPLAYING envelope's own `action_iri`/`target_resource`. A mismatch refuses,
    with the new typed code `REFUSED_TOKEN_ACTION_MISMATCH`, WITHOUT ever asking
    whether the substituted identity happens to be independently authorized -- an
    idempotency token identifies one fixed actuation identity, never a menu of
    identities the replaying request may swap in after the fact.

  MUTATION C -- FIXED by restructuring `ConsequenceBoundary.execute_admitted()` so the
    admission gate (both the `Standing.ADMITTED` check AND the new Mutation-A content
    check) is evaluated on EVERY call through this entry point, unconditionally --
    never skipped merely because `receipt_store.get_final(token)` already returns a
    final receipt from an earlier, genuinely admitted call. When the gate fails on a
    call made AFTER a final receipt already exists under the token, a deterministic,
    NON-persisted typed refusal is returned (mirroring `execute()`'s own
    non-persisted-mismatch-receipt pattern) rather than corrupting or skipping past the
    token's existing durable record.

Fixture note: Mutation C's own candidate content was changed from the byte-identical
`_HARMLESS_ADMITTABLE_TTL` used by Mutation A to a new, dedicated `_MUT_C_BOUND_TTL`
that explicitly references Mutation C's own action/target -- necessary so that Mutation
C's FIRST call (a deliberately legitimate, content-bound admission) is not itself
refused by the NEW Mutation-A content-binding check, keeping the two fixes' concerns
cleanly isolated: Mutation C's mutation is specifically "does the SECOND call still
require admission," not "is the admission content-bound," which Mutation A already
covers on its own dedicated (deliberately unbound) fixture. This is a fixture
adaptation to the tightened contract, not a weakening of the mutation itself -- the
adversarial construction (replay with `admission_result=None`) is unchanged.
"""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import (
    REFUSED_ADMISSION_CONTENT_NOT_BOUND,
    REFUSED_NOT_ADMITTED,
    REFUSED_TOKEN_ACTION_MISMATCH,
    ConsequenceBoundary,
    ExecutionEnvelope,
)
from autofde_lab.sa2a.brce.receipts import TerminalReceiptState
from autofde_lab.sa2a.conformance.courts.consequence_court import (
    DurableDiskReceiptStore,
    IndependentDiskJournalVerifier,
    RealDiskJournalActuator,
)

_HARMLESS_ADMITTABLE_TTL = """
@prefix afl: <urn:autofde-lab:> .
afl:fresh_mut_harmless_log_sync a afl:Action .
"""

# AFDE-2604 fresh-mutations closure (Mutation C fixture adaptation, this session):
# dedicated, content-bound candidate for Mutation C's legitimate first call -- see the
# module docstring's "Fixture note" for why this is distinct from
# `_HARMLESS_ADMITTABLE_TTL`. It literally references Mutation C's own action/target so
# the NEW Mutation-A content-binding check (`_admission_covers_action_target()`) passes
# for this legitimate use, isolating Mutation C's own concern (admission checked on
# every call, not just the first).
_MUT_C_BOUND_TTL = """
@prefix afl: <urn:autofde-lab:> .
<urn:action:fresh-mut-c:sync> a afl:Action ;
    afl:targetResource <urn:resource:fresh-mut-c:target> .
"""


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
# Mutation A: content-unbound admission reuse.
# ---------------------------------------------------------------------------


def test_mutation_a_admission_content_not_bound_to_actuated_action_target(tmp_path: Path) -> None:
    """A real ADMITTED AdmissionResult for a harmless, unrelated candidate must not
    authorize execution of a completely different, more sensitive action/target that
    the admitted candidate never described.

    FIXED (this session): `ConsequenceBoundary.execute_admitted()` now calls
    `_admission_covers_action_target()`, which inspects the admitted candidate's own
    RDF graph (`AdmissionResult.graph`) for the exact `action_iri`/`target_resource`
    nodes being executed. `_HARMLESS_ADMITTABLE_TTL` mentions neither
    `sensitive_action` nor `sensitive_target` (it is deliberately unrelated content,
    unchanged from the original mutation), so the check fails and the call is refused
    with the new typed code `REFUSED_ADMISSION_CONTENT_NOT_BOUND` -- before
    `AuthorityBroker.evaluate()` or actuation are ever reached. DEFEATED = TRUE.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _HARMLESS_ADMITTABLE_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    sensitive_actor = "urn:agent:fresh-mut-a-actor"
    sensitive_action = "urn:action:fresh-mut-a:delete-all-records"
    sensitive_target = "urn:resource:fresh-mut-a:critical-database"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-a",
            subject_id=sensitive_actor,
            action_iri=sensitive_action,
            target_resource_iri=sensitive_target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_a", broker)

    envelope = ExecutionEnvelope(
        idempotency_token="idemp-fresh-mut-a",
        action_iri=sensitive_action,
        target_resource=sensitive_target,
        actor_id=sensitive_actor,
        # MUTATION: an admission_result that is genuinely Standing.ADMITTED, but for a
        # candidate whose content has nothing to do with this action/target.
        admission_result=admitted,
    )
    result = boundary.execute_admitted(envelope)

    assert result.success is False, (
        "MUTATION A SURVIVED: execute_admitted() allowed a sensitive, unrelated "
        f"action ({sensitive_action!r} on {sensitive_target!r}) to actuate merely "
        "because SOME unrelated candidate reached Standing.ADMITTED -- "
        "ExecutionEnvelope.admission_result carries no content/digest binding to the "
        f"actuated action_iri/target_resource. actuator.call_count={actuator.call_count}, "
        f"journal_exists={journal.exists()}, final_receipt_state="
        f"{result.final_receipt.state if result.final_receipt else None!r}."
    )
    assert result.state == TerminalReceiptState.REFUSED
    assert result.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND, (
        f"Expected the precise Mutation-A refusal code, got {result.refusal_code!r}: "
        f"{result.reason}"
    )
    assert actuator.call_count == 0, "Zero real actuation for a content-unbound admission."
    assert journal.exists() is False, "Zero disk mutation for a content-unbound admission."
    assert result.final_receipt is not None
    assert result.final_receipt.refusal_code == REFUSED_ADMISSION_CONTENT_NOT_BOUND


# ---------------------------------------------------------------------------
# Mutation B: cross-action idempotency-token substitution.
# ---------------------------------------------------------------------------


def test_mutation_b_replay_reauthorized_for_different_action_returns_stale_receipt(
    tmp_path: Path,
) -> None:
    """The SAME actor, independently and validly granted for TWO DIFFERENT actions,
    executes action1 under token T, then replays token T with action2/target2
    substituted in. Fix (2)/(3)'s reauthorization check evaluates authority for
    action2/target2 (and it IS authorized) -- but the returned final_receipt/evidence
    must correspond to a REAL actuation of action2, not a stale receipt minted for
    action1.

    FIXED (this session): `ConsequenceBoundary.execute()` Step 1's
    `existing_final.state == TerminalReceiptState.EXECUTED` branch now compares the
    REPLAYING envelope's `action_iri`/`target_resource` against the ones bound to this
    token at its first EXECUTED write (recorded on the `PreparedReceipt` minted at that
    first call). action2/target2 differ from the token's bound action1/target1, so the
    replay is refused with the new typed code `REFUSED_TOKEN_ACTION_MISMATCH` --
    BEFORE the reauthorization check even runs, regardless of action2 being
    independently, validly authorized. DEFEATED = TRUE: the caller never receives
    action1's stale receipt for an action2 request, and action2 is never actuated
    either.

    AFDE-2604 fail-secure closure (this session, `ConsequenceBoundary.__init__`'s
    `require_admission` default flipped False -> True): `_boundary()` no longer passes
    `require_admission` explicitly, so BOTH `execute()` calls below now also run
    through `_enforce_admission_gate()` first. Admission is incidental to what this
    mutation actually probes (token/action-identity binding, not the admission fence
    itself -- see Mutation A/C in this same file for that), so both envelopes below
    are wired with a real, `Standing.ADMITTED` `AdmissionResult` whose admitted
    content explicitly, relationally binds ITS OWN action/target (action1/target1 for
    the first call, action2/target2 for the second) via the real
    `<action> afl:targetResource <target> .` triple `_admission_covers_action_target()`
    requires. This keeps the mutation's own adversarial construction intact: the
    second call's admission is completely genuine and content-bound for action2/
    target2 (it would pass `execute_admitted()` on its own), so `second`'s eventual
    `REFUSED_TOKEN_ACTION_MISMATCH` is caused ONLY by the token/action-identity check
    this test exists to exercise, never by a masking `REFUSED_NOT_ADMITTED` from the
    now-mandatory admission gate.
    """
    actor = "urn:agent:fresh-mut-b-actor"
    action1 = "urn:action:fresh-mut-b:read-report"
    target1 = "urn:resource:fresh-mut-b:report"
    action2 = "urn:action:fresh-mut-b:wire-transfer"
    target2 = "urn:resource:fresh-mut-b:treasury"
    token = "idemp-fresh-mut-b-shared-token"

    pipeline = AdmissionPipeline()
    admitted1 = pipeline.admit(
        f"""
@prefix afl: <urn:autofde-lab:> .
<{action1}> a afl:Action ;
    afl:targetResource <{target1}> .
""",
        provenance_record={"issuer": "urn:issuer:fresh-mut-b", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted1.standing == Standing.ADMITTED
    admitted2 = pipeline.admit(
        f"""
@prefix afl: <urn:autofde-lab:> .
<{action2}> a afl:Action ;
    afl:targetResource <{target2}> .
""",
        provenance_record={"issuer": "urn:issuer:fresh-mut-b", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted2.standing == Standing.ADMITTED

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-b-1",
            subject_id=actor,
            action_iri=action1,
            target_resource_iri=target1,
        )
    )
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-b-2",
            subject_id=actor,
            action_iri=action2,
            target_resource_iri=target2,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_b", broker)

    first = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=action1,
            target_resource=target1,
            actor_id=actor,
            admission_result=admitted1,
        )
    )
    assert first.success is True
    assert first.state == TerminalReceiptState.EXECUTED
    assert actuator.call_count == 1

    # MUTATION: replay the SAME token, but substitute action2/target2 -- an identity the
    # actor is ALSO validly, independently granted for AND genuinely, content-boundly
    # admitted for (so both the reauth check AND the admission gate would, on their
    # own, correctly let action2 through -- isolating the token/action-identity check
    # as the only thing that can still refuse this call).
    second = boundary.execute(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=action2,
            target_resource=target2,
            actor_id=actor,
            admission_result=admitted2,
        )
    )

    journal_records = []
    if journal.exists():
        import json as _json

        journal_records = _json.loads(journal.read_text(encoding="utf-8"))
    action2_actually_actuated = any(r.get("action") == action2 for r in journal_records)

    assert (not second.success) or action2_actually_actuated, (
        "MUTATION B SURVIVED: replaying idempotency token "
        f"{token!r} with a DIFFERENT action ({action2!r} on {target2!r}, substituted "
        f"for the original {action1!r} on {target1!r}) returned success="
        f"{second.success!r} state={second.state!r} "
        f"final_receipt_digest={second.final_receipt.digest if second.final_receipt else None!r} "
        "WITHOUT ever actuating action2 on physical disk "
        f"(actuator.call_count stayed at {actuator.call_count}; real journal records: "
        f"{journal_records!r}). The reauthorization check in ConsequenceBoundary.execute() "
        "Step 1 correctly re-evaluates AuthorityBroker for the REPLAYING request's own "
        "action_iri/target_resource, but then unconditionally returns the STALE "
        "`existing_final` receipt minted for the ORIGINAL action -- a receipt/action "
        "identity mismatch: the caller asked for action2 and was handed back a receipt "
        "for action1, reported as success, with zero real actuation of action2."
    )

    # Precise, current-fix assertions (tightened from the disjunction above, now that
    # the exact fix behavior -- refuse, never substitute-actuate -- is known):
    assert second.success is False, "The substituted-action replay must be refused outright."
    assert second.state == TerminalReceiptState.REFUSED
    assert second.refusal_code == REFUSED_TOKEN_ACTION_MISMATCH, (
        f"Expected the precise Mutation-B refusal code, got {second.refusal_code!r}: "
        f"{second.reason}"
    )
    assert not action2_actually_actuated, "action2 must never be actuated via this token."
    assert actuator.call_count == 1, "No new actuation for the refused cross-action replay."
    assert second.final_receipt is not None
    assert second.final_receipt.digest != first.final_receipt.digest, (
        "The refusal receipt must never be byte-identical to action1's original receipt."
    )

    # action1's own original durable record is left completely untouched.
    final_after = boundary.receipt_store.get_final(token)
    assert final_after is not None
    assert final_after.digest == first.final_receipt.digest
    assert final_after.state == TerminalReceiptState.EXECUTED


# ---------------------------------------------------------------------------
# Mutation C: admission fence bypass via already-executed token replay.
# ---------------------------------------------------------------------------


def test_mutation_c_execute_admitted_admission_gate_bypassed_on_replay(tmp_path: Path) -> None:
    """execute_admitted() must require a bound Standing.ADMITTED admission_result on
    EVERY call through it -- not merely the first call under a given idempotency token.

    FIXED (this session): `ConsequenceBoundary.execute_admitted()` was restructured to
    evaluate the admission gate unconditionally on every call, rather than only when
    `receipt_store.get_final(token) is None`. The second call presents
    `admission_result=None`, so the gate refuses it with `REFUSED_NOT_ADMITTED` --
    exactly the same typed code a first-call refusal would use -- as a deterministic,
    non-persisted receipt (the token's original EXECUTED final is left untouched).
    Control never falls through to `execute()`'s replay/reauth path for this call.
    DEFEATED = TRUE.

    Fixture note: uses `_MUT_C_BOUND_TTL` (not `_HARMLESS_ADMITTABLE_TTL`) so the
    legitimate first call's content genuinely covers this test's own action/target,
    isolating this mutation's concern from Mutation A's content-binding concern -- see
    the module docstring.
    """
    pipeline = AdmissionPipeline()
    admitted = pipeline.admit(
        _MUT_C_BOUND_TTL,
        provenance_record={"issuer": "urn:issuer:any", "timestamp": "2026-09-16T00:00:00Z"},
    )
    assert admitted.standing == Standing.ADMITTED

    actor = "urn:agent:fresh-mut-c-actor"
    action = "urn:action:fresh-mut-c:sync"
    target = "urn:resource:fresh-mut-c:target"
    token = "idemp-fresh-mut-c-shared-token"

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-fresh-mut-c",
            subject_id=actor,
            action_iri=action,
            target_resource_iri=target,
        )
    )
    boundary, actuator, _store, journal = _boundary(tmp_path, "mut_c", broker)

    first = boundary.execute_admitted(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=action,
            target_resource=target,
            actor_id=actor,
            admission_result=admitted,
        )
    )
    assert first.success is True, (
        f"Legitimate, content-bound first call must genuinely execute: {first.reason}"
    )
    assert first.state == TerminalReceiptState.EXECUTED
    assert actuator.call_count == 1

    # MUTATION: replay the SAME token through the SAME strict entry point, but this
    # time present NO admission_result at all.
    second = boundary.execute_admitted(
        ExecutionEnvelope(
            idempotency_token=token,
            action_iri=action,
            target_resource=target,
            actor_id=actor,
            admission_result=None,
        )
    )

    assert second.success is False and second.refusal_code == REFUSED_NOT_ADMITTED, (
        "MUTATION C SURVIVED: a second call to execute_admitted() for a "
        f"previously-executed token ({token!r}) with admission_result=None returned "
        f"success={second.success!r} refusal_code={second.refusal_code!r} "
        f"state={second.state!r} -- the admission fence was skipped entirely because "
        "ConsequenceBoundary.execute_admitted() only checks admission_result when "
        "`receipt_store.get_final(token) is None`; once ANY final receipt exists under "
        "a token (even a legitimate first execution), every subsequent call through "
        "the 'strict, admission-gated' entry point bypasses the admission check "
        "entirely and falls through to execute()'s replay/reauth path, which checks "
        "authority but never checks admission again."
    )
    assert second.state == TerminalReceiptState.REFUSED
    assert actuator.call_count == 1, "No new actuation for the admission-gate-refused replay."
    assert second.final_receipt is not None
    assert second.final_receipt.digest != first.final_receipt.digest, (
        "The refusal receipt must never be byte-identical to the original EXECUTED receipt."
    )

    # The first call's own original durable record is left completely untouched by the
    # second call's refusal.
    final_after = boundary.receipt_store.get_final(token)
    assert final_after is not None
    assert final_after.digest == first.final_receipt.digest
    assert final_after.state == TerminalReceiptState.EXECUTED
