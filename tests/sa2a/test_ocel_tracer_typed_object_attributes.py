# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Permanent tripwire for the OCEL execution tracer's object-attribute typing.

Guards the law violated on 2026-09-17 (boundary qualification, release
v26.9.17): ``OcelExecutionTracer.declare_object`` used to append raw
``(key, value)`` tuples into ``OcelObject.attributes``, whose declared type is
``tuple[OcelAttribute, ...]``. Every downstream ``to_ocel2_json`` export then
crashed with ``AttributeError: 'tuple' object has no attribute 'value'``
(``ocel/log.py::to_ocel2``) — taking the whole RFC-SA2A-002 Appendix D
Chicago Crown Qualification runner down with it. Object attributes must be
typed ``OcelAttribute`` at the tracer boundary; this test fails if raw tuples
re-enter that field.
"""

from __future__ import annotations

import json
from pathlib import Path

from autofde_lab.sa2a.falsification.ocel_tracer import OcelExecutionTracer


def test_declared_object_attributes_are_typed_and_export_conformantly(
    tmp_path: Path,
) -> None:
    tracer = OcelExecutionTracer(trace_id="tripwire_typed_object_attributes")
    tracer.declare_object(
        "urn:tripwire:release",
        "ReleaseArtifact",
        {"release": "v26.9.17", "gates": 12, "genuine": True},
    )
    tracer.record_event(
        event_id="evt_tripwire_gate_01",
        activity="TRIPWIRE:TypedObjectAttributes",
        related_objects=["urn:tripwire:release"],
        attributes={"passed": True},
    )

    out = tmp_path / "tripwire.ocel.json"
    returned = tracer.export_ocel2_json(out)

    assert returned == out
    assert out.exists()
    doc = json.loads(out.read_text(encoding="utf-8"))

    object_types = {t["name"]: t for t in doc["objectTypes"]}
    release_type = object_types["ReleaseArtifact"]
    declared = {a["name"]: a["type"] for a in release_type["attributes"]}
    assert declared == {"release": "string", "gates": "integer", "genuine": "boolean"}
