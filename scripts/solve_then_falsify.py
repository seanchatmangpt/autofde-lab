#!/usr/bin/env python3
# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Close the smallest real gap named in
`docs/2026-08-11-autofde-lab-togaf-autonomic-architecture-plan.md` section 11:
falsification (`autofde_lab.reasoning.laboratory.falsify_candidate`) existed
but, before this script, was only ever invoked once inside the one-shot
`reasoning/togaf_loop_demo.py` demo function -- never wired to run after a
real fabric solve (`autofde_lab.fabric.service.DecisionFabric.solve`, the
code path `fabric/cli.py`'s `solve` command and this session's real
Astar/PDDLDomain runs both exercise).

This script is the real per-cycle wiring: it runs one real, registered-domain
fabric solve, builds a real `ExperimentReceipt` from that solve's own
`DecisionResult` (never a fabricated postcondition), and immediately calls
the real `falsify_candidate` against it. It is not a scheduler -- it is one
callable step (`solve_and_falsify`) any real per-cycle caller (a loop, a
cron, another phase) can invoke after each real fabric solve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from autofde_lab.fabric.cli import get_fabric
from autofde_lab.fabric.models import DecisionRequest, DecisionResult, DecisionStanding
from autofde_lab.reasoning.laboratory import (
    ArchitectureCandidate,
    ExperimentReceipt,
    FalsificationResult,
    falsify_candidate,
)


def receipt_from_solve(intent_id: str, result: DecisionResult) -> ExperimentReceipt:
    """Real receipt built only from what the real solve actually observed --
    never a value invented for this script. `SOLVED` with a terminal
    trajectory is the one real postcondition this fabric result can support
    ("bounded rollout reached a terminal state"); anything else is recorded
    as violated, never silently dropped."""
    reached_terminal = result.standing == DecisionStanding.SOLVED and result.terminal
    return ExperimentReceipt(
        intent_id=intent_id,
        observed_outcome_refs=(f"fabric-receipt:{result.receipt_sha256}",),
        authority_standing="ADMITTED",
        postconditions_observed=("bounded-rollout-reached-terminal-state",)
        if reached_terminal
        else (),
        postconditions_violated=()
        if reached_terminal
        else ("bounded-rollout-reached-terminal-state",),
        ocel_evidence_ref=None,
        standing="OBSERVED",
    )


def solve_and_falsify(
    domain: str,
    domain_arguments: dict | None = None,
    max_steps: int = 100,
    solver: str | None = None,
) -> tuple[DecisionResult, FalsificationResult]:
    """The one callable per-cycle step: real fabric solve, then the real
    falsification check run immediately against that real solve's output."""
    fabric = get_fabric()
    request = DecisionRequest(
        domain=domain,
        solver=solver,
        domain_arguments=domain_arguments or {},
        max_steps=max_steps,
        use_cache=False,
    )
    result = fabric.solve(request)

    candidate = ArchitectureCandidate(
        candidate_id=f"fabric-solve:{domain}:{result.trajectory_sha256[:16]}",
        target_state_assertions=(f"{domain} bounded rollout reaches a terminal state",),
        verification_criteria=("bounded-rollout-reached-terminal-state",),
    )
    intent_id = f"solve-then-falsify:{result.trajectory_sha256}"
    receipt = receipt_from_solve(intent_id, result)
    falsification = falsify_candidate(candidate, receipts=(receipt,))
    return result, falsification


def main() -> None:
    domain = sys.argv[1] if len(sys.argv) > 1 else "Maze"
    solver = sys.argv[2] if len(sys.argv) > 2 else "Astar"
    max_steps = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    result, falsification = solve_and_falsify(domain, solver=solver, max_steps=max_steps)
    print(
        json.dumps(
            {
                "fabric_solve": {
                    "domain": domain,
                    "standing": result.standing.value,
                    "terminal": result.terminal,
                    "steps": len(result.steps),
                    "receipt_sha256": result.receipt_sha256,
                },
                "falsification": {
                    "candidate_id": falsification.candidate_id,
                    "standing": falsification.standing.value,
                    "rationale": falsification.rationale,
                    "receipt_refs": falsification.receipt_refs,
                    "violated_constraints": falsification.violated_constraints,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
