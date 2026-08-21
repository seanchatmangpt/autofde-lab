# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Drives real, sqlite/OCEL-sourced exploration candidates all the way
through a real gymact-mediated experiment into a real PSRO step -- closing
the gap this pass's own prompt named: `process_informed_hypotheses`
(previous pass) had zero real callers outside its own test; its real
2-hypothesis output had never itself been driven through
`exploration_gymact_falsification.py` / `exploration_payoff_bridge.py` /
`exploration_psro_loop.py` (confirmed via `grep -rln
"process_informed_hypotheses" src/ tests/`: only its own definition and
test file).

This module is pure composition of four already-real functions -- no new
core evidence/scoring logic is introduced here, only orchestration:

1. `process_informed_exploration.process_informed_hypotheses` -- real
   sqlite/OCEL evidence -> real `tuple[DesiredStateHypothesis, ...]`.
2. `laboratory.generate_triz_candidates` -- hypotheses -> real
   `ArchitectureCandidate`s.
3. `exploration_gymact_falsification.falsify_exploration_candidate_via_gymact`
   -- each real candidate -> a real gymact-mediated experiment (materialize/
   act/verify/teardown) -> a real `FalsificationResult`.
4. `exploration_psro_loop.run_exploration_psro_round` -- the real
   `(candidate, falsification)` pairs -> a real `PayoffHypergraph` +
   `PolicySpaceResponseOracle.step()`.

Every real object each stage produces flows unmodified into the next; this
module coerces, re-derives, or fabricates nothing along the way.
"""

from __future__ import annotations

from typing import Any, Sequence

from .exploration_gymact_falsification import falsify_exploration_candidate_via_gymact
from .exploration_psro_loop import ExplorationPsroRoundOutcome, run_exploration_psro_round
from .laboratory import (
    ArchitectureCandidate,
    EnterpriseObservation,
    FalsificationResult,
    TRIZContradiction,
    WorldExperimentProvider,
    generate_triz_candidates,
)
from .process_informed_exploration import process_informed_hypotheses

__all__ = ["run_process_informed_triz_psro_round"]


def run_process_informed_triz_psro_round(
    metadata: object,
    *,
    db_path: str,
    observation: EnterpriseObservation,
    contradiction: TRIZContradiction,
    league: Any,
    domain: Any,
    constructor_planner_ids: Sequence[str],
    falsifier_planner_id: str,
    world_id: str = "generic_enterprise",
    target_world_ref: str = "generic_enterprise",
    gymact_provider: WorldExperimentProvider | None = None,
) -> ExplorationPsroRoundOutcome:
    """Real, four-stage pipeline: real sqlite/OCEL evidence -> real TRIZ
    candidates -> real gymact-mediated falsification (one independent
    experiment per candidate) -> a real PSRO step over the resulting real
    payoff evidence.

    `db_path`/`observation` are the same real arguments
    `process_informed_hypotheses` already takes -- an already-written real
    sqlite db and the real `EnterpriseObservation` it describes. `league`/
    `domain`/`constructor_planner_ids`/`falsifier_planner_id`/`world_id`
    are the same real arguments `exploration_psro_loop.
    run_exploration_psro_round` already takes. `gymact_provider` defaults
    to `None`, meaning `falsify_exploration_candidate_via_gymact`'s own
    default: a fresh, fail-closed `GymActWorldExperimentProvider()`.

    Each real candidate's `initial_state_evidence_ref` is `db_path` itself
    -- the real sqlite file the candidate's own generating hypothesis was
    actually observed from, never a fabricated reference.
    """
    hypotheses = process_informed_hypotheses(metadata, db_path=db_path, observation=observation)
    candidates: tuple[ArchitectureCandidate, ...] = generate_triz_candidates(hypotheses, contradiction)

    candidates_and_falsifications: list[tuple[ArchitectureCandidate, FalsificationResult]] = []
    for candidate in candidates:
        outcome = falsify_exploration_candidate_via_gymact(
            candidate,
            target_world_ref=target_world_ref,
            initial_state_evidence_ref=str(db_path),
            provider=gymact_provider,
        )
        candidates_and_falsifications.append((candidate, outcome.falsification))

    return run_exploration_psro_round(
        candidates_and_falsifications,
        league=league,
        domain=domain,
        world_id=world_id,
        constructor_planner_ids=constructor_planner_ids,
        falsifier_planner_id=falsifier_planner_id,
    )
