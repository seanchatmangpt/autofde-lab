"""Evidence checkpoints for the doctrine boundary lab.

Real collaborators only: the unmodified fortune5_safe engine, the aloop OCEL
Builder, the OcelLog parser/validator and the real ProvenanceLedger on disk.
Evidence ceiling REPO_LOCAL_FIXTURE: these tests certify determinism, integrity
and model-relative reporting, not any claim about a real-world system.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from autofde_lab.ocel import OcelLog
from autofde_lab.simulation.doctrine_lab import (
    ALL_WORLDS,
    CATALOG_SHA256,
    DUALS,
    PRIMITIVES,
    CatalogIntegrityError,
    build_report,
    episode_log,
    load_catalog,
    log_bytes,
    log_sha256,
    run_doctrine_matrix,
    run_lab,
    run_strategy_episode,
    seal_episodes,
    verify_ledger,
    wilson,
    world_by_id,
)
from autofde_lab.simulation.doctrine_lab.catalog import CATALOG_PATH
from autofde_lab.simulation.fortune5_safe import Scenario

MIRROR = world_by_id("mirror/deceptive/fracturing/late/inferior")


def test_world_product_is_243_distinct_worlds_projecting_to_scenarios():
    assert len(ALL_WORLDS) == 243
    assert len({w.id for w in ALL_WORLDS}) == 243
    baseline = world_by_id("static/full/solo/mid/parity").to_scenario()
    assert baseline == Scenario(baseline.name)
    harsh = MIRROR.to_scenario()
    assert harsh.capacity_multiplier < 1.0 and harsh.dependency_multiplier > 1.0
    assert world_by_id(MIRROR.id) == MIRROR


def test_primitive_algebra_is_the_sd_fourteen_with_five_duals():
    assert len(PRIMITIVES) == 14
    for left, right in DUALS:
        assert PRIMITIVES[left].dual == right and PRIMITIVES[right].dual == left


def test_catalog_resolves_under_pin_and_refuses_tampered_bytes(tmp_path: Path):
    catalog = load_catalog()
    assert catalog.sha256 == CATALOG_SHA256
    assert [s.ordinal for s in catalog.strategies] == list(range(1, 34))
    assert all(len(s.short_title) <= 60 for s in catalog.strategies)
    assert "no text reproduced" in catalog.non_claim
    assert catalog.get(1).primitives == ("probe", "concentrate")
    assert len(catalog.operationalized) == 14

    tampered = tmp_path / "catalog.json"
    doc = json.loads(CATALOG_PATH.read_bytes())
    doc["strategies"][0]["quote"] = "x"
    tampered.write_text(json.dumps(doc))
    with pytest.raises(CatalogIntegrityError, match="does not match pinned"):
        load_catalog(tampered)
    digest = hashlib.sha256(tampered.read_bytes()).hexdigest()
    with pytest.raises(CatalogIntegrityError, match="quote"):
        load_catalog(tampered, expected_sha256=digest)


def test_same_seed_is_byte_identical_and_different_seed_differs():
    catalog = load_catalog()
    strategy = catalog.get(2)
    a = run_strategy_episode(7, strategy, MIRROR, catalog_sha256=catalog.sha256)
    b = run_strategy_episode(7, strategy, MIRROR, catalog_sha256=catalog.sha256)
    c = run_strategy_episode(8, strategy, MIRROR, catalog_sha256=catalog.sha256)
    assert a.receipt == b.receipt
    assert log_bytes(episode_log(a)) == log_bytes(episode_log(b))
    assert a.receipt.episode_digest != c.receipt.episode_digest
    assert log_sha256(episode_log(a)) != log_sha256(episode_log(c))
    assert any(r.move.adapted for r in a.rounds)  # mirror adapts after round 1
    assert a.receipt.authority == "NONE"
    assert a.receipt.evidence_ceiling == "REPO_LOCAL_FIXTURE"


def test_episode_ocel_log_is_valid_ocel2():
    catalog = load_catalog()
    episode = run_strategy_episode(
        1, catalog.get(5), MIRROR, catalog_sha256=catalog.sha256
    )
    log = OcelLog.from_ocel2_json(episode_log(episode)).validate(strict_qualifiers=True)
    activities = [e.activity for e in log.events]
    assert activities[0] == "episode.start" and activities[-1] == "episode.close"
    assert activities.count("round.execute") == 3


def test_equal_primitive_strategies_cluster_and_collisions_are_reported():
    catalog = load_catalog()
    worlds = (MIRROR, world_by_id("static/full/solo/mid/parity"))
    result = run_doctrine_matrix([1, 2], worlds, catalog.operationalized)
    report = build_report(result, catalog)
    clusters = {
        tuple(m["strategy"] for m in c["members"]): c
        for c in report["primitive_equivalence_clusters"]
    }
    same = clusters[("sd-01", "sd-12")]
    assert same["collision"] is False and same["behaviourally_identical"] is True
    assert clusters[("sd-13", "sd-14")]["collision"] is True
    assert report["evidence_ceiling"] == "REPO_LOCAL_FIXTURE"
    assert "not evidence about any real-world system" in report["model_relative"]
    assert report["selection"] is None


def test_ledger_verifies_and_tamper_fails(tmp_path: Path):
    catalog = load_catalog()
    episodes = [
        run_strategy_episode(s, catalog.get(o), MIRROR, catalog_sha256=catalog.sha256)
        for s in (1, 2)
        for o in (3, 9)
    ]
    ledger = tmp_path / "ledger.jsonl"
    verification = seal_episodes(
        [(e, log_sha256(episode_log(e))) for e in episodes], ledger
    )
    assert verification.valid and verification.records == 4
    assert verify_ledger(ledger).valid

    lines = ledger.read_text().splitlines()
    record = json.loads(lines[1])
    record["signed_attestation"]["attestation"]["value_digest"] = "0" * 64
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    ledger.write_text("\n".join(lines) + "\n")
    tampered = verify_ledger(ledger)
    assert not tampered.valid
    assert tampered.records == 1


def test_wilson_interval_bounds():
    assert wilson(0, 0) is None
    low, high = wilson(2, 2)
    assert 0.0 < low < 1.0 and high == 1.0
    assert wilson(0, 5)[0] == 0.0


def test_small_matrix_run_is_fast_and_byte_replayable(tmp_path: Path):
    start = time.perf_counter()
    kwargs = dict(seeds=[2030, 2031], worlds=ALL_WORLDS[::40], ordinals=[1, 4, 12])
    first = run_lab(tmp_path / "a", **kwargs)
    second = run_lab(tmp_path / "b", **kwargs)
    assert second == first
    assert time.perf_counter() - start < 10.0
    assert first["ledger"]["valid"] and first["episode_count"] == 2 * 7 * 3
    for name in ("report.json", "ledger.jsonl"):
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name
        ).read_bytes()
    ocel_a = sorted(p.name for p in (tmp_path / "a" / "ocel").iterdir())
    assert len(ocel_a) == 42
    for name in ocel_a:
        assert (tmp_path / "a" / "ocel" / name).read_bytes() == (
            tmp_path / "b" / "ocel" / name
        ).read_bytes()
