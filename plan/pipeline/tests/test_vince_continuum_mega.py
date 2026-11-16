"""The Vince continuum: every example from the walkthrough, one entity, one store, real Chromium.

One browser run drives all work orders of mega_factories.build(): AMC survey, Nestle tagged and
untagged units, CVS primary out-of-coverage (plans, territory flag, sales rep notified), CVS repair with an escalated provider ban, repair to project
with a site exclusion, the sole-provider secondary client, and a recall whose NTE sits under the
charge. The store is judged three ways: per-work-order outcome against the factory's expectation,
avatar roster coverage against avatar_roster.toml, and pm4pytest conformance/OCPQ/SLA. A twin test
judges the same store against a path with an extra activity and must violate (anti-vacuity)."""
import json
import os
import tomllib
from pathlib import Path

import pytest
from pm4pytest.conformance import ConformanceSpec
from pm4pytest.ocpq import OCPQ
from pm4pytest.temporal import TemporalSLA

import jtbd_factories as jf
import mega_factories as mf
import ui_driver
import ui_plan
from enterprise_pipeline import ocel_bridge, store

HERE = Path(__file__).resolve().parent
ENV = tomllib.loads((HERE / "conformance_envelopes.toml").read_text())
ACT, OBJ, RATIO, SLA = ENV["activities"], ENV["objects"], ENV["ratios"], ENV["sla_seconds"]
ROSTER = tomllib.loads((HERE / "avatar_roster.toml").read_text())
SEED = jf.seed_from_env()
RESULTS = Path(os.environ.get("PLAN_RESULTS_DIR") or HERE / ".results")
VIOLATION = "PETRI_NET_FITNESS_VIOLATION"
print(f"PLAN_TEST_SEED={SEED}")


@pytest.fixture(scope="module")
def continuum(tmp_path_factory):
    jf.reseed(SEED)
    mega = mf.build()
    tmp = tmp_path_factory.mktemp("continuum")
    with ui_driver.live_server(tmp) as srv:
        rec = ui_plan.run_plan(srv["url"], mega, srv["store"], tmp,
                               headed=os.environ.get("HEADED") == "1")
        yield {"mega": mega, "rec": rec, "store": srv["store"]}


def outcome_of(events, wo):
    """Per-work-order outcome derived only from the store."""
    kinds = [e["kind"] for e in events if e["payload"].get("wo") == wo]
    if "ledger_settled" in kinds:
        return "settled"
    if "plan_closed" in kinds:
        return "refused"          # closed plan, no settlement: the ledger refused
    if "plan_dispatched" in kinds:
        return "refused"          # stage-2 plan was refused
    return "flagged"              # stage-1 plan was refused at intake


def declare(session, mega, intended, store_file, *, strict_objects=True):
    ocel_bridge.replay_into_session(session, store_file)
    spec = ConformanceSpec.from_fsm([intended], min_fitness=1.0)
    spec.allowed_transitions = ocel_bridge.bounded_transitions(
        ocel_bridge.alphabet(store_file) | set(intended))
    session.set_conformance(spec)
    if not strict_objects:
        return
    session.set_ocpq(OCPQ().require_object_type(*OBJ["required"]).traverse(*OBJ["traversal"])
                     .require_balanced_ratio(ACT["checkin"], ACT["checkout"], RATIO["checkin_to_checkout"])
                     .require_activity(ACT["model_tag_media"]))
    session.set_temporal_sla(
        TemporalSLA()
        .require_max_latency(ACT["dispatch"], ACT["checkin"], SLA["dispatch_to_checkin"])
        .require_max_latency(ACT["checkin"], ACT["checkout"], SLA["checkin_to_checkout"]))


@pytest.mark.conformance
@pytest.mark.ocpq
@pytest.mark.temporal_sla
def test_vince_continuum_mega(continuum, pm4py_session):
    mega, sf = continuum["mega"], continuum["store"]
    events = store.read(sf)
    table = {}
    for wo, (label, want, gate) in mega.expected.items():
        got = outcome_of(events, wo)
        table[label] = {"wo": wo, "expected": want, "observed": got, "gate": gate}
    RESULTS.mkdir(parents=True, exist_ok=True)
    avatars = sorted({e["avatar"] for e in events})
    (RESULTS / "vince_continuum.json").write_text(json.dumps({
        "seed": SEED, "events": len(events), "avatars": avatars, "work_orders": table,
        "steps_done": continuum["rec"]["steps_done"], "steps_planned": len(mega.steps)}, indent=1))
    print("\nwork order               expected  observed  gate")
    for label, r in table.items():
        print(f"{label:<24} {r['expected']:<9} {r['observed']:<9} {r['gate']}")
    bad = {k: r for k, r in table.items() if r["expected"] != r["observed"]}
    assert not bad, f"work orders off their expected outcome: {bad}"
    # escalations officer acted: the ban and the site exclusion are real events
    kinds = {e["kind"] for e in events}
    assert {"provider_blacklist", "provider_filter"} <= kinds
    flagged = [wo for wo, (label, _, _) in mega.expected.items() if label == "cvs_out_of_coverage"]
    for k in ("territory_flag", "sales_rep_notified"):
        assert {e["payload"].get("wo") for e in events if e["kind"] == k} == set(flagged), k
    declare(pm4py_session, mega, mega.intended, sf)


def test_avatar_roster_coverage(continuum):
    """Every role named in the walkthrough is either driven (its avatar wrote events) or a counted gap."""
    avatars = {e["avatar"] for e in store.read(continuum["store"])}
    driven = ROSTER["roles"]
    missing = {r: a for r, a in driven.items() if a not in avatars}
    assert not missing, f"mapped roles whose avatar never acted: {missing}"
    gaps = ROSTER["unsupported"]
    assert not set(driven) & set(gaps), "a role cannot be both driven and unsupported"
    print(f"\nROSTER driven={len(driven)} unsupported={len(gaps)}")
    for role, why in sorted(gaps.items()):
        print(f"UNSUPPORTED[{role}]: {why}")


@pytest.mark.conformance
@pytest.mark.expected_conformance_violation(VIOLATION)
def test_vince_continuum_twin_must_violate(continuum, pm4py_session):
    """Same store, judged against a path that demands one more activity: must fail fitness."""
    mega = continuum["mega"]
    declare(pm4py_session, mega, mega.intended + [ACT["ledger_settled"]], continuum["store"],
            strict_objects=False)
