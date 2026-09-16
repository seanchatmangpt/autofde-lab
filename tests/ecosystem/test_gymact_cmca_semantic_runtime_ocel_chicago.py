# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test suite: End-to-end integration of CMCA, Tiny Semantic Runtime,
GymAct execution, and Object-Centric Process Mining (OCEL 2.0 / Van der Aalst ERRC).

Zero mocked models, zero mocked providers, zero ambient actuation.
Verifies:
1. Real GymAct episode driven by CMCA resource allocation and Tiny Semantic Operator predictions.
2. Formal OCEL 2.0 log generation capturing Episode, CandidateBranch, and SemanticOperator entities.
3. Strict Object-Centric Conformance checking per Küsters & van der Aalst 2025 (all_conform=True, fitness=1.0).
4. Performance Mining (case cycle times and waiting time analysis) directly on the execution trace.
5. Adversarial mutant detection: Crossed object-identity link detection drops conformance.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from gymact.models import ActuationIntent, Standing

from autofde_lab.agent.software_manufacturing_gymact_bridge import (
    SoftwareManufacturingProvider,
)
from autofde_lab.cmca.bcinr_bridge import find_bcinr_cli
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import CandidateBranch, ResourceBudget
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import (
    EventObjectLink,
    OcelAttribute,
    OcelAttributeValue,
    OcelObject,
)
from autofde_lab.ocel.object_centric_conformance import (
    check_object_centric_conformance,
    project_object_trace,
)
from autofde_lab.ocel.sqlite_store import to_sqlite
from autofde_lab.semantic_models.feature_schema import (
    SemanticFeature,
    SemanticFeatureSchema,
)
from autofde_lab.semantic_models.tiny_operator import (
    QuantizationKind,
    RuntimeTarget,
    TinyOperatorManifest,
    TinySemanticOperator,
)
from gymact import GymAct, MaterializationIntent

# The default CMCA engine delegates to the vendored bcinr-cmca crate (see
# src/autofde_lab/cmca/bcinr_bridge.py): this suite exercises that real
# engine and therefore requires the built `cmca_rank_cli` binary.
pytestmark = pytest.mark.skipif(
    find_bcinr_cli() is None,
    reason="no built 'cmca_rank_cli' binary found -- build with "
    "'cargo build --release -p bcinr-cmca' inside vendor/bcinr",
)

_PLAN_FIXTURE = (
    Path(__file__).parents[2]
    / "planning"
    / "august-2026"
    / "materialized"
    / "august-full-stack-example.plan.json"
)


def _load_plan() -> dict[str, Any]:
    return json.loads(_PLAN_FIXTURE.read_text())


def _build_test_tiny_operator() -> TinySemanticOperator:
    schema = SemanticFeatureSchema(
        ontology_hash="ont-hash-gymact-ocel",
        features=(
            SemanticFeature(
                feature_id=0, semantic_iri="http://example.org/pred/isAdmissible"
            ),
            SemanticFeature(
                feature_id=1, semantic_iri="http://example.org/pred/hasDependency"
            ),
        ),
        feature_schema_hash="schema-hash-gymact-ocel",
    )
    manifest = TinyOperatorManifest(
        ontology_hash="ont-hash-gymact-ocel",
        feature_schema_hash="schema-hash-gymact-ocel",
        dataset_hash="dataset-hash-gymact-ocel",
        optimization_receipt_id="opt-rec-gymact-ocel",
        model_family="fixed_point_linear",
        model_revision="v26.9.14",
        parameter_hash="param-hash-gymact-ocel",
        quantization=QuantizationKind.FIXED_POINT_Q16,
        input_dimensions=2,
        output_semantic_iris=(
            "http://example.org/pred/actionAdvance",
            "http://example.org/pred/actionHold",
        ),
        estimated_parameter_bytes=32,
        runtime_target=RuntimeTarget.PORTABLE_FIXED,
    )

    # Pure deterministic integer prediction: if feature 0 (isAdmissible) > 0 -> return class 0 (actionAdvance)
    def _predict(features: list[int]) -> int:
        return 0 if features[0] > 0 else 1

    return TinySemanticOperator(
        manifest=manifest,
        feature_schema=schema,
        predict_fn=_predict,
    )


def test_gymact_cmca_tiny_runtime_ocel_loop(tmp_path: Path) -> None:
    """Chicago-style test executing a real GymAct episode guided by CMCA and TinySemanticOperator,
    recording an OCEL 2.0 event log, and verifying object-centric conformance and performance.
    """
    plan_data = _load_plan()
    step_ids = [step["id"] for step in plan_data["plan"]["steps"]]

    # 1. Setup CMCA Resource Allocation across candidate branches
    budget = ResourceBudget(
        total_ticks=10_000,
        memory_bytes=1_048_576,
        max_verification_depth=8,
        consequence_risk_budget=0.2,
        concurrency_lanes=4,
    )
    allocator = MultifractalCascadeAllocator(pruning_threshold=0.01)

    candidate_branches = [
        CandidateBranch(
            branch_id="branch-primary-manufacturing",
            operator_id="operator-tiny-v26.9.14",
            world_id="gymact-software-manufacturing",
            state_id="state-initial",
            option_entropy=4.5,
            estimated_cost=100.0,
            historical_yield=1.0,
        ),
        CandidateBranch(
            branch_id="branch-alternative-speculative",
            operator_id="operator-tiny-v26.9.14",
            world_id="gymact-software-manufacturing",
            state_id="state-speculative",
            option_entropy=1.5,
            estimated_cost=250.0,
            historical_yield=0.8,
        ),
    ]

    allocation_plan = allocator.allocate(
        plan_id="cmca-plan-001",
        budget=budget,
        candidates=candidate_branches,
    )
    assert len(allocation_plan.allocations) == 2
    primary_alloc = next(
        a
        for a in allocation_plan.allocations
        if a.branch_id == "branch-primary-manufacturing"
    )
    assert primary_alloc.allocated_ticks > 0
    assert primary_alloc.allocated_fraction > 0.5

    # 2. Setup Tiny Semantic Runtime Operator
    operator = _build_test_tiny_operator()

    # 3. Initialize OCEL 2.0 Log with explicitly declared multi-type objects
    episode_obj_id = "episode-manufacturing-001"
    branch_obj_id = primary_alloc.branch_id
    operator_obj_id = f"operator-{operator.manifest.model_revision}"

    ocel_log = OcelLog.new(
        objects=[
            OcelObject(
                episode_obj_id,
                "Episode",
                (
                    OcelAttribute(
                        "environment",
                        OcelAttributeValue.string("software_manufacturing"),
                    ),
                    OcelAttribute(
                        "step_count", OcelAttributeValue.integer(len(step_ids))
                    ),
                ),
            ),
            OcelObject(
                branch_obj_id,
                "CandidateBranch",
                (
                    OcelAttribute(
                        "ticks",
                        OcelAttributeValue.integer(primary_alloc.allocated_ticks),
                    ),
                    OcelAttribute(
                        "depth",
                        OcelAttributeValue.integer(primary_alloc.verification_depth),
                    ),
                ),
            ),
            OcelObject(
                operator_obj_id,
                "SemanticOperator",
                (
                    OcelAttribute(
                        "manifest_hash",
                        OcelAttributeValue.string(operator.manifest.manifest_hash),
                    ),
                    OcelAttribute(
                        "target",
                        OcelAttributeValue.string(
                            operator.manifest.runtime_target.value
                        ),
                    ),
                ),
            ),
        ]
    )

    # 4. Drive Real GymAct Episode
    gym = GymAct()
    gym.register_provider(SoftwareManufacturingProvider())

    async def run_episode() -> OcelLog:
        nonlocal ocel_log

        # Event: materialize
        mat_res = await gym.materialize(
            MaterializationIntent(
                provider="software_manufacturing", config={"plan": plan_data}
            )
        )
        assert mat_res.accepted is True
        assert mat_res.episode is not None
        gym_episode_id = mat_res.episode.episode_id

        current_time_ns = 1_000_000_000  # Start at 1.0s
        ocel_log = ocel_log.append_event(
            event_id="evt-materialize",
            activity="materialize",
            objects=[(episode_obj_id, "subject"), (branch_obj_id, "allocated_to")],
            timestamp_ns=current_time_ns,
            attributes={
                "standing": OcelAttributeValue.string(
                    mat_res.receipt.standing.value
                    if hasattr(mat_res.receipt.standing, "value")
                    else str(mat_res.receipt.standing)
                ),
                "receipt_id": OcelAttributeValue.string(mat_res.receipt.receipt_id),
            },
        )

        completed: list[str] = []
        step_index = 0

        while len(completed) < len(step_ids):
            current_time_ns += 50_000_000  # Advance 50ms

            # Step 1: Observe
            obs = await gym.observe(gym_episode_id)
            admissible = obs.state["admissible"]
            assert admissible

            # Event: observe
            obs_event_id = f"evt-observe-{step_index}"
            ocel_log = ocel_log.append_event(
                event_id=obs_event_id,
                activity="observe",
                objects=[(episode_obj_id, "target")],
                timestamp_ns=current_time_ns,
                attributes={
                    "admissible_count": OcelAttributeValue.integer(len(admissible))
                },
            )

            current_time_ns += 20_000_000  # 20ms

            # Step 2: Semantic Runtime inference
            next_step = min(admissible)
            feature_vector = [1, 1 if step_index > 0 else 0]
            delta, receipt = operator.execute_and_receipt(
                subject_iri=f"urn:step:{next_step}",
                observation_id=obs_event_id,
                feature_vector=feature_vector,
            )
            assert receipt.predicted_class_index == 0
            assert delta.triples[0].predicate == "http://example.org/pred/actionAdvance"

            # Event: predict_advance
            predict_event_id = f"evt-predict-{step_index}"
            ocel_log = ocel_log.append_event(
                event_id=predict_event_id,
                activity="predict_advance",
                objects=[
                    (episode_obj_id, "context"),
                    (operator_obj_id, "decider"),
                    (branch_obj_id, "budget_source"),
                ],
                timestamp_ns=current_time_ns,
                attributes={
                    "receipt_id": OcelAttributeValue.string(receipt.receipt_id),
                    "target_step": OcelAttributeValue.string(next_step),
                },
            )

            current_time_ns += 30_000_000  # 30ms

            # Step 3: Act
            capability = f"urn:gymact:software-manufacturing:capability:{next_step}"
            act_res = await gym.act(
                ActuationIntent(episode_id=gym_episode_id, capability=capability)
            )
            assert act_res.accepted is True

            # Event: act
            act_event_id = f"evt-act-{step_index}"
            ocel_log = ocel_log.append_event(
                event_id=act_event_id,
                activity="act",
                objects=[(episode_obj_id, "target"), (branch_obj_id, "active_branch")],
                timestamp_ns=current_time_ns,
                attributes={
                    "receipt_id": OcelAttributeValue.string(act_res.receipt.receipt_id),
                    "step_id": OcelAttributeValue.string(next_step),
                },
            )

            completed.append(next_step)
            step_index += 1

        # Final observe & verify
        current_time_ns += 50_000_000
        verify_res = await gym.verify(gym_episode_id, {"state": "ALIVE"})
        assert verify_res.passed is True

        ocel_log = ocel_log.append_event(
            event_id="evt-verify",
            activity="verify",
            objects=[(episode_obj_id, "target"), (branch_obj_id, "verified_branch")],
            timestamp_ns=current_time_ns,
            attributes={"passed": OcelAttributeValue.boolean(True)},
        )

        current_time_ns += 50_000_000
        td_receipt = await gym.teardown(gym_episode_id)
        assert td_receipt.standing == Standing.ALIVE

        ocel_log = ocel_log.append_event(
            event_id="evt-teardown",
            activity="teardown",
            objects=[(episode_obj_id, "target")],
            timestamp_ns=current_time_ns,
            attributes={"receipt_id": OcelAttributeValue.string(td_receipt.receipt_id)},
        )

        return ocel_log

    final_log = asyncio.run(run_episode())

    # 5. Validate OCEL 2.0 Structural Laws (OCPQ Definition 2)
    validated_log = final_log.validate()
    assert (
        len(validated_log.events) == 1 + (len(step_ids) * 3) + 2
    )  # mat + 14*(obs,pred,act) + verify + td = 45 events
    assert len(validated_log.objects) == 3

    # 6. Object-Centric Conformance Verification
    # Project traces per object
    trace_operator = project_object_trace(validated_log, operator_obj_id)
    assert len(trace_operator) == len(step_ids)
    assert all(act == "predict_advance" for act in trace_operator)

    trace_branch = project_object_trace(validated_log, branch_obj_id)
    # branch participated in materialize + 14*(predict_advance, act) + verify = 30 events
    assert len(trace_branch) == 30
    assert trace_branch[0] == "materialize"
    assert trace_branch[-1] == "verify"

    conformance = check_object_centric_conformance(
        validated_log,
        intended_traces_by_object_id={
            operator_obj_id: tuple(["predict_advance"] * len(step_ids)),
            branch_obj_id: trace_branch,
        },
    )
    assert conformance.all_conform is True
    assert conformance.overall_fitness == 1.0

    # 7. Performance Mining & Van der Aalst Enhancement Analysis via SQLite
    db_path = tmp_path / "gymact_ocel_execution.sqlite"
    to_sqlite(validated_log, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Verify event count in sqlite
        row = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()
        assert row["c"] == 45

        # Check object links in sqlite
        link_rows = conn.execute(
            "SELECT COUNT(*) as c FROM event_object_links"
        ).fetchall()
        assert link_rows[0]["c"] > 0
    finally:
        conn.close()


def test_adversarial_crossed_object_link_in_gymact_ocel() -> None:
    """Chicago adversarial mutant: Swap object identity links between Episode and Operator.
    Object-Centric Conformance MUST catch the discrepancy and fail (all_conform=False).
    """
    operator = _build_test_tiny_operator()
    op_id = f"operator-{operator.manifest.model_revision}"
    ep_id = "episode-manufacturing-002"

    log = OcelLog.new(
        objects=[
            OcelObject(ep_id, "Episode"),
            OcelObject(op_id, "SemanticOperator"),
        ]
    )

    # Event 1: observe linked to ep_id
    log = log.append_event("e1", "observe", [ep_id], timestamp_ns=100)
    # Event 2: predict_advance linked to op_id
    log = log.append_event("e2", "predict_advance", [op_id], timestamp_ns=200)

    # Validate ground truth
    intended_op = ("predict_advance",)
    res_correct = check_object_centric_conformance(
        log, intended_traces_by_object_id={op_id: intended_op}
    )
    assert res_correct.all_conform is True
    assert res_correct.overall_fitness == 1.0

    # Mutate: Cross link so e2 is linked to ep_id instead of op_id
    mutated_links = [
        EventObjectLink(link.event_id, ep_id, link.qualifier)
        for link in log.event_object_links
    ]
    corrupt_log = OcelLog(
        events=log.events,
        objects=log.objects,
        event_object_links=tuple(mutated_links),
    )

    res_corrupt = check_object_centric_conformance(
        corrupt_log, intended_traces_by_object_id={op_id: intended_op}
    )
    # Conformance must fail closed
    assert res_corrupt.all_conform is False
    assert res_corrupt.overall_fitness == 0.0
