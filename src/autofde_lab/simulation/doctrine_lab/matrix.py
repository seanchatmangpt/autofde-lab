"""seeds x worlds x strategies matrix over the fortune5_safe engine.

Every episode is ``rounds`` calls of the unmodified ``engine.run_episode`` with the
opponent adapting the Scenario between rounds. Feasibility and dominance reuse the
fortune5_safe DfCM relations; nothing selects a winner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import lru_cache
from statistics import fmean
from typing import Sequence

from autofde_lab.simulation.fortune5_safe.dfcm import (
    _diversity,
    _dominates,
    _is_feasible,
)
from autofde_lab.simulation.fortune5_safe.engine import run_episode
from autofde_lab.simulation.fortune5_safe.model import (
    EnterpriseTopology,
    EpisodeMetrics,
    Fortune5Config,
    PolicyAggregate,
    Scenario,
    SimulationReceipt,
    stable_digest,
)
from autofde_lab.simulation.fortune5_safe.topology import build_topology

from .catalog import Catalog, Strategy, load_catalog
from .opponent import Opponent, OpponentMove
from .world import World

RECEIPT_SCHEMA = "autofde-lab.simulation.doctrine-lab/v1"
EVIDENCE_CEILING = "REPO_LOCAL_FIXTURE"
DEFAULT_ROUNDS = 3
# The unmodified Fortune-5 default organization; only the seed varies per episode.
LAB_CONFIG = Fortune5Config()


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    """Wilson score interval for k successes in n trials (None when n == 0)."""
    if n <= 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 12), round(min(1.0, centre + half), 12))


@lru_cache(maxsize=4)
def _topology(config: Fortune5Config) -> EnterpriseTopology:
    return build_topology(config)


def topology_for(config: Fortune5Config) -> EnterpriseTopology:
    return _topology(replace(config, seed=0))


@dataclass(frozen=True)
class RoundRecord:
    round: int
    move: OpponentMove
    scenario: Scenario
    receipt: SimulationReceipt
    metrics: EpisodeMetrics


@dataclass(frozen=True)
class DoctrineReceipt:
    schema: str
    authority: str
    authority_ceiling: str
    standing: str
    evidence_ceiling: str
    catalog_sha256: str
    strategy_ordinal: int
    strategy_signature: str
    policy_digest: str
    world_id: str
    seed: int
    rounds: int
    round_replay_digests: tuple[str, ...]
    opponent_digest: str
    outcome_digest: str
    episode_digest: str


@dataclass(frozen=True)
class EpisodeRecord:
    seed: int
    strategy: Strategy
    world: World
    rounds: tuple[RoundRecord, ...]
    aggregate: PolicyAggregate
    receipt: DoctrineReceipt

    @property
    def id(self) -> str:
        return f"{self.strategy.id}@{self.world.id}#s{self.seed}"


@dataclass(frozen=True)
class Cell:
    strategy_id: str
    world_id: str
    n: int
    k_feasible: int
    wilson95: tuple[float, float] | None
    aggregate: PolicyAggregate


@dataclass(frozen=True)
class DoctrineMatrixResult:
    catalog_sha256: str
    seeds: tuple[int, ...]
    world_ids: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    rounds: int
    episodes: tuple[EpisodeRecord, ...]
    cells: tuple[Cell, ...]
    frontiers: tuple[tuple[str, tuple[str, ...]], ...]
    frontier_diversity: tuple[tuple[str, float], ...]
    matrix_digest: str


def _aggregate(
    strategy: Strategy, metrics: Sequence[EpisodeMetrics]
) -> PolicyAggregate:
    provisional = PolicyAggregate(
        strategy.policy,
        False,
        len(metrics),
        fmean(m.throughput for m in metrics),
        fmean(m.business_value for m in metrics),
        fmean(m.predictability for m in metrics),
        min(m.reliability for m in metrics),
        max(m.compliance_risk for m in metrics),
        fmean(m.lead_time_days for m in metrics),
        fmean(m.coordination_overhead for m in metrics),
        fmean(m.budget_variance for m in metrics),
        max(m.employee_load for m in metrics),
    )
    return replace(provisional, feasible=_is_feasible(provisional))


def run_strategy_episode(
    seed: int,
    strategy: Strategy,
    world: World,
    *,
    catalog_sha256: str,
    config: Fortune5Config = LAB_CONFIG,
    rounds: int = DEFAULT_ROUNDS,
) -> EpisodeRecord:
    if rounds < 1:
        raise ValueError("rounds must be positive")
    episode_config = replace(config, seed=seed)
    topology = topology_for(config)
    policy = strategy.policy
    opponent = Opponent(seed, strategy.signature, world, concealed=strategy.concealed)
    scenario = world.to_scenario()
    records: list[RoundRecord] = []
    for index in range(1, rounds + 1):
        scenario, move = opponent.respond(index, policy, scenario)
        result = run_episode(policy, scenario, episode_config, topology)
        records.append(
            RoundRecord(index, move, scenario, result.receipt, result.metrics)
        )
    aggregate = _aggregate(strategy, [r.metrics for r in records])
    replay_digests = tuple(r.receipt.replay_digest for r in records)
    opponent_digest = stable_digest([r.move for r in records])
    outcome_digest = stable_digest(
        {
            "policy": policy.digest,
            "world": world.id,
            "seed": seed,
            "rounds": replay_digests,
            "opponent": opponent_digest,
        }
    )
    body = {
        "catalog": catalog_sha256,
        "ordinal": strategy.ordinal,
        "signature": strategy.signature,
        "outcome": outcome_digest,
    }
    receipt = DoctrineReceipt(
        RECEIPT_SCHEMA,
        "NONE",
        "CONSTRUCT",
        "MODEL_EXECUTED",
        EVIDENCE_CEILING,
        catalog_sha256,
        strategy.ordinal,
        strategy.signature,
        policy.digest,
        world.id,
        seed,
        rounds,
        replay_digests,
        opponent_digest,
        outcome_digest,
        stable_digest(body),
    )
    return EpisodeRecord(seed, strategy, world, tuple(records), aggregate, receipt)


def _frontier(cells: Sequence[Cell]) -> tuple[str, ...]:
    feasible = [c for c in cells if c.aggregate.feasible]
    return tuple(
        sorted(
            c.strategy_id
            for c in feasible
            if not any(
                o.strategy_id != c.strategy_id and _dominates(o.aggregate, c.aggregate)
                for o in feasible
            )
        )
    )


def run_doctrine_matrix(
    seeds: Sequence[int],
    worlds: Sequence[World],
    strategies: Sequence[Strategy] | None = None,
    *,
    catalog: Catalog | None = None,
    config: Fortune5Config = LAB_CONFIG,
    rounds: int = DEFAULT_ROUNDS,
) -> DoctrineMatrixResult:
    catalog = catalog or load_catalog()
    strategy_space = tuple(strategies or catalog.operationalized)
    if not seeds or not worlds or not strategy_space:
        raise ValueError("seeds, worlds and strategies must be non-empty")
    if any(s.status != "operationalized" for s in strategy_space):
        raise ValueError("stub strategies have no primitive composition to run")
    episodes: list[EpisodeRecord] = []
    cells: list[Cell] = []
    frontiers: list[tuple[str, tuple[str, ...]]] = []
    diversity: list[tuple[str, float]] = []
    for world in worlds:
        world_cells: list[Cell] = []
        for strategy in strategy_space:
            per_seed = [
                run_strategy_episode(
                    seed,
                    strategy,
                    world,
                    catalog_sha256=catalog.sha256,
                    config=config,
                    rounds=rounds,
                )
                for seed in seeds
            ]
            episodes.extend(per_seed)
            k = sum(e.aggregate.feasible for e in per_seed)
            pooled = _aggregate(
                strategy, [r.metrics for e in per_seed for r in e.rounds]
            )
            cell = Cell(
                strategy.id,
                world.id,
                len(per_seed),
                k,
                wilson(k, len(per_seed)),
                pooled,
            )
            world_cells.append(cell)
        cells.extend(world_cells)
        front = _frontier(world_cells)
        frontiers.append((world.id, front))
        by_id = {s.id: s for s in strategy_space}
        diversity.append(
            (world.id, round(_diversity([by_id[i].policy for i in front]), 12))
        )
    matrix_digest = stable_digest(
        {
            "catalog": catalog.sha256,
            "seeds": list(seeds),
            "worlds": [w.id for w in worlds],
            "strategies": [s.id for s in strategy_space],
            "rounds": rounds,
            "episodes": [e.receipt.episode_digest for e in episodes],
            "frontiers": frontiers,
        }
    )
    return DoctrineMatrixResult(
        catalog.sha256,
        tuple(seeds),
        tuple(w.id for w in worlds),
        tuple(s.id for s in strategy_space),
        rounds,
        tuple(episodes),
        tuple(cells),
        tuple(frontiers),
        tuple(diversity),
        matrix_digest,
    )
