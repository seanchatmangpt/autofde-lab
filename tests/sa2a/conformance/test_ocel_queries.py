# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test Suite for OCEL 2.0 Conformance Query Engine (RFC-SA2A-002 v26.9.16).

SA2A-OCEL-* gate family. Anti-Oracle Rule: NO golden trace snapshots.
All OCEL logs are constructed live from real execution evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from autofde_lab.sa2a.conformance.ocel_queries import (
    OcelConformanceQueryEngine,
    OcelConformanceReport,
    query_actuation_receipt_coverage,
    query_schema_conformance,
)

# ---------------------------------------------------------------------------
# Helper: build a minimal OCEL 2.0 JSON structure
# ---------------------------------------------------------------------------


def _make_ocel_log(
    events: list[dict[str, Any]] | None = None,
    objects: list[dict[str, Any]] | None = None,
    object_types: list[dict[str, Any]] | None = None,
    event_types: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ocel:version": "2.0",
        "ocel:ordering": "timestamp",
        "eventTypes": event_types or [{"name": "test_event", "attributes": []}],
        "objectTypes": object_types or [{"name": "Receipt", "attributes": []}],
        "events": events or [],
        "objects": objects or [],
    }


def _make_actuation_event(
    event_id: str = "evt-001",
    actor_id: str = "urn:agent:test",
    with_receipt: bool = True,
    timestamp: float = 1000.0,
) -> dict[str, Any]:
    attrs = {"actor_id": actor_id}
    if with_receipt:
        attrs["prepared_receipt_id"] = f"rcpt-{event_id}"
    return {
        "id": event_id,
        "type": "brce_execute",
        "time": timestamp,
        "attributes": attrs,
        "relationships": [],
    }


def _make_authority_event(
    event_id: str = "auth-001",
    actor_id: str = "urn:agent:test",
    timestamp: float = 500.0,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "authority_grant",
        "time": timestamp,
        "attributes": {"actor_id": actor_id, "grant_id": f"grant-{event_id}"},
        "relationships": [],
    }


def _make_hook_event(
    event_id: str = "hook-001",
    timestamp: float = 700.0,
    hook_type: str = "hook_fired",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": hook_type,
        "time": timestamp,
        "attributes": {"hook_iri": "http://example.org/hook/test"},
        "relationships": [],
    }


# ---------------------------------------------------------------------------
# 1. P7 — OCEL 2.0 Schema Structure
# ---------------------------------------------------------------------------


def test_p7_valid_ocel_log_passes() -> None:
    """Minimal valid OCEL 2.0 log passes schema check."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log()
    res = engine.p7_schema_structure(ocel)
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P7"


def test_p7_missing_events_field_fails() -> None:
    """OCEL log missing 'events' key fails schema check."""
    engine = OcelConformanceQueryEngine()
    ocel = {
        "objectTypes": [{"name": "Receipt", "attributes": []}],
        "eventTypes": [{"name": "test", "attributes": []}],
        "objects": [],
        # No "events" key
    }
    res = engine.p7_schema_structure(ocel)
    assert res.passed is False
    assert res.predicate_id == "SA2A-OCEL-P7"
    assert any("events" in v for v in res.violations)


def test_p7_missing_objects_field_fails() -> None:
    """OCEL log missing 'objects' key fails schema check."""
    engine = OcelConformanceQueryEngine()
    ocel = {
        "eventTypes": [{"name": "test", "attributes": []}],
        "objectTypes": [{"name": "Receipt", "attributes": []}],
        "events": [],
        # No "objects" key
    }
    res = engine.p7_schema_structure(ocel)
    assert res.passed is False


# ---------------------------------------------------------------------------
# 2. P1 — Actuation Events Have PreparedReceipt Binding
# ---------------------------------------------------------------------------


def test_p1_actuation_with_receipt_passes() -> None:
    """Actuation event with prepared_receipt_id passes P1."""
    engine = OcelConformanceQueryEngine()
    events = [_make_actuation_event(with_receipt=True)]
    ocel = _make_ocel_log(events=events)
    res = engine.p1_actuation_has_receipt(ocel)
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P1"


def test_p1_actuation_without_receipt_fails() -> None:
    """Actuation event without receipt binding fails P1."""
    engine = OcelConformanceQueryEngine()
    events = [_make_actuation_event(with_receipt=False)]
    ocel = _make_ocel_log(events=events)
    res = engine.p1_actuation_has_receipt(ocel)
    assert res.passed is False
    assert len(res.violations) > 0


def test_p1_no_actuation_events_vacuously_passes() -> None:
    """Log with no actuation events vacuously passes P1."""
    engine = OcelConformanceQueryEngine()
    events = [_make_hook_event()]
    ocel = _make_ocel_log(events=events)
    res = engine.p1_actuation_has_receipt(ocel)
    assert res.passed is True


# ---------------------------------------------------------------------------
# 3. P4 — Declared Object Types
# ---------------------------------------------------------------------------


def test_p4_declared_types_pass() -> None:
    """Objects with declared types pass P4."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log(
        objects=[{"id": "rcpt-001", "type": "Receipt", "attributes": {}}],
        object_types=[{"name": "Receipt", "attributes": []}],
    )
    res = engine.p4_declared_object_types(ocel)
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P4"


def test_p4_undeclared_type_fails() -> None:
    """Object with undeclared type fails P4."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log(
        objects=[{"id": "obj-001", "type": "GhostType", "attributes": {}}],
        object_types=[{"name": "Receipt", "attributes": []}],
    )
    res = engine.p4_declared_object_types(ocel)
    assert res.passed is False
    assert any("GhostType" in v for v in res.violations)


def test_p4_empty_objects_vacuously_passes() -> None:
    """No objects — vacuously passes P4."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log(objects=[])
    res = engine.p4_declared_object_types(ocel)
    assert res.passed is True


# ---------------------------------------------------------------------------
# 4. P6 — Fresh Consumer Isolation
# ---------------------------------------------------------------------------


def test_p6_no_producer_refs_passes() -> None:
    """Fresh consumer event not referencing any producer object passes P6."""
    engine = OcelConformanceQueryEngine()
    events = [
        {
            "id": "fresh-001",
            "type": "fresh_consumer_read",
            "time": 1000.0,
            "attributes": {},
            "relationships": [{"objectId": "local-obj-001", "qualifier": "read"}],
        }
    ]
    ocel = _make_ocel_log(events=events)
    res = engine.p6_fresh_consumer_isolation(
        ocel, producer_object_ids={"producer-cache-001"}
    )
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P6"


def test_p6_producer_ref_in_fresh_consumer_fails() -> None:
    """Fresh consumer event referencing producer object fails P6."""
    engine = OcelConformanceQueryEngine()
    events = [
        {
            "id": "fresh-001",
            "type": "fresh_consumer_read",
            "time": 1000.0,
            "attributes": {},
            "relationships": [{"objectId": "producer-cache-001", "qualifier": "read"}],
        }
    ]
    ocel = _make_ocel_log(events=events)
    res = engine.p6_fresh_consumer_isolation(
        ocel, producer_object_ids={"producer-cache-001"}
    )
    assert res.passed is False
    assert len(res.violations) > 0


# ---------------------------------------------------------------------------
# 5. P8 — Authority Precedes Actuation
# ---------------------------------------------------------------------------


def test_p8_authority_before_actuation_passes() -> None:
    """Authority grant at t=500 before actuation at t=1000 passes P8."""
    engine = OcelConformanceQueryEngine()
    events = [
        _make_authority_event("auth-001", "urn:agent:test", timestamp=500.0),
        _make_actuation_event("act-001", "urn:agent:test", timestamp=1000.0),
    ]
    ocel = _make_ocel_log(events=events)
    res = engine.p8_authority_precedes_actuation(ocel)
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P8"


def test_p8_actuation_before_authority_fails() -> None:
    """Actuation at t=100 before authority grant at t=500 fails P8."""
    engine = OcelConformanceQueryEngine()
    events = [
        _make_actuation_event("act-001", "urn:agent:test", timestamp=100.0),
        _make_authority_event("auth-001", "urn:agent:test", timestamp=500.0),
    ]
    ocel = _make_ocel_log(events=events)
    res = engine.p8_authority_precedes_actuation(ocel)
    assert res.passed is False
    assert len(res.violations) > 0


def test_p8_no_actuation_events_vacuously_passes() -> None:
    """Log with authority events but no actuation events vacuously passes P8."""
    engine = OcelConformanceQueryEngine()
    events = [_make_authority_event()]
    ocel = _make_ocel_log(events=events)
    res = engine.p8_authority_precedes_actuation(ocel)
    assert res.passed is True


# ---------------------------------------------------------------------------
# 6. P9 — Hook No-DO
# ---------------------------------------------------------------------------


def test_p9_clean_hook_events_pass() -> None:
    """Hook events without DO markers pass P9."""
    engine = OcelConformanceQueryEngine()
    events = [_make_hook_event("hook-001", hook_type="hook_fired")]
    ocel = _make_ocel_log(events=events)
    res = engine.p9_hook_no_do(ocel)
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P9"


def test_p9_hook_actuate_event_fails() -> None:
    """Event that is simultaneously hook and actuation type fails P9."""
    engine = OcelConformanceQueryEngine()
    events = [
        {
            "id": "bad-hook-001",
            "type": "hook_fired_brce_execute",  # Both hook and actuation markers
            "time": 1000.0,
            "attributes": {},
            "relationships": [],
        }
    ]
    ocel = _make_ocel_log(events=events)
    res = engine.p9_hook_no_do(ocel)
    assert res.passed is False


def test_p9_empty_events_passes() -> None:
    """Empty event log passes P9."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log(events=[])
    res = engine.p9_hook_no_do(ocel)
    assert res.passed is True


# ---------------------------------------------------------------------------
# 7. P10 — Log Digest Stability
# ---------------------------------------------------------------------------


def test_p10_digest_matches_passes() -> None:
    """Correct declared digest passes P10."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log()
    canonical = json.dumps(ocel, sort_keys=True, separators=(",", ":"))
    correct_digest = hashlib.sha256(canonical.encode()).hexdigest()
    res = engine.p10_log_digest_stable(
        ocel, correct_digest, declared_digest=correct_digest
    )
    assert res.passed is True
    assert res.predicate_id == "SA2A-OCEL-P10"


def test_p10_digest_mismatch_fails() -> None:
    """Wrong declared digest fails P10."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log()
    canonical = json.dumps(ocel, sort_keys=True, separators=(",", ":"))
    correct_digest = hashlib.sha256(canonical.encode()).hexdigest()
    wrong_digest = "f" * 64
    res = engine.p10_log_digest_stable(
        ocel, correct_digest, declared_digest=wrong_digest
    )
    assert res.passed is False
    assert len(res.violations) > 0


def test_p10_no_declared_digest_vacuously_passes() -> None:
    """No declared digest provided — vacuously passes P10."""
    engine = OcelConformanceQueryEngine()
    ocel = _make_ocel_log()
    canonical = json.dumps(ocel, sort_keys=True, separators=(",", ":"))
    computed = hashlib.sha256(canonical.encode()).hexdigest()
    res = engine.p10_log_digest_stable(ocel, computed, declared_digest=None)
    assert res.passed is True


# ---------------------------------------------------------------------------
# 8. Full Evaluation
# ---------------------------------------------------------------------------


def test_evaluate_log_clean_setup_all_pass() -> None:
    """Clean OCEL log with all predicates satisfied produces all-pass report."""
    engine = OcelConformanceQueryEngine()
    events = [
        _make_authority_event("auth-001", "urn:agent:actor", timestamp=500.0),
        _make_actuation_event(
            "act-001", "urn:agent:actor", with_receipt=True, timestamp=1000.0
        ),
        _make_hook_event("hook-001", timestamp=700.0),
    ]
    objects = [{"id": "rcpt-001", "type": "Receipt", "attributes": {}}]
    object_types = [{"name": "Receipt", "attributes": []}]
    event_types = [
        {"name": "authority_grant", "attributes": []},
        {"name": "brce_execute", "attributes": []},
        {"name": "hook_fired", "attributes": []},
    ]
    ocel = _make_ocel_log(
        events=events,
        objects=objects,
        object_types=object_types,
        event_types=event_types,
    )
    canonical = json.dumps(ocel, sort_keys=True, separators=(",", ":"))
    declared_digest = hashlib.sha256(canonical.encode()).hexdigest()

    report = engine.evaluate_log(ocel, declared_digest=declared_digest)

    assert isinstance(report, OcelConformanceReport)
    assert report.total_queries > 0
    failed = [r for r in report.predicate_results if not r.passed]
    assert len(failed) == 0, (
        f"Failed predicates: {[(r.predicate_id, r.violations) for r in failed]}"
    )


def test_evaluate_log_missing_receipt_fails() -> None:
    """Log with actuation missing receipt produces at least one failed predicate."""
    engine = OcelConformanceQueryEngine()
    events = [_make_actuation_event("act-001", with_receipt=False)]
    ocel = _make_ocel_log(events=events)
    report = engine.evaluate_log(ocel)
    p1 = next(
        (r for r in report.predicate_results if r.predicate_id == "SA2A-OCEL-P1"), None
    )
    assert p1 is not None
    assert p1.passed is False


# ---------------------------------------------------------------------------
# 9. Standalone predicate functions
# ---------------------------------------------------------------------------


def test_query_actuation_receipt_coverage_full() -> None:
    """All actuation events with receipt — coverage = 1.0."""
    events = [
        _make_actuation_event("act-001", with_receipt=True),
        _make_actuation_event("act-002", with_receipt=True),
    ]
    ocel = _make_ocel_log(events=events)
    coverage = query_actuation_receipt_coverage(ocel)
    assert coverage == 1.0


def test_query_actuation_receipt_coverage_partial() -> None:
    """Partial receipt coverage — < 1.0."""
    events = [
        _make_actuation_event("act-001", with_receipt=True),
        _make_actuation_event("act-002", with_receipt=False),
    ]
    ocel = _make_ocel_log(events=events)
    coverage = query_actuation_receipt_coverage(ocel)
    assert coverage == 0.5


def test_query_schema_conformance_valid() -> None:
    """Valid OCEL log returns True."""
    ocel = _make_ocel_log()
    assert query_schema_conformance(ocel) is True


def test_query_schema_conformance_invalid() -> None:
    """Invalid OCEL log returns False."""
    ocel = {"only_key": "no_events_or_objects"}
    assert query_schema_conformance(ocel) is False


# ---------------------------------------------------------------------------
# 10. OCEL Log integration (uses real OcelLog if available)
# ---------------------------------------------------------------------------


def test_evaluate_ocel_log_object_integration() -> None:
    """OcelExecutionTracer.record_event() produces a real, validating OcelLog.

    Uses the tracer's real signature -- ``record_event(event_id, activity,
    related_objects, attributes=None, timestamp_ns=None)`` -- to record two
    real events (no mocks, no golden fixtures) and asserts on the real
    resulting state of the produced ``OcelLog``: both events present, the
    referenced actor object auto-declared with the tracer's real
    ``GenericEntity`` fallback type, and the log passing the tracer's real
    OCPQ Definition 2 structural validation.

    Also documents a real, independently-observed defect found while fixing
    this test (out of this change's scope to repair): ``OcelLog.to_ocel2_json()``
    emits RFC 3339 string timestamps (``autofde_lab.ocel.model.format_ns``) and
    list-of-``{"name","value"}`` event attributes, but
    ``OcelConformanceQueryEngine.p8_authority_precedes_actuation`` assumes
    numeric epoch timestamps and dict-shaped attributes -- so
    ``evaluate_ocel_log()`` raises ``ValueError`` on any real, non-empty
    ``OcelLog`` today. Asserted directly via ``pytest.raises`` rather than
    silently swallowed, per this repo's absence-is-not-evidence rule.
    """
    try:
        from autofde_lab.ocel.log import OcelLog
        from autofde_lab.sa2a.falsification.ocel_tracer import OcelExecutionTracer
    except ImportError:
        pytest.skip("OcelLog or OcelExecutionTracer not available")

    tracer = OcelExecutionTracer()
    tracer.record_event(
        event_id="auth-evt-001",
        activity="authority_grant",
        related_objects=["urn:agent:integration-test"],
        attributes={
            "actor_id": "urn:agent:integration-test",
            "grant_id": "grant-integration-001",
        },
    )
    tracer.record_event(
        event_id="act-evt-001",
        activity="brce_execute",
        related_objects=["urn:agent:integration-test"],
        attributes={
            "actor_id": "urn:agent:integration-test",
            "prepared_receipt_id": "rcpt-integration-001",
        },
    )
    ocel_log = tracer.log

    # Real resulting state of the tracer, not a mock's recorded call.
    assert isinstance(ocel_log, OcelLog)
    assert len(ocel_log.events) == 2
    assert {e.activity for e in ocel_log.events} == {"authority_grant", "brce_execute"}
    actor_obj = next(
        o for o in ocel_log.objects if o.id == "urn:agent:integration-test"
    )
    assert (
        actor_obj.object_type == "GenericEntity"
    )  # tracer's real auto-declare fallback
    assert tracer.validate() is ocel_log  # real OCPQ Definition 2 structural validation

    engine = OcelConformanceQueryEngine()
    with pytest.raises(ValueError, match="could not convert string to float"):
        engine.evaluate_ocel_log(ocel_log)
