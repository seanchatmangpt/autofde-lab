# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Two-phase (write-ahead) occurrence ledger.

Why two phases and not one
--------------------------
A single ``record(occurrence)`` written *after* an act cannot distinguish two
crash states that demand opposite recoveries:

* the act happened and the record was lost — resuming re-executes it;
* the act never happened — refusing to resume strands work that was never done.

Guessing either way corrupts the no-re-execution guarantee. So :meth:`intend`
writes an ``INTENDED`` record **before** the act and :meth:`commit` writes
``COMMITTED`` after. An ``INTENDED`` with no matching ``COMMITTED`` is exactly
the unknown state, and the only sound response is to refuse to resume
(``SKD-AGENT-006``) and hand the decision to something with more standing than
this runtime has.

Nothing here actuates or admits. A record is a note about a candidate-plan
traversal, not a receipt for a change to the world.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Sequence

from skdecide.agent.refusals import AgentRefusal, AgentRefusalCode
from skdecide.fabric.canonical import sha256
from skdecide.powl.identity import OccurrenceKey

__all__ = [
    "LedgerPhase",
    "IntentToken",
    "LedgerRecord",
    "OccurrenceLedger",
]


class LedgerPhase(StrEnum):
    """The two phases of a write-ahead occurrence record."""

    INTENDED = "INTENDED"
    COMMITTED = "COMMITTED"


@dataclass(frozen=True, slots=True)
class IntentToken:
    """Handle to an ``INTENDED`` record awaiting its ``COMMITTED`` counterpart."""

    token_id: str
    sequence: int
    path: tuple[int, ...]
    context_sha256: str


@dataclass(frozen=True, slots=True)
class LedgerRecord:
    """One append-only ledger line."""

    sequence: int
    phase: LedgerPhase
    token_id: str
    path: tuple[int, ...]
    context_sha256: str
    activity_sha256: str
    occurrence_index: int | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "phase": self.phase.value,
            "token_id": self.token_id,
            "path": list(self.path),
            "context_sha256": self.context_sha256,
            "activity_sha256": self.activity_sha256,
            "occurrence_index": self.occurrence_index,
            "detail": self.detail,
        }


def _token_id(sequence: int, path: tuple[int, ...], context_sha256: str) -> str:
    return sha256(
        {
            "sequence": sequence,
            "path": list(path),
            "context_sha256": context_sha256,
        }
    )


class OccurrenceLedger:
    """Append-only, two-phase ledger of traversal occurrences."""

    __slots__ = ("_records",)

    def __init__(self, records: Sequence[LedgerRecord] = ()) -> None:
        self._records: list[LedgerRecord] = list(records)

    # ── phase 1 ────────────────────────────────────────────────────────────

    def intend(
        self,
        path: tuple[int, ...],
        context_sha256: str = "",
        *,
        activity_sha256: str = "",
        detail: str = "",
    ) -> IntentToken:
        """Write the ``INTENDED`` record. Must precede the act it describes."""
        outstanding = self.outstanding()
        if outstanding:
            raise AgentRefusal(
                AgentRefusalCode.INTENT_ALREADY_OUTSTANDING,
                "an intent is already outstanding; commit it before intending again",
                details={"outstanding": [t.token_id for t in outstanding]},
            )
        sequence = len(self._records)
        path = tuple(int(i) for i in path)
        token = IntentToken(
            token_id=_token_id(sequence, path, context_sha256),
            sequence=sequence,
            path=path,
            context_sha256=context_sha256,
        )
        self._records.append(
            LedgerRecord(
                sequence=sequence,
                phase=LedgerPhase.INTENDED,
                token_id=token.token_id,
                path=path,
                context_sha256=context_sha256,
                activity_sha256=activity_sha256,
                occurrence_index=None,
                detail=detail,
            )
        )
        return token

    # ── phase 2 ────────────────────────────────────────────────────────────

    def commit(
        self,
        token: IntentToken,
        outcome: Any = None,
        *,
        activity_sha256: str | None = None,
        detail: str = "",
    ) -> OccurrenceKey:
        """Write the ``COMMITTED`` record for ``token`` and return its key.

        ``activity_sha256`` is supplied by the caller because the ledger does not
        hold the model. When absent it falls back to a structural stand-in
        derived from the path, and the record says so in ``detail``.
        """
        if token.token_id not in {t.token_id for t in self.outstanding()}:
            raise AgentRefusal(
                AgentRefusalCode.UNKNOWN_INTENT_TOKEN,
                "commit() for a token that is not outstanding",
                details={"token_id": token.token_id},
            )
        if activity_sha256 is None:
            intended = self._by_token(token.token_id, LedgerPhase.INTENDED)
            activity_sha256 = intended.activity_sha256 or sha256(
                {"path": list(token.path)}
            )
            if not intended.activity_sha256:
                detail = (detail + " ACTIVITY_FROM_PATH").strip()
        occurrence_index = sum(
            1
            for r in self._records
            if r.phase is LedgerPhase.COMMITTED and r.activity_sha256 == activity_sha256
        )
        if outcome is not None:
            detail = (detail + f" outcome={outcome!s}").strip()
        self._records.append(
            LedgerRecord(
                sequence=len(self._records),
                phase=LedgerPhase.COMMITTED,
                token_id=token.token_id,
                path=token.path,
                context_sha256=token.context_sha256,
                activity_sha256=activity_sha256,
                occurrence_index=occurrence_index,
                detail=detail,
            )
        )
        return OccurrenceKey(activity_sha256, occurrence_index, token.context_sha256)

    # ── reads ──────────────────────────────────────────────────────────────

    def _by_token(self, token_id: str, phase: LedgerPhase) -> LedgerRecord:
        for record in self._records:
            if record.token_id == token_id and record.phase is phase:
                return record
        raise AgentRefusal(
            AgentRefusalCode.UNKNOWN_INTENT_TOKEN,
            f"no {phase.value} record for token",
            details={"token_id": token_id},
        )

    def records(self) -> tuple[LedgerRecord, ...]:
        """Every line, in append order."""
        return tuple(self._records)

    def outstanding(self) -> tuple[IntentToken, ...]:
        """Tokens with an ``INTENDED`` record and no ``COMMITTED`` counterpart."""
        committed = {
            r.token_id for r in self._records if r.phase is LedgerPhase.COMMITTED
        }
        return tuple(
            IntentToken(r.token_id, r.sequence, r.path, r.context_sha256)
            for r in self._records
            if r.phase is LedgerPhase.INTENDED and r.token_id not in committed
        )

    def occurrences(self) -> tuple[OccurrenceKey, ...]:
        """Committed occurrences, in commit order. Intents are never included."""
        return tuple(
            OccurrenceKey(
                r.activity_sha256,
                int(r.occurrence_index or 0),
                r.context_sha256,
            )
            for r in self._records
            if r.phase is LedgerPhase.COMMITTED
        )

    def is_resumable(self) -> bool:
        """False when any intent is unresolved — i.e. recovery state is UNKNOWN."""
        return not self.outstanding()

    def assert_resumable(self) -> None:
        """Refuse ``SKD-AGENT-006`` when an ``INTENDED`` has no ``COMMITTED``.

        Never repaired by assuming either outcome: "acted, did not record" and
        "did not act" are indistinguishable from here, and both repairs are
        wrong half the time.
        """
        outstanding = self.outstanding()
        if outstanding:
            raise AgentRefusal(
                AgentRefusalCode.LEDGER_UNRESUMABLE,
                "ledger has INTENDED records with no COMMITTED counterpart; "
                "recovery state is UNKNOWN and the session refuses to resume",
                details={
                    "outstanding": [
                        {"token_id": t.token_id, "path": list(t.path)}
                        for t in outstanding
                    ]
                },
            )

    def sha256(self) -> str:
        """Content hash over every line."""
        return sha256([r.as_dict() for r in self._records])

    @classmethod
    def from_records(cls, records: Iterable[LedgerRecord]) -> OccurrenceLedger:
        """Rehydrate from persisted lines (does **not** validate resumability)."""
        return cls(list(records))

    def __len__(self) -> int:
        return len(self._records)
