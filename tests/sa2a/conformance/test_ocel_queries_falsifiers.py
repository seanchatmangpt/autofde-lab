# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Falsifier suite for the OCEL 2.0 Conformance Query Engine (RFC-SA2A-002 v26.9.16).

Companion to ``test_ocel_queries.py`` (not a replacement -- that file is owned
by a separate concurrent fix and is neither imported from nor edited here).
Where that file establishes the engine's *happy-path* and *documented*
failure-path behaviour, this file drives deliberately malformed/corrupted
input at the same real public functions and reports, per case, whether the
real code already defeats the corruption or silently returns "everything is
fine" -- the exact failure mode ``.claude/rules/absence-is-not-evidence.md``
and ``.claude/rules/level4-completion-law.md`` name: a query engine that
cannot represent a defect does not fail loudly, it plans (here: reports)
straight through it.

Malformed-input classes exercised (RFC gate 138 / level4-completion-law.md),
five of the six named classes, each in its own test:

  * dropped events                    -> test_falsifier_dropped_authority_event_*
  * duplicated events                 -> test_falsifier_duplicated_events_*
  * corrupted relationship identity   -> test_falsifier_corrupted_relationship_identity_*
  * unknown event type                -> test_falsifier_unknown_event_type_*
  * out-of-order ingestion            -> test_falsifier_out_of_order_ingestion_* (x2)

("unknown object type" is deliberately not repeated here: it already has a
real, currently-passing falsifier in ``test_ocel_queries.py``
(``test_p4_undeclared_type_fails``) and this file's job is to find *new*
gaps, not restate covered ground.)

Chicago-style discipline: every OCEL log below is a real, literal OCEL 2.0
JSON document (a plain ``dict`` -- the exact interchange form
``OcelConformanceQueryEngine`` is built to consume, per its own module
docstring: "All queries are evaluated against LIVE OCEL 2.0 logs") or a real
``autofde_lab.ocel.log.OcelLog`` built from the real
``autofde_lab.ocel.model`` dataclasses. No test-double library of any kind is
imported or used anywhere in this file -- verified by a real grep for the
banned interaction-mocking tokens in the session that produced it (see the
subagent report). Every assertion is on real returned state (``OcelQueryResult.passed``,
``.violations``, ``.evidence``, ``OcelConformanceReport.passed``), never on
"was a function called."
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import (
    EventObjectLink,
    OcelAttribute,
    OcelAttributeValue,
    OcelEvent,
    OcelObject,
)
from autofde_lab.ocel.refusals import OcelError, OcelRefusal
from autofde_lab.sa2a.conformance.ocel_queries import OcelConformanceQueryEngine


# ---------------------------------------------------------------------------
# Local helper -- deliberately NOT imported from test_ocel_queries.py, which
# a separate agent is concurrently fixing. Kept minimal and self-contained.
# ---------------------------------------------------------------------------


def _ocel_shell(
    events: list[dict[str, Any]] | None = None,
    objects: list[dict[str, Any]] | None = None,
    object_types: list[dict[str, Any]] | None = None,
    event_types: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A minimal, structurally-valid OCEL 2.0 JSON shell to corrupt from."""
    return {
        "ocel:version": "2.0",
        "ocel:ordering": "timestamp",
        "eventTypes": event_types if event_types is not None else [{"name": "test_event", "attributes": []}],
        "objectTypes": object_types if object_types is not None else [{"name": "Receipt", "attributes": []}],
        "events": events or [],
        "objects": objects or [],
    }


# ---------------------------------------------------------------------------
# 1. Dropped events -- an actuation event exists; the authority event that
#    should have preceded it was never ingested at all (not reordered, not
#    corrupted -- entirely absent from the log).
# ---------------------------------------------------------------------------


def test_falsifier_dropped_authority_event_p8_vacuous_pass_on_unauthorized_actuation() -> None:
    """RFC gate 138 class: dropped events.

    An actuation event fires for actor ``urn:agent:dropped-auth``. The
    authority-grant event that a lawful sequence requires to precede it was
    DROPPED -- never recorded in this log at all. P8's own description
    ("Authority grant events precede actuation events",
    ``ocel_queries.py:299-301``) reads as an unconditional requirement, but
    the real implementation only compares timestamps for actors present in
    BOTH ``actor_authority_time`` and ``actor_actuation_time``
    (``ocel_queries.py:324-331``); an actor with an actuation event and NO
    authority event at all is simply never visited by that loop.

    The actuation event is given a valid ``prepared_receipt_id`` so P1
    stays clean and the gap in P8 is isolated, not masked by an unrelated
    P1 failure.

    RESULT: defeated=False -- real gap. Both the isolated P8 predicate and
    the full ``evaluate_log()`` aggregate report zero violations for an
    actuation event that was never authorized at all.
    """
    actuation_only = {
        "id": "act-dropped-001",
        "type": "brce_execute",
        "time": 1000.0,
        "attributes": {
            "actor_id": "urn:agent:dropped-auth",
            "prepared_receipt_id": "rcpt-dropped-001",
        },
        "relationships": [],
    }
    ocel = _ocel_shell(events=[actuation_only])

    engine = OcelConformanceQueryEngine()
    p8 = engine.p8_authority_precedes_actuation(ocel)

    # GAP: no authority event exists anywhere in the log for this actor,
    # yet P8 reports full compliance.
    assert p8.passed is True
    assert p8.violations == []
    assert p8.evidence["actors_with_authority"] == 0
    assert p8.evidence["actors_with_actuation"] == 1

    report = engine.evaluate_log(ocel)
    assert report.passed is True
    assert report.failed_queries == 0


# ---------------------------------------------------------------------------
# 2. Duplicated events -- two distinct OcelEvent records share ONE event
#    id but assert CONTRADICTORY activity/type values: a direct violation
#    of OCPQ Definition 2's "each event has exactly one event type" law.
# ---------------------------------------------------------------------------


def test_falsifier_duplicated_events_identity_corruption_evaluate_log_silently_passes() -> None:
    """RFC gate 138 class: duplicated events (corrupted entity identity).

    Builds a real ``OcelLog`` (real dataclasses, not a mock) containing two
    distinct ``OcelEvent`` records that share the id ``"evt-dup-001"`` but
    carry DIFFERENT activities (``"brce_execute"`` vs ``"hook_fired"``) --
    exactly the corruption ``OcelLog.validate()``'s law 3 exists to catch
    as ``DUPLICATE_ENTITY_ID`` (``ocel/log.py:262-282``, citing OCPQ
    Definition 2, "each event has exactly one event type").

    ``.validate()`` is deliberately NOT called on the corrupted log
    before it reaches the query engine below: this simulates corruption
    that slipped past the producer's own admission gate, which is
    exactly the scenario the "independent blind" conformance engine
    (``ocel_queries.py`` module docstring: "Anti-Oracle Rule ... NO
    pre-canned golden trace snapshots") exists to catch on its own,
    without relying on the producer having been honest.

    Two parts:

    1. Confirm the corruption is a REAL, code-recognized defect at the
       producer layer: the real ``OcelLog.validate()`` (not a stub of
       it) is called directly on the corrupted log and does refuse it,
       as ``OcelRefusal.DUPLICATE_ENTITY_ID``. This grounds the test in
       an actual admitted law, not merely this test file's own opinion
       of what should be a violation.
    2. Feed the SAME corruption -- the identical two-events-one-id shape
       -- to the query engine as a literal OCEL 2.0 JSON document (the
       dict-attributes / numeric-time fixture convention every other
       test in this suite and in ``test_ocel_queries.py`` already
       uses). Deliberately NOT routed through
       ``OcelLog.to_ocel2_json()``: that projection has its own,
       separately-tracked, pre-existing timestamp/attribute-shape
       defect (documented in ``test_ocel_queries.py``'s
       ``test_evaluate_ocel_log_object_integration``, owned by a
       different, concurrently-running fix) that is orthogonal to the
       duplicate-identity gap this test targets and is deliberately not
       depended on here.

    RESULT: defeated=False -- real gap. Part 1 proves the corruption is
    genuinely law-violating. Part 2 shows none of P1/P4/P6/P7/P8/P9/P10
    performs an event-id uniqueness check, so ``evaluate_log()`` reports
    the log as fully conformant even though its event table is not a
    well-formed set (two rows sharing one key, disagreeing on activity).
    """
    actor = OcelObject(id="urn:agent:dup-test", object_type="GenericEntity")

    event_v1 = OcelEvent(
        id="evt-dup-001",
        activity="brce_execute",
        timestamp_ns=1_000_000_000,
        attributes=(
            OcelAttribute("actor_id", OcelAttributeValue.string("urn:agent:dup-test")),
            OcelAttribute("prepared_receipt_id", OcelAttributeValue.string("rcpt-v1")),
        ),
    )
    event_v2 = OcelEvent(
        id="evt-dup-001",
        activity="hook_fired",
        timestamp_ns=2_000_000_000,
        attributes=(
            OcelAttribute("hook_iri", OcelAttributeValue.string("http://example.org/hook/dup")),
        ),
    )
    link = EventObjectLink(event_id="evt-dup-001", object_id="urn:agent:dup-test", qualifier=None)

    corrupted_log = OcelLog.new(
        objects=(actor,),
        events=(event_v1, event_v2),
        event_object_links=(link,),
    )

    # Confirm the corruption is real before asserting anything about the
    # engine's response to it.
    assert len(corrupted_log.events) == 2
    assert {e.activity for e in corrupted_log.events} == {"brce_execute", "hook_fired"}
    assert len({e.id for e in corrupted_log.events}) == 1  # both rows share ONE id

    # Part 1: the real producer-layer admission gate DOES refuse this.
    raised: OcelError | None = None
    try:
        corrupted_log.validate()
    except OcelError as exc:
        raised = exc
    assert raised is not None, "expected OcelLog.validate() to refuse a duplicate event id"
    assert raised.refusal is OcelRefusal.DUPLICATE_ENTITY_ID

    # Part 2: the identical corruption expressed as a literal OCEL 2.0 JSON
    # document (dict-attributes / numeric-time -- the fixture convention
    # every other test in this suite and in test_ocel_queries.py already
    # uses), fed straight to the independent query engine. Deliberately
    # NOT routed through OcelLog.to_ocel2_json(): that projection has its
    # own, separately-tracked, pre-existing timestamp/attribute-shape
    # defect (documented in test_ocel_queries.py's
    # test_evaluate_ocel_log_object_integration, owned by a different,
    # concurrently-running fix) orthogonal to the duplicate-identity gap
    # this test targets.
    duplicated_events_json = [
        {
            "id": "evt-dup-001",
            "type": "brce_execute",
            "time": 1.0,
            "attributes": {"actor_id": "urn:agent:dup-test", "prepared_receipt_id": "rcpt-v1"},
            "relationships": [],
        },
        {
            "id": "evt-dup-001",
            "type": "hook_fired",
            "time": 2.0,
            "attributes": {"hook_iri": "http://example.org/hook/dup"},
            "relationships": [],
        },
    ]
    ocel_json = _ocel_shell(events=duplicated_events_json)

    engine = OcelConformanceQueryEngine()
    report = engine.evaluate_log(ocel_json)

    # GAP: the independent blind engine reports full conformance for a log
    # whose event table contains two contradictory records under one id --
    # the same corruption OcelLog.validate() above correctly refused.
    assert report.passed is True
    assert report.failed_queries == 0


# ---------------------------------------------------------------------------
# 3. Corrupted relationship identity -- an event's relationship points at
#    an objectId that is never declared anywhere in the log's objects
#    table (a dangling reference).
# ---------------------------------------------------------------------------


def test_falsifier_corrupted_relationship_identity_p1_accepts_dangling_receipt_ref() -> None:
    """RFC gate 138 class: corrupted relationship identity.

    An actuation event's ``relationships`` list references an
    ``objectId`` that is never declared anywhere in the log's ``objects``
    table -- a dangling reference. This is the same class of defect
    ``OcelLog.validate()``'s ``DANGLING_EVENT_OBJECT_LINK`` law exists to
    catch at the producer layer (``ocel/log.py:302-312``); this log is fed
    directly to the query engine as raw OCEL 2.0 JSON, bypassing that
    producer-side check.

    P1's receipt-binding check (``ocel_queries.py:165-174``) accepts a
    relationship as a valid ``PreparedReceipt`` binding purely via a
    SUBSTRING MATCH on the ``objectId`` / ``qualifier`` strings
    (``"receipt" in str(r.get("objectId", "")).lower()``), with no check
    that the referenced id is declared anywhere in the log's ``objects``
    table.

    RESULT: defeated=False -- real gap. An event satisfies P1 via a
    relationship pointing at an object id that provably does not exist
    anywhere in the log.
    """
    ghost_object_id = "ghost-receipt-does-not-exist-999"
    event = {
        "id": "act-ghost-001",
        "type": "brce_execute",
        "time": 1000.0,
        "attributes": {"actor_id": "urn:agent:ghost-test"},  # no receipt attrs
        "relationships": [{"objectId": ghost_object_id, "qualifier": "binding"}],
    }
    ocel = _ocel_shell(events=[event], objects=[])  # objects table is EMPTY

    # Confirm the corruption is real: the referenced id is genuinely
    # undeclared anywhere in this log.
    declared_object_ids = {o["id"] for o in ocel["objects"]}
    assert ghost_object_id not in declared_object_ids

    engine = OcelConformanceQueryEngine()
    p1 = engine.p1_actuation_has_receipt(ocel)

    # GAP: P1 accepts a dangling reference as a valid receipt binding.
    assert p1.passed is True
    assert p1.violations == []


# ---------------------------------------------------------------------------
# 4. Unknown event type -- an event's `type` value is not declared
#    anywhere in the log's `eventTypes` table.
# ---------------------------------------------------------------------------


def test_falsifier_unknown_event_type_p7_schema_check_does_not_validate_it() -> None:
    """RFC gate 138 class: unknown event type.

    The log declares exactly one event type, ``known_event``, in
    ``eventTypes``. The single event actually in the log carries
    ``type="totally_unknown_bogus_event_xyz"`` -- a value that is not
    declared anywhere in the log at all.

    P7's description claims "OCEL log structure conforms to OCEL 2.0
    schema" (``ocel_queries.py:258-293``), but the implementation only
    checks for the PRESENCE of the four required top-level containers and
    that ``events`` is a list -- it never cross-checks that a used
    event's ``type`` value is one of the names declared in
    ``eventTypes`` (the analogous object-side check exists, but only for
    P4 and only for declared *objects*, not for event type references).

    RESULT: defeated=False -- real gap. A completely undeclared/unknown
    event type string passes P7's schema-conformance check outright.
    """
    ocel = _ocel_shell(
        events=[
            {
                "id": "evt-mystery-001",
                "type": "totally_unknown_bogus_event_xyz",
                "time": 1.0,
                "attributes": {},
                "relationships": [],
            }
        ],
        event_types=[{"name": "known_event", "attributes": []}],
    )
    declared_event_type_names = {t["name"] for t in ocel["eventTypes"]}
    assert "totally_unknown_bogus_event_xyz" not in declared_event_type_names

    engine = OcelConformanceQueryEngine()
    p7 = engine.p7_schema_structure(ocel)

    # GAP: P7 never checks that the event's `type` is declared.
    assert p7.passed is True
    assert p7.violations == []


# ---------------------------------------------------------------------------
# 5. Out-of-order ingestion -- events are appended to the log's `events`
#    list in an order that does not match their true causal (timestamp)
#    order.
# ---------------------------------------------------------------------------


def test_falsifier_out_of_order_ingestion_p8_is_order_robust_not_list_position() -> None:
    """RFC gate 138 class: out-of-order ingestion (P8 side).

    The actuation event (t=1000) is appended to the ``events`` list
    FIRST; the authority event that genuinely precedes it in time
    (t=500) is appended SECOND -- ingestion/list order is scrambled, but
    the underlying causal (timestamp) order is still correct (authority
    really did happen first).

    This is a deliberately different scenario from
    ``test_ocel_queries.py``'s ``test_p8_actuation_before_authority_fails``,
    where the actuation timestamp (t=100) is ALSO earlier than the
    authority timestamp (t=500) -- list order and causal order agree
    there that it is a genuine violation. Here only ingestion order is
    corrupted; causal order is not.

    RESULT: defeated=True -- the real code already handles this class
    correctly. ``p8_authority_precedes_actuation`` tracks a per-actor
    MINIMUM timestamp regardless of list position
    (``ocel_queries.py:316,320``), so it correctly reports no violation
    even though the authority event was appended to the log after the
    actuation event it in fact preceded.
    """
    events_out_of_order = [
        {
            "id": "act-ooo-001",
            "type": "brce_execute",
            "time": 1000.0,
            "attributes": {
                "actor_id": "urn:agent:ooo-test",
                "prepared_receipt_id": "rcpt-ooo-001",
            },
            "relationships": [],
        },
        {
            "id": "auth-ooo-001",
            "type": "authority_grant",
            "time": 500.0,
            "attributes": {"actor_id": "urn:agent:ooo-test", "grant_id": "grant-ooo-001"},
            "relationships": [],
        },
    ]
    # Confirm the corruption is real: list/ingestion order does not match
    # the events' own timestamp order.
    assert events_out_of_order[0]["time"] > events_out_of_order[1]["time"]

    ocel = _ocel_shell(events=events_out_of_order)
    engine = OcelConformanceQueryEngine()
    p8 = engine.p8_authority_precedes_actuation(ocel)

    assert p8.passed is True
    assert p8.violations == []


def test_falsifier_out_of_order_ingestion_p10_digest_detects_reordering() -> None:
    """RFC gate 138 class: out-of-order ingestion (P10/digest side).

    Companion to the P8 order-robustness case above. The exact same two
    events, canonically ordered ``[authority, actuation]``, produce a
    declared digest; the SAME two events re-ingested in swapped list
    order ``[actuation, authority]`` are then checked against that
    declared digest. ``json.dumps(ocel_json, sort_keys=True, ...)`` sorts
    dict KEYS but never reorders LIST elements, so a reordered-ingestion
    log genuinely hashes differently.

    RESULT: defeated=True -- the real code already handles this class
    correctly. P10 correctly flags the mismatch between the canonical
    declared digest and the reordered log's own computed digest.
    """
    event_a = {
        "id": "auth-ord-001",
        "type": "authority_grant",
        "time": 500.0,
        "attributes": {"actor_id": "urn:agent:ord-test", "grant_id": "grant-ord-001"},
        "relationships": [],
    }
    event_b = {
        "id": "act-ord-001",
        "type": "brce_execute",
        "time": 1000.0,
        "attributes": {"actor_id": "urn:agent:ord-test", "prepared_receipt_id": "rcpt-ord-001"},
        "relationships": [],
    }

    canonical_order = _ocel_shell(events=[event_a, event_b])
    canonical_json_str = json.dumps(canonical_order, sort_keys=True, separators=(",", ":"))
    declared_digest = hashlib.sha256(canonical_json_str.encode()).hexdigest()

    reingested_out_of_order = _ocel_shell(events=[event_b, event_a])  # swapped list order
    reingested_json_str = json.dumps(reingested_out_of_order, sort_keys=True, separators=(",", ":"))
    computed_digest = hashlib.sha256(reingested_json_str.encode()).hexdigest()

    # Confirm the corruption is real: same event content, different list
    # order, genuinely different digest.
    assert canonical_order["events"] != reingested_out_of_order["events"]
    assert declared_digest != computed_digest

    engine = OcelConformanceQueryEngine()
    p10 = engine.p10_log_digest_stable(
        reingested_out_of_order, computed_digest, declared_digest=declared_digest
    )

    assert p10.passed is False
    assert len(p10.violations) > 0
