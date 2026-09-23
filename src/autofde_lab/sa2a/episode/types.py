"""Episode, IntelligenceUsage, ExplorationMeter, frontier_clean (v26.9.17 ARD §5.9-5.10, §21-23).

`ExplorationMeter.record()` is instrumentation at the routing/allocation boundary
(ARD §21), not per-model-wrapper self-reporting: `Episode1Runner`/`Episode2Runner`
(episode1.py/episode2.py) call `.record()` at the exact call sites where a discovery
engine, planner, or worker is invoked -- an engine that is never invoked can never
produce a non-zero count by construction, and an unrecognized (engine, resource_class)
pair raises rather than silently no-op-ing, so a real call this meter doesn't know how
to categorize cannot be rounded down to "no call happened" (the ARD §41 failure mode:
"unknown usage SHALL not be rounded down to zero").
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping, Optional


class EpisodeKind(str, Enum):
    UNKNOWN_DISCOVERY = "UNKNOWN_DISCOVERY"  # Episode 1
    KNOWN_REPLAY = "KNOWN_REPLAY"  # Episode 2


@dataclass(frozen=True, slots=True)
class IntelligenceUsage:
    """Per-episode exploratory-machinery accounting (ARD §5.10)."""

    frontier_model_calls: int = 0
    frontier_input_tokens: int = 0
    frontier_output_tokens: int = 0
    local_discovery_model_calls: int = 0
    local_discovery_tokens: int = 0
    explore_unknown_invocations: int = 0
    exploratory_planner_invocations: int = 0
    search_invocations: int = 0
    worker_allocations: int = 0
    discovery_cost: float = 0.0


# (engine, resource_class) -> IntelligenceUsage field name. ARD §22's frontier_clean
# formula also names `frontier_provider_requests` as a distinct zero-check; this
# meter has no lower-level HTTP-transport signal distinct from "a frontier model was
# called", so a provider-request event is recorded under the same
# `frontier_model_calls` field -- the conjunction in `compute_frontier_clean` below
# reads that field for both clauses rather than silently dropping one of them.
_FIELD_MAP: Mapping[tuple[str, str], str] = {
    ("frontier", "calls"): "frontier_model_calls",
    ("frontier", "provider_requests"): "frontier_model_calls",
    ("frontier", "input_tokens"): "frontier_input_tokens",
    ("frontier", "output_tokens"): "frontier_output_tokens",
    ("local_discovery", "calls"): "local_discovery_model_calls",
    ("local_discovery", "tokens"): "local_discovery_tokens",
    ("explore_unknown", "invocations"): "explore_unknown_invocations",
    ("exploratory_planner", "invocations"): "exploratory_planner_invocations",
    ("search", "invocations"): "search_invocations",
    ("worker", "allocations"): "worker_allocations",
    ("discovery", "cost"): "discovery_cost",
}


class ExplorationMeter:
    """Real per-episode counter, instrumented at the routing/allocation boundary (ARD §21)."""

    def __init__(self) -> None:
        self._usage: dict[str, IntelligenceUsage] = {}

    def record(
        self, episode_id: str, engine: str, resource_class: str, amount: float
    ) -> None:
        key = (engine, resource_class)
        field_name = _FIELD_MAP.get(key)
        if field_name is None:
            raise ValueError(
                f"ExplorationMeter.record(): unrecognized (engine, resource_class) = {key!r} -- "
                "unknown usage must not be silently dropped or rounded to zero (ARD §41)."
            )
        current = self._usage.get(episode_id, IntelligenceUsage())
        value = getattr(current, field_name)
        new_value = value + amount
        self._usage[episode_id] = replace(current, **{field_name: new_value})

    def usage_for(self, episode_id: str) -> IntelligenceUsage:
        return self._usage.get(episode_id, IntelligenceUsage())


def compute_frontier_clean(
    usage: IntelligenceUsage, *, known_route_observed: bool
) -> bool:
    """Computed, never caller-supplied (ARD §22)."""
    return (
        known_route_observed
        and usage.explore_unknown_invocations == 0
        and usage.frontier_model_calls == 0
        and usage.discovery_cost == 0.0
        and usage.worker_allocations == 0
    )


def guarded_frontier_clean(
    usage: IntelligenceUsage,
    *,
    classification_is_known: bool,
    route_executed: bool,
    required_postcondition_verified: bool,
) -> bool:
    """Anti-vacuity guard (ARD §23): a zero-call result from a no-op run is not clean."""
    if not (
        classification_is_known and route_executed and required_postcondition_verified
    ):
        return False
    return compute_frontier_clean(
        usage, known_route_observed=classification_is_known and route_executed
    )


@dataclass(frozen=True, slots=True)
class Episode:
    """One Episode 1 or Episode 2 run (ARD §5.9)."""

    episode_id: str
    kind: EpisodeKind
    exact_subject_digest: str
    fixture_id: str
    semantic_class_id: str
    request_identity: str
    actuation_identity: str
    classification: str  # "UNKNOWN" | "KNOWN" | "REFUSED" | "BLOCKED" | "UNSUPPORTED"
    route_executed: bool = False
    required_postcondition_verified: bool = False
    allocation_digest: str = ""
    plan_digest: str = ""
    manufacture_digest: str = ""
    authority_grant_id: Optional[str] = None
    prepared_receipt_digest: str = ""
    final_receipt_digest: str = ""
    ocel_digest: str = ""
    intelligence_usage: IntelligenceUsage = field(default_factory=IntelligenceUsage)
    standing: str = "CANDIDATE"
    known_route_id: str = ""
    experience_id: str = ""

    @property
    def frontier_clean(self) -> bool:
        return guarded_frontier_clean(
            self.intelligence_usage,
            classification_is_known=self.classification == "KNOWN",
            route_executed=self.route_executed,
            required_postcondition_verified=self.required_postcondition_verified,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "kind": self.kind.value,
            "exact_subject_digest": self.exact_subject_digest,
            "fixture_id": self.fixture_id,
            "semantic_class_id": self.semantic_class_id,
            "request_identity": self.request_identity,
            "actuation_identity": self.actuation_identity,
            "classification": self.classification,
            "route_executed": self.route_executed,
            "required_postcondition_verified": self.required_postcondition_verified,
            "allocation_digest": self.allocation_digest,
            "plan_digest": self.plan_digest,
            "manufacture_digest": self.manufacture_digest,
            "authority_grant_id": self.authority_grant_id,
            "prepared_receipt_digest": self.prepared_receipt_digest,
            "final_receipt_digest": self.final_receipt_digest,
            "ocel_digest": self.ocel_digest,
            "intelligence_usage": {
                "frontier_model_calls": self.intelligence_usage.frontier_model_calls,
                "frontier_input_tokens": self.intelligence_usage.frontier_input_tokens,
                "frontier_output_tokens": self.intelligence_usage.frontier_output_tokens,
                "local_discovery_model_calls": self.intelligence_usage.local_discovery_model_calls,
                "local_discovery_tokens": self.intelligence_usage.local_discovery_tokens,
                "explore_unknown_invocations": self.intelligence_usage.explore_unknown_invocations,
                "exploratory_planner_invocations": self.intelligence_usage.exploratory_planner_invocations,
                "search_invocations": self.intelligence_usage.search_invocations,
                "worker_allocations": self.intelligence_usage.worker_allocations,
                "discovery_cost": self.intelligence_usage.discovery_cost,
            },
            "standing": self.standing,
            "known_route_id": self.known_route_id,
            "experience_id": self.experience_id,
            "frontier_clean": self.frontier_clean,
        }
