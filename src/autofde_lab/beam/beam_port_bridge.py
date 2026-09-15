"""Stdio JSON-lines Port bridge exposing AutoFDE-Lab to the BEAM cluster.

Speaks the standard BEAM port protocol:
- in:  {"op": "ping"} -> {"ok": True, "pong": True}
- in:  {"op": "cmca_allocate", "budget": {...}, "candidates": [...], "tau": float, "plan_id": str}
       -> {"ok": True, "plan": {...}}
- in:  {"op": "calculate_salience", "branch": {...}}
       -> {"ok": True, "salience": float}
"""

from __future__ import annotations

import json
import sys
from typing import Any

from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    CandidateBranch,
    ResourceBudget,
)


def handle_request(req: dict[str, Any], allocator: MultifractalCascadeAllocator) -> dict[str, Any]:
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

        tau = float(req["tau"]) if "tau" in req and req["tau"] is not None else None
        plan_id = str(req.get("plan_id", "beam_plan"))

        plan = allocator.allocate(
            plan_id=plan_id,
            budget=budget,
            candidates=candidates,
            tau=tau,
        )

        return {
            "ok": True,
            "plan": {
                "plan_id": plan.plan_id,
                "tau_temperature": plan.tau_temperature,
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
        return {"ok": True, "salience": allocator.calculate_branch_salience(cand)}

    return {"ok": False, "error": f"unknown_op: {op}"}


def main() -> None:
    allocator = MultifractalCascadeAllocator()
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            req = json.loads(text)
            resp = handle_request(req, allocator)
        except Exception as e:
            resp = {"ok": False, "error": str(e), "exception_type": type(e).__name__}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
