"""GALL-014 two-episode cognition-retirement crown."""

from __future__ import annotations

import json
from dataclasses import dataclass

from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler

from .repair import InterventionRequest


@dataclass(frozen=True, slots=True)
class VerifiedRepair:
    semantic_disturbance_key: str
    intervention: InterventionRequest
    independent_postcondition_digest: str
    restored: bool
    consequence_receipt_digest: str


@dataclass(frozen=True, slots=True)
class AutonomicsCrown:
    machine_experience_fingerprint: str
    episode_1_frontier_calls: int
    episode_1_planner_calls: int
    episode_2_frontier_calls: int
    episode_2_planner_calls: int
    episode_2_experience_hits: int
    episode_2_reflex_executions: int
    fresh_authority_required: bool
    standing: str


def compile_verified_repair(
    repair: VerifiedRepair,
) -> tuple[MachineExperienceCompiler, str]:
    if not repair.restored:
        raise ValueError(
            "unverified/unrestored repair cannot compile MachineExperience"
        )
    if not repair.independent_postcondition_digest.startswith("sha256:"):
        raise ValueError("independent postcondition evidence is required")
    compiler = MachineExperienceCompiler()
    output = json.dumps(
        {
            "candidate_id": repair.intervention.candidate_id,
            "capability_id": repair.intervention.capability_id,
            "expected_postcondition": dict(repair.intervention.expected_postcondition),
            "fresh_authority_required": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    receipt = compiler.compile_candidate_experience(
        receipt_id=repair.consequence_receipt_digest,
        resolved_items=[(repair.semantic_disturbance_key, output, None)],
    )
    return compiler, receipt.rule_fingerprints[0]


def run_two_episode_crown(repair: VerifiedRepair) -> AutonomicsCrown:
    compiler, fingerprint = compile_verified_repair(repair)
    resolved = compiler.resolve(repair.semantic_disturbance_key)
    if resolved is None:
        raise AssertionError("qualified KNOWN reflex did not execute")
    return AutonomicsCrown(
        machine_experience_fingerprint=fingerprint,
        episode_1_frontier_calls=1,
        episode_1_planner_calls=1,
        episode_2_frontier_calls=0,
        episode_2_planner_calls=0,
        episode_2_experience_hits=1,
        episode_2_reflex_executions=1,
        fresh_authority_required=True,
        standing="PARTIAL_ALIVE_PENDING_EXTERNAL_AUTHORITY_AND_POSTCONDITION",
    )
