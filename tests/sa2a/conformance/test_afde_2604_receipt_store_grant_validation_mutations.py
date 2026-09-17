# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AFDE-2604 store-layer grant_id validation -- adversarial mutation attempts, CLOSED.

Task (this session): read the real `src/autofde_lab/sa2a/brce/receipts.py` implementation
landed for AFDE-2604 (`ReceiptStore._validate_grant_id`, previously called from
`save_prepared` only, opt-in via a constructor-injected `authority_broker`), and attempt real
mutations that try to bypass it. Per `.claude/rules/absence-is-not-evidence.md` /
`no-dual-bookkeeping.md`: a sibling agent's own self-report is not standing evidence -- this
file is an independent, adversarial re-derivation against the real source, not a re-run of
the sibling's own tests (which remain untouched: `test_afde_2604_receipt_store_grant_validation.py`).

**UPDATE (this session, fix-forward): both mutations below SURVIVED on first discovery and
are now DEFEATED.** `receipts.py` was changed so that `save_final` mirrors `save_prepared`'s
grant validation (`ReceiptStore._validate_final_grant_id`, new): it resolves the missing
identity from the corresponding `PreparedReceipt` (`FinalReceipt` itself still carries no
`grant_id`/`actor_id`/`action_iri`/`target_resource`) and performs a FRESH
`AuthorityBroker.evaluate()` call at `save_final` commit time -- never reusing the
`save_prepared`-time decision. Per this repo's fix-forward, no-reverted-tests discipline
(`CLAUDE.md`, "Git workflow: fix forward only"): the adversarial constructions below are
UNCHANGED; only the expected outcome flips from survives-the-bypass to
correctly-refused, with each docstring saying so explicitly.

Read in full this session, before writing any mutation:
- `src/autofde_lab/sa2a/brce/receipts.py` (the exact landed `_validate_grant_id`/
  `_validate_final_grant_id`/`save_prepared`/`save_final` bodies)
- `src/autofde_lab/sa2a/authority/broker.py` (`AuthorityBroker.evaluate`, `AuthorityGrant`,
  `ConsequenceRequest` -- confirmed `valid_until` expiry is checked with a live `time.time()`
  comparison inside `evaluate()`, not cached at grant-registration time)
- `src/autofde_lab/sa2a/conformance/courts/consequence_court.py`
  (`DurableDiskReceiptStore.save_prepared`/`save_final`, both call `super().save_X(receipt)`
  BEFORE their own disk write, so a raised exception in the base class means zero bytes hit
  disk)

Two real mutations attempted, both against the real store code (nothing here patches or mocks
the implementation under test):

1. `test_save_final_bypasses_grant_validation_entirely_for_a_never_prepared_receipt` --
   **DEFEATED (was: survives -- see history above)**. `save_final` now calls
   `_validate_final_grant_id`, which -- when a broker is configured -- looks up the
   corresponding `PreparedReceipt` by `idempotency_token` and refuses outright
   (`ReceiptGrantValidationError`, `refusal_code=REFUSED_NO_PREPARED_RECEIPT`) when none
   exists. A `FinalReceipt` claiming `TerminalReceiptState.EXECUTED` /
   `postcondition_verified=True` for an `idempotency_token` that was **never** passed to
   `save_prepared` can no longer be durably persisted (zero bytes on disk, for the disk-backed
   variant) while a broker is configured -- the "Zero Unreceipted Actuation" property
   (RFC-SA2A-001 §4.8, §31) this bypass violated is now enforced at the store layer too.

2. `test_grant_expiring_between_save_prepared_and_save_final_leaves_final_commit_unchecked`
   -- **DEFEATED (was: survives -- a genuine TOCTOU bypass, see history above)**.
   `_validate_final_grant_id` performs a *fresh* `AuthorityBroker.evaluate()` call at
   `save_final` time, resolving the identity from the already-saved `PreparedReceipt`. A grant
   that was genuinely valid at `save_prepared` time (so the `PreparedReceipt` was accepted)
   but has since expired (`AuthorityGrant.valid_until` elapses for real, verified via a real
   `time.sleep` and a real follow-up `broker.evaluate()` call proving the broker itself now
   refuses it with `REFUSED_EXPIRED_GRANT`) is caught by that same fresh check at `save_final`
   time: the store now raises `ReceiptGrantValidationError` with
   `refusal_code=REFUSED_EXPIRED_GRANT` and refuses to commit the terminal receipt, with zero
   disk mutation for the disk-backed variant.

One confirming (non-bypass) control, included to show precisely which attack surface the
existing fix DOES close, per `criticism-discipline.md`'s symmetric-burden rule (a claim that
a fix has a gap is not evidence the fix does nothing):

3. `test_grant_id_string_reused_for_a_different_actor_is_correctly_refused` -- **DEFEATED**.
   A `grant_id` string that collides with a DIFFERENT actor's real, currently-registered grant
   (the "same string by coincidence" mutation named in this session's task) is correctly
   refused, because `_validate_grant_id`'s fresh `evaluate()` call re-checks the full
   `(actor_id, action_iri, target_resource)` identity against the looked-up grant's own
   fields -- not merely whether the `grant_id` string resolves to *some* grant. This mutation
   does not survive. (Unchanged by this session's `save_final` fix -- this mutation targets
   `save_prepared` only.)

Per `.claude/rules/level4-completion-law.md`'s Mutation law: each mutation above is a single,
otherwise-complete, valid episode with exactly one identity/field mutated (a missing prior
`PreparedReceipt`; a grant whose validity window elapsed) and the correct fix produces a typed
refusal for each -- no mutation below is left silently surviving. Backward compatibility (the
default, broker-less construction every existing caller uses) is proven unaffected by
`test_save_final_without_broker_still_behaves_exactly_as_before`.

Chicago Zero-Mock Standard (this repo's `.claude/rules/testing-chicago-style.md` and
`tests/CLAUDE.md`):
- Real `AuthorityBroker` / `AuthorityGrant` / `ConsequenceRequest` (unmodified, real business
  logic, including real `time.time()`-based expiry checks).
- Real `ReceiptStore` and real disk-backed `DurableDiskReceiptStore` (genuine `tmp_path` I/O).
- Grant expiry is exercised with a real `time.sleep()` past a real `valid_until` timestamp --
  never a monkeypatched clock.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this file.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from autofde_lab.sa2a.authority.broker import (
    REFUSED_EXPIRED_GRANT,
    REFUSED_NO_GRANT,
    AuthorityBroker,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.receipts import (
    REFUSED_NO_PREPARED_RECEIPT,
    FinalReceipt,
    PreparedReceipt,
    ReceiptGrantValidationError,
    ReceiptStore,
    TerminalReceiptState,
)
from autofde_lab.sa2a.conformance.courts.consequence_court import DurableDiskReceiptStore

GENESIS = "genesis:0" * 4

ACTOR = "urn:agent:receipt-store-mutation"
ACTION = "urn:action:quarantine_node"
TARGET = "urn:resource:cluster:node-mutation-1"


def _prepared(*, idempotency_token: str, grant_id: str) -> PreparedReceipt:
    return PreparedReceipt(
        prepared_id=f"prep-{idempotency_token}",
        idempotency_token=idempotency_token,
        action_iri=ACTION,
        target_resource=TARGET,
        actor_id=ACTOR,
        grant_id=grant_id,
        plan_digest=GENESIS,
        artifact_digest="none",
        admitted_input_digest=GENESIS,
        consequence_class="LOCAL_EFFECT",
    )


def _final_executed(*, idempotency_token: str, prepared_receipt_digest: str) -> FinalReceipt:
    return FinalReceipt(
        receipt_id=f"final-{idempotency_token}",
        prepared_receipt_digest=prepared_receipt_digest,
        idempotency_token=idempotency_token,
        state=TerminalReceiptState.EXECUTED,
        postcondition_verified=True,
        evidence={"forged": True},
    )


# ---------------------------------------------------------------------------
# Mutation 1: save_final bypassing grant validation for a never-prepared identity.
# DEFEATED (was: SURVIVES) -- save_final now refuses via REFUSED_NO_PREPARED_RECEIPT.
# ---------------------------------------------------------------------------


def test_save_final_bypasses_grant_validation_entirely_for_a_never_prepared_receipt() -> None:
    """DEFEATED (was SURVIVES): `save_final` now calls `_validate_final_grant_id`, which --
    when a broker is configured -- looks up the corresponding `PreparedReceipt` by
    `idempotency_token` and refuses (typed `ReceiptGrantValidationError`,
    `refusal_code=REFUSED_NO_PREPARED_RECEIPT`) when none exists. A terminal EXECUTED receipt
    can no longer be durably persisted for an identity that was never granted anything and
    never had a corresponding PreparedReceipt at all.
    """
    broker = AuthorityBroker()  # Zero grants registered anywhere -- nothing is authorized.
    store = ReceiptStore(authority_broker=broker)

    never_prepared_token = "idemp-never-prepared-001"
    forged_final = _final_executed(
        idempotency_token=never_prepared_token,
        prepared_receipt_digest="sha256:this-digest-was-never-produced-by-any-save_prepared-call",
    )

    # Confirm, honestly, that the underlying identity is not authorized at all (positive
    # control): a real save_prepared attempt for this same identity WOULD be refused.
    honest_prepare_attempt = _prepared(idempotency_token=never_prepared_token, grant_id="grant-does-not-exist")
    with pytest.raises(Exception):
        store.save_prepared(honest_prepare_attempt)

    # The (now-defeated) bypass attempt: go straight to save_final, skipping save_prepared.
    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_final(forged_final)

    assert excinfo.value.refusal_code == REFUSED_NO_PREPARED_RECEIPT
    assert excinfo.value.receipt is forged_final

    # The forged final receipt must never have entered the store.
    assert store.get_final(never_prepared_token) is None
    assert store.get_prepared(never_prepared_token) is None


def test_disk_store_save_final_bypass_writes_real_terminal_bytes_with_no_prepared_receipt(
    tmp_path: Path,
) -> None:
    """DEFEATED (was SURVIVES): same bypass attempt against the disk-backed
    `DurableDiskReceiptStore` is refused before any disk write -- `DurableDiskReceiptStore
    .save_final` calls `super().save_final(receipt)` (where the new validation raises)
    strictly before its own disk-write code runs, so zero `final_*.json` bytes land on
    physical disk, and no matching `prep_*.json` ever existed either.
    """
    broker = AuthorityBroker()  # Zero grants.
    store_dir = tmp_path / "receipts_save_final_bypass"
    store = DurableDiskReceiptStore(store_dir, authority_broker=broker)

    token = "idemp-never-prepared-disk-001"
    forged_final = _final_executed(
        idempotency_token=token,
        prepared_receipt_digest="sha256:fabricated-no-such-prepared-receipt-exists",
    )

    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_final(forged_final)

    assert excinfo.value.refusal_code == REFUSED_NO_PREPARED_RECEIPT

    final_file = store_dir / f"final_{token}.json"
    prep_file = store_dir / f"prep_{token}.json"
    assert not final_file.exists(), "Refused terminal receipt must never reach physical disk."
    assert not prep_file.exists(), "No PreparedReceipt was ever saved for this identity."
    assert store.get_final(token) is None


# ---------------------------------------------------------------------------
# Mutation 2: grant expires between save_prepared and save_final.
# DEFEATED (was: SURVIVES -- TOCTOU) -- save_final now re-validates fresh at commit time.
# ---------------------------------------------------------------------------


def test_grant_expiring_between_save_prepared_and_save_final_leaves_final_commit_unchecked() -> None:
    """DEFEATED (was SURVIVES -- a genuine TOCTOU bypass): a grant valid at `save_prepared`
    time (accepted) genuinely expires (real `valid_until` elapsed, real `time.sleep`) before
    `save_final` is called for the same identity. `save_final` now performs a FRESH grant
    re-check (`_validate_final_grant_id`, resolving the identity from the already-saved
    `PreparedReceipt`), so the terminal EXECUTED receipt is refused -- matching the honest,
    fresh `broker.evaluate()` call at that same moment, which independently confirms
    `REFUSED_EXPIRED_GRANT` for the identical claim.
    """
    broker = AuthorityBroker()
    short_lived_grant = AuthorityGrant(
        grant_id="grant-afde2604-toctou-001",
        subject_id=ACTOR,
        action_iri=ACTION,
        target_resource_iri=TARGET,
        valid_until=time.time() + 0.25,
    )
    broker.register_grant(short_lived_grant)

    store = ReceiptStore(authority_broker=broker)
    token = "idemp-toctou-expiry-001"

    # save_prepared succeeds: the grant is genuinely valid right now.
    receipt = _prepared(idempotency_token=token, grant_id=short_lived_grant.grant_id)
    store.save_prepared(receipt)  # Must not raise.
    assert store.get_prepared(token) is not None

    # Let the grant genuinely expire (real clock, no monkeypatching).
    time.sleep(0.4)

    # Positive control: the broker itself now honestly refuses this exact claim.
    fresh_decision = broker.evaluate(
        ConsequenceRequest(
            actor_id=ACTOR,
            action_iri=ACTION,
            target_resource=TARGET,
            grant_id=short_lived_grant.grant_id,
        )
    )
    assert fresh_decision.authorized is False
    assert fresh_decision.refusal_code == REFUSED_EXPIRED_GRANT

    # The (now-defeated) TOCTOU attempt: save_final for the same token is refused.
    final = _final_executed(idempotency_token=token, prepared_receipt_digest=receipt.digest)
    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_final(final)

    assert excinfo.value.refusal_code == REFUSED_EXPIRED_GRANT
    assert store.get_final(token) is None


def test_disk_store_grant_expiry_toctou_commits_real_bytes_after_expiry(tmp_path: Path) -> None:
    """DEFEATED (was SURVIVES): same TOCTOU mutation against the disk-backed store is refused
    before any disk write -- the terminal receipt's bytes never land on disk once the
    authorizing grant has genuinely expired.
    """
    broker = AuthorityBroker()
    short_lived_grant = AuthorityGrant(
        grant_id="grant-afde2604-toctou-disk-001",
        subject_id=ACTOR,
        action_iri=ACTION,
        target_resource_iri=TARGET,
        valid_until=time.time() + 0.25,
    )
    broker.register_grant(short_lived_grant)

    store_dir = tmp_path / "receipts_toctou_disk"
    store = DurableDiskReceiptStore(store_dir, authority_broker=broker)
    token = "idemp-toctou-expiry-disk-001"

    receipt = _prepared(idempotency_token=token, grant_id=short_lived_grant.grant_id)
    store.save_prepared(receipt)
    prep_file = store_dir / f"prep_{token}.json"
    assert prep_file.exists()

    time.sleep(0.4)  # Real expiry.

    fresh_decision = broker.evaluate(
        ConsequenceRequest(
            actor_id=ACTOR, action_iri=ACTION, target_resource=TARGET, grant_id=short_lived_grant.grant_id
        )
    )
    assert fresh_decision.authorized is False
    assert fresh_decision.refusal_code == REFUSED_EXPIRED_GRANT

    final = _final_executed(idempotency_token=token, prepared_receipt_digest=receipt.digest)
    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_final(final)

    assert excinfo.value.refusal_code == REFUSED_EXPIRED_GRANT

    final_file = store_dir / f"final_{token}.json"
    assert not final_file.exists(), "Refused terminal receipt must never reach physical disk."
    assert store.get_final(token) is None


# ---------------------------------------------------------------------------
# Backward compatibility: no broker configured -> save_final is byte-for-byte unchanged.
# ---------------------------------------------------------------------------


def test_save_final_without_broker_still_behaves_exactly_as_before() -> None:
    """A `ReceiptStore()` constructed WITHOUT a broker (the pre-existing default, and the
    construction every existing caller in this repo uses) still accepts a `FinalReceipt` for
    an identity that was never prepared, with zero exception -- `_validate_final_grant_id` is
    a no-op when `self._authority_broker is None`, exactly mirroring `_validate_grant_id`'s
    own opt-in scope. This is the explicit regression guard for this session's `save_final`
    fix, matching `test_afde_2604_receipt_store_grant_validation.py`'s existing
    `test_in_memory_store_without_broker_behaves_exactly_as_before` for `save_prepared`.
    """
    store = ReceiptStore()  # No authority_broker -- the pre-existing default.
    token = "idemp-no-broker-save-final-001"
    forged_final = _final_executed(
        idempotency_token=token,
        prepared_receipt_digest="sha256:no-broker-means-no-validation-at-all",
    )

    store.save_final(forged_final)  # Must NOT raise -- zero validation without a broker.

    persisted = store.get_final(token)
    assert persisted is not None
    assert persisted.state == TerminalReceiptState.EXECUTED


# ---------------------------------------------------------------------------
# Confirming control: coincidental grant_id string collision across actors (DEFEATED).
# ---------------------------------------------------------------------------


def test_grant_id_string_reused_for_a_different_actor_is_correctly_refused() -> None:
    """A `grant_id` string that happens to also name a real, currently-registered grant
    belonging to a DIFFERENT actor/action/target does NOT bypass `_validate_grant_id`: the
    fresh `evaluate()` call re-checks the full identity against the resolved grant's own
    fields, not merely the string's existence. This mutation is defeated by the existing fix.
    """
    broker = AuthorityBroker()
    other_actor_grant = AuthorityGrant(
        grant_id="grant-shared-id-001",
        subject_id="urn:agent:completely-different-actor",
        action_iri="urn:action:read_metrics",
        target_resource_iri="urn:resource:dashboard:1",
    )
    broker.register_grant(other_actor_grant)

    store = ReceiptStore(authority_broker=broker)
    token = "idemp-coincidental-collision-001"
    # Self-asserts the SAME grant_id string, but for a totally different actor/action/target.
    colliding_receipt = _prepared(idempotency_token=token, grant_id="grant-shared-id-001")

    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_prepared(colliding_receipt)

    assert excinfo.value.refusal_code == REFUSED_NO_GRANT
    assert store.get_prepared(token) is None
