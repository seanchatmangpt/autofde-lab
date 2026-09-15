# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style adversarial suite for the vendored bcinr-cmca bridge.

Validates that autofde-lab's default CMCA engine really delegates its
allocation measure to the vendored ``bcinr-cmca`` crate's
``cmca_rank_cli`` (Q16.16 fixed-point, compiled lens policy) -- and that
every failure mode fails closed with a typed refusal instead of silently
degrading to a local reimplementation.

Adversarial mutants proven:
1. Determinism/replay: identical inputs -> identical plan hashes; input
   order must not leak into the plan.
2. Cardinality: > 8 candidates is refused (compiled N=8 shape), never
   truncated.
3. Non-finite features (NaN/Inf) are refused before reaching the wire --
   clamping would fabricate a different candidate.
4. Absent transports: with every bcinr transport unavailable, the engine
   refuses with a typed ``BcinrCliUnavailable`` -- never a silent fallback
   to reference-softmax. (The CLI alone going missing no longer refuses:
   the WASM transport legitimately serves the engine.)
5. Mass/budget conservation holds through the full projection.
6. Provenance: the bridge's pin constant matches the vendored snapshot's
   recorded commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.cmca.bcinr_bridge import (
    VENDORED_BCINR_COMMIT,
    BcinrCardinalityRefusal,
    BcinrCliUnavailable,
    BcinrFeatureRefusal,
    find_bcinr_cli,
    rank_candidates,
    resolve_bcinr_cli,
)
from autofde_lab.cmca.bcinr_wasm import find_bcinr_wasm
from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import CandidateBranch, ResourceBudget

pytestmark = pytest.mark.skipif(
    find_bcinr_cli() is None and find_bcinr_wasm() is None,
    reason="no bcinr transport available -- build the wasm artifact "
    "(wasm/README.md) or the binary ('cargo build --release -p bcinr-cmca' "
    "inside vendor/bcinr)",
)


def _budget() -> ResourceBudget:
    return ResourceBudget(
        total_ticks=997,  # prime: discrete floor assignment cannot alias it
        memory_bytes=1_000_000,
        max_verification_depth=5,
        consequence_risk_budget=0.5,
        concurrency_lanes=4,
    )


def _candidates(n: int = 4) -> list[CandidateBranch]:
    return [
        CandidateBranch(
            branch_id=f"branch_{i}",
            operator_id=f"op_{i}",
            world_id="world_test",
            state_id=f"state_{i}",
            option_entropy=float(8 - i),
            estimated_cost=1.0 + i,
            historical_yield=1.5,
        )
        for i in range(n)
    ]


def test_bcinr_cli_resolves_and_is_vendored():
    """The bridge resolves a binary; the vendored build takes priority over
    any upstream checkout so the tested math is the pinned snapshot's."""
    binary = resolve_bcinr_cli()
    assert Path(binary).is_file()
    # When the vendored build exists it must win discovery.
    vendored = (
        Path(__file__).resolve().parents[2]
        / "vendor"
        / "bcinr"
        / "target"
        / "release"
        / "cmca_rank_cli"
    )
    if vendored.is_file():
        assert Path(binary) == vendored


def test_bcinr_rank_is_deterministic_and_input_order_independent():
    candidates = _candidates()
    ranking_a = rank_candidates(candidates)
    ranking_b = rank_candidates(list(reversed(candidates)))
    assert ranking_a == ranking_b
    # shares are renormalized over real candidates only
    assert sum(ranking_a.values()) == pytest.approx(1.0)
    assert set(ranking_a) == {c.branch_id for c in candidates}


def test_default_engine_replay_hash_is_stable_across_orderings():
    allocator = MultifractalCascadeAllocator()
    assert allocator.engine == "bcinr"
    plan_a = allocator.allocate(
        plan_id="replay", budget=_budget(), candidates=_candidates()
    )
    plan_b = allocator.allocate(
        plan_id="replay", budget=_budget(), candidates=list(reversed(_candidates()))
    )
    assert plan_a.plan_hash == plan_b.plan_hash


def test_default_engine_mass_and_budget_conservation():
    allocator = MultifractalCascadeAllocator()
    plan = allocator.allocate(
        plan_id="conservation", budget=_budget(), candidates=_candidates()
    )
    admitted = [a for a in plan.allocations if a.standing.value == "ADMITTED"]
    assert admitted, "anti-starvation fallback must keep at least one branch"
    assert sum(a.allocated_fraction for a in admitted) == pytest.approx(1.0)
    assert sum(a.allocated_ticks for a in plan.allocations) <= _budget().total_ticks
    assert (
        sum(a.allocated_memory_bytes for a in plan.allocations)
        <= _budget().memory_bytes
    )
    assert all(a.priority_lane < _budget().concurrency_lanes for a in plan.allocations)


def test_dominant_candidate_earns_dominant_share():
    """A candidate strictly dominating another on every measure axis must
    not receive a smaller share -- the compiled lens policy must not invert
    dominance."""
    dominant = CandidateBranch(
        branch_id="dominant",
        operator_id="op",
        world_id="w",
        state_id="s",
        option_entropy=10.0,
        estimated_cost=0.5,
        historical_yield=3.0,
    )
    dominated = CandidateBranch(
        branch_id="dominated",
        operator_id="op",
        world_id="w",
        state_id="s",
        option_entropy=1.0,
        estimated_cost=8.0,
        historical_yield=0.25,
    )
    ranking = rank_candidates([dominant, dominated])
    assert ranking["dominant"] > ranking["dominated"]


def test_cardinality_above_compiled_shape_is_refused_not_truncated():
    allocator = MultifractalCascadeAllocator()
    with pytest.raises(BcinrCardinalityRefusal, match="N=8"):
        allocator.allocate(
            plan_id="refuse", budget=_budget(), candidates=_candidates(9)
        )
    # exactly 8 is admissible
    plan = allocator.allocate(
        plan_id="eight", budget=_budget(), candidates=_candidates(8)
    )
    assert len(plan.allocations) == 8


def test_non_finite_features_refused_before_the_wire():
    for bad_entropy in (float("nan"), float("inf"), float("-inf")):
        poisoned = CandidateBranch(
            branch_id="poisoned",
            operator_id="op",
            world_id="w",
            state_id="s",
            option_entropy=bad_entropy,
            estimated_cost=1.0,
            historical_yield=1.0,
        )
        with pytest.raises(BcinrFeatureRefusal):
            rank_candidates([poisoned, *_candidates(2)])


def test_all_transports_unavailable_is_typed_refusal_not_silent_fallback(monkeypatch):
    """With discovery forced empty on every transport, the bcinr engine must
    refuse -- it may never quietly fall back to the reference-softmax
    engine. (CLI alone going missing is served by the WASM transport; that
    independence is pinned separately in
    test_bcinr_wasm_bridge.test_wasm_serves_rank_candidates_with_cli_unavailable.)"""
    monkeypatch.setattr("autofde_lab.cmca.bcinr_bridge.find_bcinr_cli", lambda: None)
    monkeypatch.delenv("BCINR_CMCA_CLI", raising=False)
    monkeypatch.setattr("autofde_lab.cmca.bcinr_wasm.find_bcinr_wasm", lambda: None)
    monkeypatch.delenv("BCINR_CMCA_WASM", raising=False)
    allocator = MultifractalCascadeAllocator()
    with pytest.raises(BcinrCliUnavailable, match="cargo build"):
        allocator.allocate(
            plan_id="unavailable", budget=_budget(), candidates=_candidates()
        )


def test_tau_is_refused_under_bcinr_engine_not_silently_ignored():
    allocator = MultifractalCascadeAllocator(default_tau=1.0)
    with pytest.raises(ValueError, match="tau"):
        allocator.allocate(
            plan_id="tau", budget=_budget(), candidates=_candidates(), tau=0.5
        )
    with pytest.raises(ValueError, match="tau"):
        MultifractalCascadeAllocator(default_tau=1.5)


def test_zero_cost_saturates_instead_of_dividing_by_zero():
    zero_cost = CandidateBranch(
        branch_id="zero_cost",
        operator_id="op",
        world_id="w",
        state_id="s",
        option_entropy=4.0,
        estimated_cost=0.0,
        historical_yield=1.0,
    )
    allocator = MultifractalCascadeAllocator()
    plan = allocator.allocate(
        plan_id="zero-cost", budget=_budget(), candidates=[zero_cost, *_candidates(2)]
    )
    assert any(a.standing.value == "ADMITTED" for a in plan.allocations)


def test_bridge_pin_matches_vendored_snapshot_record():
    """The in-code provenance constant must equal the pin recorded in
    vendor/bcinr/VENDORING.md -- drift means the bridge claims a commit it
    was not built against."""
    vendoring = (
        Path(__file__).resolve().parents[2] / "vendor" / "bcinr" / "VENDORING.md"
    ).read_text(encoding="utf-8")
    assert f"`{VENDORED_BCINR_COMMIT}`" in vendoring


def test_reference_engine_remains_selectable_and_replay_stable():
    """The local float engine stays available under its explicit name and
    keeps its own deterministic replay hash."""
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=1.0, pruning_threshold=0.01
    )
    plan_a = allocator.allocate(
        plan_id="ref", budget=_budget(), candidates=_candidates()
    )
    plan_b = allocator.allocate(
        plan_id="ref", budget=_budget(), candidates=list(reversed(_candidates()))
    )
    assert plan_a.plan_hash == plan_b.plan_hash
    assert plan_a.tau_temperature == 1.0
