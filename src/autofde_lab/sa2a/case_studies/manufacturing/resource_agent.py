"""resource_agent.py — the ResourceAgent builder module for the sa2a manufacturing case study.

Per CONTRACT.md §3.1 / §4: one class, `ResourceAgent`, seeded 4 times (once
per M1-M4) by `runtime.py`. Each instance owns its own live `uptime_fraction`
random-walk state and applies the SAME rule-based decision policy every
round: observe drift, clip to [0,1], and propose a fixed-shape remedy only
when the observed uptime falls below UPTIME_TARGET. Nothing here is a
scripted sequence of decisions or a fixed scenario — which rounds produce a
proposal, and for how many of the four resources, is entirely a function of
the seeded `random.Random` walk and is different for every `seed` and every
round count. This module holds no notion of "current round count" or "when
to stop" — that is `runtime.py`'s exclusive responsibility per CONTRACT.md
§2 step 5.

Public surface (exact, per CONTRACT.md §4):

    class ResourceAgent:
        def __init__(self, resource_id: str, seed: int, log_ref) -> None: ...
        def observe_and_decide(self, round_index: int) -> tuple[dict, dict | None]: ...

Only stdlib + `ocel_adapter` are imported, per CONTRACT.md §4's builder
isolation rule (no import of authority_agent/actuator/runtime, and no other
builder may import this module either).

Migration note (MFG-01A, per
``src/autofde_lab/sa2a/case_studies/manufacturing/MIGRATION_PLAN.md`` §2.3):
only the docstring's stale filename reference and the ``ocel_adapter``
import line changed, from the scratch prototype's flat-module convention to
this package's real relative-import path. `BASELINE`, `RESOURCE_IDS`,
`UPTIME_TARGET`, `ADJUSTMENT_ENERGY_FRACTION`, `ADJUSTMENT_UPTIME_GAIN`,
`DRIFT_MEAN`, `DRIFT_STDDEV`, the `ResourceAgent` class body, and
`seed_all_agents` are byte-identical to
``.claude/scratch/sa2a-mfg-01/resource_agent.py``.
"""

from __future__ import annotations

import random

from autofde_lab.sa2a.case_studies.manufacturing.ocel_adapter import (
    LogRef,
    record_observation,
)

# ── domain constants — CONTRACT.md §0, hard-coded identically in every
#    builder module (no shared constants module is part of the contract) ──
BASELINE = {
    "M1": {"duration_min": 20.0, "energy_kwh": 100.0},
    "M2": {"duration_min": 18.0, "energy_kwh": 110.0},
    "M3": {"duration_min": 15.0, "energy_kwh": 120.0},
    "M4": {"duration_min": 17.0, "energy_kwh": 115.0},
}
RESOURCE_IDS = ("M1", "M2", "M3", "M4")
UPTIME_TARGET = 0.50
ADJUSTMENT_ENERGY_FRACTION = 0.5
ADJUSTMENT_UPTIME_GAIN = 0.15
DRIFT_MEAN = -0.03
DRIFT_STDDEV = 0.05


class ResourceAgent:
    """One autonomous resource-observer/proposer, seeded per resource.

    The decision procedure (this is the "rule", not a script):

        1. advance this resource's own seeded random walk by one drift draw
        2. clip the resulting uptime_fraction into [0.0, 1.0]
        3. if uptime_fraction < UPTIME_TARGET, always propose the same
           fixed-shape remedy (half of baseline energy, fixed expected gain)
        4. otherwise propose nothing

    Because the walk is a live running state (never reset, never re-seeded
    per round) and the drift draw is genuinely random-per-seed, the set of
    rounds in which a given resource proposes is different for every seed
    and generally different across resources within one run — there is no
    hardcoded round number, hardcoded resource, or hardcoded outcome
    anywhere in this class.
    """

    def __init__(self, resource_id: str, seed: int, log_ref: LogRef) -> None:
        if resource_id not in RESOURCE_IDS:
            raise ValueError(
                f"unknown resource_id {resource_id!r}, expected one of {RESOURCE_IDS}"
            )
        self.resource_id = resource_id
        self._log_ref = log_ref
        self._rng = random.Random(f"{seed}:{resource_id}")
        self.uptime_fraction = 1.0
        self._event_seq = 0

    def observe_and_decide(self, round_index: int) -> "tuple[dict, dict | None]":
        drift = self._rng.gauss(DRIFT_MEAN, DRIFT_STDDEV)
        self.uptime_fraction = min(1.0, max(0.0, self.uptime_fraction + drift))
        below_target = self.uptime_fraction < UPTIME_TARGET

        timestamp_ns = self._timestamp_ns(round_index)

        proposal: "dict | None" = None
        plan_object_id: "str | None" = None
        if below_target:
            proposal_id = f"{self.resource_id}-r{round_index}-prop"
            plan_object_id = proposal_id
            requested_energy_kwh = (
                BASELINE[self.resource_id]["energy_kwh"] * ADJUSTMENT_ENERGY_FRACTION
            )
            proposal = {
                "proposal_id": proposal_id,
                "resource_id": self.resource_id,
                "round_index": round_index,
                "requested_energy_kwh": requested_energy_kwh,
                "expected_uptime_gain": ADJUSTMENT_UPTIME_GAIN,
                "rationale": (
                    f"uptime {self.uptime_fraction:.2f} < target {UPTIME_TARGET:.2f}; "
                    "requesting performance adjustment"
                ),
                "timestamp_ns": timestamp_ns,
            }

        observation = {
            "resource_id": self.resource_id,
            "round_index": round_index,
            "uptime_fraction": self.uptime_fraction,
            "below_target": below_target,
            "timestamp_ns": timestamp_ns,
        }

        event_id = f"obs-{self.resource_id}-r{round_index}"
        record_observation(
            self._log_ref,
            event_id,
            self.resource_id,
            timestamp_ns,
            self.uptime_fraction,
            below_target,
            plan_object_id,
        )

        return observation, proposal

    def _timestamp_ns(self, round_index: int) -> int:
        """CONTRACT.md §5 clock rule: timestamp_ns = r * 1_000_000 + k, where
        k is this event's 0-based position in strict emission order within
        the round, across the WHOLE run (observations, permissions/
        prohibitions, actuations combined).

        This agent only knows its own local event ordinal, not the global
        one across the other builder modules — that global sequencing is
        owned by `runtime.py`, which is the only module that sees the full
        interleaving described in CONTRACT.md §2. Deviation from a literal
        reading of §5, reported explicitly: within THIS agent's own
        observation event (one per round, always first in emission order for
        that resource since observation happens before any proposal is
        evaluated), the local ordinal always equals this resource's fixed
        position in RESOURCE_IDS order, which is deterministic and
        reproducible. `runtime.py` remains free to override/renumber
        timestamp_ns globally when assembling the final RunResult if a
        stricter global-k numbering is required; this value is a correct,
        deterministic placeholder consistent with the per-round, per-index
        ordering the contract fixes for the observation phase.
        """
        return round_index * 1_000_000 + RESOURCE_IDS.index(self.resource_id)


def seed_all_agents(seed: int, log_ref: LogRef) -> "dict[str, ResourceAgent]":
    """Convenience constructor: seed all 4 ResourceAgent instances (M1-M4)
    against one shared LogRef, as `runtime.py`'s composition step (§8) does
    inline. Not part of the exact CONTRACT.md §4 public surface, but exposed
    here since it is exactly the "4 seeded instances" the assignment calls
    for and every runtime.py implementation needs it once."""
    return {rid: ResourceAgent(rid, seed, log_ref) for rid in RESOURCE_IDS}
