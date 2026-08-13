# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reconciles `gymact.ocel`'s JSON-only OCEL producer with
`autofde_lab.ocel`'s JSON+SQLite producer — `docs/jira/v26.8.12/cloud-cert-
wbpr-prd.md` FR5, Correction 2.

Confirmed (5-agent audit, 2026-08-12): `gymact.ocel.receipts_to_ocel` and
`autofde_lab.ocel.log.OcelLog`/`sqlite_store.py` are two independent
producers with no bridge between them — every `*goat` episode script uses
the former (JSON only); the real `docs/ocel/sregym/*.ocel2.sqlite` files
were produced by the latter. Rather than reimplementing a second SQLite
writer inside `gymact` (which would duplicate `sqlite_store.py`'s schema
logic and risk drifting from it), this module routes gymact's real OCEL 2.0
JSON output through `OcelLog.from_ocel2_json` — the same interchange
projection `autofde_lab.ocel.log` already uses for every other OCEL source
— then reuses the existing, real `sqlite_store.to_sqlite` unchanged.

`gymact.ocel`'s output uses the literal OCEL 2.0 JSON Schema key names
(`eventTypes`/`objectTypes`/`events`/`objects`) — the same keys
`OcelLog.from_ocel2_json` already parses, confirmed by direct read of both
modules — so no field-renaming layer is needed, only the two real calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.sqlite_store import to_sqlite

__all__ = ["gymact_ocel_json_to_log", "write_gymact_ocel_to_sqlite"]


def gymact_ocel_json_to_log(gymact_ocel_document: dict[str, Any]) -> OcelLog:
    """Parse a real `gymact.ocel.receipts_to_ocel(...)` (or
    `write_ocel_log`'s first return value) document into the shared
    `OcelLog` working form.
    """
    return OcelLog.from_ocel2_json(gymact_ocel_document)


def write_gymact_ocel_to_sqlite(gymact_ocel_document: dict[str, Any], path: str | Path) -> OcelLog:
    """Parse a real gymact OCEL JSON document and write it to a real
    OCEL 2.0 SQLite database at `path`, via the existing, real
    `sqlite_store.to_sqlite` — no new SQLite-writing logic. Returns the
    parsed `OcelLog` so a caller can also inspect/digest it without a
    second parse.
    """
    log = gymact_ocel_json_to_log(gymact_ocel_document)
    to_sqlite(log, path)
    return log
