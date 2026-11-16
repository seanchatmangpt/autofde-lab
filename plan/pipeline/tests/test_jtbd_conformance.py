"""JTBD conformance: Playwright only clicks; pm4pytest judges the projected store, fail-closed.

No journey assertions live in the test bodies: the pm4pytest plugin evaluates the specs set on
the session after the call phase (Petri-net/FSM conformance, OCPQ, temporal SLA, anti-vacuity).
The reference order comes from a real happy-path run; the alphabet and the activity names come
from the store via ocel_bridge, and every bound comes from conformance_envelopes.toml."""
import tomllib
from pathlib import Path

import pytest
from pm4pytest.conformance import ConformanceSpec
from pm4pytest.ocpq import OCPQ
from pm4pytest.temporal import TemporalSLA

import ui_driver
from enterprise_pipeline import ocel_bridge

ENV = tomllib.loads((Path(__file__).resolve().parent / "conformance_envelopes.toml").read_text())
ACT, OBJ, RATIO, SLA = ENV["activities"], ENV["objects"], ENV["ratios"], ENV["sla_seconds"]


@pytest.fixture(scope="module")
def happy_store(tmp_path_factory):
    """One real blank-slate -> settlement journey (model tag included); yields its store file."""
    tmp = tmp_path_factory.mktemp("happy")
    with ui_driver.live_server(tmp) as srv:
        ui_driver.drive_ui_journey(srv["url"], ui_driver.CFG, srv["store"], include_model_tag=True,
                                   tmp=tmp)
        yield srv["store"]


def judge(session, store_file, reference_store):
    """Replay the store into the session and declare every gate; pm4pytest evaluates them."""
    ocel_bridge.replay_into_session(session, store_file)
    paths = [ocel_bridge.trace(reference_store)]
    spec = ConformanceSpec.from_fsm(paths, min_fitness=1.0)
    spec.allowed_transitions = ocel_bridge.bounded_transitions(
        ocel_bridge.alphabet(store_file) | ocel_bridge.alphabet(reference_store))
    session.set_conformance(spec)
    session.set_ocpq(
        OCPQ().require_object_type(*OBJ["required"]).traverse(*OBJ["traversal"])
        .require_activity(ACT["model_tag_media"])
        .require_balanced_ratio(ACT["checkin"], ACT["checkout"], RATIO["checkin_to_checkout"])
        .require_balanced_ratio(ACT["plan_closed"], ACT["ledger_settled"],
                                RATIO["plan_closed_to_ledger_settled"]))
    session.set_temporal_sla(
        TemporalSLA()
        .require_max_latency(ACT["dispatch"], ACT["checkin"], SLA["dispatch_to_checkin"])
        .require_max_latency(ACT["checkin"], ACT["checkout"], SLA["checkin_to_checkout"])
        .require_max_latency(ACT["work_order"], ACT["ledger_settled"],
                             SLA["work_order_to_ledger_settled"]))


@pytest.mark.conformance
@pytest.mark.ocpq
@pytest.mark.temporal_sla
def test_jtbd_compressor_replacement_happy_path(pm4py_session, happy_store):
    judge(pm4py_session, happy_store, happy_store)


@pytest.mark.conformance
@pytest.mark.expected_conformance_violation("PETRI_NET_FITNESS_VIOLATION")
def test_jtbd_withheld_model_tag_violates_fitness(pm4py_session, live_streamlit,
                                                  drive_ui_journey, happy_store):
    url, store_file, cfg, tmp = live_streamlit
    drive_ui_journey(url, cfg, store_file, include_model_tag=False, tmp=tmp)
    ocel_bridge.replay_into_session(pm4py_session, store_file)
    spec = ConformanceSpec.from_fsm([ocel_bridge.trace(happy_store)], min_fitness=1.0)
    spec.allowed_transitions = ocel_bridge.bounded_transitions(
        ocel_bridge.alphabet(store_file) | ocel_bridge.alphabet(happy_store))
    pm4py_session.set_conformance(spec)
