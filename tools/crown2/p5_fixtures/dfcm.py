"""DfCM feature vector, hard feasibility, Pareto frontier, portfolio planner,
goal admission and stale-world gate.

Spec: tools/crown2/PLANNER-SOVEREIGN-ACTUATION.md, sections
"DfCM is a planner, not a hidden scorer", "Contracts", "gymact refuses raw
commands". Pure Python, no native hub dependency.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, Callable, Optional, Sequence


# --------------------------------------------------------------------------- #
# Feature vector V(s, a)
# --------------------------------------------------------------------------- #

POSITIVE_FEATURES = (
    "goal_progress",
    "reversibility",
    "information_gain",
    "future_reachability",
    "option_diversity",
    "evidence_strength",
    "manufacturability",
    "qualifiability",
)
NEGATIVE_FEATURES = (
    "authority_consumption",
    "irreversibility",
    "blast_radius",
    "compute_cost",
)


@dataclass(frozen=True)
class DfCMVector:
    """Common feature vector V(s,a). All fields are floats in [0, 1] except
    blast_radius (count-like, >= 0) and compute_cost (>= 0).
    Positive features are maximised; negative features are minimised."""

    goal_progress: float
    reversibility: float
    information_gain: float
    future_reachability: float
    option_diversity: float
    evidence_strength: float
    manufacturability: float
    qualifiability: float
    authority_consumption: float
    irreversibility: float
    blast_radius: float
    compute_cost: float

    def __post_init__(self) -> None:
        for f in fields(self):
            v = getattr(self, f.name)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise TypeError(f"{f.name} must be numeric, got {type(v).__name__}")
            if v < 0:
                raise ValueError(f"{f.name} must be >= 0, got {v}")
        for name in POSITIVE_FEATURES + ("authority_consumption", "irreversibility"):
            if getattr(self, name) > 1.0:
                raise ValueError(f"{name} must be <= 1.0, got {getattr(self, name)}")

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    def better_or_equal(self, other: "DfCMVector") -> bool:
        return all(
            getattr(self, n) >= getattr(other, n) for n in POSITIVE_FEATURES
        ) and all(getattr(self, n) <= getattr(other, n) for n in NEGATIVE_FEATURES)

    def dominates(self, other: "DfCMVector") -> bool:
        """Pareto dominance: >= on every positive, <= on every negative, and
        strictly better on at least one axis."""
        return self.better_or_equal(other) and self != other


@dataclass(frozen=True)
class DfCMHardConstraints:
    """Hard feasibility: Evidence ∩ Compatibility ∩ AuthorityPotential ∩
    Manufacturability ∩ Qualifiability. A candidate failing any is infeasible
    before any frontier reasoning happens."""

    min_evidence_strength: float = 0.0
    min_future_reachability: float = 0.0  # 0 => self-destruction still allowed
    max_authority_consumption: float = 1.0
    min_manufacturability: float = 0.0
    min_qualifiability: float = 0.0

    def violations(self, v: DfCMVector) -> list[str]:
        out = []
        if v.evidence_strength < self.min_evidence_strength:
            out.append("EVIDENCE")
        if v.future_reachability < self.min_future_reachability:
            out.append("FUTURE_REACHABILITY")
        if v.authority_consumption > self.max_authority_consumption:
            out.append("AUTHORITY_POTENTIAL")
        if v.manufacturability < self.min_manufacturability:
            out.append("MANUFACTURABILITY")
        if v.qualifiability < self.min_qualifiability:
            out.append("QUALIFIABILITY")
        return out


def pareto_frontier(items: Sequence[tuple[Any, DfCMVector]]) -> list[tuple[Any, DfCMVector]]:
    """Keep every (key, vector) not Pareto-dominated by another item."""
    keep = []
    for k, v in items:
        if not any(o.dominates(v) for _, o in items):
            keep.append((k, v))
    return keep


def astar_edge_cost(v: DfCMVector) -> float:
    """A*/AO* projection: positive edge cost. Strictly positive so A* stays
    admissible with a zero heuristic. The raw vector is kept alongside every
    receipt; this scalar is only the planner adapter."""
    shortfall = sum(1.0 - getattr(v, n) for n in POSITIVE_FEATURES)
    penalty = (
        v.authority_consumption
        + v.irreversibility
        + v.blast_radius
        + v.compute_cost
    )
    return 0.01 + shortfall + penalty


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #


class RefusalCode(str, Enum):
    UNBOUNDED_GOAL = "UNBOUNDED_GOAL"
    STALE_WORLD_STATE = "STALE_WORLD_STATE"
    NO_PLANNER_SELECTION = "NO_PLANNER_SELECTION"
    NO_AUTHORITY = "NO_AUTHORITY"
    NON_PLANNER_ACTUATION = "NON_PLANNER_ACTUATION"
    NO_FEASIBLE_CANDIDATE = "NO_FEASIBLE_CANDIDATE"


class Refused(Exception):
    def __init__(self, code: RefusalCode, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"REFUSED[{code.value}] {detail}".rstrip())


# --------------------------------------------------------------------------- #
# Goal admission (E)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Goal:
    text: str
    terminal_predicate: Optional[Callable[[Any], bool]] = None
    horizon_or_budget: Optional[int] = None
    standing_semantics: Optional[str] = None
    falsifier: Optional[str] = None


def admit_goal(goal: Goal) -> Goal:
    """Goal admission: terminal_predicate, horizon_or_budget, standing_semantics,
    falsifier are all required — else REFUSED[UNBOUNDED_GOAL]."""
    missing = [
        n
        for n in ("terminal_predicate", "horizon_or_budget", "standing_semantics", "falsifier")
        if getattr(goal, n) is None
    ]
    if goal.horizon_or_budget is not None and goal.horizon_or_budget <= 0:
        missing.append("horizon_or_budget(non-positive)")
    if missing:
        raise Refused(RefusalCode.UNBOUNDED_GOAL, f"missing {missing} for goal {goal.text!r}")
    return goal


# --------------------------------------------------------------------------- #
# World digest and staleness (C)
# --------------------------------------------------------------------------- #


def world_digest(state: Any) -> str:
    payload = json.dumps(_jsonable(state), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _jsonable(x: Any) -> Any:
    if hasattr(x, "_asdict"):
        return {k: _jsonable(v) for k, v in x._asdict().items()}
    if isinstance(x, Enum):
        return x.name
    if isinstance(x, (list, tuple)):
        return [_jsonable(i) for i in x]
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    return x


@dataclass(frozen=True)
class PlanCandidate:
    planner: str
    ordered_actions: tuple
    predicted_world_states: tuple
    terminal_standing: str
    dfcm_vectors: tuple  # one DfCMVector per action
    planner_value: float
    world_digest: str
    assumptions: tuple = ()

    @property
    def first_vector(self) -> DfCMVector:
        return self.dfcm_vectors[0]


@dataclass(frozen=True)
class PlannerSelectionReceipt:
    planner: str
    selected: PlanCandidate
    rejected: tuple  # (candidate, reason)
    frontier: tuple  # candidates surviving Pareto
    raw_vectors: tuple  # raw DfCMVector for every candidate (survives scalarisation)
    world_digest: str


def check_world_fresh(candidate: PlanCandidate, current_state: Any) -> str:
    """gymact gate: planner_receipt.world_digest != world.digest -> REFUSED[STALE_WORLD_STATE]."""
    now = world_digest(current_state)
    if candidate.world_digest != now:
        raise Refused(
            RefusalCode.STALE_WORLD_STATE,
            f"plan digest {candidate.world_digest[:19]} != world {now[:19]}",
        )
    return now


# --------------------------------------------------------------------------- #
# DfCMPortfolioPlanner (a planner that selects among PlanCandidate[])
# --------------------------------------------------------------------------- #


@dataclass
class DfCMPortfolioPlanner:
    """Selects one PlanCandidate: hard feasibility first, then Pareto frontier
    on the first-action vector, then a deterministic scalar tie-break. The
    raw vector of every candidate survives into the receipt."""

    hard: DfCMHardConstraints = field(default_factory=DfCMHardConstraints)
    name: str = "DfCMPortfolioPlanner"

    def select(self, candidates: Sequence[PlanCandidate], current_state: Any) -> PlannerSelectionReceipt:
        digest = world_digest(current_state)
        rejected: list[tuple[PlanCandidate, str]] = []
        feasible: list[PlanCandidate] = []
        for c in candidates:
            if c.world_digest != digest:
                rejected.append((c, "STALE_WORLD_STATE"))
                continue
            viol = self.hard.violations(c.first_vector)
            if viol:
                rejected.append((c, "INFEASIBLE:" + ",".join(viol)))
                continue
            feasible.append(c)
        frontier = [c for c, _ in pareto_frontier([(c, c.first_vector) for c in feasible])]
        for c in feasible:
            if c not in frontier:
                rejected.append((c, "PARETO_DOMINATED"))
        if not frontier:
            raise Refused(RefusalCode.NO_FEASIBLE_CANDIDATE, f"{len(candidates)} candidates, 0 feasible")
        selected = min(frontier, key=lambda c: (astar_edge_cost(c.first_vector), c.planner_value, c.planner))
        return PlannerSelectionReceipt(
            planner=self.name,
            selected=selected,
            rejected=tuple(rejected),
            frontier=tuple(frontier),
            raw_vectors=tuple(c.first_vector for c in candidates),
            world_digest=digest,
        )
