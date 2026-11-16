"""Eight factory-generated JTBD plans, each driven through the real UI and judged by pm4pytest.

Four plans are built to run to settlement and four to be refused by a real gate (stage-2 plan,
stage-1 plan plus dispatch eligibility, the dual-clock plan, the ledger). Playwright only clicks;
the store is projected into the pm4py session and pm4pytest decides, fail-closed: pass plans must
conform with fitness 1.0, fail plans must violate it (their observed trace stops before the
intended path ends)."""
import json
import os
import tomllib
from pathlib import Path

import pytest
from pm4pytest.conformance import ConformanceSpec
from pm4pytest.ocpq import OCPQ
from pm4pytest.temporal import TemporalSLA

import jtbd_factories as jf
import ui_driver
import ui_plan
from enterprise_pipeline import ocel_bridge

HERE = Path(__file__).resolve().parent
ENV = tomllib.loads((HERE / "conformance_envelopes.toml").read_text())
ACT, OBJ, RATIO, SLA = ENV["activities"], ENV["objects"], ENV["ratios"], ENV["sla_seconds"]
VIOLATION = "PETRI_NET_FITNESS_VIOLATION"
SEED = jf.seed_from_env()
RESULTS = Path(os.environ.get("PLAN_RESULTS_DIR") or HERE / ".results")
print(f"PLAN_TEST_SEED={SEED}")


def _marks(sc):
    if sc.verdict == "pass":
        return [pytest.mark.conformance, pytest.mark.ocpq, pytest.mark.temporal_sla]
    return [pytest.mark.conformance, pytest.mark.expected_conformance_violation(VIOLATION)]


SCENARIOS = jf.batch(SEED)
PARAMS = [pytest.param(sc, id=sc.name, marks=_marks(sc)) for sc in SCENARIOS]


def judge(session, store_file, sc):
    """Replay the store into the session and declare the gates; pm4pytest evaluates them."""
    ocel_bridge.replay_into_session(session, store_file)
    spec = ConformanceSpec.from_fsm([sc.intended], min_fitness=1.0)
    spec.allowed_transitions = ocel_bridge.bounded_transitions(
        ocel_bridge.alphabet(store_file) | set(sc.intended))
    session.set_conformance(spec)
    if sc.verdict != "pass":
        return
    ocpq = (OCPQ().require_object_type(*OBJ["required"]).traverse(*OBJ["traversal"])
            .require_balanced_ratio(ACT["checkin"], ACT["checkout"], RATIO["checkin_to_checkout"])
            .require_balanced_ratio(ACT["plan_closed"], ACT["ledger_settled"],
                                    RATIO["plan_closed_to_ledger_settled"]))
    if sc.part:
        ocpq = ocpq.require_activity(ACT["model_tag_media"])
    session.set_ocpq(ocpq)
    session.set_temporal_sla(
        TemporalSLA()
        .require_max_latency(ACT["dispatch"], ACT["checkin"], SLA["dispatch_to_checkin"])
        .require_max_latency(ACT["checkin"], ACT["checkout"], SLA["checkin_to_checkout"])
        .require_max_latency(ACT["work_order"], ACT["ledger_settled"], SLA["work_order_to_ledger_settled"]))


@pytest.mark.parametrize("sc", PARAMS)
def test_jtbd_plan(sc, pm4py_session, tmp_path):
    headed = os.environ.get("HEADED") == "1"
    with ui_driver.live_server(tmp_path) as srv:
        rec = ui_plan.run_plan(srv["url"], sc, srv["store"], tmp_path, headed=headed)
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"{sc.name}.json").write_text(json.dumps({
            "plan": sc.name, "expected": sc.verdict, "gate": sc.gate, "fault": sc.fault,
            "steps_planned": len(sc.steps), "steps_done": rec["steps_done"],
            "intended_activities": len(sc.intended), "observed_activities": len(rec["observed"]),
            "completed": rec["observed"] == sc.intended, "seed": SEED}, indent=1))
        judge(pm4py_session, srv["store"], sc)
