# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""UNIT checkpoint for single-hop preserve maps. Structure only -- nothing
here actuates, admits, brokers, or issues receipts."""

import pytest

from skdecide.agent.replan import (
    Epoch,
    Ledger,
    LedgerEntry,
    OccurrenceStatus,
    PreserveMap,
    ReplanningMode,
    ReplanRefusal,
    ReplanError,
    activity_of,
    infer_preserve_map,
    leaf_paths,
    redo_occurrence_key,
    seed_marking,
    validate_preserve_map,
)
from skdecide.powl.algebra import Atom, OrderEdge, PartialOrder
from skdecide.powl.executor import enabled, fire
from skdecide.powl.identity import OccurrenceKey


def _po(labels, edges=()):
    return PartialOrder(
        tuple(Atom(l) for l in labels),
        frozenset(OrderEdge(a, b) for a, b in edges),
    )


def _ledger(model, paths, epoch=0, status=OccurrenceStatus.COMPLETED, resumable=False):
    counts = {}
    entries = []
    for p in paths:
        act = activity_of(model.children[p[0]] if len(p) == 1 else None) if False else activity_of(
            _node_at(model, p)
        )
        i = counts.get(act, 0)
        counts[act] = i + 1
        entries.append(
            LedgerEntry(OccurrenceKey(act, i, ""), p, status, epoch, resumable)
        )
    return Ledger(tuple(entries))


def _node_at(model, path):
    n = model
    for i in path:
        n = n.children[i]
    return n


def test_modes_are_the_nine_named():
    assert {m.value for m in ReplanningMode} == {
        "Continue", "Repair", "Replan", "Reschedule", "UpdatePolicy",
        "LearnModel", "SpawnChild", "Terminate", "Refuse",
    }


def test_infer_maps_unambiguous_and_seed_removes_from_enabled():
    m0 = _po(["triage", "collect", "scope"])
    m1 = _po(["triage", "collect", "scope"])
    ledger = _ledger(m0, [(0,)])
    pm = infer_preserve_map(Epoch(0, m0), ledger, m1)
    assert set(pm.entries) == {(0,)}
    validate_preserve_map(m1, pm, ledger)
    mk = seed_marking(m1, pm)
    assert (0,) not in enabled(m1, mk)
    assert enabled(m1, mk) == {(1,), (2,)}


def test_ambiguous_match_is_left_unmapped_not_guessed():
    m0 = _po(["a", "b"])
    # POWL1 has TWO nodes carrying activity "a" for ONE prior occurrence
    m1 = _po(["a", "a", "b"])
    ledger = _ledger(m0, [(0,)])
    pm = infer_preserve_map(Epoch(0, m0), ledger, m1)
    assert pm.entries == {}


def test_004_not_downward_closed():
    m1 = _po(["a", "b"], edges=[(0, 1)])
    act = activity_of(m1.children[1])
    key = OccurrenceKey(act, 0, "")
    ledger = Ledger((LedgerEntry(key, (1,), OccurrenceStatus.COMPLETED, 0),))
    pm = PreserveMap(entries={(1,): key})
    with pytest.raises(ReplanError) as e:
        validate_preserve_map(m1, pm, ledger)
    assert e.value.refusal is ReplanRefusal.NOT_DOWNWARD_CLOSED


def test_005_intended_only_is_not_an_observation():
    m1 = _po(["a", "b"])
    act = activity_of(m1.children[0])
    key = OccurrenceKey(act, 0, "")
    ledger = Ledger((LedgerEntry(key, (0,), OccurrenceStatus.INTENDED, 0),))
    with pytest.raises(ReplanError) as e:
        validate_preserve_map(m1, PreserveMap(entries={(0,): key}), ledger)
    assert e.value.refusal is ReplanRefusal.OCCURRENCE_NOT_IN_LEDGER


def test_005_absent_from_ledger():
    m1 = _po(["a", "b"])
    key = OccurrenceKey(activity_of(m1.children[0]), 0, "")
    with pytest.raises(ReplanError) as e:
        validate_preserve_map(m1, PreserveMap(entries={(0,): key}), Ledger(()))
    assert e.value.refusal is ReplanRefusal.OCCURRENCE_NOT_IN_LEDGER


def test_006_unresumable_torn_fire():
    m1 = _po(["a", "b"])
    key = OccurrenceKey(activity_of(m1.children[0]), 0, "")
    ledger = Ledger((LedgerEntry(key, (0,), OccurrenceStatus.TORN, 0, resumable=False),))
    with pytest.raises(ReplanError) as e:
        validate_preserve_map(m1, PreserveMap(entries={(0,): key}), ledger)
    assert e.value.refusal is ReplanRefusal.UNRESUMABLE_TORN_FIRE
    # resumable torn fire is admissible
    ok = Ledger((LedgerEntry(key, (0,), OccurrenceStatus.TORN, 0, resumable=True),))
    validate_preserve_map(m1, PreserveMap(entries={(0,): key}), ok)


def test_redo_without_justification_refuses():
    m1 = _po(["a", "b"])
    with pytest.raises(ReplanError) as e:
        validate_preserve_map(m1, PreserveMap(redo=frozenset({(0,)})), Ledger(()))
    assert e.value.refusal is ReplanRefusal.REDO_WITHOUT_JUSTIFICATION


def test_non_adjacent_epoch_refuses():
    m1 = _po(["a", "b"])
    pm = PreserveMap(from_epoch=0, to_epoch=2)
    with pytest.raises(ReplanError) as e:
        validate_preserve_map(m1, pm, Ledger(()))
    assert e.value.refusal is ReplanRefusal.NON_ADJACENT_EPOCH


def test_redo_is_legal_and_gets_a_fresh_rising_occurrence_index():
    m0 = _po(["revoke", "other"])
    m1 = _po(["revoke", "other"])
    act = activity_of(m1.children[0])
    prior = OccurrenceKey(act, 0, "")
    ledger = Ledger((LedgerEntry(prior, (0,), OccurrenceStatus.COMPLETED, 0),))
    pm = PreserveMap(
        entries={},
        redo=frozenset({(0,)}),
        redo_justification={(0,): "population B appeared after the revoke"},
    )
    validate_preserve_map(m1, pm, ledger)
    fresh = redo_occurrence_key(m1, ledger, (0,))
    assert fresh.occurrence_index == 1
    assert fresh != prior

    # and the executor, seeded with the prior key, derives the same index
    seeded = seed_marking(m1, PreserveMap(entries={(1,): OccurrenceKey(
        activity_of(m1.children[1]), 0, "")}))
    # seed_marking only carries what is preserved; add the prior key by hand
    from dataclasses import replace as _replace
    seeded = _replace(seeded, completed=seeded.completed | {prior})
    after = fire(m1, seeded, (0,))
    got = [k for k in after.completed if k.activity_sha256 == act]
    assert sorted(k.occurrence_index for k in got) == [0, 1]
