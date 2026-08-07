# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The two ledgers are one ledger.

``skdecide.agent.ledger.OccurrenceLedger`` is the write-ahead record;
``skdecide.agent.replan.Ledger`` is the read view a reuse claim is validated
against. Before this module they were unrelated types that nothing reconciled,
so the central guarantee -- *an intention is not an observation* -- held only
for hand-built views and was never checked against the WAL that a live session
actually writes.

Nothing here actuates, admits, brokers, or issues receipts.
"""

import pytest

from skdecide.agent.ledger import LedgerPhase, OccurrenceLedger
from skdecide.agent.replan import (
    Ledger,
    OccurrenceStatus,
    PreserveMap,
    ReplanError,
    ReplanRefusal,
    activity_of,
    as_ledger,
    validate_preserve_map,
)
from skdecide.powl.algebra import Atom, PartialOrder


def _model():
    return PartialOrder((Atom("a"), Atom("b")), frozenset())


def _wal_with_one_committed():
    model = _model()
    wal = OccurrenceLedger()
    activity = activity_of(model.children[0])
    token = wal.intend((0,), "ctx", activity_sha256=activity, activity="a")
    key = wal.commit(token, activity_sha256=activity)
    return model, wal, key


def _wal_with_only_intended():
    model = _model()
    wal = OccurrenceLedger()
    activity = activity_of(model.children[0])
    wal.intend((0,), "ctx", activity_sha256=activity, activity="a")
    return model, wal, activity


# ── the projection itself ────────────────────────────────────────────────────


def test_committed_wal_lines_project_to_COMPLETED_view_entries():
    model, wal, key = _wal_with_one_committed()
    view = Ledger.from_occurrence_ledger(wal)
    assert [e.status for e in view.entries] == [OccurrenceStatus.COMPLETED]
    assert view.find(key, 0) is not None


def test_outstanding_intent_projects_as_INTENDED_not_as_absent():
    """The refusal must be able to name it, so it must survive the projection."""
    _model_, wal, activity = _wal_with_only_intended()
    view = Ledger.from_occurrence_ledger(wal)
    assert [e.status for e in view.entries] == [OccurrenceStatus.INTENDED]
    assert view.entries[0].key.activity_sha256 == activity
    # ... and it is NOT counted as prior completion, so a redo index is 0
    assert view.completed_count(activity) == 0


def test_committed_only_view_drops_the_intended_line_entirely():
    _model_, wal, _activity = _wal_with_only_intended()
    assert Ledger.from_occurrence_ledger(wal, committed_only=True).entries == ()


def test_as_ledger_accepts_both_types_and_refuses_a_third():
    _model_, wal, _k = _wal_with_one_committed()
    assert isinstance(as_ledger(wal), Ledger)
    view = Ledger(())
    assert as_ledger(view) is view
    with pytest.raises(TypeError):
        as_ledger(object())


# ── the guarantee that had no test ───────────────────────────────────────────


def _intended_only_preserve_map(model, wal):
    """A preserve map naming the occurrence key an INTENDED line would take."""
    view = Ledger.from_occurrence_ledger(wal)
    (entry,) = view.entries
    return PreserveMap(entries={(0,): entry.key}, from_epoch=0, to_epoch=1)


def test_preserve_map_against_a_COMMITTED_only_view_rejects_an_INTENDED_occurrence():
    """The guarantee: intent is never preservable, even via the live WAL.

    Validated against the committed-only view, the occurrence is simply not
    there -- the reuse claim rests on nothing.
    """
    model, wal, _activity = _wal_with_only_intended()
    pm = _intended_only_preserve_map(model, wal)
    committed_only = Ledger.from_occurrence_ledger(wal, committed_only=True)
    with pytest.raises(ReplanError) as excinfo:
        validate_preserve_map(model, pm, committed_only)
    assert excinfo.value.refusal is ReplanRefusal.OCCURRENCE_NOT_IN_LEDGER


def test_preserve_map_against_the_full_view_rejects_it_by_name():
    """Same rejection, better reason: recorded, but only as an intention."""
    model, wal, _activity = _wal_with_only_intended()
    pm = _intended_only_preserve_map(model, wal)
    with pytest.raises(ReplanError) as excinfo:
        validate_preserve_map(model, pm, Ledger.from_occurrence_ledger(wal))
    assert excinfo.value.refusal is ReplanRefusal.OCCURRENCE_NOT_IN_LEDGER
    assert "INTENDED" in excinfo.value.detail


def test_validate_accepts_the_WAL_object_directly():
    """replan.py consumes the WAL; no caller has to convert by hand."""
    model, wal, key = _wal_with_one_committed()
    pm = PreserveMap(entries={(0,): key}, from_epoch=0, to_epoch=1)
    validate_preserve_map(model, pm, wal)  # does not raise


def test_the_same_WAL_rejects_once_the_commit_is_removed():
    """Guard against a vacuous pass: the accepting case must be load-bearing."""
    model, wal, key = _wal_with_one_committed()
    intended_only = OccurrenceLedger.from_records(
        [r for r in wal.records() if r.phase is LedgerPhase.INTENDED]
    )
    pm = PreserveMap(entries={(0,): key}, from_epoch=0, to_epoch=1)
    with pytest.raises(ReplanError) as excinfo:
        validate_preserve_map(model, pm, intended_only)
    assert excinfo.value.refusal is ReplanRefusal.OCCURRENCE_NOT_IN_LEDGER
