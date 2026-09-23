"""v26.9.17 CMCA self-dogfood crown across the eight repo-native use cases.

The crown deliberately separates two episodes:

Episode 1 (UNKNOWN to this compiler instance)
    benchmark contract -> CMCA/planning -> native verification -> MachineExperience

Episode 2 (KNOWN)
    compiled MachineExperience -> deterministic replay -> native verification

The second episode is forbidden from calling the frontier resolver.  CMCA itself
may run again: it is deterministic machinery, not frontier intelligence.  This
proves the architectural claim that verified experience removes repeated
semantic discovery while preserving the same native execution courts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from gymact.models import ActuationIntent

from autofde_lab.agent.autodev_domain import build_autodev_hddl_domain
from autofde_lab.agent.autodev_gymact_env import AutoDevGymActEnvironment
from autofde_lab.beam.beam_port_bridge import handle_request
from autofde_lab.cmca.atomvm_schedule import generate_atomvm_cmca_module
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    AllocationStanding,
    CandidateBranch,
    ResourceBudget,
)
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import EventObjectLink, OcelEvent, OcelObject
from autofde_lab.ocel.object_centric_conformance import (
    check_object_centric_conformance,
)
from autofde_lab.planning.cmca_probe import probe_product_frontier
from autofde_lab.planning.fond_hddl_product import ProductState, build_fond_problem
from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler

CROWN_SCHEMA = "autofde.cmca.dogfood-crown/v26.9.17"

USE_CASE_TITLES: dict[str, str] = {
    "UC-1": "Closed-Loop AutoDev CI/CD Loop",
    "UC-2": "High-Frequency In-Process Swarm Dispatch",
    "UC-3": "BEAM Cluster Cross-Host Interop",
    "UC-4": "Adversarial Defect Repair Frontier",
    "UC-5": "Deceptive Multi-Armed Frontier",
    "UC-6": "High-Dimension Prime Budget Conservation",
    "UC-7": "Embedded AtomVM Microcontroller Projection",
    "UC-8": "Object-Centric Process Mining Conformance",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    text = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _budget(spec: dict[str, Any]) -> ResourceBudget:
    return ResourceBudget(
        total_ticks=int(spec["total_ticks"]),
        memory_bytes=int(spec["memory_bytes"]),
        max_verification_depth=int(spec["max_verification_depth"]),
        consequence_risk_budget=float(spec["consequence_risk_budget"]),
        concurrency_lanes=int(spec["concurrency_lanes"]),
    )


def _candidate(spec: dict[str, Any], *, world_id: str) -> CandidateBranch:
    return CandidateBranch(
        branch_id=str(spec["branch_id"]),
        operator_id=str(spec.get("operator_id", "cmca-demo")),
        world_id=world_id,
        state_id=str(spec.get("state_id", spec["branch_id"])),
        option_entropy=float(spec["option_entropy"]),
        estimated_cost=float(spec["estimated_cost"]),
        historical_yield=float(spec.get("historical_yield", 1.0)),
        metadata={"demo_case": world_id},
    )


def _base_budget(
    *,
    ticks: int = 10000,
    memory: int = 65536,
    depth: int = 6,
    risk: float = 0.5,
    lanes: int = 8,
) -> dict[str, Any]:
    return {
        "total_ticks": ticks,
        "memory_bytes": memory,
        "max_verification_depth": depth,
        "consequence_risk_budget": risk,
        "concurrency_lanes": lanes,
    }


def demo_contracts() -> tuple[dict[str, Any], ...]:
    """Return the eight exact operational surfaces from the repo benchmark."""
    swarm_candidates = [
        {
            "branch_id": f"agent_task_{i}",
            "operator_id": "swarm_agent",
            "option_entropy": 1.0 + (i * 0.5),
            "historical_yield": 0.5 + (i * 0.05),
            "estimated_cost": 10.0 + (i * 2.0),
        }
        for i in range(8)
    ]
    beam_candidates = [
        {
            "branch_id": f"node_{i}",
            "option_entropy": 2.0 + i,
            "historical_yield": 0.8,
            "estimated_cost": 10.0,
        }
        for i in range(6)
    ]
    deceptive_candidates = [
        {
            "branch_id": f"local_trap_{i}",
            "option_entropy": 1.0 + (i * 0.1),
            "historical_yield": 0.95,
            "estimated_cost": 1.0,
        }
        for i in range(7)
    ] + [
        {
            "branch_id": "latent_breakthrough",
            "option_entropy": 20.0,
            "historical_yield": 0.60,
            "estimated_cost": 1.0,
        }
    ]
    prime_candidates = [
        {
            "branch_id": f"candidate_{i}",
            "option_entropy": 1.5 + (i * 0.7),
            "historical_yield": 0.2 + (i * 0.1),
            "estimated_cost": 10.0 + (i * 3.0),
        }
        for i in range(8)
    ]
    atomvm_candidates = [
        {
            "branch_id": f"mcu_task_{i}",
            "operator_id": "atomvm_task",
            "option_entropy": 1.0 + i,
            "historical_yield": 0.9,
            "estimated_cost": 5.0,
        }
        for i in range(4)
    ]
    repair_candidates = [
        {
            "branch_id": "repair_retry",
            "option_entropy": 2.0,
            "historical_yield": 0.4,
            "estimated_cost": 1.0,
        },
        {
            "branch_id": "repair_patch",
            "option_entropy": 5.0,
            "historical_yield": 0.9,
            "estimated_cost": 2.0,
        },
        {
            "branch_id": "repair_rollback",
            "option_entropy": 4.0,
            "historical_yield": 0.8,
            "estimated_cost": 1.5,
        },
        {
            "branch_id": "repair_escalate",
            "option_entropy": 7.0,
            "historical_yield": 0.7,
            "estimated_cost": 4.0,
        },
    ]
    ocel_candidates = [
        {
            "branch_id": name,
            "option_entropy": entropy,
            "historical_yield": 0.9,
            "estimated_cost": cost,
        }
        for name, entropy, cost in (
            ("allocate", 3.0, 1.0),
            ("execute", 5.0, 2.0),
            ("verify", 4.0, 1.5),
        )
    ]

    return (
        {
            "case_id": "UC-1",
            "title": USE_CASE_TITLES["UC-1"],
            "budget": _base_budget(
                ticks=5000, memory=32768, depth=5, risk=0.2, lanes=4
            ),
        },
        {
            "case_id": "UC-2",
            "title": USE_CASE_TITLES["UC-2"],
            "budget": _base_budget(),
            "candidates": swarm_candidates,
        },
        {
            "case_id": "UC-3",
            "title": USE_CASE_TITLES["UC-3"],
            "budget": _base_budget(ticks=8000),
            "candidates": beam_candidates,
        },
        {
            "case_id": "UC-4",
            "title": USE_CASE_TITLES["UC-4"],
            "budget": _base_budget(ticks=4000, memory=32768, risk=0.25, lanes=4),
            "candidates": repair_candidates,
        },
        {
            "case_id": "UC-5",
            "title": USE_CASE_TITLES["UC-5"],
            "budget": _base_budget(ticks=12000),
            "candidates": deceptive_candidates,
        },
        {
            "case_id": "UC-6",
            "title": USE_CASE_TITLES["UC-6"],
            "budget": _base_budget(
                ticks=104729,
                memory=2147483647,
                depth=10,
            ),
            "candidates": prime_candidates,
        },
        {
            "case_id": "UC-7",
            "title": USE_CASE_TITLES["UC-7"],
            "budget": _base_budget(
                ticks=1000,
                memory=4096,
                depth=4,
                risk=0.1,
                lanes=4,
            ),
            "candidates": atomvm_candidates,
        },
        {
            "case_id": "UC-8",
            "title": USE_CASE_TITLES["UC-8"],
            "budget": _base_budget(
                ticks=3000, memory=16384, depth=4, risk=0.2, lanes=3
            ),
            "candidates": ocel_candidates,
        },
    )


def _allocate_contract(contract: dict[str, Any], *, plan_id: str):
    allocator = MultifractalCascadeAllocator()
    candidates = tuple(
        _candidate(spec, world_id=str(contract["case_id"]))
        for spec in contract.get("candidates", ())
    )
    return allocator.allocate(
        plan_id=plan_id,
        budget=_budget(contract["budget"]),
        candidates=candidates,
    )


def _execute_uc1(contract: dict[str, Any]) -> dict[str, Any]:
    """Real FONDxHDDL -> CMCA planning probe -> GymAct execution."""
    domain = build_autodev_hddl_domain()
    initial = ProductState(world=frozenset({"repo_clean"}), tau=("deliver_feature",))
    reachability = build_fond_problem(
        domain=domain,
        initial=initial,
        is_goal=lambda state: len(state.tau) == 0 and "cycle_receipted" in state.world,
    )
    probe = probe_product_frontier(
        reachability=reachability,
        state=initial,
        budget=_budget(contract["budget"]),
        plan_id="dogfood_uc1_planning",
    )
    if not probe.allocation_plan.allocations:
        return {"verified": False, "reason": "empty planning allocation"}

    allocation = max(
        probe.allocation_plan.allocations,
        key=lambda item: item.allocated_ticks,
    )
    candidate_by_id = {candidate.branch_id: candidate for candidate in probe.candidates}
    selected = candidate_by_id[allocation.branch_id]
    selected_action = str((selected.metadata or {})["planning_action"])

    env = AutoDevGymActEnvironment(
        domain=domain,
        initial_state=initial,
        episode_id="ep_cmca_dogfood_uc1",
        outcome_oracle="reference",
    )
    trace: list[str] = []
    for step in range(15):
        capabilities = tuple(env.capabilities())
        if not capabilities:
            break
        if step == 0:
            matching = [
                capability
                for capability in capabilities
                if capability.binding == selected_action
            ]
            capability = matching[0] if matching else capabilities[0]
        else:
            capability = capabilities[0]
        observation = env.actuate(
            ActuationIntent(
                episode_id=env.episode_id,
                capability=capability.iri,
            )
        )
        if observation.state.get("refused"):
            break
        trace.append(capability.binding)
        if not env.current_state.tau and "cycle_receipted" in env.current_state.world:
            break

    goal = not env.current_state.tau and "cycle_receipted" in env.current_state.world
    return {
        "verified": bool(goal and probe.preserves_dfcm_frontier),
        "plan_hash": probe.allocation_plan.plan_hash,
        "probe_hash": probe.probe_hash,
        "selected_planning_action": selected_action,
        "lawful_branch_ids": list(probe.lawful_branch_ids),
        "allocated_branch_ids": list(probe.allocated_branch_ids),
        "deferred_branch_ids": list(probe.deferred_branch_ids),
        "trace": trace,
        "goal_reached": goal,
    }


def _execute_uc2(contract: dict[str, Any]) -> dict[str, Any]:
    plan = _allocate_contract(contract, plan_id="dogfood_uc2_swarm")
    budget = _budget(contract["budget"])
    admitted = [
        a for a in plan.allocations if a.standing == AllocationStanding.ADMITTED
    ]
    verified = (
        len(plan.allocations) == 8
        and sum(a.allocated_ticks for a in plan.allocations) <= budget.total_ticks
        and all(0 <= a.priority_lane < budget.concurrency_lanes for a in admitted)
    )
    return {
        "verified": verified,
        "plan_hash": plan.plan_hash,
        "allocation_count": len(plan.allocations),
        "admitted_count": len(admitted),
        "lanes": sorted({a.priority_lane for a in admitted}),
    }


def _execute_uc3(contract: dict[str, Any]) -> dict[str, Any]:
    req = {
        "op": "cmca_allocate",
        "plan_id": "dogfood_uc3_beam",
        "budget": contract["budget"],
        "candidates": contract["candidates"],
    }
    response = handle_request(req, MultifractalCascadeAllocator())
    plan = response.get("plan", {})
    allocations = plan.get("allocations", [])
    verified = bool(
        response.get("ok")
        and plan.get("plan_id") == "dogfood_uc3_beam"
        and len(allocations) == 6
    )
    return {
        "verified": verified,
        "bridge_ok": bool(response.get("ok")),
        "allocation_count": len(allocations),
        "plan_digest": _digest(plan),
    }


def _execute_uc4(contract: dict[str, Any]) -> dict[str, Any]:
    domain = build_autodev_hddl_domain()
    state = ProductState(world=frozenset({"code_modified"}), tau=("run_tests",))
    env = AutoDevGymActEnvironment(
        domain=domain,
        initial_state=state,
        episode_id="ep_cmca_dogfood_uc4",
        outcome_oracle="adversarial",
    )
    capability = next(cap for cap in env.capabilities() if cap.binding == "run_tests")
    env.actuate(
        ActuationIntent(
            episode_id=env.episode_id,
            capability=capability.iri,
        )
    )
    plan = _allocate_contract(contract, plan_id="dogfood_uc4_repair")
    failed = {"tests_fail", "test_failing"} <= set(env.current_state.world)
    return {
        "verified": bool(failed and plan.allocations),
        "plan_hash": plan.plan_hash,
        "adversarial_failure_observed": failed,
        "repair_frontier": [a.branch_id for a in plan.allocations],
    }


def _execute_uc5(contract: dict[str, Any]) -> dict[str, Any]:
    plan = _allocate_contract(contract, plan_id="dogfood_uc5_deceptive")
    by_id = {allocation.branch_id: allocation for allocation in plan.allocations}
    latent = by_id["latent_breakthrough"]
    admitted = [
        allocation
        for allocation in plan.allocations
        if allocation.standing == AllocationStanding.ADMITTED
    ]
    verified = (
        latent.standing == AllocationStanding.ADMITTED
        and latent.allocated_ticks > 0
        and len(plan.allocations) == 8
    )
    return {
        "verified": verified,
        "plan_hash": plan.plan_hash,
        "latent_ticks": latent.allocated_ticks,
        "admitted_count": len(admitted),
        "option_value_preserved": plan.total_option_value_preserved,
    }


def _execute_uc6(contract: dict[str, Any]) -> dict[str, Any]:
    plan = _allocate_contract(contract, plan_id="dogfood_uc6_prime")
    budget = _budget(contract["budget"])
    ticks = sum(a.allocated_ticks for a in plan.allocations)
    memory = sum(a.allocated_memory_bytes for a in plan.allocations)
    admitted = [
        a for a in plan.allocations if a.standing == AllocationStanding.ADMITTED
    ]
    verified = (
        ticks <= budget.total_ticks
        and memory <= budget.memory_bytes
        and budget.total_ticks - ticks <= len(admitted)
        and budget.memory_bytes - memory <= len(admitted)
    )
    return {
        "verified": verified,
        "plan_hash": plan.plan_hash,
        "ticks_allocated": ticks,
        "ticks_budget": budget.total_ticks,
        "memory_allocated": memory,
        "memory_budget": budget.memory_bytes,
    }


def _execute_uc7(contract: dict[str, Any]) -> dict[str, Any]:
    plan = _allocate_contract(contract, plan_id="dogfood_uc7_atomvm")
    source = generate_atomvm_cmca_module(plan, module_name="cmca_dogfood_demo")
    verified = (
        "-module(cmca_dogfood_demo)." in source
        and "schedule_branch" in source
        and plan.plan_hash in source
    )
    return {
        "verified": verified,
        "plan_hash": plan.plan_hash,
        "erlang_source_digest": _digest(source),
        "source_lines": len(source.splitlines()),
    }


def _execute_uc8(contract: dict[str, Any]) -> dict[str, Any]:
    plan = _allocate_contract(contract, plan_id="dogfood_uc8_ocel")
    events = (
        OcelEvent(id="e_alloc", activity="cmca_allocate", timestamp_ns=100),
        OcelEvent(id="e_step_1", activity="gymact_step", timestamp_ns=200),
        OcelEvent(id="e_receipt", activity="issue_receipt", timestamp_ns=300),
    )
    objects = (
        OcelObject(id="obj_plan", object_type="CascadePlan"),
        OcelObject(id="obj_branch", object_type="CandidateBranch"),
    )
    links = (
        EventObjectLink(event_id="e_alloc", object_id="obj_plan", qualifier="governs"),
        EventObjectLink(
            event_id="e_step_1", object_id="obj_branch", qualifier="executes"
        ),
        EventObjectLink(
            event_id="e_receipt", object_id="obj_plan", qualifier="certifies"
        ),
    )
    log = OcelLog(events=events, objects=objects, event_object_links=links)
    report = check_object_centric_conformance(
        log,
        intended_traces_by_object_id={
            "obj_plan": ["cmca_allocate", "issue_receipt"],
            "obj_branch": ["gymact_step"],
        },
    )
    return {
        "verified": bool(report.all_conform and report.overall_fitness == 1.0),
        "plan_hash": plan.plan_hash,
        "ocel_all_conform": report.all_conform,
        "ocel_fitness": report.overall_fitness,
    }


_EXECUTORS = {
    "UC-1": _execute_uc1,
    "UC-2": _execute_uc2,
    "UC-3": _execute_uc3,
    "UC-4": _execute_uc4,
    "UC-5": _execute_uc5,
    "UC-6": _execute_uc6,
    "UC-7": _execute_uc7,
    "UC-8": _execute_uc8,
}


@dataclass(frozen=True, slots=True)
class DogfoodEpisodeReceipt:
    case_id: str
    title: str
    episode: int
    epistemic_route: str
    verified: bool
    contract_digest: str
    evidence_digest: str
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class DogfoodCaseResult:
    case_id: str
    title: str
    discovery: DogfoodEpisodeReceipt
    replay: DogfoodEpisodeReceipt
    experience_receipt_digest: str
    replay_identical: bool


@dataclass(frozen=True, slots=True)
class DogfoodCrownResult:
    standing: str
    cases: tuple[DogfoodCaseResult, ...]
    frontier_resolution_calls_episode_1: int
    frontier_resolution_calls_episode_2: int
    compiled_experience_rules: int
    replay_inference_avoidance_rate: float
    crown_receipt_hash: str

    @property
    def is_alive(self) -> bool:
        return self.standing == "ALIVE"

    def to_dict(
        self, *, subject_identity: Mapping[str, str] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": CROWN_SCHEMA,
            "standing": self.standing,
            "frontier_resolution_calls_episode_1": (
                self.frontier_resolution_calls_episode_1
            ),
            "frontier_resolution_calls_episode_2": (
                self.frontier_resolution_calls_episode_2
            ),
            "compiled_experience_rules": self.compiled_experience_rules,
            "replay_inference_avoidance_rate": self.replay_inference_avoidance_rate,
            "crown_receipt_hash": self.crown_receipt_hash,
            "cases": [
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "experience_receipt_digest": case.experience_receipt_digest,
                    "replay_identical": case.replay_identical,
                    "discovery": asdict(case.discovery),
                    "replay": asdict(case.replay),
                }
                for case in self.cases
            ],
        }
        if subject_identity is not None:
            payload["subject_identity"] = {
                str(key): str(value) for key, value in sorted(subject_identity.items())
            }
            payload["artifact_receipt_hash"] = _digest(payload)
        return payload


def _episode_receipt(
    *,
    contract: dict[str, Any],
    episode: int,
    epistemic_route: str,
    evidence: dict[str, Any],
) -> DogfoodEpisodeReceipt:
    contract_digest = _digest(contract)
    evidence_digest = _digest(evidence)
    payload = {
        "case_id": contract["case_id"],
        "episode": episode,
        "route": epistemic_route,
        "verified": bool(evidence.get("verified")),
        "contract_digest": contract_digest,
        "evidence_digest": evidence_digest,
    }
    return DogfoodEpisodeReceipt(
        case_id=str(contract["case_id"]),
        title=str(contract["title"]),
        episode=episode,
        epistemic_route=epistemic_route,
        verified=bool(evidence.get("verified")),
        contract_digest=contract_digest,
        evidence_digest=evidence_digest,
        receipt_hash=_digest(payload),
    )


def run_cmca_dogfood_crown() -> DogfoodCrownResult:
    """Run UNKNOWN->verified experience->KNOWN replay over all eight use cases."""
    compiler = MachineExperienceCompiler()
    results: list[DogfoodCaseResult] = []
    frontier_episode_1 = 0
    frontier_episode_2 = 0

    # Episode 1: the compiler starts with no rules.  Each exact semantic case is
    # resolved by the bounded repo-native frontier once, verified, then compiled.
    for contract in demo_contracts():
        key = f"{CROWN_SCHEMA}:{contract['case_id']}:{_digest(contract)}"
        frontier_episode_1 += 1
        evidence = _EXECUTORS[str(contract["case_id"])](contract)
        discovery = _episode_receipt(
            contract=contract,
            episode=1,
            epistemic_route="UNKNOWN_FRONTIER",
            evidence=evidence,
        )
        if not discovery.verified:
            results.append(
                DogfoodCaseResult(
                    case_id=str(contract["case_id"]),
                    title=str(contract["title"]),
                    discovery=discovery,
                    replay=_episode_receipt(
                        contract=contract,
                        episode=2,
                        epistemic_route="NOT_RUN",
                        evidence={"verified": False, "reason": "discovery_failed"},
                    ),
                    experience_receipt_digest="",
                    replay_identical=False,
                )
            )
            continue

        experience_receipt = compiler.compile_candidate_experience(
            receipt_id=discovery.receipt_hash,
            resolved_items=((key, _canonical(contract), None),),
        )

        fallback_called = False

        def _forbidden_fallback() -> str:
            nonlocal fallback_called, frontier_episode_2
            fallback_called = True
            frontier_episode_2 += 1
            raise AssertionError(
                f"KNOWN replay for {contract['case_id']} attempted frontier resolution"
            )

        encoded_contract = compiler.resolve(
            key, fallback_llm_inference=_forbidden_fallback
        )
        if not isinstance(encoded_contract, str):
            raise AssertionError(
                f"compiled replay contract missing for {contract['case_id']}"
            )
        replay_contract = json.loads(encoded_contract)
        replay_evidence = _EXECUTORS[str(contract["case_id"])](replay_contract)
        replay = _episode_receipt(
            contract=replay_contract,
            episode=2,
            epistemic_route="KNOWN_REPLAY",
            evidence=replay_evidence,
        )

        results.append(
            DogfoodCaseResult(
                case_id=str(contract["case_id"]),
                title=str(contract["title"]),
                discovery=discovery,
                replay=replay,
                experience_receipt_digest=experience_receipt.digest,
                replay_identical=(
                    not fallback_called
                    and discovery.contract_digest == replay.contract_digest
                    and discovery.evidence_digest == replay.evidence_digest
                    and replay.verified
                ),
            )
        )

    all_cases_closed = (
        len(results) == 8
        and all(case.discovery.verified for case in results)
        and all(case.replay.verified for case in results)
        and all(case.replay_identical for case in results)
        and frontier_episode_1 == 8
        and frontier_episode_2 == 0
        and len(compiler.rules) == 8
        and compiler.inference_avoidance_ratio == 1.0
    )
    standing = "ALIVE" if all_cases_closed else "PARTIAL_ALIVE"
    crown_payload = {
        "schema": CROWN_SCHEMA,
        "standing": standing,
        "case_receipts": [
            {
                "case_id": case.case_id,
                "discovery": case.discovery.receipt_hash,
                "replay": case.replay.receipt_hash,
                "experience": case.experience_receipt_digest,
                "replay_identical": case.replay_identical,
            }
            for case in results
        ],
        "frontier_episode_1": frontier_episode_1,
        "frontier_episode_2": frontier_episode_2,
        "compiled_rules": len(compiler.rules),
        "replay_avoidance": compiler.inference_avoidance_ratio,
    }
    return DogfoodCrownResult(
        standing=standing,
        cases=tuple(results),
        frontier_resolution_calls_episode_1=frontier_episode_1,
        frontier_resolution_calls_episode_2=frontier_episode_2,
        compiled_experience_rules=len(compiler.rules),
        replay_inference_avoidance_rate=compiler.inference_avoidance_ratio,
        crown_receipt_hash=_digest(crown_payload),
    )
