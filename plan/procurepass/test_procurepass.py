"""Real-solver tests: CP-SAT + PDDL parse via unified_planning PDDLReader."""
import copy, json, pathlib, re, pytest
from supplier_cpsat import solve

HERE = pathlib.Path(__file__).parent
BASE = json.loads((HERE / "scenario_compressor.json").read_text())


def test_optimal_picks_cheapest_feasible():
    r = solve(BASE)
    assert r["status"] == "OPTIMAL"
    assert (r["supplier"], r["delivery_slot_start"]) == ("acme_hvac", 2000)  # slowco cheaper but breaches SLA
    assert r["install_end"] <= BASE["sla_minutes"]
    assert r["path"] == "in_nte" and r["proposal_total"] == 100000 + 180000


def test_lead_time_over_sla_typed_infeasible():
    q = copy.deepcopy(BASE); q["sla_minutes"] = 1000
    r = solve(q)
    assert r["status"] == "INFEASIBLE" and r["reason"] == "LEAD_TIME_EXCEEDS_SLA"


def test_total_over_nte_takes_change_order_path():
    q = copy.deepcopy(BASE); q["nte_limit"] = 250000
    r = solve(q)
    assert r["status"] == "OPTIMAL" and r["path"] == "change_order" and r["change_order_required"]


def test_missing_fields_typed_invalid():
    assert solve({})["reason"] == "MISSING_FIELDS"


def test_slot_before_lead_time_excluded():
    q = copy.deepcopy(BASE); q["options"] = [q["options"][0]]; q["options"][0]["slots"] = [{"start": 100}]
    assert solve(q)["reason"] == "LEAD_TIME_EXCEEDS_SLA"


@pytest.mark.parametrize("p", ["problem_compressor_in_nte.pddl", "problem_compressor_over_nte.pddl"])
def test_pddl_parses_with_real_parser(p):
    from unified_planning.io import PDDLReader
    pr = PDDLReader().parse_problem(str(HERE / "procure_domain.pddl"), str(HERE / p))
    names = {a.name.replace("-", "_") for a in pr.actions}
    assert {"order_part", "deliver_part_to_site", "schedule_return_visit", "spawn_change_order",
            "propose_parts", "client_accept_proposal"} <= names


def test_instances_encode_nte_split():
    def v(f, k):
        t = (HERE / f).read_text()
        labor = int(re.search(r"wo-labor-cost wo_9001\) (\d+)", t)[1])
        cost = int(re.search(r"part-cost po_compressor\) (\d+)", t)[1])
        mk = int(re.search(r"part-markup po_compressor\) (\d+)", t)[1])
        nte = int(re.search(r"wo-nte-limit wo_9001\) (\d+)", t)[1])
        return labor * 100 + cost * mk > nte * 100
    assert not v("problem_compressor_in_nte.pddl", 0)
    assert v("problem_compressor_over_nte.pddl", 0)
