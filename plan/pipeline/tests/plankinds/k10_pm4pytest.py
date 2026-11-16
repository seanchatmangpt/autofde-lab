"""K10: pm4pytest gates (FSM conformance, OCPQ rules, TemporalSLA) over generated traces.

Activities come from the store's own observation vocabulary; a conformant trace is PLAN, a
trace the gate rejects is REFUSED. Evaluation goes through the real PM4PySession."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import Case, Outcome, Skip

KIND = "K10"
TITLE = "pm4pytest conformance / OCPQ / TemporalSLA"
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _acts():
    from enterprise_pipeline import store
    return list(store.OBSERVATIONS)


def probe():
    try:
        import pm4pytest  # noqa: F401
        import pm4py  # noqa: F401
        from enterprise_pipeline import store  # noqa: F401
    except ImportError as e:
        return Skip(f"import failed: {e}", "uv run --with /Users/sac/pm4pytest (PYTHONPATH=pipeline)")
    return None


def cases():
    return [
        Case("fsm_conformant", "PLAN", {"gate": "fsm", "order": "intended"}),
        Case("fsm_reordered", "REFUSED", {"gate": "fsm", "order": "reversed"}),
        Case("fsm_truncated", "REFUSED", {"gate": "fsm", "order": "truncated"}),
        Case("ocpq_rules_hold", "PLAN", {"gate": "ocpq", "drop": False}),
        Case("ocpq_activity_missing", "REFUSED", {"gate": "ocpq", "drop": True}),
        Case("sla_within_bound", "PLAN", {"gate": "sla", "gap": 10, "bound": 60}),
        Case("sla_over_bound", "REFUSED", {"gate": "sla", "gap": 120, "bound": 60}),
    ]


def _emit(session, trace, gap=1):
    session.register_object("obj1", "plan")
    for i, a in enumerate(trace):
        session.emit_event(f"ev{i}", a, timestamp=BASE + timedelta(seconds=i * gap),
                           relationships=[{"objectId": "obj1", "qualifier": "of"}])


def run(case):
    from pm4pytest.conformance import ConformanceSpec
    from pm4pytest.ocpq import OCPQ
    from pm4pytest.plugin import PM4PySession
    from pm4pytest.temporal import TemporalSLA

    acts, p = _acts(), case.payload
    s = PM4PySession(test_name=f"k10_{case.id}")
    try:
        if p["gate"] == "fsm":
            trace = {"intended": acts, "reversed": acts[::-1], "truncated": acts[:-1]}[p["order"]]
            _emit(s, trace)
            s.set_conformance(ConformanceSpec.from_fsm([acts], min_fitness=1.0))
        elif p["gate"] == "ocpq":
            _emit(s, acts[:-1] if p["drop"] else acts)
            s.set_ocpq(OCPQ().require_object_type("plan").require_activity(acts[0])
                       .require_activity(acts[-1]).require_balanced_ratio(acts[0], acts[1], 1.0))
        else:
            _emit(s, acts, gap=p["gap"])
            s.set_temporal_sla(TemporalSLA().require_max_latency(acts[0], acts[1], p["bound"]))
        ok, violations, _ = s.evaluate_all()
    finally:
        s.cleanup()
    return Outcome("PLAN" if ok else "REFUSED", "; ".join(v[:120] for v in violations[:2]) or "all gates held")
