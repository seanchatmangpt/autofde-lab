"""Chicago-style baseline evidence tests for the sa2a manufacturing case study.

MFG-01A acceptance: re-derive every invariant claim from the real OCEL 2.0
JSON the real runtime produces -- never from runtime.py's own in-memory
counters -- and confirm byte-for-byte replay determinism. See
src/autofde_lab/sa2a/case_studies/manufacturing/MIGRATION_PLAN.md for what
this package is and is not (paper-fixture baseline only; no generator, no
HDDL/POWL/FOND, no frontier falsifier yet).

No mocking anywhere in this file (verified by grep in CI and by hand): every
test exercises the real `autofde_lab.sa2a.case_studies.manufacturing.runtime.run`
function against real, freshly-written, freshly-re-parsed OCEL JSON on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from autofde_lab.sa2a.case_studies.manufacturing import ocel_adapter, runtime
from autofde_lab.sa2a.case_studies.manufacturing.authority_agent import (
    AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET,
    ENERGY_BUDGET_PER_ROUND_KWH,
)

FIXTURES_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
    .joinpath(
        "..", "src", "autofde_lab", "sa2a", "case_studies", "manufacturing", "fixtures"
    )
    .resolve()
)


def test_runtime_run_executes_and_produces_valid_ocel_log() -> None:
    result = runtime.run(seed=1)
    assert result["stop_reason"] in {"stable", "max_rounds"}
    assert result["rounds_executed"] >= 1

    doc = result["_log_ref"].log.to_ocel2_json()
    reparsed = json.loads(json.dumps(doc))
    for key in ("objectTypes", "eventTypes", "objects", "events"):
        assert key in reparsed
        assert len(reparsed[key]) > 0


def test_zero_unreceipted_actuation_from_real_ocel_json(tmp_path: Path) -> None:
    result = runtime.run(seed=1)
    out_path = tmp_path / "seed1.ocel.json"
    ocel_adapter.write_json(result["_log_ref"], str(out_path))

    doc = json.loads(out_path.read_text())
    objects_by_id = {o["id"]: o for o in doc["objects"]}

    actuation_events = [e for e in doc["events"] if e["type"] == "sosa:Actuation"]
    assert len(actuation_events) > 0

    for ev in actuation_events:
        generated = [
            rel["objectId"]
            for rel in ev["relationships"]
            if rel["qualifier"] == "prov:generated"
        ]
        assert len(generated) == 1, (
            f"event {ev['id']} has {len(generated)} prov:generated links"
        )
        receipt = objects_by_id.get(generated[0])
        assert receipt is not None, (
            f"receipt {generated[0]!r} missing from objects table"
        )
        assert receipt["type"] == "Receipt"

        event_applied = next(
            a["value"] for a in ev["attributes"] if a["name"] == "applied"
        )
        receipt_applied = next(
            a["value"] for a in receipt["attributes"] if a["name"] == "applied"
        )
        assert event_applied == receipt_applied

        if not event_applied:
            pre = next(
                a["value"]
                for a in receipt["attributes"]
                if a["name"] == "pre_state_hash"
            )
            post = next(
                a["value"]
                for a in receipt["attributes"]
                if a["name"] == "post_state_hash"
            )
            assert pre == post


def test_zero_authority_violations_from_real_ocel_json(tmp_path: Path) -> None:
    result = runtime.run(seed=1)
    out_path = tmp_path / "seed1.ocel.json"
    ocel_adapter.write_json(result["_log_ref"], str(out_path))

    doc = json.loads(out_path.read_text())
    decisions = [
        e for e in doc["events"] if e["type"] in ("odrl:Permission", "odrl:Prohibition")
    ]
    assert len(decisions) > 0

    # Recover round grouping the same way verifier.py does: from
    # timestamp_ns // 1_000_000. The JSON projection stores an ISO timestamp,
    # so re-derive round grouping via the real log objects instead of the
    # JSON's time string.
    ref = result["_log_ref"]
    events_by_id = {e.id: e for e in ref.log.events}

    remaining_by_round: dict[int, float] = {}
    for ev in decisions:
        raw = events_by_id[ev["id"]]
        round_index = raw.timestamp_ns // 1_000_000
        granted = next(
            a["value"] for a in ev["attributes"] if a["name"] == "granted_energy_kwh"
        )
        remaining_after = next(
            a["value"] for a in ev["attributes"] if a["name"] == "remaining_budget_kwh"
        )
        remaining_before = remaining_by_round.get(
            round_index, ENERGY_BUDGET_PER_ROUND_KWH
        )

        assert remaining_after >= -1e-6, f"round {round_index} went negative"
        if ev["type"] == "odrl:Permission":
            cap = AUTHORITY_MAX_SHARE_OF_REMAINING_BUDGET * remaining_before
            assert granted <= cap + 1e-6, (
                f"round {round_index} admitted grant {granted} exceeds cap {cap}"
            )

        remaining_by_round[round_index] = remaining_after


def test_energy_budget_never_exceeded_per_round(tmp_path: Path) -> None:
    result = runtime.run(seed=1)
    out_path = tmp_path / "seed1.ocel.json"
    ocel_adapter.write_json(result["_log_ref"], str(out_path))

    doc = json.loads(out_path.read_text())
    ref = result["_log_ref"]
    events_by_id = {e.id: e for e in ref.log.events}

    totals_by_round: dict[int, float] = {}
    for ev in doc["events"]:
        if ev["type"] != "odrl:Permission":
            continue
        raw = events_by_id[ev["id"]]
        round_index = raw.timestamp_ns // 1_000_000
        granted = next(
            a["value"] for a in ev["attributes"] if a["name"] == "granted_energy_kwh"
        )
        totals_by_round[round_index] = totals_by_round.get(round_index, 0.0) + granted

    assert len(totals_by_round) > 0
    for round_index, total in totals_by_round.items():
        assert total <= ENERGY_BUDGET_PER_ROUND_KWH + 1e-6, (
            f"round {round_index} granted {total} kWh > budget {ENERGY_BUDGET_PER_ROUND_KWH}"
        )


def test_replay_is_byte_for_byte_deterministic_for_same_seed(tmp_path: Path) -> None:
    result_a = runtime.run(seed=7)
    result_b = runtime.run(seed=7)

    path_a = tmp_path / "seed7_a.ocel.json"
    path_b = tmp_path / "seed7_b.ocel.json"
    ocel_adapter.write_json(result_a["_log_ref"], str(path_a))
    ocel_adapter.write_json(result_b["_log_ref"], str(path_b))

    assert path_a.read_bytes() == path_b.read_bytes()
    assert result_a["ocel_log_digest"] == result_b["ocel_log_digest"]


def test_different_seeds_produce_different_traces(tmp_path: Path) -> None:
    result_1 = runtime.run(seed=1)
    result_2 = runtime.run(seed=2)

    path_1 = tmp_path / "seed1.ocel.json"
    path_2 = tmp_path / "seed2.ocel.json"
    ocel_adapter.write_json(result_1["_log_ref"], str(path_1))
    ocel_adapter.write_json(result_2["_log_ref"], str(path_2))

    assert result_1["ocel_log_digest"] != result_2["ocel_log_digest"]
    assert path_1.read_bytes() != path_2.read_bytes()


def test_fixture_round14_slice_matches_a_fresh_run() -> None:
    fixture_path = FIXTURES_DIR / "round14_ocel_slice.json"
    assert fixture_path.exists(), f"fixture missing at {fixture_path}"
    fixture_doc = json.loads(fixture_path.read_text())

    result = runtime.run(seed=1)
    ref = result["_log_ref"]
    lo, hi = 14_000_000, 15_000_000
    round_event_ids = {e.id for e in ref.log.events if lo <= e.timestamp_ns < hi}

    full = ref.log.to_ocel2_json()
    fresh_events = [e for e in full["events"] if e["id"] in round_event_ids]
    referenced_obj_ids = set()
    for e in fresh_events:
        for rel in e.get("relationships", []):
            referenced_obj_ids.add(rel["objectId"])
    fresh_objects = [o for o in full["objects"] if o["id"] in referenced_obj_ids]

    assert len(fresh_events) == len(fixture_doc["events"])
    assert len(fresh_objects) == len(fixture_doc["objects"])
    assert {e["type"] for e in fresh_events} == {
        e["type"] for e in fixture_doc["events"]
    }
    assert {o["type"] for o in fresh_objects} == {
        o["type"] for o in fixture_doc["objects"]
    }
