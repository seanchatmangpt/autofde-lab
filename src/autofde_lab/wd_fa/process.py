from __future__ import annotations

from pathlib import Path

from .domain import FailureCase
from .synthetic import event_rows


def build_ocel(case: FailureCase):
    from pm4py.objects.ocel.obj import OCEL

    events, objects, relations = event_rows(case)
    return OCEL(events=events, objects=objects, relations=relations)


def roundtrip_ocel2(case: FailureCase, path: Path):
    import pm4py

    ocel = build_ocel(case)
    pm4py.write_ocel2(ocel, str(path))
    return pm4py.read_ocel2(str(path))


def process_evidence(case: FailureCase) -> dict[str, object]:
    import pm4py

    ocel = build_ocel(case)
    object_types = tuple(sorted(pm4py.ocel_get_object_types(ocel)))
    ocdfg = pm4py.discover_ocdfg(ocel)
    flattened = pm4py.ocel_flattening(ocel, "Drive")
    powl = pm4py.discover_powl(flattened)
    return {
        "object_types": object_types,
        "event_count": len(ocel.events),
        "relation_count": len(ocel.relations),
        "ocdfg_activities": tuple(sorted(ocdfg["activities"])),
        "powl_type": type(powl).__name__,
        "powl": powl,
    }
