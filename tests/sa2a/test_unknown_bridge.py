"""Unit tests for UNKNOWN state handling, CMCA allocation, machine experience compilation,
downgrade guard, and SA2A CLI (RFC-SA2A-001 v26.9.16).
"""

from __future__ import annotations

import json
import pytest
from typer.testing import CliRunner

from autofde_lab.cli import app as root_cli_app
from autofde_lab.sa2a.a2a_bridge.agent_card import (
    SA2A_PROFILE_V26_9_16,
    SemanticAgentCard,
    SemanticCapability,
    create_default_sa2a_agent_card,
)
from autofde_lab.sa2a.a2a_bridge.downgrade_guard import (
    DowngradeGuard,
    UnsupportedProfileError,
)
from autofde_lab.sa2a.a2a_bridge.negotiation import ProfileNegotiator
from autofde_lab.sa2a.cli import app as sa2a_app
from autofde_lab.sa2a.unknown.allocator import (
    AllocationStanding,
    AutonomousBudgetExpansionRefused,
    CMCACandidateAllocator,
    ExplorationBudget,
    UnknownCandidate,
)
from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler
from autofde_lab.sa2a.unknown.resolution import (
    CandidateResolution,
    EpistemicState,
    UnknownQuery,
    UnknownResolutionPipeline,
)


runner = CliRunner()


# --- 1. CMCA Resource Allocation Tests (§38, §73) ---


def test_cmca_frontier_allocation_bounded_and_deterministic() -> None:
    budget = ExplorationBudget(
        max_compute_ticks=1000,
        max_tokens=10000,
        max_experiments=5,
        concurrency_lanes=8,
    )
    cands = [
        UnknownCandidate(
            item_id="cand_1",
            description="Explore candidate ontology branch 1",
            option_entropy=2.5,
            estimated_cost=5.0,
            historical_yield=1.2,
        ),
        UnknownCandidate(
            item_id="cand_2",
            description="Explore candidate ontology branch 2",
            option_entropy=1.0,
            estimated_cost=20.0,
            historical_yield=0.5,
        ),
        UnknownCandidate(
            item_id="cand_3",
            description="Explore low-salience pruned branch",
            option_entropy=0.01,
            estimated_cost=100.0,
            historical_yield=0.1,
        ),
    ]

    allocator = CMCACandidateAllocator(pruning_threshold=0.05)
    plan1 = allocator.allocate(plan_id="plan_test", budget=budget, candidates=cands)
    plan2 = allocator.allocate(plan_id="plan_test", budget=budget, candidates=cands)

    # Determinism: identical plans and digests
    assert plan1.plan_hash == plan2.plan_hash
    assert len(plan1.allocations) == 3

    # Higher salience gets larger fraction and higher resources
    cand1_alloc = next(a for a in plan1.allocations if a.item_id == "cand_1")
    cand2_alloc = next(a for a in plan1.allocations if a.item_id == "cand_2")
    cand3_alloc = next(a for a in plan1.allocations if a.item_id == "cand_3")

    assert cand1_alloc.standing == AllocationStanding.ADMITTED
    assert cand1_alloc.allocated_fraction > cand2_alloc.allocated_fraction
    assert cand1_alloc.allocated_ticks > cand2_alloc.allocated_ticks
    assert cand3_alloc.standing == AllocationStanding.PRUNED

    # Total allocated budget within parent budget boundaries
    total_ticks = sum(a.allocated_ticks for a in plan1.allocations)
    total_tokens = sum(a.allocated_tokens for a in plan1.allocations)
    total_experiments = sum(a.allocated_experiments for a in plan1.allocations)

    assert total_ticks <= budget.max_compute_ticks
    assert total_tokens <= budget.max_tokens
    assert total_experiments <= budget.max_experiments


def test_cmca_enforces_no_autonomous_budget_expansion() -> None:
    budget = ExplorationBudget(
        max_compute_ticks=1000,
        max_tokens=10000,
        max_experiments=5,
    )
    cand = UnknownCandidate(
        item_id="cand_autonomous",
        description="Autonomous agent attempting budget self-grant",
        option_entropy=1.0,
        estimated_cost=10.0,
    )
    allocator = CMCACandidateAllocator()
    plan = allocator.allocate(plan_id="plan_auto", budget=budget, candidates=[cand])
    alloc = plan.allocations[0]

    # Model or candidate cannot expand budget (§38, §73)
    with pytest.raises(AutonomousBudgetExpansionRefused) as excinfo:
        allocator.enforce_no_autonomous_expansion(
            allocation=alloc,
            requested_additional_tokens=5000,
            caller_authority="model",
        )
    assert "models cannot grant themselves more budget" in str(excinfo.value)

    # Subagent or untrusted authority also refused
    with pytest.raises(AutonomousBudgetExpansionRefused):
        allocator.enforce_no_autonomous_expansion(
            allocation=alloc,
            requested_additional_ticks=200,
            caller_authority="subagent",
        )

    # 0 expansion request succeeds
    allocator.enforce_no_autonomous_expansion(
        allocation=alloc,
        requested_additional_tokens=0,
        caller_authority="model",
    )


# --- 2. UNKNOWN State Handling & Resolution Tests (§36, §37, §64) ---


def test_unknown_state_routing_and_admission_pipeline() -> None:
    pipeline = UnknownResolutionPipeline()
    budget = ExplorationBudget(
        max_compute_ticks=500,
        max_tokens=5000,
        max_experiments=3,
    )
    queries = [
        UnknownQuery(query_id="q1", predicate_or_topic="urn:autofde:prop:latency"),
        UnknownQuery(query_id="q2", predicate_or_topic="urn:autofde:prop:throughput"),
    ]

    plan, cand_map = pipeline.route_unknown_to_frontier(queries, budget)
    assert len(plan.allocations) == 2
    assert "q1" in cand_map and "q2" in cand_map

    # Discovered Candidate must pass admission court
    good_cand = CandidateResolution(
        candidate_id="cand_res_1",
        query_id="q1",
        proposed_assertion="latency_sla <= 50ms",
        evidence_payload={"measured_p99": 42, "source": "synthetic_bench"},
        source_identity="discovery_agent",
        consumed_ticks=20,
        consumed_tokens=200,
    )
    receipt = pipeline.admit_candidate(good_cand)
    assert receipt.admitted is True
    assert receipt.epistemic_standing == EpistemicState.KNOWN
    assert pipeline.known_store["q1"] == "latency_sla <= 50ms"

    # Refused candidate cannot grant itself KNOWN standing
    bad_cand = CandidateResolution(
        candidate_id="cand_res_2",
        query_id="q2",
        proposed_assertion="",  # Empty assertion fails admission
        evidence_payload={},
        source_identity="untrusted_agent",
        consumed_ticks=10,
        consumed_tokens=50,
    )
    bad_receipt = pipeline.admit_candidate(bad_cand)
    assert bad_receipt.admitted is False
    assert bad_receipt.epistemic_standing == EpistemicState.REFUSED
    assert "q2" not in pipeline.known_store


# --- 3. Machine Experience Compiler Tests (§39, §65) ---


def test_machine_experience_compiler_avoids_llm_inference() -> None:
    compiler = MachineExperienceCompiler()

    resolved_items = [
        ("resolve_entity(A)", "AdmittedEntity(A)", "ShapeA"),
        ("resolve_entity(B)", "AdmittedEntity(B)", "ShapeB"),
    ]

    receipt = compiler.compile_candidate_experience(
        receipt_id="comp_rec_1", resolved_items=resolved_items
    )
    assert receipt.compiled_rule_count == 2
    assert receipt.digest is not None

    llm_mock_called = [0]

    def mock_llm() -> str:
        llm_mock_called[0] += 1
        return "DYNAMIC_LLM_OUTPUT"

    # Query matching compiled experience avoids LLM call
    res_a = compiler.resolve("resolve_entity(A)", fallback_llm_inference=mock_llm)
    assert res_a == "AdmittedEntity(A)"
    assert llm_mock_called[0] == 0  # LLM avoided
    assert compiler.inference_avoidance_ratio == 1.0

    # Query not in experience falls back to LLM
    res_c = compiler.resolve("resolve_entity(C)", fallback_llm_inference=mock_llm)
    assert res_c == "DYNAMIC_LLM_OUTPUT"
    assert llm_mock_called[0] == 1
    assert compiler.inference_avoidance_ratio == 0.5


# --- 4. Agent Card, Profile Negotiation & Strict Downgrade Guard Tests (§9, §10, §76) ---


def test_agent_card_and_downgrade_guard() -> None:
    guard = DowngradeGuard()
    guard.assert_supported_profile(SA2A_PROFILE_V26_9_16)

    # Downgrade or unsupported profile raises typed UnsupportedProfileError
    with pytest.raises(UnsupportedProfileError) as excinfo:
        guard.assert_supported_profile("SA2A-PROFILE-v1.0.0-DEPRECATED")
    assert excinfo.value.code == "UNSUPPORTED_PROFILE"

    with pytest.raises(UnsupportedProfileError):
        guard.check_downgrade("SA2A-PROFILE-v0.1")


def test_profile_negotiator_success_and_refusal() -> None:
    agent_a = create_default_sa2a_agent_card(agent_id="agent-a")
    agent_b = create_default_sa2a_agent_card(agent_id="agent-b")

    negotiator = ProfileNegotiator()
    session = negotiator.negotiate(agent_a, agent_b)
    assert session.negotiated_profile == SA2A_PROFILE_V26_9_16
    assert len(session.active_capabilities) == 2

    # Incompatible agent card
    incompatible_agent = SemanticAgentCard(
        agent_id="legacy-agent",
        name="Legacy Agent",
        version="v0.1",
        supported_profiles=("LEGACY-INCOMPATIBLE-PROFILE",),
        capabilities=(),
    )

    with pytest.raises(UnsupportedProfileError):
        negotiator.negotiate(agent_a, incompatible_agent)


# --- 5. SA2A Typer CLI Tests ---


def test_sa2a_cli_help() -> None:
    result = runner.invoke(sa2a_app, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.output
    assert "admit" in result.output
    assert "plan" in result.output
    assert "execute" in result.output
    assert "replay" in result.output


def test_sa2a_cli_validate() -> None:
    # Valid default
    result = runner.invoke(sa2a_app, ["validate"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["status"] == "VALID"

    # Downgraded profile refusal
    refusal_result = runner.invoke(sa2a_app, ["validate", "--profile", "v0.0-unsupported"])
    assert refusal_result.exit_code != 0
    refusal_data = json.loads(refusal_result.output)
    assert refusal_data["ok"] is False
    assert refusal_data["code"] == "UNSUPPORTED_PROFILE"


def test_sa2a_cli_plan() -> None:
    candidates_json = json.dumps([
        {"item_id": "cand_x", "option_entropy": 2.0, "estimated_cost": 5.0},
        {"item_id": "cand_y", "option_entropy": 1.0, "estimated_cost": 10.0},
    ])
    result = runner.invoke(sa2a_app, ["plan", candidates_json, "--ticks", "500"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert len(data["allocations"]) == 2
    assert "plan_hash" in data


def test_sa2a_cli_admit_and_execute() -> None:
    # Test admit
    admit_result = runner.invoke(sa2a_app, [
        "admit",
        "-i", "cand_exec",
        "-a", "ResourceBound <= 1024",
        "-s", "engine_test",
        "-e", '{"proof": "observed_pass"}',
    ])
    assert admit_result.exit_code == 0
    data = json.loads(admit_result.output)
    assert data["ok"] is True
    assert data["standing"] == "KNOWN"

    # Test execute with compiled rule
    rules_json = json.dumps([["query_alpha", "ResultAlpha"]])
    exec_result = runner.invoke(sa2a_app, ["execute", "query_alpha", "--rules", rules_json])
    assert exec_result.exit_code == 0
    exec_data = json.loads(exec_result.output)
    assert exec_data["ok"] is True
    assert exec_data["result"] == "ResultAlpha"
    assert exec_data["llm_avoidance_ratio"] == 1.0


def test_root_cli_wiring() -> None:
    # Root autofde cli must include sa2a
    result = runner.invoke(root_cli_app, ["--help"])
    assert result.exit_code == 0
    assert "sa2a" in result.output

    # Subcommand through root
    sa2a_help = runner.invoke(root_cli_app, ["sa2a", "--help"])
    assert sa2a_help.exit_code == 0
    assert "governor" in sa2a_help.output
    assert "validate" in sa2a_help.output
