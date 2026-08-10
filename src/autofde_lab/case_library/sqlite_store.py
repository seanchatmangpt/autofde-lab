# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SQLite persistence for :class:`~autofde_lab.case_library.model.Case`.

Style mirrors ``autofde_lab.ocel.sqlite_store`` and
``autofde_lab.fabric.cache.SQLiteERRCCache``: stdlib ``sqlite3``,
``sqlite3.connect(path, check_same_thread=False)``, ``row_factory =
sqlite3.Row``, idempotent ``CREATE TABLE IF NOT EXISTS``, a
``_transaction()`` contextmanager, and a ``:memory:``-first design -- a
fresh, unrelated schema (this is not OCEL data), reusing only the
persistence *pattern*.

Schema:

.. code-block:: sql

    CREATE TABLE cases(
        case_id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        anomalous_kinds_json TEXT NOT NULL,
        diverged_fields_json TEXT NOT NULL,
        diagnosis TEXT NOT NULL,
        mitigation_commands_json TEXT NOT NULL,
        outcome INTEGER
    );

``anomalous_kinds_json``/``diverged_fields_json``/``mitigation_commands_json``
each hold a JSON array (``json.dumps(sorted(...))`` for the two feature
sets, so the on-disk representation is deterministic across writes of the
same case). ``outcome`` is stored as SQLite's native tri-state: ``1`` for
``True``, ``0`` for ``False``, SQL ``NULL`` for Python ``None`` -- never
coerced to a boolean at the boundary, matching
``.claude/rules/absence-is-not-evidence.md``.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from autofde_lab.case_library.model import Case, ProblemSignature

__all__ = ["CaseLibraryStore"]


def _initialize(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS cases("
        "case_id TEXT PRIMARY KEY, "
        "namespace TEXT NOT NULL, "
        "anomalous_kinds_json TEXT NOT NULL, "
        "diverged_fields_json TEXT NOT NULL, "
        "diagnosis TEXT NOT NULL, "
        "mitigation_commands_json TEXT NOT NULL, "
        "outcome INTEGER"
        ")"
    )


@contextmanager
def _transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _case_to_row(case: Case) -> tuple[str, str, str, str, str, str, int | None]:
    return (
        case.case_id,
        case.signature.namespace,
        json.dumps(sorted(case.signature.anomalous_kinds)),
        json.dumps(sorted(case.signature.diverged_fields)),
        case.diagnosis,
        json.dumps(list(case.mitigation_commands)),
        None if case.outcome is None else int(case.outcome),
    )


def _row_to_case(row: sqlite3.Row) -> Case:
    outcome_raw = row["outcome"]
    return Case(
        case_id=row["case_id"],
        signature=ProblemSignature(
            namespace=row["namespace"],
            anomalous_kinds=frozenset(json.loads(row["anomalous_kinds_json"])),
            diverged_fields=frozenset(json.loads(row["diverged_fields_json"])),
        ),
        diagnosis=row["diagnosis"],
        mitigation_commands=tuple(json.loads(row["mitigation_commands_json"])),
        outcome=None if outcome_raw is None else bool(outcome_raw),
    )


class CaseLibraryStore:
    """A persistent, SQLite-backed store of :class:`Case` records.

    :param path: Filesystem path to the SQLite database, or ``":memory:"``.
        Parent directories are created if missing (so the documented default
        of ``docs/case_library/cases.sqlite`` works on first use without a
        separate mkdir step).
    """

    def __init__(self, path: str | Path = "docs/case_library/cases.sqlite") -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        _initialize(self._connection)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CaseLibraryStore":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def put(self, case: Case) -> None:
        """Insert or replace ``case`` (keyed by ``case.case_id``)."""
        with _transaction(self._connection) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cases("
                "case_id, namespace, anomalous_kinds_json, diverged_fields_json, "
                "diagnosis, mitigation_commands_json, outcome"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                _case_to_row(case),
            )

    def get(self, case_id: str) -> Case | None:
        """Return the case stored under ``case_id``, or ``None`` if absent."""
        cursor = self._connection.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        )
        row = cursor.fetchone()
        return None if row is None else _row_to_case(row)

    def all_cases(self) -> list[Case]:
        """Return every stored case, ordered by ``case_id`` for determinism."""
        cursor = self._connection.execute("SELECT * FROM cases ORDER BY case_id")
        return [_row_to_case(row) for row in cursor.fetchall()]

    def __len__(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(*) AS n FROM cases")
        return int(cursor.fetchone()["n"])
