"""Evidence checkpoints for worldgen sampling, doctrine injection, and the
outcome-row matrix (lane W8, RESOLUTIONS #7 schema).

These are repo-local model-execution tests over the same non-actuating
Fortune-5 engine; no evidence about real enterprises or real actuation.

Anti-vacuity witness (clamp mutation, measured live on this exact tree,
fb87a617 + lane W8 edits, pytest exit codes witnessed):

1. First mutation — deleting only the explicit `min(1.0, max(0.0, ...))` clamp
   line in `resolve` (src/autofde_lab/simulation/fortune5_safe/model.py) —
   did NOT fail this test (exit 0, 1 passed): nearest-legal argmin saturates
   intrinsically, so the standalone clamp was a zero-bit check. It was
   removed; the clamp semantics now live solely in the argmin saturation
   (weights <= 0.0 => lowest-score enum, >= 1.0 => highest-score enum).
2. Re-aimed mutation — replacing the saturating argmin with raw-weight index
   arithmetic (`members[round(raw_weight * (len - 1))]`, out-of-enum weights
   flowing through as indices) — FAILED exactly one test::

    src/autofde_lab/simulation/fortune5_safe/model.py:416: IndexError
    E           IndexError: list index out of range
    FAILED tests/simulation/test_worldgen_doctrine.py::test_resolve_clamps_out_of_enum_weights_to_nearest_legal_endpoint

   The mutation was restored and the full lane suite re-run green (19 passed).
   A resolve that lets out-of-enum weights through un-saturated is exactly
   the vacuum this test pins shut.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autofde_lab.simulation.fortune5_safe.dfcm import (
    boundary_report,
    claims_robustness,
    first_violated_constraint,
    kill_doctrines,
    run_outcome_matrix,
)
from autofde_lab.simulation.fortune5_safe.engine import replay, run_episode
from autofde_lab.simulation.fortune5_safe.model import (
    AUTOFDE_BASE_SHA,
    DoctrineSpec,
    Fortune5Config,
    PolicyVector,
    Scenario,
    ScenarioName,
    resolve,
)
from autofde_lab.simulation.fortune5_safe.space import SCENARIOS
from autofde_lab.simulation.fortune5_safe.worldgen import WORLD_RANGES, WorldSample, sample_worlds

OUTCOME_ROW_KEYS = {
    "backend",
    "doctrine_id",
    "world_id",
    "seed",
    "metrics",
    "feasible",
    "receipt_digests",
}


def _rigged_doctrine() -> DoctrineSpec:
    # Resolves (measured) to architecture_first / option_reserve /
    # innovation_reserve / event_driven / platform_first / compliance_first
    # and is infeasible (employee_load) on the baseline scenario.
    return DoctrineSpec(
        id="doct-rigged",
        text="robust against every disruption",
        weights={
            "priority": 1.0,
            "funding": 1.0,
            "capacity": 1.0,
            "cadence": 1.0,
            "architecture": 1.0,
            "risk": 0.0,
        },
    )


def _mid_doctrine(claim: bool) -> DoctrineSpec:
    return DoctrineSpec(
        id="doct-mid-claimed" if claim else "doct-mid-quiet",
        text="steady mid-axis strategy" + (" that is robust" if claim else ""),
        weights={},
    )


def test_world_sampler_is_byte_identical_for_same_seed():
    left = sample_worlds(7, 5)
    right = sample_worlds(7, 5)

    assert left == right
    assert [world.world_id for world in left] == [world.world_id for world in right]
    assert [world.digest for world in left] == [world.digest for world in right]


def test_world_sampler_changes_with_seed_and_is_hashable():
    worlds = sample_worlds(1, 4)
    other = sample_worlds(2, 4)

    assert worlds != other
    assert len({*worlds, *other}) == 8  # frozen dataclasses are hashable
    assert len({world.world_id for world in worlds}) == 4  # content-addressed


def test_world_samples_stay_inside_documented_ranges():
    for world in sample_worlds(2030, 40):
        for field, (low, high) in WORLD_RANGES.items():
            value = getattr(world, field)
            assert low <= value <= high, (field, value)


def test_resolve_is_deterministic_and_nearest_legal():
    doctrine = DoctrineSpec(
        id="d",
        text="",
        weights={"priority": 0.26, "risk": 0.9, "cadence": 0.1},
    )

    first = resolve(doctrine)
    second = resolve(doctrine)

    assert first == second  # pure function of weights/overrides
    assert isinstance(first, PolicyVector)
    assert first.priority.value == "cost_of_delay"  # |0.26 - 0.25| nearest
    assert first.risk.value == "fast_feedback"  # 0.9 nearest 1.0
    assert first.cadence.value == "synchronized"  # 0.1 nearest 0.0
    # Exact float tie (0.375 between 0.25 and 0.5) breaks to the lower score.
    assert resolve(
        DoctrineSpec(id="t", text="", weights={"priority": 0.375})
    ).priority.value == "cost_of_delay"
    # Missing axes default to the 0.5 midpoint; on the 4-value capacity axis
    # the float distances to 1/3 vs 2/3 are asymmetric, landing on
    # reliability_reserve (measured, deterministic).
    assert resolve(DoctrineSpec(id="m", text="", weights={})).capacity.value == (
        "reliability_reserve"
    )


def test_resolve_clamps_out_of_enum_weights_to_nearest_legal_endpoint():
    low = DoctrineSpec(id="c1", text="", weights={"priority": -3.0})
    zero = DoctrineSpec(id="c2", text="", weights={"priority": 0.0})
    high = DoctrineSpec(id="c3", text="", weights={"priority": 7.0})
    one = DoctrineSpec(id="c4", text="", weights={"priority": 1.0})

    assert resolve(low) == resolve(zero)
    assert resolve(high) == resolve(one)


def test_resolve_overrides_beat_weights_and_illegal_values_are_refused():
    doctrine = DoctrineSpec(
        id="o",
        text="",
        weights={"risk": 0.0},
        rule_overrides={"risk": "fast_feedback"},
    )
    assert resolve(doctrine).risk.value == "fast_feedback"

    with pytest.raises(ValueError):
        resolve(
            DoctrineSpec(id="b1", text="", rule_overrides={"tenor": "fast_feedback"})
        )
    with pytest.raises(ValueError):
        resolve(
            DoctrineSpec(id="b2", text="", rule_overrides={"risk": "not_a_rule"})
        )
    with pytest.raises(ValueError):
        resolve(DoctrineSpec(id="b3", text="", weights={"priority": float("nan")}))


def test_non_axis_weights_are_doctrine_metadata_not_rule_inputs():
    plain = DoctrineSpec(id="p", text="", weights={})
    claimed = DoctrineSpec(id="c", text="", weights={"robustness": 0.9})

    assert resolve(plain) == resolve(claimed)  # ignored by resolve
    assert plain.digest != claimed.digest  # but digest-able doctrine metadata
    assert claims_robustness(claimed)
    assert not claims_robustness(plain)


def test_run_outcome_matrix_tiny_grid_matches_pinned_row_schema_and_ndjson():
    doctrines = [_mid_doctrine(False), _rigged_doctrine()]
    worlds = [SCENARIOS[0], sample_worlds(11, 1)[0]]
    config = Fortune5Config(seed=9)

    rows = run_outcome_matrix(doctrines, worlds, [2, 1], config)

    assert len(rows) == 2 * 2 * 2
    assert [row["seed"] for row in rows] == [1, 2] * 4  # seeds sorted ascending
    assert [row["doctrine_id"] for row in rows] == [
        "doct-mid-quiet",
        "doct-mid-quiet",
        "doct-mid-quiet",
        "doct-mid-quiet",
        "doct-rigged",
        "doct-rigged",
        "doct-rigged",
        "doct-rigged",
    ]
    for row in rows:
        assert set(row) == OUTCOME_ROW_KEYS  # RESOLUTIONS #7, nothing extra
        assert row["backend"] == f"fortune5_safe@{AUTOFDE_BASE_SHA[:12]}"
        assert isinstance(row["world_id"], str)
        assert isinstance(row["seed"], int)
        assert isinstance(row["metrics"], dict) and row["metrics"]
        assert row["feasible"] == (first_violated_constraint(row["metrics"]) is None)
        assert len(row["receipt_digests"]) == 1

    with pytest.raises(ValueError):
        run_outcome_matrix([], worlds, [1], config)
    with pytest.raises(ValueError):
        run_outcome_matrix(doctrines, [], [1], config)
    with pytest.raises(ValueError):
        run_outcome_matrix(doctrines, worlds, [], config)


def test_run_outcome_matrix_ndjson_roundtrip_is_byte_identical(tmp_path: Path):
    doctrines = [_mid_doctrine(False), _rigged_doctrine()]
    worlds = [SCENARIOS[0], sample_worlds(11, 1)[0]]
    config = Fortune5Config(seed=9)
    path = tmp_path / "nested" / "outcome_rows.ndjson"

    rows = run_outcome_matrix(doctrines, worlds, [2, 1], config, output_path=path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == len(rows) == 8
    assert [json.loads(line) for line in lines] == list(rows)  # exact roundtrip
    run_outcome_matrix(doctrines, worlds, [2, 1], config, output_path=path)
    again = path.read_text(encoding="utf-8").splitlines()
    assert again == lines  # deterministic order => byte-identical file


def test_boundary_report_reports_infeasible_doctrine_and_feasible_doctrine():
    doctrines = [_rigged_doctrine(), _mid_doctrine(False)]
    worlds = [SCENARIOS[0]]
    rows = run_outcome_matrix(doctrines, worlds, [1, 2], Fortune5Config(seed=9))

    report = {entry["doctrine_id"]: entry for entry in boundary_report(rows)}

    assert report["doct-rigged"]["infeasible_world_ids"] == ("baseline",)
    # Measured: the rigged mapping (option_reserve funding + extreme axes)
    # breaches the pinned employee_load ceiling first on baseline.
    assert report["doct-rigged"]["first_violated_constraint"] == "employee_load"
    assert report["doct-mid-quiet"]["infeasible_world_ids"] == ()
    assert report["doct-mid-quiet"]["first_violated_constraint"] is None


def test_worldsample_episodes_replay_and_new_axes_change_consequence():
    config = Fortune5Config(seed=42)
    policy = resolve(_mid_doctrine(False))
    world = sample_worlds(7, 1)[0]

    episode = run_episode(policy, world, config)
    assert replay(episode, config)
    # Neutral-axis world still differs from any Scenario (distinct RNG label).
    baseline_episode = run_episode(policy, SCENARIOS[0], config)
    assert episode.receipt.scenario == world.world_id
    assert episode.receipt.replay_digest != baseline_episode.receipt.replay_digest
    # New axes carry consequence, not decoration.
    jittered = run_episode(
        policy,
        WorldSample(timing_jitter=0.10, volatility=0.25),
        config,
    )
    calm = run_episode(policy, WorldSample(), config)
    assert jittered.receipt.replay_digest != calm.receipt.replay_digest
    assert jittered.metrics.lead_time_days != calm.metrics.lead_time_days


def test_kill_doctrines_kills_rigged_claimant_and_spares_the_rest():
    config = Fortune5Config(seed=9)
    rigged = _rigged_doctrine()
    claimed = _mid_doctrine(claim=True)
    quiet = _mid_doctrine(claim=False)

    verdicts = {
        verdict["doctrine_id"]: verdict
        for verdict in kill_doctrines(
            [rigged, claimed, quiet], [WorldSample()], [1, 2], config=config
        )
    }

    # Claimed robust, infeasible on baseline for some seed => killed.
    assert verdicts["doct-rigged"]["claims_robustness"] is True
    assert verdicts["doct-rigged"]["baseline_feasible"] is False
    assert verdicts["doct-rigged"]["killed"] is True
    assert verdicts["doct-rigged"]["reason"] == "infeasible_on_baseline"
    # Claims robust, feasible everywhere it was run => claim survives.
    assert verdicts["doct-mid-claimed"]["claims_robustness"] is True
    assert verdicts["doct-mid-claimed"]["killed"] is False
    assert verdicts["doct-mid-claimed"]["reason"] == "claim_survives"
    # Never claimed robustness => never killed, however badly it performs.
    assert verdicts["doct-mid-quiet"]["claims_robustness"] is False
    assert verdicts["doct-mid-quiet"]["killed"] is False
    assert verdicts["doct-mid-quiet"]["reason"] == "no_robustness_claim"


def test_scenario_path_replay_equality_survives_worldgen_changes():
    # Tripwire for the strategy-injection edge: the pre-existing Scenario fast
    # path must stay byte-identical (receipt == receipt) after the WorldSample
    # overload landed.
    config = Fortune5Config(seed=42)
    from autofde_lab.simulation.fortune5_safe.space import all_policies

    policy = all_policies()[0]
    episode = run_episode(policy, SCENARIOS[0], config)
    disruption = run_episode(policy, SCENARIOS[-1], config)

    assert replay(episode, config)
    assert episode.receipt.scenario == ScenarioName.BASELINE.value
    assert episode.receipt.output_digest != disruption.receipt.output_digest
