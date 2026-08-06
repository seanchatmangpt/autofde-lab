# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for skdecide.ocel — real logs, real refusals.

Every named refusal in ``OcelRefusal`` gets the adversarial log that triggers
it, asserted by name. Plus the round-trip and digest-stability laws.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skdecide.ocel import (
    EventObjectLink,
    ObjectChange,
    ObjectObjectLink,
    OcelAttribute,
    OcelAttributeValue,
    OcelError,
    OcelEvent,
    OcelLog,
    OcelObject,
    OcelRefusal,
    OcelValueKind,
    format_ns,
    parse_ns,
)

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_NAMES = ["out.json", "gundam_factory_trace.json", "vision_ocel_trace.json"]


def lawful_log() -> OcelLog:
    """A minimal lawful log: one object, one event, one E2O link."""
    return (
        OcelLog()
        .with_objects(OcelObject("o1", "order"))
        .append_event("e1", "place", [("o1", "belongs_to")], timestamp_ns=1_700_000_000_000_000_000)
    )


# ── the lawful baseline ───────────────────────────────────────────────────


def test_lawful_log_validates_and_returns_itself():
    log = lawful_log()
    assert log.validate() is log


def test_append_event_is_pure():
    base = OcelLog().with_objects(OcelObject("o1", "order"))
    once = base.append_event("e1", "place", ["o1"])
    assert base.events == ()
    assert len(once.events) == 1
    assert once.event_object_links == (EventObjectLink("e1", "o1", None),)


def test_append_event_accepts_bare_ids_and_qualified_pairs():
    log = OcelLog().with_objects(
        OcelObject("o1", "order"), OcelObject("i1", "item")
    ).append_event("e1", "place", ["o1", ("i1", "contains")])
    assert log.event_object_links == (
        EventObjectLink("e1", "o1", None),
        EventObjectLink("e1", "i1", "contains"),
    )
    log.validate()


# ── refusal: EmptyEventObjectLinks (object-centricity law) ────────────────


def test_refusal_empty_event_object_links_when_log_has_none():
    log = OcelLog.new(objects=[OcelObject("o1", "order")])
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.EMPTY_EVENT_OBJECT_LINKS


def test_refusal_empty_event_object_links_when_an_event_has_none():
    """An executor can emit an object-free event silently. This catches it."""
    log = (
        OcelLog()
        .with_objects(OcelObject("o1", "order"))
        .append_event("e1", "place", ["o1"])
        .append_event("e2", "audit", [])  # touches nothing
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.EMPTY_EVENT_OBJECT_LINKS
    assert "e2" in excinfo.value.detail


# ── refusal: DanglingEventObjectLink ──────────────────────────────────────


def test_refusal_dangling_event_object_link():
    log = OcelLog().with_objects(OcelObject("o1", "order")).append_event(
        "e1", "place", ["missing"]
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.DANGLING_EVENT_OBJECT_LINK


def test_refusal_dangling_link_names_unknown_event():
    log = OcelLog.new(
        objects=[OcelObject("o1", "order")],
        events=[OcelEvent("e1", "place")],
        event_object_links=[
            EventObjectLink("e1", "o1"),
            EventObjectLink("ghost", "o1"),
        ],
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.DANGLING_EVENT_OBJECT_LINK
    assert "ghost" in excinfo.value.detail


def test_refusal_dangling_object_object_link():
    log = lawful_log()
    log = OcelLog.new(
        log.objects, log.events, log.event_object_links, [ObjectObjectLink("o1", "nope")]
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.DANGLING_EVENT_OBJECT_LINK
    assert "target" in excinfo.value.detail


def test_refusal_dangling_object_change():
    base = lawful_log()
    log = OcelLog.new(
        base.objects,
        base.events,
        base.event_object_links,
        (),
        [ObjectChange("nope", "status", OcelAttributeValue.string("x"), 5)],
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.DANGLING_EVENT_OBJECT_LINK


# ── refusals: Gianola 2026 locality ───────────────────────────────────────


def test_refusal_missing_reference_object():
    log = (
        OcelLog()
        .with_objects(OcelObject("p1", "employee"))
        .append_event("e1", "assign", ["p1"])
    )
    log.validate()
    with pytest.raises(OcelError) as excinfo:
        log.validate_locality("team", "employee")
    assert excinfo.value.refusal is OcelRefusal.MISSING_REFERENCE_OBJECT


def test_refusal_multiple_reference_objects():
    log = (
        OcelLog()
        .with_objects(OcelObject("t1", "team"), OcelObject("t2", "team"))
        .append_event("e1", "merge_teams", ["t1", "t2"])
    )
    log.validate()
    with pytest.raises(OcelError) as excinfo:
        log.validate_locality("team", "employee")
    assert excinfo.value.refusal is OcelRefusal.MULTIPLE_REFERENCE_OBJECTS


def test_refusal_violates_locality_principle():
    """Gianola (2026) Example 4, transcribed from the Rust doctest at ocel.rs:852.

    ``p2`` is a member of ``t1``; a later event creates ``t2`` including
    ``p2``, which implicitly deletes the ``(t1, p2)`` relationship — a
    modification of an object other than the event's reference object.
    """
    log = (
        OcelLog()
        .with_objects(
            OcelObject("t1", "team"),
            OcelObject("t2", "team"),
            OcelObject("p2", "employee"),
        )
        .append_event("evt1", "create_team", ["t1", "p2"])
        .append_event("evt2", "create_team", ["t2", "p2"])
    )
    log.validate()
    with pytest.raises(OcelError) as excinfo:
        log.validate_locality("team", "employee")
    assert excinfo.value.refusal is OcelRefusal.VIOLATES_LOCALITY_PRINCIPLE


def test_locality_passes_when_child_stays_with_its_reference_object():
    log = (
        OcelLog()
        .with_objects(
            OcelObject("t1", "team"),
            OcelObject("t2", "team"),
            OcelObject("p2", "employee"),
            OcelObject("p3", "employee"),
        )
        .append_event("evt1", "create_team", ["t1", "p2"])
        .append_event("evt2", "create_team", ["t2", "p3"])
        .append_event("evt3", "touch_team", ["t1", "p2"])
    )
    assert log.validate_locality("team", "employee") is log


# ── refusals: OCPQ Definition 2 (Küsters & van der Aalst 2025, pp. 5-6) ───


@pytest.mark.parametrize("attribute", ["type", "objects"])
def test_refusal_time_stable_attribute_changed(attribute):
    """Definition 2, p. 6: for a in {objects, type}, oaval^t_o(a) = oaval^t'_o(a).

    An ``ObjectChange`` naming one of those attributes *is* the forbidden
    time-varying assignment, so it is refused at admission.
    """
    base = lawful_log()
    log = OcelLog.new(
        base.objects,
        base.events,
        base.event_object_links,
        (),
        [ObjectChange("o1", attribute, OcelAttributeValue.string("invoice"), 5)],
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.TIME_STABLE_ATTRIBUTE_CHANGED
    assert attribute in excinfo.value.detail


def test_non_time_stable_attribute_may_still_change():
    """The counterpart: ``city`` in the paper's own Fig. 3(a) example changes."""
    base = lawful_log()
    log = OcelLog.new(
        base.objects,
        base.events,
        base.event_object_links,
        (),
        [
            ObjectChange("o1", "city", OcelAttributeValue.string("Bonn"), 5),
            ObjectChange("o1", "city", OcelAttributeValue.string("Aachen"), 9),
        ],
    )
    assert log.validate() is log


def test_time_stable_law_survives_a_json_round_trip():
    """A hostile *document* — not just a hostile in-memory log — is refused."""
    document = {
        "eventTypes": [],
        "objectTypes": [],
        "events": [
            {
                "id": "e1",
                "type": "place",
                "time": "2026-01-01T00:00:00Z",
                "attributes": [],
                "relationships": [{"objectId": "o1", "qualifier": "belongs_to"}],
            }
        ],
        "objects": [
            {
                "id": "o1",
                "type": "order",
                "attributes": [
                    {"name": "type", "value": "invoice", "time": "2026-02-01T00:00:00Z"}
                ],
                "relationships": [],
            }
        ],
    }
    log = OcelLog.from_ocel2_json(document)
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.TIME_STABLE_ATTRIBUTE_CHANGED


def test_refusal_duplicate_object_id_gives_an_object_two_types():
    """Definition 2, p. 6: every object has *exactly* one object type."""
    log = (
        OcelLog()
        .with_objects(OcelObject("o1", "order"), OcelObject("o1", "invoice"))
        .append_event("e1", "place", ["o1"])
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.DUPLICATE_ENTITY_ID
    assert "invoice" in excinfo.value.detail


def test_refusal_duplicate_event_id_gives_an_event_two_types():
    """Definition 2, p. 5: each event has *exactly* one event type."""
    log = (
        OcelLog()
        .with_objects(OcelObject("o1", "order"))
        .append_event("e1", "place", ["o1"])
        .append_event("e1", "cancel", ["o1"])
    )
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal is OcelRefusal.DUPLICATE_ENTITY_ID
    assert "cancel" in excinfo.value.detail


def test_refusal_unqualified_event_to_object_reference_is_opt_in():
    """Definition 2, p. 6: eaval_e(objects) subset U_qual x O.

    Off by default: "" is a member of ``U_Sigma`` and the OCEL 2.0 schema
    permits it, so a qualifier-less reference is formally admissible.
    """
    log = OcelLog().with_objects(OcelObject("o1", "order")).append_event(
        "e1", "place", ["o1"]
    )
    assert log.validate() is log
    with pytest.raises(OcelError) as excinfo:
        log.validate(strict_qualifiers=True)
    assert excinfo.value.refusal is OcelRefusal.UNQUALIFIED_OBJECT_REFERENCE


def test_refusal_unqualified_object_to_object_reference():
    """Definition 2, p. 6: oaval_o(objects) subset U_qual x O."""
    base = lawful_log().with_objects(OcelObject("i1", "item"))
    log = OcelLog.new(
        base.objects,
        base.events,
        base.event_object_links,
        [ObjectObjectLink("o1", "i1", None)],
    )
    assert log.validate() is log
    with pytest.raises(OcelError) as excinfo:
        log.validate(strict_qualifiers=True)
    assert excinfo.value.refusal is OcelRefusal.UNQUALIFIED_OBJECT_REFERENCE
    assert "i1" in excinfo.value.detail


def test_strict_qualifiers_admits_a_fully_qualified_log():
    base = lawful_log().with_objects(OcelObject("i1", "item"))
    log = OcelLog.new(
        base.objects,
        base.events,
        base.event_object_links,
        [ObjectObjectLink("o1", "i1", "contains")],
    )
    assert log.validate(strict_qualifiers=True) is log


def test_every_refusal_variant_is_exercised():
    """Guards against a refusal being added without an adversarial test."""
    covered = {
        OcelRefusal.DANGLING_EVENT_OBJECT_LINK,
        OcelRefusal.EMPTY_EVENT_OBJECT_LINKS,
        OcelRefusal.MISSING_REFERENCE_OBJECT,
        OcelRefusal.MULTIPLE_REFERENCE_OBJECTS,
        OcelRefusal.VIOLATES_LOCALITY_PRINCIPLE,
        OcelRefusal.TIME_STABLE_ATTRIBUTE_CHANGED,
        OcelRefusal.DUPLICATE_ENTITY_ID,
        OcelRefusal.UNQUALIFIED_OBJECT_REFERENCE,
    }
    assert covered == set(OcelRefusal)


# ── timestamps ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ns", [0, 1, 999_999_999, 1_700_000_000_123_456_789])
def test_timestamp_round_trip_is_nanosecond_exact(ns):
    assert parse_ns(format_ns(ns)) == ns


@pytest.mark.parametrize(
    "text,expected_suffix",
    [("2026-06-19T06:22:27.725Z", 725_000_000), ("2026-06-19T06:22:27Z", 0)],
)
def test_parse_ns_accepts_variable_fraction_widths(text, expected_suffix):
    assert parse_ns(text) % 1_000_000_000 == expected_suffix


def test_parse_ns_honours_offsets():
    assert parse_ns("2026-06-19T08:22:27+02:00") == parse_ns("2026-06-19T06:22:27Z")


# ── round trip and digest stability ───────────────────────────────────────


def rich_log() -> OcelLog:
    """A log covering every value kind, both link kinds, and a change."""
    return OcelLog.new(
        objects=[
            OcelObject(
                "o1",
                "order",
                (
                    OcelAttribute("priority", OcelAttributeValue.integer(3)),
                    OcelAttribute("weight", OcelAttributeValue.floating(1.5)),
                    OcelAttribute("rush", OcelAttributeValue.boolean(True)),
                    OcelAttribute("label", OcelAttributeValue.string("gold")),
                    OcelAttribute("opened", OcelAttributeValue.time_ns(1_000_000_007)),
                    OcelAttribute("note", OcelAttributeValue.null()),
                ),
            ),
            OcelObject("i1", "item"),
        ],
        events=[
            OcelEvent(
                "e1",
                "place",
                1_700_000_000_000_000_000,
                (
                    OcelAttribute("channel", OcelAttributeValue.string("web")),
                    OcelAttribute("units", OcelAttributeValue.integer(2)),
                    OcelAttribute("at", OcelAttributeValue.time_ns(42_000_000_000)),
                ),
            ),
            OcelEvent("e2", "ship", 1_700_000_060_000_000_000),
        ],
        event_object_links=[
            EventObjectLink("e1", "o1", "belongs_to"),
            EventObjectLink("e1", "i1", None),
            EventObjectLink("e2", "o1", "belongs_to"),
        ],
        object_object_links=[ObjectObjectLink("o1", "i1", "contains")],
        object_changes=[
            ObjectChange("o1", "status", OcelAttributeValue.string("shipped"), 1_700_000_060_000_000_000)
        ],
    )


def test_round_trip_is_value_equal():
    log = rich_log().validate()
    restored = OcelLog.from_ocel2_json(log.to_ocel2_json())
    assert restored == log
    assert restored is not log


def test_round_trip_preserves_typed_time_values():
    restored = OcelLog.from_ocel2_json(rich_log().to_ocel2_json())
    opened = {a.key: a.value for a in restored.objects[0].attributes}["opened"]
    assert opened.kind is OcelValueKind.TIME
    assert opened.value == 1_000_000_007


def test_round_trip_preserves_null_and_qualifierless_links():
    restored = OcelLog.from_ocel2_json(rich_log().to_ocel2_json())
    note = {a.key: a.value for a in restored.objects[0].attributes}["note"]
    assert note.kind is OcelValueKind.NULL
    assert EventObjectLink("e1", "i1", None) in restored.event_object_links


def test_round_trip_preserves_object_changes_versus_static_attributes():
    restored = OcelLog.from_ocel2_json(rich_log().to_ocel2_json())
    assert restored.object_changes == rich_log().object_changes
    assert len(restored.objects[0].attributes) == 6


def test_digest_is_stable_across_equal_logs():
    assert rich_log().digest() == rich_log().digest()
    assert OcelLog.from_ocel2_json(rich_log().to_ocel2_json()).digest() == rich_log().digest()


def test_digest_changes_when_the_log_changes():
    other = rich_log().append_event("e3", "cancel", ["o1"])
    assert other.digest() != rich_log().digest()


def test_canonical_json_is_sorted_and_compact():
    text = rich_log().canonical_json()
    assert " " not in text.split('"')[0]
    assert json.loads(text)["events"][0]["id"] == "e1"


# ── fixtures from an independent implementation (optional) ────────────────


def _fixture(name: str) -> dict:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(
            f"BLOCKED:POWLV2LSP_ABSENT: {name} comes from ~/powlv2lsp and is not present"
        )
    return json.loads(path.read_text())


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_parses_independent_ocel2_output(name):
    log = OcelLog.from_ocel2_json(_fixture(name))
    assert log.events
    assert log.objects
    log.validate()


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_independent_output_reprojects_and_re_parses_identically(name):
    log = OcelLog.from_ocel2_json(_fixture(name))
    assert OcelLog.from_ocel2_json(log.to_ocel2_json()) == log
