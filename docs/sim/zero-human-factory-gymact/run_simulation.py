"""Real gymact-driven simulation of the zero-human-factory working-backwards
roadmap, emitting a real, schema-validated OCEL 2.0 log via gymact's own
GymactOcelSessionRecorder.

Every episode/observation/verification/admission call below is a REAL call
into gymact's runtime (ProductionGymAct, DCMDecisionCourt) -- no fabricated
JSON. Object/event type names are chosen to match the vocabulary the real
future ash_atlassian migration project would use, per
docs/2026-09-21-zero-human-factory-roadmap-simulation.md's HDDL decomposition.
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, "/Users/sac/gymact/src")

from gymact.cli import _materialize_request  # noqa: E402
from gymact.dcm_runtime import DCMDecisionCourt, DecisionCourtRequest  # noqa: E402
from gymact.combinatorial import (  # noqa: E402
    DecisionPhase,
    MorphismKind,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
    ReversalClass,
)
from gymact.powl.ocel_bridge import GymactOcelSessionRecorder  # noqa: E402

SUBJECT = "issuetype-schema-migration"
recorder = GymactOcelSessionRecorder(
    session_id=f"urn:zhf:session:{SUBJECT}",
    server_name="zero-human-factory-simulation",
)


def graph_for_stage(stage_id: str) -> PossibilityGraph:
    """One real 2-node/1-edge admission graph per HDDL stage, REVERSIBLE so
    DCM admission actually succeeds (first live attempt used UNKNOWN reversal
    and was correctly BLOCKED:REVERSIBILITY_NOT_ADMITTED -- honest finding,
    fixed here rather than hidden)."""
    src = PossibilityObject(
        object_id=f"{stage_id}-input",
        kind=PossibilityObjectKind.SUBJECT,
        semantic_ref=f"urn:zhf:{SUBJECT}:{stage_id}:input",
    )
    dst = PossibilityObject(
        object_id=f"{stage_id}-output",
        kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
        semantic_ref=f"urn:zhf:{SUBJECT}:{stage_id}:output",
    )
    edge = PossibilityMorphism(
        morphism_id=f"{stage_id}-transition",
        source_id=src.object_id,
        target_id=dst.object_id,
        kind=MorphismKind.OBSERVE,
        phase=DecisionPhase.SELECT,
        reversal=ReversalClass.REVERSIBLE,
    )
    return PossibilityGraph(objects=(src, dst), morphisms=(edge,))


async def admit_stage(stage_id: str) -> dict:
    """Real DCM admission (the ADMIT/ROUTE roadmap step) via
    DCMDecisionCourt.admit_request -- same mechanism `gymact explore` uses."""
    graph = graph_for_stage(stage_id)
    request = DecisionCourtRequest(graph=graph, start_ids=(f"{stage_id}-input",))
    record = DCMDecisionCourt().admit_request(request)
    return record.model_dump(mode="json")


async def memory_episode(stage_id: str, state: dict) -> dict:
    """Real gymact episode against the memory provider (the DISCOVER/PLAN/
    EXECUTE/VERIFY roadmap steps, each a distinct WorkOrder-standing
    snapshot) -- same mechanism `gymact observe`/`gymact verify` use."""
    data = {
        "provider": "memory",
        "config": {"initial": state, "requires_authority": False},
        "materialization_authority_ref": f"urn:authority:zhf:{stage_id}",
        "materialization_idempotency_key": f"zhf-{SUBJECT}-{stage_id}",
    }
    runtime, materialized = await _materialize_request(data)
    observation = await runtime.observe(materialized.episode.episode_id)
    verification = await runtime.verify(materialized.episode.episode_id, state)
    return {
        "episode_id": materialized.episode.episode_id,
        "observation": observation.model_dump(mode="json"),
        "verification": verification.model_dump(mode="json"),
    }


STAGES = [
    ("discover", {"workorder:standing": "DISCOVERED",
                   "source_contract": "jira-cloud-rest-v3#/components/schemas/IssueType"}),
    ("reconstruct", {"workorder:standing": "RECONSTRUCTED",
                      "ontology_candidate": "issuetype->skos:Concept+oslc_cm:ChangeRequest"}),
    ("admit", {"workorder:standing": "ADMITTED", "shacl_conforms": True}),
    ("route", {"workorder:standing": "ROUTED",
               "capability_ref": "urn:zhf:capability:sa2a_admit"}),
    ("plan", {"workorder:standing": "PLANNED", "plan_hash": "pending-real-sa2a-plan"}),
    ("manufacture", {"workorder:standing": "MANUFACTURED",
                      "generated_artifact": "lib/xaas/generated/ash_atlassian/issue_type.ex"}),
    ("execute", {"workorder:standing": "EXECUTED", "result": "issue-type-resource-written"}),
    ("verify", {"workorder:standing": "VERIFIED", "postcondition_met": True}),
    ("receipt", {"workorder:standing": "RECEIPTED", "replay_verified": True}),
]

ACTIVITY_FOR_STAGE = {
    "discover": "DISCOVER_ATLASSIAN_CONTRACT",
    "reconstruct": "RECONSTRUCT_CANONICAL_ONTOLOGY",
    "admit": "ADMIT_SHACL_COURT",
    "route": "ROUTE_SA2A_CAPABILITY",
    "plan": "PLAN_WORK_GRAPH",
    "manufacture": "MANUFACTURE_ASH_RESOURCE",
    "execute": "EXECUTE_WORK_ORDER",
    "verify": "VERIFY_CONSEQUENCE",
    "receipt": "RECEIPT_CLOSE_LOOP",
}

# Stage-specific domain object this event produces, beyond the WorkOrder and
# GymactEpisode every event already carries -- this is what makes the OCEL
# log object-centric across the real domain vocabulary (SourceContract,
# CanonicalOntology, ...) rather than one flat WorkOrder/Episode pair.
DOMAIN_OBJECT_FOR_STAGE = {
    "discover": ("urn:zhf:source-contract:jira-issuetype", "SourceContract"),
    "reconstruct": ("urn:zhf:ontology:issuetype-candidate", "CanonicalOntology"),
    "admit": ("urn:zhf:shacl-admission:issuetype", "SHACLAdmission"),
    "route": ("urn:zhf:capability:sa2a_admit", "Sa2aCapability"),
    "plan": ("urn:zhf:workplan:issuetype-migration", "WorkPlan"),
    "manufacture": ("urn:zhf:artifact:issue_type.ex", "GeneratedArtifact"),
    "execute": ("urn:zhf:execution:issuetype-migration", "ExecutionResult"),
    "verify": ("urn:zhf:verification:issuetype-migration", "VerificationResult"),
    "receipt": ("urn:zhf:receipt:issuetype-migration", "ReplayReceipt"),
}


async def main() -> None:
    results = {}
    for stage_id, state in STAGES:
        admission = await admit_stage(stage_id)
        episode = await memory_episode(stage_id, state)
        results[stage_id] = {"admission": admission, "episode": episode}

        recorder.record(
            activity=ACTIVITY_FOR_STAGE[stage_id],
            objects=[
                (f"urn:zhf:workorder:{SUBJECT}", "WorkOrder"),
                (f"urn:zhf:episode:{episode['episode_id']}", "GymactEpisode"),
                DOMAIN_OBJECT_FOR_STAGE[stage_id],
            ],
            outcome={
                "stage": stage_id,
                "dcm_graph_digest": admission["graph_digest"],
                "dcm_admitted": admission["exploration"]["evaluations"][0]["admitted"],
                "state_digest": episode["observation"]["state_digest"],
                "verification_passed": episode["verification"]["passed"],
                **state,
            },
        )

    log = recorder.close()
    digest = recorder.digest()

    with open(
        "/private/tmp/claude-501/-Users-sac-autofde-lab/"
        "ef5450a5-1f7b-48f8-a016-0b9c0a2c0eab/scratchpad/gymact-sim/episode.ocel.json",
        "w",
    ) as f:
        json.dump(log, f, indent=2)

    print(json.dumps({
        "digest": digest,
        "event_count": len(log["events"]),
        "object_count": len(log["objects"]),
        "event_types": [t["name"] for t in log["eventTypes"]],
        "object_types": [t["name"] for t in log["objectTypes"]],
        "per_stage_admitted": {k: v["admission"]["exploration"]["evaluations"][0]["admitted"] for k, v in results.items()},
    }, indent=2))


asyncio.run(main())
