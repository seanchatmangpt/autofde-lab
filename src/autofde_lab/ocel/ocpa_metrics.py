# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Object-Centric Process Analysis (OCPA) integration for AutoFDE and ~/ash_*.

Bridges multi-object interaction analysis, calculating:
- Object synchronization delays between concurrent A2A agents and Reactor steps
- Resource pooling and contention across shared Ash resources
- Object interaction graphs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autofde_lab.ocel.log import OcelLog

__all__ = [
    "OCPA_AVAILABLE",
    "ObjectInteractionMetric",
    "calculate_object_synchronization_delays",
    "ocel_to_ocpa_object_centric_event_log",
]

try:
    import pandas as pd
    from ocpa.objects.log.importer.ocel import factory as ocel_import_factory
    from ocpa.objects.log.ocel import OCEL

    OCPA_AVAILABLE = True
except ImportError:  # pragma: no cover
    OCPA_AVAILABLE = False
    OCEL = None
    ocel_import_factory = None
    pd = None


@dataclass(frozen=True)
class ObjectInteractionMetric:
    """Quantitative measurement of multi-object interaction."""

    source_object_id: str
    target_object_id: str
    event_id: str
    activity: str
    delay_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _require_ocpa() -> None:
    if not OCPA_AVAILABLE:
        raise RuntimeError("ocpa is required for advanced multi-object metrics.")


def ocel_to_ocpa_object_centric_event_log(ocel_log: OcelLog) -> Any:
    """Convert an AutoFDE OcelLog into an OCPA OCEL object via temporary JSON interchange."""
    _require_ocpa()
    import json
    import tempfile
    from datetime import datetime, timezone

    obj_dict = {
        obj.id: {"ocel:type": obj.object_type, "ocel:ovmap": {}}
        for obj in ocel_log.objects
    }
    e_links: dict[str, list[str]] = {}
    for link in ocel_log.event_object_links:
        e_links.setdefault(link.event_id, []).append(link.object_id)

    events_dict: dict[str, dict[str, Any]] = {}
    for e in ocel_log.events:
        dt = datetime.fromtimestamp(e.timestamp_ns / 1e9, tz=timezone.utc).isoformat()
        events_dict[e.id] = {
            "ocel:activity": e.activity,
            "ocel:timestamp": dt,
            "ocel:omap": e_links.get(e.id, []),
            "ocel:vmap": {},
        }

    data = {
        "ocel:global-log": {
            "ocel:attribute-names": [],
            "ocel:object-types": list({obj.object_type for obj in ocel_log.objects}),
        },
        "ocel:events": events_dict,
        "ocel:objects": obj_dict,
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as f:
        json.dump(data, f)
        f.flush()
        return ocel_import_factory.apply(f.name, parameters={})


def calculate_object_synchronization_delays(
    ocel_log: OcelLog,
) -> list[ObjectInteractionMetric]:
    """Calculate synchronization delays across events that join two or more distinct objects.

    When an event links multiple objects (e.g. an A2A Agent interacting with an Ash Resource),
    the synchronization delay measures the time elapsed since the previous event of each participating object.
    """
    metrics: list[ObjectInteractionMetric] = []
    last_event_time: dict[str, int] = {}

    # Sort events chronologically
    sorted_events = sorted(ocel_log.events, key=lambda e: (e.timestamp_ns, e.id))
    links_by_event: dict[str, list[str]] = {}
    for link in ocel_log.event_object_links:
        links_by_event.setdefault(link.event_id, []).append(link.object_id)

    for event in sorted_events:
        involved_objects = links_by_event.get(event.id, [])
        if len(involved_objects) >= 2:
            # Multi-object interaction / synchronization point
            for i, obj_a in enumerate(involved_objects):
                for obj_b in involved_objects[i + 1 :]:
                    t_a = last_event_time.get(obj_a, event.timestamp_ns)
                    t_b = last_event_time.get(obj_b, event.timestamp_ns)
                    delay_ns = abs(t_a - t_b)
                    delay_sec = delay_ns / 1e9

                    metrics.append(
                        ObjectInteractionMetric(
                            source_object_id=obj_a,
                            target_object_id=obj_b,
                            event_id=event.id,
                            activity=event.activity,
                            delay_seconds=delay_sec,
                        )
                    )

        # Update last seen timestamp for each involved object
        for obj_id in involved_objects:
            last_event_time[obj_id] = event.timestamp_ns

    return metrics
