"""Stdio JSON-lines Port bridge exposing AutoFDE-Lab to the BEAM cluster.

Speaks the standard BEAM port protocol:
- in:  {"op": "ping"} -> {"ok": True, "pong": True}
- in:  {"op": "cmca_allocate", "budget": {...}, "candidates": [...], "plan_id": str}
       -> {"ok": True, "plan": {...}}
- in:  {"op": "calculate_salience", "branch": {...}}
       -> {"ok": True, "salience": float}
- in:  {"op": "sa2a_validate", "card_path": str|None, "profile": str|None}
       -> {"ok": True, "agent_id": str, "profile": str, "status": "VALID"}
- in:  {"op": "sa2a_admit", "candidate_id", "query_id", "assertion", "source", "evidence"}
       -> {"ok": bool, "receipt_id", "candidate_hash", "standing", "reasons", "admitted_assertion"}
- in:  {"op": "sa2a_plan", "candidates": [...], "plan_id", "ticks", "tokens", "experiments"}
       -> {"ok": True, "plan_id", "plan_hash", "total_entropy_preserved", "allocations": [...]}
- in:  {"op": "sa2a_execute", "query": str, "compiled_rules": [[pattern, output], ...]}
       -> {"ok": True, "query", "result", "llm_avoidance_ratio"}
- in:  {"op": "sa2a_replay", "manifest": <any JSON>, "expected_hash": str}
       -> {"ok": bool, "computed_hash", "expected_hash", "verified"}

The CMCA measure is the vendored bcinr allocator's (wasm-first; no tau --
the lens policy is compiled upstream, and an explicit tau is refused by
the engine). "calculate_salience" reports the salience feature axis
exactly as ``bcinr_bridge.candidate_measures`` encodes it for the wire;
it is feature extraction, not a local allocation measure.

The five ``sa2a_*`` ops are thin wrappers over the exact same in-process
objects ``autofde_lab.sa2a.cli``'s Typer commands call (``DowngradeGuard``,
``UnknownResolutionPipeline``, ``CMCACandidateAllocator``,
``MachineExperienceCompiler``) and build the identical response-payload
shape those commands pass to ``_emit`` -- so the CLI and this port speak
one JSON encoding, not two independently maintained ones. They do not call
into the Typer app itself (no argument parsing / no stdout side effects);
they call the underlying pipeline objects directly.
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

from autofde_lab.cmca.bcinr_bridge import candidate_measures
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    CandidateBranch,
    ResourceBudget,
)


def handle_request(
    req: dict[str, Any], allocator: MultifractalCascadeAllocator
) -> dict[str, Any]:
    op = req.get("op")
    if op == "ping":
        return {"ok": True, "pong": True}

    if op == "cmca_allocate":
        b_raw = req.get("budget", {})
        budget = ResourceBudget(
            total_ticks=int(b_raw.get("total_ticks", 10000)),
            memory_bytes=int(b_raw.get("memory_bytes", 65536)),
            max_verification_depth=int(b_raw.get("max_verification_depth", 6)),
            consequence_risk_budget=float(b_raw.get("consequence_risk_budget", 0.5)),
            concurrency_lanes=int(b_raw.get("concurrency_lanes", 8)),
        )

        raw_candidates = req.get("candidates", [])
        candidates = [
            CandidateBranch(
                branch_id=str(c.get("branch_id", f"b_{i}")),
                operator_id=str(c.get("operator_id", "c8l")),
                world_id=str(c.get("world_id", "default")),
                state_id=str(c.get("state_id", "s0")),
                option_entropy=float(c.get("option_entropy", 1.0)),
                estimated_cost=float(c.get("estimated_cost", 10.0)),
                historical_yield=float(c.get("historical_yield", 1.0)),
                metadata=c.get("metadata"),
            )
            for i, c in enumerate(raw_candidates)
        ]

        plan_id = str(req.get("plan_id", "beam_plan"))

        plan = allocator.allocate(
            plan_id=plan_id,
            budget=budget,
            candidates=candidates,
        )

        return {
            "ok": True,
            "plan": {
                "plan_id": plan.plan_id,
                "total_option_value_preserved": plan.total_option_value_preserved,
                "entropy": plan.entropy,
                "allocations": [
                    {
                        "branch_id": a.branch_id,
                        "allocated_fraction": a.allocated_fraction,
                        "allocated_ticks": a.allocated_ticks,
                        "allocated_memory_bytes": a.allocated_memory_bytes,
                        "verification_depth": a.verification_depth,
                        "standing": str(a.standing.value),
                        "priority_lane": a.priority_lane,
                    }
                    for a in plan.allocations
                ],
            },
        }

    if op == "calculate_salience":
        b = req.get("branch", {})
        cand = CandidateBranch(
            branch_id=str(b.get("branch_id", "b0")),
            operator_id=str(b.get("operator_id", "c8l")),
            world_id=str(b.get("world_id", "default")),
            state_id=str(b.get("state_id", "s0")),
            option_entropy=float(b.get("option_entropy", 1.0)),
            estimated_cost=float(b.get("estimated_cost", 10.0)),
            historical_yield=float(b.get("historical_yield", 1.0)),
        )
        return {"ok": True, "salience": candidate_measures(cand)[3]}

    if op == "sa2a_validate":
        return _sa2a_validate(req)

    if op == "sa2a_admit":
        return _sa2a_admit(req)

    if op == "sa2a_plan":
        return _sa2a_plan(req)

    if op == "sa2a_execute":
        return _sa2a_execute(req)

    if op == "sa2a_replay":
        return _sa2a_replay(req)

    return {"ok": False, "error": f"unknown_op: {op}"}


def _sa2a_validate(req: dict[str, Any]) -> dict[str, Any]:
    """Wraps ``autofde_lab.sa2a.cli.validate``'s body, without Typer parsing/exit."""
    from pathlib import Path

    from autofde_lab.sa2a.a2a_bridge.agent_card import (
        SA2A_PROFILE_V26_9_16,
        create_default_sa2a_agent_card,
    )
    from autofde_lab.sa2a.a2a_bridge.downgrade_guard import DowngradeGuard, UnsupportedProfileError

    profile = str(req.get("profile") or SA2A_PROFILE_V26_9_16)
    guard = DowngradeGuard()
    try:
        guard.assert_supported_profile(profile)
    except UnsupportedProfileError as exc:
        return {"ok": False, "error": str(exc), "code": exc.code, "profile": exc.profile}

    card_path = req.get("card_path")
    if card_path:
        p = Path(card_path)
        if not p.exists():
            return {"ok": False, "error": f"Card file not found: {card_path}", "code": "NOT_FOUND"}
        raw = json.loads(p.read_text(encoding="utf-8"))
        profiles = raw.get("supported_profiles", [])
        if profile not in profiles:
            return {
                "ok": False,
                "error": f"Agent card does not declare support for profile {profile}",
                "code": "UNSUPPORTED_PROFILE",
            }
        card_id = raw.get("agent_id", "unknown")
    else:
        card_id = create_default_sa2a_agent_card().agent_id

    return {"ok": True, "agent_id": card_id, "profile": profile, "status": "VALID"}


def _sa2a_admit(req: dict[str, Any]) -> dict[str, Any]:
    """Wraps ``autofde_lab.sa2a.cli.admit``'s body."""
    from autofde_lab.sa2a.unknown.resolution import CandidateResolution, UnknownResolutionPipeline

    cand = CandidateResolution(
        candidate_id=str(req.get("candidate_id", "")),
        query_id=str(req.get("query_id", "q0")),
        proposed_assertion=str(req.get("assertion", "")),
        evidence_payload=req.get("evidence", {}),
        source_identity=str(req.get("source", "discovery-engine")),
        consumed_ticks=10,
        consumed_tokens=100,
    )

    pipeline = UnknownResolutionPipeline()
    receipt = pipeline.admit_candidate(cand)

    return {
        "ok": receipt.admitted,
        "receipt_id": receipt.receipt_id,
        "candidate_hash": receipt.candidate_hash,
        "standing": receipt.epistemic_standing.value,
        "reasons": list(receipt.reasons),
        "admitted_assertion": receipt.admitted_assertion,
    }


def _sa2a_plan(req: dict[str, Any]) -> dict[str, Any]:
    """Wraps ``autofde_lab.sa2a.cli.plan``'s body."""
    from autofde_lab.sa2a.unknown.allocator import (
        CMCACandidateAllocator,
        ExplorationBudget,
        UnknownCandidate,
    )

    raw_candidates = req.get("candidates", [])
    cands = [
        UnknownCandidate(
            item_id=str(c.get("item_id", f"item_{i}")),
            description=str(c.get("description", "")),
            option_entropy=float(c.get("option_entropy", 1.0)),
            estimated_cost=float(c.get("estimated_cost", 10.0)),
            historical_yield=float(c.get("historical_yield", 1.0)),
        )
        for i, c in enumerate(raw_candidates)
    ]

    budget = ExplorationBudget(
        max_compute_ticks=int(req.get("ticks", 1000)),
        max_tokens=int(req.get("tokens", 50000)),
        max_experiments=int(req.get("experiments", 10)),
    )

    allocator = CMCACandidateAllocator()
    allocation_plan = allocator.allocate(
        plan_id=str(req.get("plan_id", "frontier_plan_0")), budget=budget, candidates=cands
    )

    return {
        "ok": True,
        "plan_id": allocation_plan.plan_id,
        "plan_hash": allocation_plan.plan_hash,
        "total_entropy_preserved": allocation_plan.total_entropy_preserved,
        "allocations": [
            {
                "item_id": a.item_id,
                "fraction": a.allocated_fraction,
                "ticks": a.allocated_ticks,
                "tokens": a.allocated_tokens,
                "experiments": a.allocated_experiments,
                "lane": a.priority_lane,
                "standing": a.standing.value,
            }
            for a in allocation_plan.allocations
        ],
    }


def _sa2a_execute(req: dict[str, Any]) -> dict[str, Any]:
    """Wraps ``autofde_lab.sa2a.cli.execute``'s body."""
    from autofde_lab.sa2a.unknown.compilation import MachineExperienceCompiler

    query = str(req.get("query", ""))
    compiler = MachineExperienceCompiler()
    compiled_rules = req.get("compiled_rules")
    if compiled_rules:
        items = [(r[0], r[1], None) for r in compiled_rules]
        compiler.compile_candidate_experience(receipt_id="port_exec_rec", resolved_items=items)

    resolved = compiler.resolve(query, fallback_llm_inference=lambda: f"FALLBACK_INFERENCE_FOR({query})")

    return {
        "ok": True,
        "query": query,
        "result": resolved,
        "llm_avoidance_ratio": compiler.inference_avoidance_ratio,
    }


def _sa2a_replay(req: dict[str, Any]) -> dict[str, Any]:
    """Wraps ``autofde_lab.sa2a.cli.replay``'s body."""
    data = req.get("manifest")
    expected_hash = str(req.get("expected_hash", ""))

    dumped = json.dumps(data, sort_keys=True, separators=(",", ":"))
    computed_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    matches = computed_hash == expected_hash
    return {
        "ok": matches,
        "computed_hash": computed_hash,
        "expected_hash": expected_hash,
        "verified": matches,
    }


def main() -> None:
    allocator = MultifractalCascadeAllocator()
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            req = json.loads(text)
            resp = handle_request(req, allocator)
        except Exception as e:  # noqa: BLE001 -- the port protocol requires
            # every failure to become an {"ok": false} envelope line, never
            # a dead port: the BEAM caller reads exactly one reply per
            # request and cannot recover a crashed bridge process.
            resp = {"ok": False, "error": str(e), "exception_type": type(e).__name__}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
