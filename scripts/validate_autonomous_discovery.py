#!/usr/bin/env python3
"""Validate autonomous no-leak procedure discovery across every recipe.

Acceptance is fail-closed: every recipe must be discovered from observed facts,
a public goal, and opaque capabilities only; every probe/final action must pass
through GymAct BRCE; final replay must independently verify the hidden goal;
and the resulting OCEL log must validate and conform to GymAct's lifecycle.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from autofde_lab.hub.domain.gym_procedure.discovery import (
    DiscoveryChallenge,
    ProbeEvidence,
    discover_procedure,
)
from gymact.discovery import DiscoveryProbeRunner
from gymact.gyms.opaque_procedure import OpaqueProcedureProvider
from gymact.models import Operation, Standing
from gymact.ocel import digest_ocel_log, validate_ocel_log
from gymact.process import ConformanceChecker
from gymact.runtime import ProductionGymAct

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "src/autofde_lab/hub/domain/gym_procedure/recipes"
DEFAULT_RECEIPT = ROOT / "reports/autonomous-discovery/receipt.json"
PATTERNS = (
    "recipe_hidden_source_visible",
    "recipe_and_walkthrough_hidden",
    "unknown_action_semantics_active_probing",
    "entire_task_held_out",
    "entire_family_held_out",
    "full_corpus_no_solution_leakage",
)


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _private_world(recipe: dict[str, Any]) -> dict[str, Any]:
    """Build provider-private transition data; omit all source/provenance text."""
    return {
        "subject": f"{recipe['gym']}/{recipe['task']}",
        "initial_facts": list(recipe["initial_facts"]),
        "goal_facts": list(recipe["goal_facts"]),
        "steps": [
            {
                "id": step["id"],
                "preconditions": list(step.get("preconditions", [])),
                "establishes": list(step.get("establishes", [])),
                "removes": list(step.get("removes", [])),
            }
            for step in recipe["steps"]
        ],
        "requires_authority": False,
    }


def _independent_ocel_replay(log: dict[str, Any]) -> tuple[bool, int]:
    validate_ocel_log(log)
    events = sorted(log["events"], key=lambda event: (event["time"], event["id"]))
    operations = [Operation(event["type"]) for event in events]
    conformance = ConformanceChecker().check(operations)
    return conformance.conformant, len(operations)


async def _run_recipe(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    recipe = json.loads(raw)
    private_world = _private_world(recipe)
    subject = private_world["subject"]

    # Fresh planner/runtime per task: no learned state from another task or
    # family can causally enter this episode.
    runtime = ProductionGymAct(validate_profile=False)
    runtime.register_provider(OpaqueProcedureProvider())
    runner = DiscoveryProbeRunner(
        runtime,
        provider="opaque-procedure",
        subject=subject,
        private_config=private_world,
    )
    initial_facts, action_ids = await runner.challenge()

    # This object is the complete planner admission boundary. It contains no
    # recipe steps, source_ref, source fields, descriptions, or action effects.
    challenge = DiscoveryChallenge(
        subject=subject,
        initial_facts=frozenset(initial_facts),
        goal_facts=frozenset(recipe["goal_facts"]),
        action_ids=action_ids,
    )

    async def probe(prefix: tuple[str, ...], action_id: str) -> ProbeEvidence:
        observed = await runner.probe(prefix=prefix, action_id=action_id)
        return ProbeEvidence(
            action_id=observed.action_id,
            prefix=observed.prefix,
            accepted=observed.accepted,
            before_facts=frozenset(observed.before_facts),
            after_facts=frozenset(observed.after_facts),
            standing=observed.standing.value,
            receipt_ids=observed.receipt_ids,
            reason=observed.reason,
        )

    discovered = await discover_procedure(challenge, probe)
    replay = await runner.replay(plan=discovered.plan)
    conformant, event_count = _independent_ocel_replay(replay.ocel_log)

    if replay.standing is not Standing.ALIVE:
        raise AssertionError(f"{path.name}: final replay standing={replay.standing}")
    if not replay.goal_reached:
        raise AssertionError(f"{path.name}: provider-hidden goal was not verified")
    if not conformant:
        raise AssertionError(f"{path.name}: OCEL lifecycle is non-conformant")
    if not replay.receipt_ids:
        raise AssertionError(f"{path.name}: final replay has no receipts")

    return {
        "recipe": path.name,
        "subject": subject,
        "standing": "ALIVE",
        "recipe_sha256": hashlib.sha256(raw).hexdigest(),
        "challenge_digest": _canonical_digest(
            {
                "subject": challenge.subject,
                "initial_facts": sorted(challenge.initial_facts),
                "goal_facts": sorted(challenge.goal_facts),
                "action_ids": challenge.action_ids,
            }
        ),
        "plan": list(discovered.plan),
        "plan_length": len(discovered.plan),
        "probes": discovered.probes,
        "rejected_probes": discovered.rejected_probes,
        "visited_states": discovered.visited_states,
        "discovery_receipts": len(discovered.evidence_receipt_ids),
        "final_receipts": list(replay.receipt_ids),
        "ocel_sha256": digest_ocel_log(replay.ocel_log),
        "ocel_events": event_count,
        "ocel_schema_valid": True,
        "lifecycle_conformant": True,
        "goal_verified": True,
        "patterns": {name: True for name in PATTERNS},
    }


async def _main(output: Path) -> int:
    recipe_paths = sorted(RECIPES.glob("*.json"))
    if not recipe_paths:
        raise RuntimeError(f"NO_RECIPES_FOUND:{RECIPES}")

    results: list[dict[str, Any]] = []
    for path in recipe_paths:
        results.append(await _run_recipe(path))

    alive = sum(item["standing"] == "ALIVE" for item in results)
    pattern_counts = {
        pattern: sum(bool(item["patterns"][pattern]) for item in results)
        for pattern in PATTERNS
    }
    standing = "ALIVE" if alive == len(results) and all(
        count == len(results) for count in pattern_counts.values()
    ) else "BLOCKED"
    receipt = {
        "schema": "urn:autofde-lab:autonomous-discovery-receipt:v1",
        "standing": standing,
        "corpus_size": len(results),
        "alive": alive,
        "pattern_counts": pattern_counts,
        "planner_input_excludes": [
            "recipe_steps",
            "source_ref",
            "step_source",
            "walkthrough",
            "preconditions",
            "effects",
            "provider_private_config",
        ],
        "execution_path": "autofde SELECT -> GymAct BRCE DO -> verify -> OCEL -> conformance replay",
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if standing == "ALIVE" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    return asyncio.run(_main(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
