# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `togaf_loop_demo`.

Real collaborators throughout: a real POWL `ChoiceGraph` execution, a real
hand-built `OcelLog`, and a real call into
`object_centric_conformance.check_object_centric_conformance` (a module
built and tested in a prior turn, exercised here against this turn's
freshly-produced log). No `unittest.mock` / `Mock` / `MagicMock` / `patch`
/ `monkeypatch` anywhere in this file.
"""

from __future__ import annotations

from autofde_lab.reasoning.togaf_loop_demo import PHASE_SEQUENCE, run_full_togaf_loop_with_ocel


def test_all_ten_real_phases_fire_in_the_real_intended_order() -> None:
    log, phase_results, conformance = run_full_togaf_loop_with_ocel()

    assert len(log.events) == 10
    assert conformance.all_conform is True
    assert conformance.overall_fitness == 1.0

    execution_object = next(o for o in conformance.per_object if o.object_type == "TogafLoopExecution")
    assert execution_object.observed_trace == PHASE_SEQUENCE


def test_phase_d_is_a_real_explicit_refusal_never_a_fabricated_technology_decision() -> None:
    """The one place this module must stay honest: Phase D belongs to
    gymact, not this repo. Confirm the real recorded result names the
    refusal explicitly, rather than silently proceeding as if a real
    technology-architecture decision had been made."""
    _, phase_results, _ = run_full_togaf_loop_with_ocel()

    phase_d = phase_results["phase_d_delegated_to_gymact_boundary_refusal"]
    assert phase_d["refused"] is True
    assert phase_d["delegated_to"] == "gymact"
    assert "technology-architecture" in phase_d["reason"]


def test_every_phase_produced_a_real_nonempty_computed_result() -> None:
    """Not just 'an event fired' -- each phase's atom_invoker must have
    actually computed something real, not a placeholder."""
    _, phase_results, _ = run_full_togaf_loop_with_ocel()

    for label in PHASE_SEQUENCE:
        assert label in phase_results, f"{label} produced no real result"
        assert phase_results[label], f"{label}'s real result was empty"


def test_phase_e_delta_and_candidate_match_the_real_deterministic_orchestrator() -> None:
    """Cross-check against the real world_transformation_orchestrator
    functions directly -- this module's Phase E must not silently drift
    from the already-tested rule-based selector."""
    from autofde_lab.reasoning.scenarios.world_transformation_scenarios import (
        ScenarioMetadata_checkout_latency_scenario_v_1,
    )
    from autofde_lab.reasoning.world_transformation_orchestrator import (
        compute_delta,
        infer_desired_state,
        select_transformation,
    )

    metadata = ScenarioMetadata_checkout_latency_scenario_v_1()
    expected_delta = compute_delta(metadata, infer_desired_state(metadata))
    expected_candidate = select_transformation(expected_delta)

    _, phase_results, _ = run_full_togaf_loop_with_ocel()
    phase_e = phase_results["phase_e_compute_delta_and_select_transformation"]

    assert phase_e["delta_item_count"] == len(expected_delta)
    assert phase_e["candidate_label"] == expected_candidate.label


def test_the_conformance_verdict_is_computed_by_the_real_independent_module_not_reimplemented_here() -> None:
    """Confirm togaf_loop_demo imports and calls the real
    check_object_centric_conformance rather than reimplementing its own
    scoring -- a structural, no-dual-bookkeeping check."""
    import autofde_lab.reasoning.togaf_loop_demo as module

    assert module.check_object_centric_conformance.__module__ == "autofde_lab.ocel.object_centric_conformance"
