# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Typer projection of the CMCA (Chatman Multifractal Cascade Allocation) engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from autofde_lab.cmca.bcinr_bridge import candidate_measures
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    CandidateBranch,
    ResourceBudget,
)

app = typer.Typer(
    name="cmca",
    help="CMCA multifractal consequence allocation and Q16.16 ranking.",
    no_args_is_help=True,
)


def _emit(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


@app.command("allocate")
def allocate(
    candidates_json: str = typer.Argument(..., help="JSON array of candidate branches or file path"),
    plan_id: str = typer.Option("cmca_plan", help="Unique allocation plan ID"),
    total_ticks: int = typer.Option(10000, help="Total execution ticks budget"),
    memory_bytes: int = typer.Option(65536, help="Memory budget in bytes"),
    max_verification_depth: int = typer.Option(6, help="Max verification depth"),
    concurrency_lanes: int = typer.Option(8, help="Number of concurrency lanes"),
    pruning_threshold: float = typer.Option(0.01, help="Pruning threshold for non-viable candidates"),
) -> None:
    """Allocate budget across candidate branches using the certified multifractal cascade."""
    # Check if candidates_json is a path
    p = Path(candidates_json)
    if p.exists() and p.is_file():
        candidates_raw = json.loads(p.read_text(encoding="utf-8"))
    else:
        try:
            candidates_raw = json.loads(candidates_json)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"candidates_json must be valid JSON: {exc}") from exc

    if not isinstance(candidates_raw, list):
        raise typer.BadParameter("candidates_json must decode to a JSON array of candidates")

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
        for i, c in enumerate(candidates_raw)
    ]

    budget = ResourceBudget(
        total_ticks=total_ticks,
        memory_bytes=memory_bytes,
        max_verification_depth=max_verification_depth,
        consequence_risk_budget=0.5,
        concurrency_lanes=concurrency_lanes,
    )

    allocator = MultifractalCascadeAllocator(pruning_threshold=pruning_threshold)
    plan = allocator.allocate(plan_id=plan_id, budget=budget, candidates=candidates)

    payload = {
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
    _emit(payload)


@app.command("salience")
def salience(
    branch_json: str = typer.Argument(..., help="JSON object of a single candidate branch"),
) -> None:
    """Calculate the exact Q16.16 salience measure for a candidate branch."""
    try:
        b = json.loads(branch_json)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"branch_json must be valid JSON: {exc}") from exc

    cand = CandidateBranch(
        branch_id=str(b.get("branch_id", "b0")),
        operator_id=str(b.get("operator_id", "c8l")),
        world_id=str(b.get("world_id", "default")),
        state_id=str(b.get("state_id", "s0")),
        option_entropy=float(b.get("option_entropy", 1.0)),
        estimated_cost=float(b.get("estimated_cost", 10.0)),
        historical_yield=float(b.get("historical_yield", 1.0)),
    )
    measures = candidate_measures(cand)
    _emit({
        "ok": True,
        "measures": {
            "option_entropy": measures[0],
            "inverse_cost": measures[1],
            "historical_yield": measures[2],
            "salience": measures[3],
        }
    })
