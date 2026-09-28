"""Integration checkpoint: the PTD court over real manifests (fixtures/), no mocks.

Scope: composes ptd.metrics, fabric.canonical, ocel.OcelLog, scipy. It establishes the
court's verdicts on the fixtures; it says nothing about a real defended system.
"""
import copy
import json
import math
from pathlib import Path

import pytest

from autofde_lab.ptd_exp.court import evaluate_experiment
from autofde_lab.ptd_exp.models import AttackObservation

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


def verdict(name):
    return evaluate_experiment(load(name))["rows"][0]


def test_strong_phase_passes_with_measured_depreciation():
    r = verdict("strong_phase")
    assert r["status"] == "PASS" and r["falsifiers"] == []
    m = r["metrics"]
    assert m["retention"] == 0.25 and m["depreciation"] == 0.75
    assert m["regeneration_advantage"] == 4.0 and m["common_mode"] == 0.0


def test_zero_transfer_is_full_depreciation():
    assert verdict("zero_transfer")["metrics"]["depreciation"] == 1.0


def test_retention_boundary_is_inclusive():
    r = verdict("boundary_retention")
    assert r["metrics"]["retention"] == 0.5 and r["status"] == "PASS"


@pytest.mark.parametrize("name,falsifier", [
    ("high_retention", "churn_without_depreciation"),
    ("bad_economics", "regeneration_advantage_too_low"),
    ("common_mode", "common_mode_persisted"),
    ("common_mode", "critical_fact_persisted"),
    ("authority_compromise", "persistent_authority_compromise"),
])
def test_negative_controls_are_falsified(name, falsifier):
    r = verdict(name)
    assert r["status"] == "FALSIFIED" and falsifier in r["falsifiers"]


def test_semantic_drift_is_refused_and_computes_no_metrics():
    r = verdict("semantic_drift")
    assert r["status"] == "REFUSED" and "semantic_drift" in r["refusals"]
    assert r["metrics"] is None


def test_churn_is_distinguished_from_unexplained_transfer():
    m = load("strong_phase")
    m["attacks"][0]["stale_performance"] = 4.4  # performance transfers, but no fact overlap
    assert "unexplained_transfer_channel" in evaluate_experiment(m)["rows"][0]["falsifiers"]


def test_unlisted_authority_is_refused():
    m = load("strong_phase")
    m["epochs"][1]["authority_id"] = "auth:rogue"
    r = evaluate_experiment(m)["rows"][0]
    assert r["status"] == "REFUSED" and "authority_refused:e2" in r["refusals"]


def test_cross_subject_epoch_is_refused():
    m = load("strong_phase")
    m["epochs"][1]["subject_id"] = "subject:other"
    assert "subject_mismatch" in evaluate_experiment(m)["rows"][0]["refusals"]


def test_unphased_realization_is_refused():
    m = load("strong_phase")
    m["epochs"][1]["realization_digest"] = "r1"
    assert "realization_did_not_phase" in evaluate_experiment(m)["rows"][0]["refusals"]


def test_nondeterministic_surface_is_reported_not_compared():
    m = load("common_mode")
    m["epochs"][0]["nondeterministic"] = ["a", "b", "c"]
    m["epochs"][1]["nondeterministic"] = ["a", "b", "c"]
    r = evaluate_experiment(m)["rows"][0]
    assert r["nondeterministic_surfaces"] == ["a", "b", "c"]
    assert r["metrics"]["common_mode"] == 0.0 and r["status"] == "PASS"


@pytest.mark.parametrize("field", ["stale_performance", "realignment_cost", "realignment_time"])
def test_nan_and_negative_observations_never_reach_metrics(field):
    for bad in (math.nan, -1.0):
        m = load("strong_phase")
        m["attacks"][0][field] = bad
        with pytest.raises(ValueError):
            evaluate_experiment(m)


def test_attack_referencing_unknown_epoch_is_an_error():
    m = load("strong_phase")
    m["attacks"][0]["target_epoch"] = "nope"
    with pytest.raises(ValueError):
        evaluate_experiment(m)


def _three_epoch_campaign():
    m = load("strong_phase")
    e3 = copy.deepcopy(m["epochs"][1])
    e3.update(epoch_id="e3", realization_digest="r3", surface=["p", "q", "r", "s"], critical=["p"])
    m["epochs"].append(e3)
    a2 = copy.deepcopy(m["attacks"][0])
    a2.update(task_id="t2", source_epoch="e2", target_epoch="e3", stale_performance=1.6, stale_facts=["w", "x", "y", "z"])
    m["attacks"].append(a2)
    return m


def test_multi_epoch_campaign_has_a_t_band_and_budget():
    m = _three_epoch_campaign()
    m["criteria"]["budget"] = 4
    c = evaluate_experiment(m)["campaign"]
    assert c["pass_count"] == 2 and c["all_pass"]
    lo, hi = c["retention_band_95"]
    assert lo < c["mean_retention"] < hi
    assert c["budget"] == {"funded_phases": 2, "required_phases": 2, "exhausted": False}


def test_budget_exhaustion_fails_the_campaign():
    m = _three_epoch_campaign()
    m["criteria"]["budget"] = 3
    c = evaluate_experiment(m)["campaign"]
    assert c["budget"]["exhausted"] and not c["all_pass"]


def test_single_sample_has_unknown_band_not_a_fabricated_one():
    assert evaluate_experiment(load("strong_phase"))["campaign"]["retention_band_95"] is None


def test_replay_is_byte_deterministic_and_bound_to_manifest():
    m = load("strong_phase")
    a, b = evaluate_experiment(m), evaluate_experiment(json.loads(json.dumps(m)))
    assert a == b and a["report_sha256"] == b["report_sha256"]
    m["attacks"][0]["realignment_cost"] = 9
    c = evaluate_experiment(m)
    assert c["manifest_sha256"] != a["manifest_sha256"] and c["report_sha256"] != a["report_sha256"]


def test_organizational_standing_is_never_claimed():
    s = evaluate_experiment(load("strong_phase"))["standing"]
    assert s["organizationalStanding"] == "UNKNOWN"


def test_ocel_projection_is_valid_and_carries_attack_status():
    from autofde_lab.ocel import OcelLog
    from autofde_lab.ptd_exp.ocel import project_ocel

    log = project_ocel("s", "x", ["e1", "e2"], [{"task_id": "t", "source_epoch": "e1", "target_epoch": "e2", "status": "PASS"}])
    assert isinstance(log, OcelLog) and len(log.events) == 3
    assert log.digest() == project_ocel("s", "x", ["e1", "e2"], [{"task_id": "t", "source_epoch": "e1", "target_epoch": "e2", "status": "PASS"}]).digest()
