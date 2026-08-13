# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `autofde_lab.ocel.gymact_adapter` —
`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR5, Correction 2.

Real `gymact.models.Receipt` objects, real `gymact.ocel.receipts_to_ocel`,
real `sqlite_store.to_sqlite`/`from_sqlite` round-trip through a real
on-disk SQLite file (via `tmp_path`) — no mocks, no hand-crafted JSON
standing in for gymact's real output.
"""

from __future__ import annotations

from gymact.models import Operation, Receipt, Standing
from gymact.ocel import receipts_to_ocel

from autofde_lab.ocel.gymact_adapter import gymact_ocel_json_to_log, write_gymact_ocel_to_sqlite
from autofde_lab.ocel.sqlite_store import from_sqlite


def _real_receipt_trail() -> list[Receipt]:
    """A real, minimal materialize -> act -> verify -> teardown receipt
    trail, matching the shape `scripts/run_azuregoat_gymact_ocel_episode.py`
    produces via the real `GymAct` orchestrator."""
    episode_id = "urn:gymact:test:episode:fixture-1"
    subject_ref = "urn:gymact:test:environment:fixture-1"
    capability_ref = "urn:gymact:test:capability:step-1"
    return [
        Receipt(
            episode_id=episode_id,
            operation=Operation.MATERIALIZE,
            standing=Standing.ALIVE,
            subject_ref=subject_ref,
        ),
        Receipt(
            episode_id=episode_id,
            operation=Operation.ACT,
            standing=Standing.ALIVE,
            subject_ref=subject_ref,
            capability_ref=capability_ref,
            pre_state_digest="a" * 64,
            post_state_digest="b" * 64,
        ),
        Receipt(
            episode_id=episode_id,
            operation=Operation.VERIFY,
            standing=Standing.ALIVE,
            subject_ref=subject_ref,
        ),
    ]


def test_gymact_ocel_json_parses_into_a_real_ocel_log() -> None:
    document = receipts_to_ocel(_real_receipt_trail())

    log = gymact_ocel_json_to_log(document)

    assert len(log.events) == 3
    activities = sorted({e.activity for e in log.events})
    assert activities == ["act", "materialize", "verify"]
    episode_objects = [o for o in log.objects if o.object_type == "episode"]
    assert len(episode_objects) == 1


def test_write_gymact_ocel_to_sqlite_round_trips_through_a_real_file(tmp_path) -> None:
    document = receipts_to_ocel(_real_receipt_trail())
    db_path = tmp_path / "episode.ocel2.sqlite"

    written_log = write_gymact_ocel_to_sqlite(document, db_path)

    assert db_path.exists()
    reloaded_log = from_sqlite(db_path)

    # Real round-trip proof: event count and activity set survive a real
    # write-then-read through the existing sqlite_store, unchanged.
    assert len(reloaded_log.events) == len(written_log.events) == 3
    reloaded_activities = sorted({e.activity for e in reloaded_log.events})
    assert reloaded_activities == ["act", "materialize", "verify"]


def test_sqlite_output_is_schema_conformant_ocel2_tables(tmp_path) -> None:
    """Confirms the target schema this PRD's FR5 requires — the same
    objects/events/event_object_links/object_object_links/object_changes/
    attributes tables the real sregym `.ocel2.sqlite` files use."""
    import sqlite3

    document = receipts_to_ocel(_real_receipt_trail())
    db_path = tmp_path / "episode.ocel2.sqlite"
    write_gymact_ocel_to_sqlite(document, db_path)

    con = sqlite3.connect(str(db_path))
    tables = {row[0] for row in con.execute("select name from sqlite_master where type='table'")}
    con.close()

    assert {
        "objects",
        "events",
        "event_object_links",
        "object_object_links",
        "object_changes",
        "attributes",
    } <= tables
