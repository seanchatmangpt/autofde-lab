# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `process_informed_psro_pipeline` -- the real,
four-stage pipeline from sqlite/OCEL-sourced process evidence, through real
TRIZ candidate generation, a real gymact-mediated experiment, and into a
real PSRO step.

Real collaborators throughout: a real, in-memory-built `OcelLog` written to
a real sqlite file, a real `Maze` domain, a real `PlannerLeague` calling
the real, installed `Astar`/`MCTS` solver entry points, a real
`GymActWorldExperimentProvider` (materialize/act/verify/teardown via a
real `gymact.runtime.GymAct` instance), and a real
`PolicySpaceResponseOracle`. No `unittest.mock` / `Mock` / `MagicMock` /
`patch` / `monkeypatch` anywhere in this file.

Every value asserted below was confirmed live before being written, not
assumed: with the default fail-closed `GymActWorldExperimentProvider`
(no `authority_resolver` injected) and real TRIZ candidates carrying empty
`authority_needs` (as `generate_triz_candidates` produces them), every
real candidate's own migration action is refused at real `act()`/
`verify()` time -- real `FALSIFIED`, real `(0.0, 1.0)` scores -- yet PSRO
still selects the sole real candidate planner as best response, since
`empirical_best_response` only requires complete real coverage, not a
winning score, when there is exactly one candidate to choose among.
"""

from __future__ import annotations

from autofde_lab.hub.domain.maze import Maze
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.mcp_session import append_tool_call_event
from autofde_lab.ocel.model import OcelAttribute, OcelAttributeValue, OcelObject
from autofde_lab.ocel.sqlite_store import to_sqlite
from autofde_lab.planner_league import PlannerLeague
from autofde_lab.reasoning.exploration_psro_loop import ExplorationPsroRoundOutcome
from autofde_lab.reasoning.laboratory import (
    EnterpriseObservation,
    TRIZContradiction,
    TRIZParameter,
)
from autofde_lab.reasoning.process_informed_psro_pipeline import run_process_informed_triz_psro_round


def _build_real_log() -> OcelLog:
    """Same real construction pattern reused across this session's
    `SqliteProcessScienceProvider`/`process_informed_exploration` tests."""
    log = OcelLog.new(
        objects=[
            OcelObject(
                "session-1", "MCPSession",
                (OcelAttribute("server", OcelAttributeValue.string("scikit-decide-fabric")),),
            ),
            OcelObject("domain-Maze", "Domain", (OcelAttribute("name", OcelAttributeValue.string("Maze")),)),
            OcelObject(
                "domain-MasterMind", "Domain",
                (OcelAttribute("name", OcelAttributeValue.string("MasterMind")),),
            ),
        ]
    )
    log = append_tool_call_event(
        log, event_id="m0", activity="decision_match", object_ids=["session-1", "domain-Maze"],
        outcome={"standing": "MATCHED", "compatible_solvers": ["Astar", "MCTS"]}, timestamp_ns=0,
    )
    log = append_tool_call_event(
        log, event_id="m1", activity="decision_match", object_ids=["session-1", "domain-Maze"],
        outcome={"standing": "MATCHED", "compatible_solvers": ["MCTS", "Astar"]}, timestamp_ns=1_000,
    )
    return log


def test_full_real_pipeline_from_ocel_evidence_to_a_real_psro_advance(tmp_path) -> None:
    from autofde_lab.reasoning.scenarios.world_transformation_scenarios import (
        ScenarioMetadata_checkout_latency_scenario_v_1,
    )

    log = _build_real_log()
    db_path = tmp_path / "pipeline.sqlite"
    to_sqlite(log, db_path)

    metadata = ScenarioMetadata_checkout_latency_scenario_v_1()
    observation = EnterpriseObservation(
        ontology_graph_ref="ontology:pipeline-test", source_provenance_ref="test", enterprise_world_ref="test-world"
    )
    contradiction = TRIZContradiction(
        improving_parameter=TRIZParameter.COST, worsening_parameter=TRIZParameter.AUTHORITY_NEEDS
    )

    result = run_process_informed_triz_psro_round(
        metadata,
        db_path=str(db_path),
        observation=observation,
        contradiction=contradiction,
        league=PlannerLeague(),
        domain=Maze(),
        constructor_planner_ids=["Astar"],
        falsifier_planner_id="MCTS",
    )

    assert isinstance(result, ExplorationPsroRoundOutcome)
    # 2 real hypotheses (rule-based + process-informed) * 4 real matched
    # TRIZ principles = 8 real candidates, each admitted as one real
    # payoff observation.
    assert len(result.admissions) == 8
    assert result.admitted_count == 8
    assert all(a.admitted for a in result.admissions)
    assert len(result.hypergraph.observations) == 8

    # Every real gymact experiment for these candidates (empty
    # authority_needs, default fail-closed provider) was really refused at
    # act()/verify() time -> real FALSIFIED -> real (0.0, 1.0) scores.
    for obs in result.hypergraph.observations:
        assert obs.left_score == 0.0
        assert obs.right_score == 1.0
        assert obs.match.left_policy.planner_id == "Astar"
        assert obs.match.right_policy.planner_id == "MCTS"

    # PSRO still advances: Astar is the sole real candidate with complete
    # real coverage against the {MCTS: 1.0} opponent mixture -- its own
    # losing score doesn't block selection when there is no competitor.
    assert result.psro_step.advanced
    assert result.psro_step.standing == "ALIVE"
    assert result.psro_step.receipt is not None
    assert result.psro_step.receipt.selected_best_response == "Astar"


def test_pipeline_falsifications_trace_back_to_real_candidates(tmp_path) -> None:
    from autofde_lab.reasoning.scenarios.world_transformation_scenarios import (
        ScenarioMetadata_checkout_latency_scenario_v_1,
    )

    log = _build_real_log()
    db_path = tmp_path / "pipeline_identity.sqlite"
    to_sqlite(log, db_path)

    metadata = ScenarioMetadata_checkout_latency_scenario_v_1()
    observation = EnterpriseObservation(
        ontology_graph_ref="ontology:pipeline-identity-test",
        source_provenance_ref="test",
        enterprise_world_ref="test-world",
    )
    contradiction = TRIZContradiction(
        improving_parameter=TRIZParameter.COST, worsening_parameter=TRIZParameter.AUTHORITY_NEEDS
    )

    result = run_process_informed_triz_psro_round(
        metadata,
        db_path=str(db_path),
        observation=observation,
        contradiction=contradiction,
        league=PlannerLeague(),
        domain=Maze(),
        constructor_planner_ids=["Astar"],
        falsifier_planner_id="MCTS",
    )

    # Every real admitted observation's real receipt_id is a non-empty
    # digest, and every real candidate really reached FALSIFIED (not
    # UNKNOWN/UNSUPPORTED, which would have been refused rather than
    # admitted -- exploration_payoff_bridge's own real, unmodified
    # falsification_to_payoff_scores mapping).
    for admission in result.admissions:
        assert admission.observation is not None
        assert admission.observation.receipt_id
        assert admission.standing == "ALIVE"

    # Real, deterministic candidate identities -- 8 distinct real
    # candidate_ids, never collapsed or deduplicated away.
    receipt_ids = {a.observation.receipt_id for a in result.admissions}
    assert len(receipt_ids) == 8
