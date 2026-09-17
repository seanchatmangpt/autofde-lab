# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AFDE-2604 receipt-store TOCTOU fix -- independent residual-gap qualification.

Task (this session): read the REAL, current `src/autofde_lab/sa2a/brce/boundary.py`,
`src/autofde_lab/sa2a/hooks/reactive_loop.py`, `src/autofde_lab/sa2a/cli.py`, and
`src/autofde_lab/sa2a/brce/receipts.py` (both sibling agents' self-reports are untrusted
observations, per `.claude/rules/absence-is-not-evidence.md` / `no-dual-bookkeeping.md` --
re-verified against the real source in this session, not assumed from the reports). Lens:
receipt-store TOCTOU residual -- does a window remain where a grant's real validity changes
between admission/authorization and final commit that `receipts.py`'s
`_validate_final_grant_id` fix does not cover? Two concrete angles named by the task: a grant
REVOKED (not merely expired) mid-flight, and concurrent `execute()` calls on the same token.

Three real, adversarial mutations attempted below (real `AuthorityBroker`, real
`ConsequenceBoundary`, real `ReceiptStore`; a real `threading.Thread` for the concurrency
mutation; zero `unittest.mock`/`Mock`/`MagicMock`/`patch`/`monkeypatch` anywhere in this
file -- verified by grep in the session transcript this file was produced in).

**Finding 1 (Mutation R1): SURVIVED.** `ConsequenceBoundary.__init__` (boundary.py:270)
constructs `self._receipt_store = receipt_store or ReceiptStore()` -- when no `receipt_store`
is passed, the resulting `ReceiptStore()` is built with its own `authority_broker` parameter
left at its default, `None` (receipts.py:291). `ConsequenceBoundary` never threads its own
`self._authority_broker` into that default `ReceiptStore()`. Grepping every real
`ConsequenceBoundary(...)` construction in `src/` (`cli.py:445`, the only production
construction site) and every `ReceiptStore(...)`/`DurableDiskReceiptStore(...)` construction
in `src/` (`conformance/runner.py`, `conformance/benchmarks/harness.py`,
`conformance/courts/*.py`) confirms: in this entire repository, as of this session, NO
production code path ever constructs a `ReceiptStore` with `authority_broker=` set. The ONLY
constructions that pass `authority_broker=` are two dedicated store-validation test files
(`test_afde_2604_receipt_store_grant_validation.py`,
`test_afde_2604_receipt_store_grant_validation_mutations.py`). This means `receipts.py`'s
entire save_final TOCTOU fix is a **structural no-op for the real, live `cli.py hook reflex`
execution path** -- the fix exists in the codebase but is not wired to anything that actually
runs. A grant revoked between the Step 2 `AuthorityBroker.evaluate()` call and Step 7's
`save_final()` (e.g. inside the real actuator's own `actuate()` call -- the actuation itself
may be exactly the window an out-of-band revocation lands in) is never re-checked anywhere on
this path, and a terminal `EXECUTED` / `postcondition_verified=True` `FinalReceipt` is
durably persisted for an identity whose authority no longer exists at the moment of persist.

**Finding 2 (Mutation R2): SURVIVED, in a materially worse form than "unchecked."** Even when
a caller DOES wire `ReceiptStore(authority_broker=broker)` into `ConsequenceBoundary` (opting
into the fix), `ConsequenceBoundary.execute()` Step 7 (boundary.py:702-703) calls
`self._receipt_store.save_final(final_receipt)` with **no surrounding try/except**. When the
grant was revoked during `actuate()` (Step 5, already executed -- the real, possibly
irreversible external effect has already happened by this point), the fresh
`AuthorityBroker.evaluate()` call inside `_validate_final_grant_id` correctly detects the
revocation and raises `ReceiptGrantValidationError` -- but that exception propagates
**uncaught** out of `ConsequenceBoundary.execute()` itself. The caller never receives a
`BoundaryExecutionResult` at all (typed REFUSED or otherwise) for an actuation that
genuinely, physically occurred, and the receipt store durably has **no terminal receipt
whatsoever** for this idempotency_token (`get_final()` returns `None` after the crash) --
not even a REFUSED one. This is a "Zero Unreceipted Actuation" violation of the exact kind
this repo's law's exist to prevent, produced BY the fix itself: closing the false-EXECUTED
gap converts it into an unreceipted, unrepresented crash rather than a typed refusal.

**Finding 3 (Mutation R3, concurrency): SURVIVED.** Using two genuinely concurrent
`ConsequenceBoundary.execute()` calls on the SAME `idempotency_token` (real
`threading.Thread`, real `threading.Event` synchronization, no sleeps/timing luck): thread A
begins a first-time execution, commits a real `PreparedReceipt` (Step 4), and blocks inside
a real actuator's `actuate()` (Step 5, i.e. AFTER authority was checked and the actuation
side effect is already in flight). While A is blocked mid-actuation, the grant is revoked
(a real, out-of-band revocation) and a SECOND, fully concurrent `execute()` call (thread
B, same envelope, same token) is issued: B's Step 1 sees no final receipt yet (A hasn't
finished), so B proceeds to its OWN Step 2 authority check -- which now correctly refuses
(grant is gone) -- and B durably commits a REFUSED `FinalReceipt` for this token via
`save_final()`, which succeeds because no final receipt exists yet. When A is then allowed
to finish (its actuation already genuinely occurred), A's OWN Step 7 attempts to commit its
EXECUTED `FinalReceipt` under the SAME token -- and `ReceiptStore.save_final()`
(receipts.py:440-446) raises a bare `ValueError` ("Idempotency token conflict") because B's
REFUSED receipt digest differs from A's EXECUTED one. Net real-world outcome: the actuation
genuinely happened (A's actuator recorded it), the durably persisted terminal record for
this token is REFUSED (physically false), and A's `execute()` call raises an uncaught
`ValueError` instead of returning any `BoundaryExecutionResult`. `ReceiptStore` has no
locking of any kind (plain `dict`s, no `threading.Lock`) -- Step 1's "check `get_final`, then
later commit a terminal receipt" is a textbook, unguarded check-then-act race, entirely
independent of whether `authority_broker` is wired into the store or not.

None of these three findings is patched here -- reporting only, per this session's task.

Verification, this session:
    grep -n "unittest.mock\|Mock(\|MagicMock\|patch(\|monkeypatch" \
        tests/sa2a/conformance/test_afde_2604_toctou_residual_qualification.py
    .venv/bin/python -m pytest \
        tests/sa2a/conformance/test_afde_2604_toctou_residual_qualification.py -v
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional

import pytest

from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.brce.boundary import ConsequenceBoundary, ExecutionEnvelope
from autofde_lab.sa2a.brce.receipts import ReceiptStore, TerminalReceiptState

ACTION_IRI = "urn:autofde-lab:action:doThing"
TARGET_RESOURCE = "urn:autofde-lab:resource:thing1"
ACTOR_ID = "actor-1"


class RecordingVerifier:
    """Real, simple ConsequenceVerifier implementation -- always confirms the
    postcondition. Not a mock: a genuine, if trivial, implementation of the real
    protocol's contract (testing-chicago-style.md: "a hand-written, simple, real
    implementation ... is not a mock -- the distinction is ... does it genuinely
    implement the collaborator's contract").
    """

    def verify_postcondition(
        self,
        action_iri: str,
        target_resource: str,
        parameters: Mapping[str, Any],
        evidence: Optional[Mapping[str, Any]],
    ) -> bool:
        return True

    def verifier_digest(self) -> str:
        return "digest-recording-verifier"


class RevokingActuator:
    """Real ConsequenceActuator: as a genuine side effect of actuating, revokes the
    grant that authorized it -- simulating a real, out-of-band revocation (e.g. an
    admin action, a policy update) landing exactly inside the actuation window, after
    authority was already checked (Step 2) and before the terminal receipt is
    committed (Step 7)."""

    def __init__(self, broker: AuthorityBroker, grant_id: str) -> None:
        self._broker = broker
        self._grant_id = grant_id
        self.actuated = False

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        # Real revocation of the real grant, via the broker's own real grant registry --
        # not a synthetic effect, and not something already checked before this
        # actuation was authorized to begin.
        self._broker._grants.pop(self._grant_id, None)
        self.actuated = True
        return {"actuated": True}

    def actuator_digest(self) -> str:
        return "digest-revoking-actuator"


class BlockingThenRevokingActuator:
    """Real ConsequenceActuator used for the concurrency mutation: signals that it has
    genuinely entered `actuate()` (so a concurrent thread can act while this call is
    physically in flight, mid-actuation, past Step 2's authority check), then blocks on
    a real `threading.Event` until released."""

    def __init__(self, entered: threading.Event, proceed: threading.Event) -> None:
        self._entered = entered
        self._proceed = proceed
        self.actuated = False

    def actuate(
        self, action_iri: str, target_resource: str, parameters: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self._entered.set()
        released = self._proceed.wait(timeout=5.0)
        assert released, "test setup error: proceed event was never signaled"
        self.actuated = True
        return {"actuated": True}

    def actuator_digest(self) -> str:
        return "digest-blocking-then-revoking-actuator"


def _make_grant(grant_id: str = "grant-toctou-1") -> AuthorityGrant:
    return AuthorityGrant(
        grant_id=grant_id,
        subject_id=ACTOR_ID,
        action_iri=ACTION_IRI,
        target_resource_iri=TARGET_RESOURCE,
        valid_until=None,  # deliberately NOT an expiry-based grant -- this is a
        # REVOCATION scenario (grant_id disappears from the registry entirely), a
        # distinct failure mode from AuthorityGrant.valid_until elapsing, which
        # receipts.py's existing test coverage already exercises.
    )


def test_r1_grant_revoked_mid_actuation_default_receipt_store_survives() -> None:
    """Mutation R1: the REAL production configuration -- `ConsequenceBoundary`
    constructed exactly as `cli.py:445` constructs it (no explicit `receipt_store=`,
    so the default, broker-less `ReceiptStore()` is used). A grant is revoked for
    real, mid-actuation (inside a real actuator's `actuate()` call, i.e. AFTER Step 2
    already authorized it). Expected if the fix covered this path: refusal or at
    least a non-EXECUTED terminal state. Actual (verified below): the real, current
    code SURVIVES this mutation -- a terminal EXECUTED, postcondition_verified=True
    FinalReceipt is durably persisted for a revoked grant, because the default
    receipt store never had the broker wired into it at all.
    """
    grant = _make_grant()
    broker = AuthorityBroker(grants=[grant])
    actuator = RevokingActuator(broker, grant.grant_id)
    verifier = RecordingVerifier()

    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        # No receipt_store= passed -- exactly cli.py's own real construction shape
        # (cli.py:445-452 passes authority_broker/actuator/verifier/require_admission
        # only; receipt_store defaults to `ReceiptStore()`, broker-less).
    )

    envelope = ExecutionEnvelope(
        idempotency_token="tok-r1",
        action_iri=ACTION_IRI,
        target_resource=TARGET_RESOURCE,
        actor_id=ACTOR_ID,
        grant_id=grant.grant_id,
    )

    # Sanity: the grant is genuinely present and valid before execute() runs.
    assert grant.grant_id in broker._grants

    result = boundary.execute(envelope)

    # The revocation genuinely happened (real side effect on the real broker).
    assert grant.grant_id not in broker._grants
    assert actuator.actuated is True

    # SURVIVED: despite the grant being gone by the time the terminal receipt is
    # committed, the boundary still reports a full, real EXECUTED success and
    # durably persists it -- the receipt-store TOCTOU fix never engages on this,
    # the actual production, code path.
    assert result.success is True
    assert result.state == TerminalReceiptState.EXECUTED
    assert result.final_receipt is not None
    assert result.final_receipt.postcondition_verified is True
    stored_final = boundary.receipt_store.get_final("tok-r1")
    assert stored_final is not None
    assert stored_final.state == TerminalReceiptState.EXECUTED


def test_r2_grant_revoked_mid_actuation_with_wired_broker_raises_uncaught() -> None:
    """Mutation R2: opt INTO the fix (wire `ReceiptStore(authority_broker=broker)`
    into the boundary, exactly as the sibling agent's own dedicated test files do).
    Same revocation-mid-actuation scenario as R1. Expected if the fix fully closed
    this window: a typed `BoundaryExecutionResult` refusal. Actual (verified below):
    the real, current code SURVIVES in a worse form -- `execute()` raises a bare,
    uncaught `ReceiptGrantValidationError` (boundary.py Step 7 has no try/except
    around `self._receipt_store.save_final(...)`), so the caller receives no typed
    result at all for an actuation that has ALREADY, physically happened, and the
    receipt store ends up with ZERO terminal receipt for this token -- not even a
    REFUSED one. Zero Unreceipted Actuation is violated by the fix's own refusal
    path, not merely left unchecked.
    """
    from autofde_lab.sa2a.brce.receipts import ReceiptGrantValidationError

    grant = _make_grant(grant_id="grant-toctou-2")
    broker = AuthorityBroker(grants=[grant])
    actuator = RevokingActuator(broker, grant.grant_id)
    verifier = RecordingVerifier()
    wired_store = ReceiptStore(authority_broker=broker)

    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator,
        verifier=verifier,
        receipt_store=wired_store,  # opting INTO the receipts.py fix, deliberately.
    )

    envelope = ExecutionEnvelope(
        idempotency_token="tok-r2",
        action_iri=ACTION_IRI,
        target_resource=TARGET_RESOURCE,
        actor_id=ACTOR_ID,
        grant_id=grant.grant_id,
    )

    with pytest.raises(ReceiptGrantValidationError):
        boundary.execute(envelope)

    # The actuation genuinely, physically occurred before the crash.
    assert actuator.actuated is True

    # SURVIVED (worse form): no terminal receipt of ANY state exists for this token --
    # the fix correctly detected the revocation but had no typed-refusal path to
    # report it through, so it destroyed the receipt trail for a real actuation
    # instead of producing a REFUSED record.
    assert wired_store.get_final("tok-r2") is None
    prepared = wired_store.get_prepared("tok-r2")
    assert prepared is not None  # the PreparedReceipt (Step 4) DID commit durably,
    # confirming the actuation that followed was genuinely authorized to begin --
    # only the terminal commit is where this now fails, uncaught.


def test_r3_concurrent_execute_calls_same_token_race_past_final_commit() -> None:
    """Mutation R3 (concurrency): two genuinely concurrent `execute()` calls on the
    SAME idempotency_token, real `threading.Thread` + `threading.Event`
    synchronization (no sleeps, no timing luck). Thread A performs a first-time
    execution and blocks mid-`actuate()` (post Step 2 authority check, actuation
    physically in flight). While A is blocked, the grant is revoked and a second,
    genuinely concurrent `execute()` call (same envelope, same token) is issued from
    the main thread ("thread B") -- exercising the literal "concurrent execute()
    calls on the same token" scenario named by this task. Expected if the store were
    race-safe: A's real actuation and B's refusal reconcile into one consistent
    terminal record. Actual (verified below): SURVIVED -- B's REFUSED FinalReceipt
    commits first (nothing blocks it), then A's own EXECUTED FinalReceipt commit
    raises a bare, uncaught `ValueError` ("Idempotency token conflict") because
    `ReceiptStore` has no locking of any kind (plain dicts) around
    check-`get_final`-then-commit. The durably persisted record is REFUSED even
    though the actuation genuinely, physically happened -- independent of whether
    `authority_broker` is wired into the store (this reproduces with the SAME
    broker-less default `ReceiptStore()` as R1, i.e. this is not merely the R1/R2
    gap restated -- it is a distinct, store-level race with no locking primitive
    anywhere in `ReceiptStore`/`ConsequenceBoundary`).
    """
    grant = _make_grant(grant_id="grant-toctou-3")
    broker = AuthorityBroker(grants=[grant])
    entered = threading.Event()
    proceed = threading.Event()
    actuator_a = BlockingThenRevokingActuator(entered, proceed)
    verifier = RecordingVerifier()

    boundary = ConsequenceBoundary(
        authority_broker=broker,
        actuator=actuator_a,
        verifier=verifier,
        # default receipt_store again -- the real production shape.
    )

    envelope = ExecutionEnvelope(
        idempotency_token="tok-r3",
        action_iri=ACTION_IRI,
        target_resource=TARGET_RESOURCE,
        actor_id=ACTOR_ID,
        grant_id=grant.grant_id,
    )

    results: dict[str, Any] = {}

    def run_thread_a() -> None:
        try:
            results["a_result"] = boundary.execute(envelope)
        except Exception as exc:  # noqa: BLE001 -- deliberately capturing for assertion
            results["a_exception"] = exc

    thread_a = threading.Thread(target=run_thread_a, name="execute-A")
    thread_a.start()

    # Wait for A to be GENUINELY inside actuate() -- past Step 2's authority check,
    # PreparedReceipt already durably committed (Step 4), actuation physically
    # underway -- before doing anything else. Real synchronization, not a sleep.
    assert entered.wait(timeout=5.0), "thread A never reached actuate() in time"

    # A real, out-of-band revocation of the grant A was legitimately authorized
    # under, landing while A's actuation is genuinely in flight.
    assert grant.grant_id in broker._grants
    del broker._grants[grant.grant_id]

    # Thread B: a second, genuinely concurrent execute() call on the SAME
    # idempotency_token, issued from the main thread while A is still blocked.
    result_b = boundary.execute(envelope)

    # Now let A finish its (already-occurred) actuation and reach its own Step 7.
    proceed.set()
    thread_a.join(timeout=5.0)
    assert not thread_a.is_alive(), "thread A did not finish in time"

    # B's real, correct outcome: revoked grant -> refused, and durably persisted
    # (nothing else held this token's final slot yet).
    assert result_b.success is False
    assert result_b.state == TerminalReceiptState.REFUSED

    # A's actuation genuinely, physically happened.
    assert actuator_a.actuated is True

    # SURVIVED: A's own attempt to commit its EXECUTED FinalReceipt collides with
    # B's already-persisted REFUSED FinalReceipt for the SAME token, and
    # ReceiptStore.save_final() raises a bare ValueError -- uncaught by
    # ConsequenceBoundary.execute() (no try/except around Step 7's save_final call).
    assert "a_exception" in results, (
        "expected thread A's execute() call to raise on the digest-mismatch "
        f"idempotency conflict; instead it returned: {results.get('a_result')!r}"
    )
    assert isinstance(results["a_exception"], ValueError)
    assert "Idempotency token conflict" in str(results["a_exception"])

    # The durably persisted terminal record for this token is REFUSED -- physically
    # false, since the real actuation (actuator_a.actuated) genuinely occurred.
    stored_final = boundary.receipt_store.get_final("tok-r3")
    assert stored_final is not None
    assert stored_final.state == TerminalReceiptState.REFUSED
