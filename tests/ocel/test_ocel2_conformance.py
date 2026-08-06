# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Independent OCEL 2.0 conformance checks for :mod:`skdecide.ocel`.

Written by an agent that did not build the package, against the *specification*
rather than against the package's own docstrings. Two authorities are used, and
where they disagree the disagreement is asserted rather than papered over:

* the published JSON Schema, ``https://www.ocel-standard.org/2.0/ocel20-schema-json.json``
  (draft-07), vendored below as :data:`OCEL20_JSON_SCHEMA` so this suite has no
  network dependency;
* the specification PDF, ``https://www.ocel-standard.org/2.0/ocel20_specification.pdf``,
  section 8 "JSON Format", quoted inline where a test depends on its wording.

Both were retrieved 2026-08-06.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from skdecide.ocel.log import SPEC_ATTRIBUTE_TYPES, STATIC_ATTRIBUTE_NS, OcelLog
from skdecide.ocel.model import (
    EventObjectLink,
    ObjectChange,
    ObjectObjectLink,
    OcelAttribute,
    OcelAttributeValue,
    OcelEvent,
    OcelObject,
    format_ns,
    parse_ns,
)
from skdecide.ocel.refusals import OcelError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

#: Verbatim from https://www.ocel-standard.org/2.0/ocel20-schema-json.json (2026-08-06).
OCEL20_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "eventTypes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                            },
                            "required": ["name", "type"],
                        },
                    },
                },
                "required": ["name", "attributes"],
            },
        },
        "objectTypes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                            },
                            "required": ["name", "type"],
                        },
                    },
                },
                "required": ["name", "attributes"],
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "time": {"type": "string", "format": "date-time"},
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["name", "value"],
                        },
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "objectId": {"type": "string"},
                                "qualifier": {"type": "string"},
                            },
                            "required": ["objectId", "qualifier"],
                        },
                    },
                },
                "required": ["id", "type", "time"],
            },
        },
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "objectId": {"type": "string"},
                                "qualifier": {"type": "string"},
                            },
                            "required": ["objectId", "qualifier"],
                        },
                    },
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                                "time": {"type": "string", "format": "date-time"},
                            },
                            "required": ["name", "value", "time"],
                        },
                    },
                },
                "required": ["id", "type"],
            },
        },
    },
    "required": ["eventTypes", "objectTypes", "events", "objects"],
}


def _validator():
    jsonschema = pytest.importorskip(
        "jsonschema", reason="UNSUPPORTED: jsonschema not installed"
    )
    return jsonschema.Draft7Validator(OCEL20_JSON_SCHEMA)


def _sample_log() -> OcelLog:
    """A log exercising every shape the projection can emit."""
    return OcelLog.new(
        objects=[
            OcelObject(
                "order-1",
                "Order",
                (OcelAttribute("label", OcelAttributeValue.string("first")),),
            ),
            OcelObject("item-1", "Item"),
        ],
        events=[
            OcelEvent(
                "e1",
                "Place Order",
                1_500_000_000_123_456_789,
                (OcelAttribute("clerk", OcelAttributeValue.string("ada")),),
            )
        ],
        event_object_links=[
            EventObjectLink("e1", "order-1", "primary"),
            EventObjectLink("e1", "item-1", None),
        ],
        object_object_links=[ObjectObjectLink("order-1", "item-1", "contains")],
        object_changes=[
            ObjectChange(
                "order-1",
                "label",
                OcelAttributeValue.string("second"),
                1_600_000_000_000_000_000,
            )
        ],
    )


# ── check 1: top-level document shape ─────────────────────────────────────


def test_toplevel_keys_are_exactly_the_four_camelcase_names():
    """Spec section 8: "top-level arrays events, eventTypes, objects, and objectTypes"."""
    doc = _sample_log().to_ocel2_json()
    assert set(doc) == {"eventTypes", "objectTypes", "events", "objects"}
    for key in doc:
        assert isinstance(doc[key], list)


def test_emitted_document_validates_against_published_schema():
    validator = _validator()
    doc = _sample_log().to_ocel2_json()
    assert list(validator.iter_errors(doc)) == []


# ── check 2: type declarations ────────────────────────────────────────────


def test_declared_attribute_types_are_in_the_spec_vocabulary():
    """Spec section 8: "Valid types are string, time, integer, float, and boolean"."""
    assert SPEC_ATTRIBUTE_TYPES == {"string", "time", "integer", "float", "boolean"}
    doc = _sample_log().to_ocel2_json()
    for section in ("eventTypes", "objectTypes"):
        for entry in doc[section]:
            assert set(entry) == {"name", "attributes"}
            for attr in entry["attributes"]:
                assert set(attr) == {"name", "type"}
                assert attr["type"] in SPEC_ATTRIBUTE_TYPES


def test_union_only_value_kinds_are_not_declared_out_of_vocabulary():
    """``null`` / ``list`` / ``map`` exist in the internal union but not in OCEL 2.0.

    Regression guard for the defect fixed this session: they used to be emitted
    verbatim as ``"type": "null"`` / ``"list"`` / ``"map"``.
    """
    log = OcelLog.new(
        objects=[
            OcelObject(
                "o1",
                "T",
                (
                    OcelAttribute("n", OcelAttributeValue.null()),
                    OcelAttribute(
                        "l", OcelAttributeValue.listing([OcelAttributeValue.integer(1)])
                    ),
                    OcelAttribute(
                        "m", OcelAttributeValue.mapping({"a": OcelAttributeValue.string("b")})
                    ),
                ),
            )
        ],
        events=[OcelEvent("e1", "A", 0, (OcelAttribute("x", OcelAttributeValue.null()),))],
        event_object_links=[EventObjectLink("e1", "o1", None)],
    )
    doc = log.to_ocel2_json()
    declared = {
        a["type"]
        for section in ("eventTypes", "objectTypes")
        for entry in doc[section]
        for a in entry["attributes"]
    }
    assert declared <= SPEC_ATTRIBUTE_TYPES, f"out-of-spec declared types: {declared}"
    # and the values still recover, so the remap costs no fidelity
    assert OcelLog.from_ocel2_json(doc) == log


def test_time_values_round_trip_only_because_the_declaration_is_right():
    """The builder's stated dependency, checked rather than trusted."""
    when = 1_700_000_000_987_654_321
    log = OcelLog.new(
        objects=[OcelObject("o1", "T")],
        events=[
            OcelEvent("e1", "A", 0, (OcelAttribute("due", OcelAttributeValue.time_ns(when)),))
        ],
        event_object_links=[EventObjectLink("e1", "o1", None)],
    )
    doc = log.to_ocel2_json()
    assert doc["eventTypes"][0]["attributes"] == [{"name": "due", "type": "time"}]
    assert OcelLog.from_ocel2_json(doc) == log

    # strip the declaration and the time silently degrades to a string
    stripped = dict(doc, eventTypes=[{"name": "A", "attributes": []}])
    degraded = OcelLog.from_ocel2_json(stripped)
    assert degraded.events[0].attributes[0].value.kind == "string"


# ── check 3: event shape ──────────────────────────────────────────────────


def test_event_shape_and_objectid_spelling():
    doc = _sample_log().to_ocel2_json()
    event = doc["events"][0]
    assert set(event) == {"id", "type", "time", "attributes", "relationships"}
    assert event["attributes"] == [{"name": "clerk", "value": "ada"}]
    for rel in event["relationships"]:
        assert set(rel) == {"objectId", "qualifier"}  # camelCase, per schema
        assert "object_id" not in rel and "objectID" not in rel
    assert [r["objectId"] for r in event["relationships"]] == ["order-1", "item-1"]
    # qualifier is required by the schema; None becomes ""
    assert event["relationships"][1]["qualifier"] == ""


def test_event_attributes_carry_no_time():
    """Only object attributes are time-versioned (spec section 8)."""
    doc = _sample_log().to_ocel2_json()
    for event in doc["events"]:
        for attr in event["attributes"]:
            assert "time" not in attr


# ── check 4: object shape ─────────────────────────────────────────────────


def test_object_shape_and_time_versioned_attributes():
    doc = _sample_log().to_ocel2_json()
    obj = next(o for o in doc["objects"] if o["id"] == "order-1")
    assert set(obj) == {"id", "type", "attributes", "relationships"}
    for attr in obj["attributes"]:
        assert set(attr) == {"name", "value", "time"}
    assert obj["attributes"] == [
        {"name": "label", "value": "first", "time": "1970-01-01T00:00:00.000000000Z"},
        {"name": "label", "value": "second", "time": "2020-09-13T12:26:40.000000000Z"},
    ]
    assert obj["relationships"] == [{"objectId": "item-1", "qualifier": "contains"}]


def test_static_object_attributes_use_the_specs_epoch_sentinel():
    """Spec section 7 uses 1970-01-01 00:00 UTC for the initial value assignment."""
    assert STATIC_ATTRIBUTE_NS == 0
    assert format_ns(STATIC_ATTRIBUTE_NS).startswith("1970-01-01T00:00:00")


# ── check 5: timestamps ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "1970-01-01T00:00:00Z",  # the spec's own example
        "2022-02-03T07:30:00Z",
        "2026-06-19T18:13:43.490Z",  # 3 fractional digits, as third-party logs emit
        "2017-07-14T02:40:00.123456789Z",  # 9, as we emit
        "2022-02-03T07:30:00+01:00",  # RFC 3339 numeric offset
    ],
)
def test_parse_ns_accepts_iso8601_variants(text):
    assert isinstance(parse_ns(text), int)


def test_format_ns_output_is_accepted_by_a_date_time_validator():
    jsonschema = pytest.importorskip("jsonschema")
    fmt = jsonschema.FormatChecker()
    for ns in (0, 1, 1_500_000_000_123_456_789):
        assert fmt.conforms(format_ns(ns), "date-time"), format_ns(ns)


def test_nanosecond_precision_survives_a_round_trip():
    ns = 1_500_000_000_123_456_789
    assert parse_ns(format_ns(ns)) == ns


# ── check 6: the builder's known lossy edge ───────────────────────────────


def test_untimed_object_change_degrades_to_a_static_attribute():
    """Documented lossy edge, reproduced: ``timestamp_ns=None`` collides with epoch.

    This is an *internal-model* artifact, not a spec violation: the emitted
    document is schema-valid and the spec has no representation for an untimed
    value assignment (section 7 explicitly maps a missing timestamp onto the
    epoch). The loss is that the link-table model cannot distinguish "static"
    from "changed at time 0" after a round trip.
    """
    log = OcelLog.new(
        objects=[OcelObject("o1", "T")],
        events=[OcelEvent("e1", "A", 0)],
        event_object_links=[EventObjectLink("e1", "o1", None)],
        object_changes=[
            ObjectChange("o1", "st", OcelAttributeValue.string("done"), None)
        ],
    )
    doc = log.to_ocel2_json()
    assert doc["objects"][0]["attributes"] == [
        {"name": "st", "value": "done", "time": "1970-01-01T00:00:00.000000000Z"}
    ]
    assert list(_validator().iter_errors(doc)) == []  # still conformant on the wire

    back = OcelLog.from_ocel2_json(doc)
    assert back != log
    assert back.object_changes == ()
    assert back.objects[0].attributes == (
        OcelAttribute("st", OcelAttributeValue.string("done")),
    )
    # ...and it is stable from there: the degradation happens at most once
    assert OcelLog.from_ocel2_json(back.to_ocel2_json()) == back


def test_a_timed_object_change_is_not_lossy():
    log = OcelLog.new(
        objects=[OcelObject("o1", "T")],
        events=[OcelEvent("e1", "A", 0)],
        event_object_links=[EventObjectLink("e1", "o1", None)],
        object_changes=[
            ObjectChange("o1", "st", OcelAttributeValue.string("done"), 5_000_000_000)
        ],
    )
    assert OcelLog.from_ocel2_json(log.to_ocel2_json()) == log


# ── check 7: third-party fixtures ─────────────────────────────────────────

_FIXTURES = sorted(FIXTURES.glob("*.json"))


@pytest.mark.skipif(not _FIXTURES, reason="BLOCKED:POWLV2LSP_ABSENT")
@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.name)
def test_fixture_is_ocel2_shaped_not_ocel1(path):
    doc = json.loads(path.read_text())
    assert set(doc) >= {"eventTypes", "objectTypes", "events", "objects"}
    # negative control: none of the OCEL 1.0 vocabulary is present
    assert not any(k.startswith("ocel:") for k in doc)


@pytest.mark.skipif(not _FIXTURES, reason="BLOCKED:POWLV2LSP_ABSENT")
@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.name)
def test_fixture_roundtrip_is_idempotent_and_emits_a_valid_document(path):
    doc = json.loads(path.read_text())
    log = OcelLog.from_ocel2_json(doc)
    emitted = log.to_ocel2_json()
    # our output is schema-valid even where the input was not
    assert list(_validator().iter_errors(emitted)) == []
    assert OcelLog.from_ocel2_json(emitted) == log


@pytest.mark.skipif(not _FIXTURES, reason="BLOCKED:POWLV2LSP_ABSENT")
@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.name)
def test_fixture_roundtrip_preserves_every_field_a_conformant_reader_needs(path):
    doc = json.loads(path.read_text())
    emitted = OcelLog.from_ocel2_json(doc).to_ocel2_json()

    def _ev(d):
        return {
            e["id"]: (
                e["type"],
                parse_ns(e["time"]),
                {a["name"]: a["value"] for a in e.get("attributes") or ()},
                sorted(
                    (r["objectId"], r.get("qualifier") or "")
                    for r in e.get("relationships") or ()
                ),
            )
            for e in d["events"]
        }

    def _ob(d):
        return {
            o["id"]: (
                o["type"],
                sorted(
                    (a["name"], json.dumps(a["value"]), parse_ns(a["time"]) if a.get("time") else 0)
                    for a in o.get("attributes") or ()
                ),
                sorted(
                    (r["objectId"], r.get("qualifier") or "")
                    for r in o.get("relationships") or ()
                ),
            )
            for o in d["objects"]
        }

    assert _ev(emitted) == _ev(doc)
    assert _ob(emitted) == _ob(doc)


@pytest.mark.skipif(
    not pathlib.Path.home().joinpath("powlv2lsp/ocel_fig3b.json").exists(),
    reason="BLOCKED:POWLV2LSP_ABSENT",
)
def test_excluded_fixture_really_is_ocel_1_0():
    """Checks the PROVENANCE.md exclusion claim rather than trusting it."""
    doc = json.loads(pathlib.Path.home().joinpath("powlv2lsp/ocel_fig3b.json").read_text())
    assert any(k.startswith("ocel:") for k in doc)
    assert not {"eventTypes", "objectTypes", "events", "objects"} & set(doc)
    assert list(_validator().iter_errors(doc))  # fails the OCEL 2.0 schema


# ── check 8: what we accept that we should reject ─────────────────────────

_MINIMAL_EVENT = {
    "id": "e",
    "type": "A",
    "time": "1970-01-01T00:00:00Z",
    "relationships": [{"objectId": "ghost", "qualifier": "q"}],
}


def test_dangling_objectid_is_refused_by_validate():
    doc = {
        "eventTypes": [],
        "objectTypes": [],
        "objects": [{"id": "o1", "type": "T"}],
        "events": [_MINIMAL_EVENT],
    }
    log = OcelLog.from_ocel2_json(doc)  # the parser is permissive by design
    with pytest.raises(OcelError) as excinfo:
        log.validate()
    assert excinfo.value.refusal == "DanglingEventObjectLink"


@pytest.mark.parametrize(
    "doc",
    [
        pytest.param({}, id="no-toplevel-keys"),
        pytest.param({"events": [_MINIMAL_EVENT]}, id="missing-objects-and-types"),
    ],
)
def test_document_missing_required_toplevel_keys_is_accepted_silently(doc):
    """DEVIATION, recorded not fixed.

    The schema's ``"required": ["eventTypes", "objectTypes", "events", "objects"]``
    makes all four mandatory; :meth:`OcelLog.from_ocel2_json` treats each as
    optional and returns a log rather than raising a named refusal. Permissive
    reading is defensible for a parser, but it means "it parsed" carries no
    conformance information about the input.
    """
    log = OcelLog.from_ocel2_json(doc)
    assert isinstance(log, OcelLog)


def test_unknown_attribute_type_string_is_accepted_silently():
    """DEVIATION, recorded not fixed.

    Spec section 8: "Valid types are string, time, integer, float, and boolean."
    A declaration of ``"type": "quaternion"`` is out of that vocabulary; the
    parser ignores the declaration and falls back to sniffing the untagged JSON,
    so no named refusal is raised.
    """
    doc = {
        "eventTypes": [{"name": "A", "attributes": [{"name": "x", "type": "quaternion"}]}],
        "objectTypes": [],
        "objects": [{"id": "o1", "type": "T"}],
        "events": [
            {
                "id": "e",
                "type": "A",
                "time": "1970-01-01T00:00:00Z",
                "attributes": [{"name": "x", "value": "v"}],
                "relationships": [{"objectId": "o1", "qualifier": "q"}],
            }
        ],
    }
    log = OcelLog.from_ocel2_json(doc).validate()
    assert log.events[0].attributes[0].value.kind == "string"


def test_event_missing_required_id_raises_a_raw_keyerror():
    """DEVIATION, recorded not fixed.

    The schema marks ``id``/``type``/``time`` required on an event. A document
    missing ``id`` escapes as an unnamed ``KeyError`` rather than an
    :class:`OcelError`, so a caller branching on ``OcelError.refusal`` cannot
    handle it.
    """
    doc = {
        "eventTypes": [],
        "objectTypes": [],
        "objects": [],
        "events": [{"type": "A", "time": "1970-01-01T00:00:00Z"}],
    }
    with pytest.raises(KeyError):
        OcelLog.from_ocel2_json(doc)


# ── spec-vs-schema divergence, asserted so it cannot drift unnoticed ──────


def test_native_typed_values_fail_the_published_schema_but_match_the_spec_text():
    """The two authorities disagree; this pins which side we are on.

    Published schema: an attribute ``value`` is ``{"type": "string"}``.
    Spec section 8: "Valid types are string, time, integer, float, and boolean."
    We follow the spec text (and pm4py's exporter) and emit native JSON numbers
    and booleans, which the literal schema rejects.
    """
    log = OcelLog.new(
        objects=[OcelObject("o1", "T")],
        events=[
            OcelEvent("e1", "A", 0, (OcelAttribute("n", OcelAttributeValue.integer(7)),))
        ],
        event_object_links=[EventObjectLink("e1", "o1", "q")],
    )
    doc = log.to_ocel2_json()
    assert doc["events"][0]["attributes"] == [{"name": "n", "value": 7}]
    assert doc["eventTypes"][0]["attributes"] == [{"name": "n", "type": "integer"}]
    messages = [e.message for e in _validator().iter_errors(doc)]
    assert messages == ["7 is not of type 'string'"]
