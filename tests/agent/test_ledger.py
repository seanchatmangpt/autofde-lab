# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for the two-phase occurrence ledger.

Real objects throughout — no mocks, no patched internals.
"""

from __future__ import annotations

import pytest

from skdecide.agent.ledger import LedgerPhase, OccurrenceLedger
from skdecide.agent.refusals import AgentRefusal, AgentRefusalCode


def test_intend_writes_before_commit_and_commit_appends():
    ledger = OccurrenceLedger()
    token = ledger.intend((0,), "ctx")

    records = ledger.records()
    assert len(records) == 1
    assert records[0].phase is LedgerPhase.INTENDED
    assert ledger.occurrences() == ()  # an intent is not an occurrence

    key = ledger.commit(token, activity_sha256="a" * 64)
    assert ledger.records()[1].phase is LedgerPhase.COMMITTED
    assert key.activity_sha256 == "a" * 64
    assert key.occurrence_index == 0
    assert ledger.occurrences() == (key,)


def test_occurrence_index_rises_per_activity():
    ledger = OccurrenceLedger()
    keys = []
    for step in range(3):
        token = ledger.intend((step,), "ctx")
        keys.append(ledger.commit(token, activity_sha256="a" * 64))
    assert [k.occurrence_index for k in keys] == [0, 1, 2]


def test_intended_without_committed_refuses_to_resume():
    ledger = OccurrenceLedger()
    ledger.intend((0,), "ctx")  # crash right here: acted? did not act? UNKNOWN

    assert ledger.is_resumable() is False
    with pytest.raises(AgentRefusal) as excinfo:
        ledger.assert_resumable()
    assert excinfo.value.code is AgentRefusalCode.LEDGER_UNRESUMABLE
    assert "SKD-AGENT-006" in str(excinfo.value)


def test_a_session_refuses_to_open_on_an_unresumable_ledger():
    from skdecide.hub.domain.maze import Maze

    from skdecide.agent.session import AgentSession

    ledger = OccurrenceLedger()
    ledger.intend((0,), "ctx")

    with pytest.raises(AgentRefusal) as excinfo:
        AgentSession(Maze(), ledger=ledger)
    assert excinfo.value.code is AgentRefusalCode.LEDGER_UNRESUMABLE


def test_resume_is_allowed_once_the_intent_is_resolved():
    ledger = OccurrenceLedger()
    token = ledger.intend((0,), "ctx")
    ledger.commit(token, activity_sha256="b" * 64)
    ledger.assert_resumable()  # must not raise
    assert ledger.is_resumable() is True


def test_commit_of_an_unknown_token_is_refused():
    ledger = OccurrenceLedger()
    token = ledger.intend((0,), "ctx")
    ledger.commit(token, activity_sha256="c" * 64)

    with pytest.raises(AgentRefusal) as excinfo:
        ledger.commit(token, activity_sha256="c" * 64)  # double commit
    assert excinfo.value.code is AgentRefusalCode.UNKNOWN_INTENT_TOKEN


def test_second_intent_while_one_is_outstanding_is_refused():
    ledger = OccurrenceLedger()
    ledger.intend((0,), "ctx")
    with pytest.raises(AgentRefusal) as excinfo:
        ledger.intend((1,), "ctx")
    assert excinfo.value.code is AgentRefusalCode.INTENT_ALREADY_OUTSTANDING


def test_ledger_digest_changes_when_a_record_is_appended():
    ledger = OccurrenceLedger()
    empty = ledger.sha256()
    token = ledger.intend((0,), "ctx")
    intended = ledger.sha256()
    ledger.commit(token, activity_sha256="d" * 64)
    committed = ledger.sha256()
    assert len({empty, intended, committed}) == 3


def test_rehydrated_ledger_preserves_outstanding_state():
    ledger = OccurrenceLedger()
    ledger.intend((0,), "ctx")
    revived = OccurrenceLedger.from_records(ledger.records())
    assert [t.token_id for t in revived.outstanding()] == [
        t.token_id for t in ledger.outstanding()
    ]
    with pytest.raises(AgentRefusal):
        revived.assert_resumable()
