"""Model-relative doctrine report: applicability, counter-dominance, equivalence.

Every statement here is about the fortune5_safe simulation model under the lab's
world projection. Evidence ceiling REPO_LOCAL_FIXTURE: nothing in it is a claim
about any real organization, market, or the source the catalog ordinals index.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from autofde_lab.simulation.fortune5_safe.model import stable_digest

from .catalog import Catalog
from .matrix import EVIDENCE_CEILING, DoctrineMatrixResult
from .relations import dominates
from .world import AXES, world_by_id

REPORT_SCHEMA = "autofde-lab.simulation.doctrine-lab.report/v1"
MODEL_RELATIVE = (
    "Results are relative to the autofde-lab fortune5_safe simulation model and the "
    "lab world projection only; they are not evidence about any real-world system."
)


def applicability_regions(result: DoctrineMatrixResult) -> dict[str, Any]:
    frontier = dict(result.frontiers)
    regions: dict[str, Any] = {}
    for strategy_id in result.strategy_ids:
        cells = [c for c in result.cells if c.strategy_id == strategy_id]
        applicable = sorted(
            c.world_id
            for c in cells
            if c.n and c.k_feasible == c.n and strategy_id in frontier[c.world_id]
        )
        marginals: dict[str, dict[str, float]] = {}
        for axis, enum in AXES:
            marginals[axis] = {}
            for value in enum:
                in_axis = [
                    c
                    for c in cells
                    if world_by_id(c.world_id).axis(axis) == value.value
                ]
                hit = sum(1 for c in in_axis if c.world_id in applicable)
                marginals[axis][value.value] = (
                    round(hit / len(in_axis), 12) if in_axis else None
                )
        regions[strategy_id] = {
            "applicable_world_count": len(applicable),
            "world_count": len(cells),
            "applicable_worlds": applicable,
            "axis_marginals": marginals,
            "feasible_wilson95": {
                c.world_id: list(c.wilson95) if c.wilson95 else None for c in cells
            },
        }
    return regions


def counter_dominance(result: DoctrineMatrixResult) -> dict[str, Any]:
    by_world: dict[str, dict[str, Any]] = defaultdict(dict)
    for cell in result.cells:
        by_world[cell.world_id][cell.strategy_id] = cell.aggregate
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for aggregates in by_world.values():
        for a in result.strategy_ids:
            for b in result.strategy_ids:
                if a != b and dominates(aggregates[a], aggregates[b]):
                    counts[(a, b)] += 1
    dominance = [
        {"dominant": a, "dominated": b, "worlds": n}
        for (a, b), n in sorted(counts.items())
    ]
    counters = [
        {"a": a, "b": b, "a_over_b_worlds": n, "b_over_a_worlds": counts[(b, a)]}
        for (a, b), n in sorted(counts.items())
        if a < b and counts.get((b, a), 0) > 0
    ]
    return {"dominance": dominance, "conditional_counters": counters}


def equivalence_clusters(
    result: DoctrineMatrixResult, catalog: Catalog
) -> list[dict[str, Any]]:
    outcomes: dict[str, list[str]] = defaultdict(list)
    for episode in result.episodes:
        outcomes[episode.strategy.id].append(episode.receipt.outcome_digest)
    groups: dict[str, list] = defaultdict(list)
    for strategy_id in result.strategy_ids:
        strategy = catalog.get(int(strategy_id.split("-")[1]))
        groups[strategy.policy.id].append(strategy)
    clusters = []
    for policy_id, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        signatures = sorted({m.signature for m in members})
        clusters.append(
            {
                "policy_id": policy_id,
                "members": [
                    {"strategy": m.id, "signature": m.signature} for m in members
                ],
                "collision": len(signatures) > 1,
                "behaviourally_identical": len({tuple(outcomes[m.id]) for m in members})
                == 1,
            }
        )
    return clusters


def report_body(report: dict[str, Any]) -> dict[str, Any]:
    """The digested part of a report (drops ``report_digest`` and the ledger anchor)."""
    return {k: v for k, v in report.items() if k not in ("report_digest", "ledger")}


def build_report(result: DoctrineMatrixResult, catalog: Catalog) -> dict[str, Any]:
    body = {
        "schema": REPORT_SCHEMA,
        "evidence_ceiling": EVIDENCE_CEILING,
        "model_relative": MODEL_RELATIVE,
        "authority": "NONE",
        "authority_ceiling": "CONSTRUCT",
        "selection": None,
        "catalog": {
            "sha256": catalog.sha256,
            "provenance": catalog.provenance,
            "non_claim": catalog.non_claim,
        },
        "seeds": list(result.seeds),
        "rounds": result.rounds,
        "world_count": len(result.world_ids),
        "world_ids": list(result.world_ids),
        "strategy_ids": list(result.strategy_ids),
        "episode_count": len(result.episodes),
        "matrix_digest": result.matrix_digest,
        "frontiers": {w: list(f) for w, f in result.frontiers},
        "frontier_diversity": dict(result.frontier_diversity),
        "applicability_regions": applicability_regions(result),
        "counter_dominance": counter_dominance(result),
        "primitive_equivalence_clusters": equivalence_clusters(result, catalog),
    }
    return {**body, "report_digest": stable_digest(body)}
