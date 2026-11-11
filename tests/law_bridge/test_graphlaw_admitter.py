"""Courts for the GraphLaw bridge: real WASM module, real CP-SAT plans, real pm4pytest verdicts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PM4 = "/Users/sac/pm4pytest"
if Path(PM4).is_dir() and PM4 not in sys.path:
    sys.path.append(PM4)

from autofde_lab.law_bridge import Action, GraphLawAdmitter, GraphLawUnavailable
from autofde_lab.law_bridge.airport_encoding import stand_actions, turnaround_actions

try:
    ADM = GraphLawAdmitter()
except GraphLawUnavailable as exc:  # loud skip, never a faked pass
    pytest.skip(f"BLOCKED: graphlaw wasm unavailable: {exc}", allow_module_level=True)

pm = pytest.importorskip("tests.airport.planning.test_rows_scheduling",
                         reason="BLOCKED: set PYTHONPATH=/Users/sac/pm4pytest")
from pm4pytest import ConformanceSpec
from tests.airport.factories import SERVICES
from tests.airport.planning.common import executed_trace, verdict

T = lambda v: f"<urn:d:door> <urn:p:is> <urn:v:{v}> ."


def test_readme_door_plan_matches_published_hash():
    r = ADM.admit(T("closed"), [
        Action("open", T("closed"), T("open"), T("closed")),
        Action("close", T("open"), T("closed"), T("open")),
        Action("lock", T("closed"), T("locked"), T("closed")),
    ], goal=T("locked"))
    assert r.status == "ADMITTED"
    assert r.state_id.startswith("blake3:3be6530b")
    assert len(r.receipts) == 3 and r.chain[-1] == r.state_id
    assert r.receipts[1]["parent"] == r.receipts[0]["child"]


def test_refusal_names_step_and_unmet_triple_and_admits_nothing_later():
    key = "<urn:d:door> <urn:p:has> <urn:v:key> ."
    r = ADM.admit(T("closed"), [Action("lock", T("closed"), T("locked")),
                                Action("paint", key, T("red")),
                                Action("polish", T("locked"), T("shiny"))])
    assert r.status == "REFUSED" and r.index == 1 and r.action == "paint"
    assert r.unmet == (key,)
    assert r.admitted_actions == ("lock",)


def test_rule_pack_derivation_precedes_plan():
    rules = [{"step": "n3", "rules": "{ ?x <urn:p:is> <urn:v:closed> } => { ?x <urn:p:has> <urn:v:key> } ."}]
    key = "<urn:d:door> <urn:p:has> <urn:v:key> ."
    r = ADM.admit(T("closed"), [Action("paint", key, T("red"))], rules=rules)
    assert r.status == "ADMITTED"
    assert ADM.admit(T("closed"), [Action("paint", key, T("red"))]).status == "REFUSED"


def _turnaround():
    t = pm.TestChapter1TurnaroundScheduling()
    vocab, roles, ids, dur, crew, capacity, sched = t._solve()
    order = sorted(roles, key=lambda r: (sched[ids[r]]["start_time"], ids[r]))
    steps = [(vocab[r], sched[ids[r]]["start_time"] * 60.0 + ids[r] * 1e-3) for r in roles]
    return vocab, order, steps, roles, ids, sched


def test_ch1_turnaround_plan_is_admitted_and_fitness_is_one():
    vocab, order, steps, *_ = _turnaround()
    init, acts = turnaround_actions(order, "deboarding", SERVICES, "boarding")
    r = ADM.admit(init, acts)
    assert r.status == "ADMITTED" and len(r.receipts) == len(order)
    spec = ConformanceSpec.from_fsm(pm._service_perms(vocab))
    ok, viol = verdict(spec, executed_trace("turn-ok", steps))
    assert ok, viol
    assert spec.evaluate(executed_trace("turn-ok2", steps).events()).success


def test_ch1_refuel_during_boarding_is_refused_at_boarding():
    vocab, order, steps, roles, ids, sched = _turnaround()
    bad = [a for a in order if a != "boarding"]
    bad.insert(bad.index("refuel"), "boarding")  # boarding starts before refuelling finishes
    init, acts = turnaround_actions(bad, "deboarding", SERVICES, "boarding")
    r = ADM.admit(init, acts)
    assert r.status == "REFUSED" and r.action == "boarding"
    assert r.index == bad.index("boarding")
    assert r.unmet and all("done" in u for u in r.unmet)
    # the same mutation fails pm4pytest on the equivalent trace
    ts = {vocab[x]: s for x, s in zip(roles, [v for _, v in steps])}
    ts[vocab["boarding"]] = ts[vocab["refuel"]] - 1.0
    spec = ConformanceSpec.from_fsm(pm._service_perms(vocab))
    ok, viol = verdict(spec, executed_trace("turn-bad", list(ts.items())))
    assert not ok


def _stand_case():
    t = pm.TestChapter2StandAssignment()
    flights = t._problem()
    assignment = t._assign(flights, stands=t._max_overlap(flights))
    return t, flights, assignment


def _events(flights, assignment):
    ev = []
    for f, a, d in flights:
        ev.append((a * 60.0 + 0.5, "occupy", assignment[f], f))
        ev.append((d * 60.0, "release", assignment[f], f))
    ev.sort(key=lambda e: e[0])
    return [(k, str(s), f) for _, k, s, f in ev]


def test_ch8_stand_dispatch_admitted_and_fitness_one():
    t, flights, assignment = _stand_case()
    init, acts = stand_actions(_events(flights, assignment))
    assert ADM.admit(init, acts).status == "ADMITTED"
    occ, rel, spec = t._spec()
    for s, tr in t._per_stand_traces(flights, assignment, occ, rel).items():
        ok, viol = verdict(spec, tr)
        assert ok, (s, viol)


def test_ch8_double_booked_stand_refused_at_second_occupy():
    t, flights, assignment = _stand_case()
    f0, f1 = flights[0], flights[1]
    flights[1] = (f1[0], f0[1] + 1, f0[2] + 5)  # overlaps flight 0
    assignment[f1[0]] = assignment[f0[0]]       # same stand
    ev = _events(flights, assignment)
    init, acts = stand_actions(ev)
    r = ADM.admit(init, acts)
    assert r.status == "REFUSED"
    assert r.action.split(":")[1] == "occupy" and r.action.endswith(f1[0])
    assert r.unmet and "free" in r.unmet[0]
    assert not any(a.endswith(f1[0]) for a in r.admitted_actions)
    occ, rel, spec = t._spec()
    assert any(not verdict(spec, tr)[0] for tr in t._per_stand_traces(flights, assignment, occ, rel).values())
