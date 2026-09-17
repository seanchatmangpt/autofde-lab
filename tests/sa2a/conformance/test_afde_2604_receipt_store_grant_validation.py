# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AFDE-2604 store-layer defense-in-depth: `ReceiptStore.save_prepared` grant_id validation
(RFC-SA2A-002 v26.9.16).

Context (read in full this session, both files):
- `docs/jira/v26.9.16/AFDE-2604-admission-fencing-local-closure.md` -- the ticket. Its
  "Local closure work (fix implemented)" section records that a prior pass closed the
  candidate-to-authority / replay-reauthorization gap entirely at the point of use
  (`ConsequenceBoundary.execute()`), deliberately leaving `ReceiptStore.save_prepared`/
  `save_final` performing zero validation of a receipt's claimed `grant_id` -- named there
  as `UNSUPPORTED` (not attempted, not an oversight): "this was a deliberate scope decision
  ... see the Gap (3) fix description above for why the store was intentionally left
  unchanged."
- `tests/sa2a/conformance/test_mutation_cross_court_identity.py` -- Test 1
  (`test_receipt_store_accepts_grant_id_claim_for_never_authorized_actuation_identity`)
  is the executable pinning of that exact gap: a `PreparedReceipt` self-asserting a real
  `grant_id` for an action/target pair that grant never actually covers is durably persisted
  by `ReceiptStore.save_prepared` with zero exception and zero cross-check.

This file adds the SECOND, INDEPENDENT layer named in this session's task: real grant_id
validation directly inside `ReceiptStore.save_prepared`, opt-in via a constructor-injected
`authority_broker` reference (default `None`). It does NOT modify
`test_mutation_cross_court_identity.py`'s own pinned finding -- that file's `store` fixtures
are constructed WITHOUT a broker (`DurableDiskReceiptStore(tmp_path / "receipts")`), so this
session's fix does not change their outcome: Test 1 there still passes, for the same reason
it always has (no broker configured -> zero validation, exactly as before). This file proves
the same store construction now behaves differently the moment a broker IS supplied.

Three properties, matching this session's task exactly:

(a) A `PreparedReceipt` whose `grant_id` claim IS backed by a real, currently-registered
    `AuthorityGrant` for that receipt's own (actor_id, action_iri, target_resource) is
    ACCEPTED -- both by the base in-memory `ReceiptStore` and by the disk-backed
    `DurableDiskReceiptStore`, with real bytes landing on disk.
(b) A `PreparedReceipt` whose `grant_id` claim is forged/mismatched (the exact
    same-label-different-identity construction `test_mutation_cross_court_identity.py`
    uses -- a real grant_id string, scoped by the real broker to a DIFFERENT
    action/target, self-asserted onto a receipt for a target that grant never covers) is
    REFUSED with the new typed `ReceiptGrantValidationError` when a broker is configured --
    for both store variants, and with ZERO disk mutation for the disk-backed variant
    (Zero Unreceipted Actuation's own spirit applied one layer earlier: a receipt that
    fails this fence is never durably committed at all).
(c) Backward compatibility: a `ReceiptStore`/`DurableDiskReceiptStore` constructed WITHOUT a
    broker (the existing default, and the construction every current caller in this repo
    uses) accepts the identical forged receipt with zero exception and zero cross-check --
    byte-for-byte the same outcome `test_mutation_cross_court_identity.py` Test 1 already
    pins, re-proven here as this new file's own regression guard.

Chicago Zero-Mock Standard:
- Real `AuthorityBroker` / `AuthorityGrant` / `ConsequenceRequest` instances (the same
  collaborators `test_court_authority.py`, `test_mutation_authority.py`, and
  `test_mutation_cross_court_identity.py` use).
- Real `ReceiptStore` and real `DurableDiskReceiptStore` performing genuine disk I/O under
  `tmp_path` (the same collaborator `test_court_consequence.py` and
  `test_mutation_cross_court_identity.py` use).
- The one adversarial step -- directly constructing a `PreparedReceipt` with a
  self-asserted `grant_id` and calling `ReceiptStore.save_prepared`/
  `DurableDiskReceiptStore.save_prepared` on it -- is not a mock. It is the exact
  construction path `ConsequenceBoundary.execute()` itself uses internally
  (`src/autofde_lab/sa2a/brce/boundary.py`), performed directly the way a compromised or
  buggy upstream caller of the receipt store legitimately could.
- Zero `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in this
  file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.sa2a.authority.broker import (
    REFUSED_NO_GRANT,
    AuthorityBroker,
    AuthorityGrant,
    ConsequenceRequest,
)
from autofde_lab.sa2a.brce.receipts import (
    PreparedReceipt,
    ReceiptGrantValidationError,
    ReceiptStore,
)
from autofde_lab.sa2a.conformance.courts.consequence_court import DurableDiskReceiptStore

GENESIS = "genesis:0" * 4

# The exact actuation identity grant G is legitimately issued for.
LEGIT_ACTOR = "urn:agent:receipt-store-grant-validation"
LEGIT_ACTION = "urn:action:quarantine_node"
LEGIT_TARGET = "urn:resource:cluster:node-1"

# A DIFFERENT actuation identity -- same actor, different action + target -- that a forged
# receipt will falsely claim grant G authorized.
FORGED_ACTION = "urn:action:delete_all_data"
FORGED_TARGET = "urn:resource:cluster:node-99"


def _make_grant() -> AuthorityGrant:
    return AuthorityGrant(
        grant_id="grant-afde2604-store-001",
        subject_id=LEGIT_ACTOR,
        action_iri=LEGIT_ACTION,
        target_resource_iri=LEGIT_TARGET,
    )


def _legit_prepared(*, idempotency_token: str, grant_id: str) -> PreparedReceipt:
    """A PreparedReceipt whose claimed grant_id genuinely covers its own identity."""
    return PreparedReceipt(
        prepared_id=f"prep-{idempotency_token}",
        idempotency_token=idempotency_token,
        action_iri=LEGIT_ACTION,
        target_resource=LEGIT_TARGET,
        actor_id=LEGIT_ACTOR,
        grant_id=grant_id,
        plan_digest=GENESIS,
        artifact_digest="none",
        admitted_input_digest=GENESIS,
        consequence_class="LOCAL_EFFECT",
    )


def _forged_prepared(*, idempotency_token: str, grant_id: str) -> PreparedReceipt:
    """A PreparedReceipt claiming grant_id for an identity that grant never covers -- the
    same same-label-different-identity construction
    `test_mutation_cross_court_identity.py` uses.
    """
    return PreparedReceipt(
        prepared_id=f"prep-{idempotency_token}",
        idempotency_token=idempotency_token,
        action_iri=FORGED_ACTION,
        target_resource=FORGED_TARGET,
        actor_id=LEGIT_ACTOR,
        grant_id=grant_id,  # <-- same-label-different-identity claim
        plan_digest=GENESIS,
        artifact_digest="none",
        admitted_input_digest=GENESIS,
        consequence_class="LOCAL_EFFECT",
    )


# ---------------------------------------------------------------------------
# (a) Real, matching grant is accepted -- both store variants.
# ---------------------------------------------------------------------------


def test_in_memory_store_accepts_receipt_with_real_matching_grant() -> None:
    """A broker-configured `ReceiptStore` accepts a `PreparedReceipt` whose grant_id claim
    a fresh, real `AuthorityBroker.evaluate()` call genuinely confirms for that receipt's
    own (actor_id, action_iri, target_resource).
    """
    broker = AuthorityBroker()
    grant = _make_grant()
    broker.register_grant(grant)

    store = ReceiptStore(authority_broker=broker)
    receipt = _legit_prepared(idempotency_token="idemp-legit-memory-001", grant_id=grant.grant_id)

    store.save_prepared(receipt)  # Must not raise.

    persisted = store.get_prepared(receipt.idempotency_token)
    assert persisted is not None
    assert persisted.grant_id == grant.grant_id
    assert persisted.action_iri == LEGIT_ACTION
    assert persisted.target_resource == LEGIT_TARGET


def test_disk_store_accepts_receipt_with_real_matching_grant_and_writes_real_bytes(
    tmp_path: Path,
) -> None:
    """The disk-backed `DurableDiskReceiptStore` variant accepts the same legitimate claim
    and durably commits real bytes to physical disk.
    """
    broker = AuthorityBroker()
    grant = _make_grant()
    broker.register_grant(grant)

    store_dir = tmp_path / "receipts_accepted"
    store = DurableDiskReceiptStore(store_dir, authority_broker=broker)
    receipt = _legit_prepared(idempotency_token="idemp-legit-disk-001", grant_id=grant.grant_id)

    store.save_prepared(receipt)  # Must not raise.

    disk_file = store_dir / f"prep_{receipt.idempotency_token}.json"
    assert disk_file.exists(), "Legitimate receipt must be durably committed to real disk."
    assert disk_file.stat().st_size > 0

    persisted = store.get_prepared(receipt.idempotency_token)
    assert persisted is not None
    assert persisted.grant_id == grant.grant_id


# ---------------------------------------------------------------------------
# (b) Forged/mismatched grant_id is refused when a broker IS configured -- both variants,
#     with an explicit zero-disk-mutation check for the disk-backed variant.
# ---------------------------------------------------------------------------


def test_in_memory_store_refuses_forged_grant_id_when_broker_configured() -> None:
    """A broker-configured `ReceiptStore.save_prepared` raises `ReceiptGrantValidationError`
    (typed, never silent) for a receipt whose grant_id claim the broker's real grant
    registry does not support for that receipt's own identity.
    """
    broker = AuthorityBroker()
    grant = _make_grant()
    broker.register_grant(grant)

    # Positive control, mirroring test_mutation_cross_court_identity.py: the real broker
    # itself refuses grant G for the FORGED identity when asked honestly.
    honest_decision = broker.evaluate(
        ConsequenceRequest(
            actor_id=LEGIT_ACTOR,
            action_iri=FORGED_ACTION,
            target_resource=FORGED_TARGET,
            grant_id=grant.grant_id,
        )
    )
    assert honest_decision.authorized is False
    assert honest_decision.refusal_code == REFUSED_NO_GRANT

    store = ReceiptStore(authority_broker=broker)
    forged = _forged_prepared(idempotency_token="idemp-forged-memory-001", grant_id=grant.grant_id)

    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_prepared(forged)

    err = excinfo.value
    assert err.refusal_code == REFUSED_NO_GRANT
    assert err.receipt is forged
    assert "grant_id" in err.reason

    # The forged receipt must never have entered the store.
    assert store.get_prepared(forged.idempotency_token) is None
    assert store.has_idempotency_token(forged.idempotency_token) is False


def test_disk_store_refuses_forged_grant_id_with_zero_disk_mutation(tmp_path: Path) -> None:
    """The disk-backed variant refuses the identical forged claim and, critically, never
    writes the forged receipt to physical disk -- the refusal happens in
    `ReceiptStore.save_prepared` (the base class), which `DurableDiskReceiptStore
    .save_prepared` calls via `super().save_prepared(receipt)` BEFORE performing any disk
    I/O of its own (see `src/autofde_lab/sa2a/conformance/courts/consequence_court.py`), so
    a raised exception there means the disk write is never reached.
    """
    broker = AuthorityBroker()
    grant = _make_grant()
    broker.register_grant(grant)

    store_dir = tmp_path / "receipts_refused"
    store = DurableDiskReceiptStore(store_dir, authority_broker=broker)
    forged = _forged_prepared(idempotency_token="idemp-forged-disk-001", grant_id=grant.grant_id)

    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_prepared(forged)

    assert excinfo.value.refusal_code == REFUSED_NO_GRANT

    disk_file = store_dir / f"prep_{forged.idempotency_token}.json"
    assert not disk_file.exists(), (
        "A forged receipt refused by the store-layer grant check must never reach physical "
        "disk -- zero disk mutation on refusal."
    )
    assert store.get_prepared(forged.idempotency_token) is None


def test_unregistered_grant_id_is_refused_not_a_lookup_error() -> None:
    """A grant_id that references no registered grant at all (not merely a mismatched one)
    is refused the same way -- `AuthorityBroker.evaluate()` itself returns a typed
    `REFUSED_NO_GRANT` decision rather than raising, and the store surfaces that as the
    same typed `ReceiptGrantValidationError`.
    """
    broker = AuthorityBroker()  # Zero grants registered.
    store = ReceiptStore(authority_broker=broker)
    receipt = _legit_prepared(idempotency_token="idemp-no-such-grant-001", grant_id="grant-does-not-exist")

    with pytest.raises(ReceiptGrantValidationError) as excinfo:
        store.save_prepared(receipt)

    assert excinfo.value.refusal_code == REFUSED_NO_GRANT
    assert store.get_prepared(receipt.idempotency_token) is None


# ---------------------------------------------------------------------------
# (c) Backward compatibility: no broker configured -> zero regression, for every existing
#     caller's construction pattern.
# ---------------------------------------------------------------------------


def test_in_memory_store_without_broker_behaves_exactly_as_before() -> None:
    """`ReceiptStore()` -- the exact zero-argument construction every existing caller in
    this repo uses (grep evidence in this session's closure note) -- accepts the identical
    forged receipt with zero exception and zero cross-check, exactly as before this
    session's fix. This is the explicit backward-compatibility guard the task requires.
    """
    store = ReceiptStore()  # No authority_broker -- the pre-existing default.
    forged = _forged_prepared(
        idempotency_token="idemp-forged-no-broker-memory-001",
        grant_id="grant-any-string-at-all",
    )

    store.save_prepared(forged)  # Must NOT raise -- zero validation without a broker.

    persisted = store.get_prepared(forged.idempotency_token)
    assert persisted is not None
    assert persisted.grant_id == "grant-any-string-at-all"
    assert persisted.action_iri == FORGED_ACTION
    assert persisted.target_resource == FORGED_TARGET


def test_disk_store_without_broker_behaves_exactly_as_before(tmp_path: Path) -> None:
    """`DurableDiskReceiptStore(store_dir)` -- the exact single-positional-argument
    construction every existing caller in this repo uses (13 call sites as of this
    session, per grep) -- accepts the identical forged receipt with zero exception and
    durably commits it to disk, exactly as
    `test_mutation_cross_court_identity.py`'s Test 1 already pins. Re-proven here as this
    new file's own regression guard, using this file's own fixtures.
    """
    store_dir = tmp_path / "receipts_no_broker"
    store = DurableDiskReceiptStore(store_dir)  # No authority_broker -- the pre-existing API.
    forged = _forged_prepared(
        idempotency_token="idemp-forged-no-broker-disk-001",
        grant_id="grant-any-string-at-all",
    )

    store.save_prepared(forged)  # Must NOT raise -- zero validation without a broker.

    disk_file = store_dir / f"prep_{forged.idempotency_token}.json"
    assert disk_file.exists(), "Without a broker, the store's pre-existing dumb, append-only persistence is unchanged."

    persisted = store.get_prepared(forged.idempotency_token)
    assert persisted is not None
    assert persisted.grant_id == "grant-any-string-at-all"
    assert persisted.action_iri == FORGED_ACTION
    assert persisted.target_resource == FORGED_TARGET
