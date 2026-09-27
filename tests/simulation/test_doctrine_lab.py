"""Evidence checkpoints for the doctrine boundary lab.

Real collaborators only: the unmodified fortune5_safe engine, the aloop OCEL
Builder, the OcelLog parser/validator and the real ProvenanceLedger on disk.
Evidence ceiling REPO_LOCAL_FIXTURE: these tests certify determinism, integrity
and model-relative reporting, not any claim about a real-world system.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from autofde_lab.ocel import OcelLog
from autofde_lab.simulation import doctrine_lab
from autofde_lab.simulation.doctrine_lab import (
    ALL_WORLDS,
    CATALOG_SHA256,
    DUALS,
    PRIMITIVES,
    Catalog,
    CatalogIntegrityError,
    ProvenanceRefused,
    build_report,
    episode_log,
    load_catalog,
    log_bytes,
    log_sha256,
    run_doctrine_matrix,
    run_lab,
    run_strategy_episode,
    seal,
    seal_episodes,
    verify_ledger,
    verify_run,
    wilson,
    world_by_id,
)
from autofde_lab.simulation.doctrine_lab.catalog import CATALOG_PATH
from autofde_lab.simulation.doctrine_lab.matrix import EVIDENCE_CEILING
from autofde_lab.simulation.doctrine_lab.opponent import opponent_rng
from autofde_lab.simulation.doctrine_lab.relations import dominates
from autofde_lab.simulation.fortune5_safe import Scenario

MIRROR = world_by_id("mirror/deceptive/fracturing/late/inferior")
PARITY = world_by_id("static/full/solo/mid/parity")


def _repinned(tmp_path: Path, mutate) -> tuple[Path, str]:
    """Write a mutated copy of the vendored catalog; return it with its own digest.

    Re-pinning is the Lane 1 replacement seam: these gates must hold even when the
    digest pin is satisfied by a different catalog.
    """
    doc = json.loads(CATALOG_PATH.read_bytes())
    mutate(doc)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(doc))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _set(entry_index: int, key: str, value):
    def mutate(doc):
        doc["strategies"][entry_index][key] = value

    return mutate


def _drop(entry_index: int, key: str):
    def mutate(doc):
        del doc["strategies"][entry_index][key]

    return mutate


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


def test_unmutated_catalog_repinned_is_admitted(tmp_path: Path):
    path, digest = _repinned(tmp_path, lambda doc: None)
    assert load_catalog(path, expected_sha256=digest).get(1).iri == "sd:strategy-01"


@pytest.mark.parametrize(
    ("mutate", "refusal"),
    [
        (lambda d: d.__setitem__("authority", "DO"), "authority must be NONE"),
        (lambda d: d.__setitem__("authority_ceiling", "DO"), "ceiling"),
        (lambda d: d.__setitem__("non_claim", "x"), "non-claim"),
        (lambda d: d.__setitem__("iri", "https://example.org/x#"), "sd: strategic"),
        (_set(0, "primitives", ["probe", "feint"]), "unknown primitive 'feint'"),
        (_set(0, "short_title", "x" * 61), "title too long"),
        (_set(0, "summary", "free text"), r"extra=\['summary'\]"),
        (_set(0, "quote", "x"), "carries a quote"),
        (_set(0, "iri", "https://example.org/strategy-01"), "is not sd:"),
        (_set(1, "iri", "sd:strategy-01"), "is not sd:"),
        (_set(0, "status", "retired"), "unknown status 'retired'"),
        (_drop(0, "primitives"), r"missing=\['primitives'\]"),
        (_set(0, "primitives", []), "has no primitives"),
        (_set(20, "primitives", ["probe"]), "stub with primitives"),
        (_set(0, "primitives", "probe"), "not a list"),
        (lambda d: d.__setitem__("summary", "free text"), r"extra=\['summary'\]"),
        (
            lambda d: d.pop("schema"),
            r"top-level keys outside allow-list: .*missing=\['schema'\]",
        ),
        (lambda d: d.pop("primitives"), r"missing=\['primitives'\]"),
        (
            lambda d: d["primitives"][0].__setitem__("quote", "x"),
            r"primitive 'shape' keys outside allow-list: extra=\['quote'\]",
        ),
        (
            lambda d: d["primitives"][2].__setitem__("dual", "probe"),
            r"primitive 'conceal' dual 'probe' differs",
        ),
        (
            lambda d: d["primitives"][0].__setitem__("iri", "sd:wrong"),
            r"primitive 'shape' iri 'sd:wrong' is not sd:",
        ),
    ],
    ids=[
        "authority_DO",
        "ceiling_DO",
        "drop_nonclaim",
        "forged_graph_iri",
        "unknown_primitive",
        "title_61",
        "extra_text_field",
        "quote",
        "entry_iri_foreign",
        "entry_iri_wrong_ordinal",
        "unknown_status",
        "missing_primitives_key",
        "operationalized_without_primitives",
        "stub_with_primitives",
        "primitives_not_list",
        "top_level_summary",
        "top_level_missing_schema",
        "top_level_missing_primitives_no_keyerror",
        "primitive_extra_quote",
        "primitive_dual_off_algebra",
        "primitive_iri_not_sd",
    ],
)
def test_catalog_gates_refuse_under_repinned_digest(tmp_path: Path, mutate, refusal):
    path, digest = _repinned(tmp_path, mutate)
    with pytest.raises(CatalogIntegrityError, match=refusal):
        load_catalog(path, expected_sha256=digest)


def test_duplicate_json_keys_are_refused_under_repinned_digest(tmp_path: Path):
    raw = CATALOG_PATH.read_text()
    needle = '"short_title": "Probe, then mass on the weak point"'
    assert raw.count(needle) == 1
    forged = raw.replace(needle, f'"short_title": "dupe", {needle}', 1)
    path = tmp_path / "catalog.json"
    path.write_text(forged)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(CatalogIntegrityError, match="duplicate JSON key 'short_title'"):
        load_catalog(path, expected_sha256=digest)


def test_stub_strategy_runs_are_refused():
    catalog = load_catalog()
    stub = catalog.get(15)
    assert stub.status == "stub" and stub.primitives == ()
    with pytest.raises(ValueError, match="stub strategies"):
        run_doctrine_matrix([1], [PARITY], [stub], catalog=catalog)
    with pytest.raises(ValueError, match="stub strategies"):
        run_strategy_episode(1, stub, PARITY, catalog_sha256=catalog.sha256)


def test_frontier_is_the_feasible_nondominated_set_and_feeds_the_report():
    catalog = load_catalog()
    result = run_doctrine_matrix([1, 2], (MIRROR, PARITY), catalog.operationalized)
    frontiers = dict(result.frontiers)
    for world_id in result.world_ids:
        cells = [c for c in result.cells if c.world_id == world_id]
        feasible = [c for c in cells if c.aggregate.feasible]
        expected = sorted(
            c.strategy_id
            for c in feasible
            if not any(
                o is not c and dominates(o.aggregate, c.aggregate) for o in feasible
            )
        )
        assert list(frontiers[world_id]) == expected
    # model state, pinned: the harsh world admits nothing, parity admits 13 of 14
    assert frontiers[MIRROR.id] == ()
    parity_front = frontiers[PARITY.id]
    assert len(parity_front) == 13 and "sd-08" not in parity_front
    by_id = {c.strategy_id: c for c in result.cells if c.world_id == PARITY.id}
    assert by_id["sd-08"].aggregate.feasible
    assert any(
        dominates(by_id[f].aggregate, by_id["sd-08"].aggregate) for f in parity_front
    )
    diversity = dict(result.frontier_diversity)
    assert diversity[MIRROR.id] == 0.0 and diversity[PARITY.id] > 0.0

    report = build_report(result, catalog)
    regions = report["applicability_regions"]
    assert regions["sd-08"]["applicable_world_count"] == 0
    for strategy_id in parity_front:
        assert regions[strategy_id]["applicable_worlds"] == [PARITY.id]
    dominance = report["counter_dominance"]["dominance"]
    assert dominance, "parity world carries at least one dominance pair"
    cell = {(c.world_id, c.strategy_id): c.aggregate for c in result.cells}
    for row in dominance:
        holds = sum(
            dominates(cell[(w, row["dominant"])], cell[(w, row["dominated"])])
            for w in result.world_ids
        )
        assert row["worlds"] == holds >= 1
    assert any(
        r["dominated"] == "sd-08" and r["dominant"] in parity_front for r in dominance
    )


def test_opponent_rng_binds_seed_signature_and_world():
    sig = load_catalog().get(2).signature
    draws = {
        key: opponent_rng(*key).random()
        for key in (
            (7, sig, MIRROR),
            (8, sig, MIRROR),
            (7, "x", MIRROR),
            (7, sig, PARITY),
        )
    }
    assert len(set(draws.values())) == 4
    assert opponent_rng(7, sig, MIRROR).random() == draws[(7, sig, MIRROR)]


def test_forged_catalog_origin_is_refused(tmp_path: Path):
    catalog = load_catalog()
    strategy = catalog.get(2)
    with pytest.raises(ProvenanceRefused, match="never admitted"):
        run_strategy_episode(7, strategy, MIRROR, catalog_sha256="0" * 64)
    forged = Catalog(
        "0" * 64, catalog.provenance, catalog.non_claim, catalog.strategies
    )
    with pytest.raises(ProvenanceRefused, match="never admitted"):
        run_doctrine_matrix([1], [PARITY], [strategy], catalog=forged)

    episode = run_strategy_episode(7, strategy, MIRROR, catalog_sha256=catalog.sha256)
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(ProvenanceRefused, match="OCEL digest"):
        seal_episodes([(episode, "f" * 64)], ledger)
    import dataclasses

    fake = dataclasses.replace(
        episode,
        receipt=dataclasses.replace(episode.receipt, catalog_sha256="0" * 64),
    )
    with pytest.raises(ProvenanceRefused, match="never admitted"):
        seal_episodes([(fake, log_sha256(episode_log(fake)))], ledger)
    relabelled = dataclasses.replace(
        episode, receipt=dataclasses.replace(episode.receipt, strategy_ordinal=9)
    )
    with pytest.raises(ProvenanceRefused, match="is not the admitted catalog's"):
        seal_episodes([(relabelled, log_sha256(episode_log(relabelled)))], ledger)
    redigested = dataclasses.replace(
        episode, receipt=dataclasses.replace(episode.receipt, episode_digest="0" * 64)
    )
    with pytest.raises(ProvenanceRefused, match="digest does not recompute"):
        seal_episodes([(redigested, log_sha256(episode_log(redigested)))], ledger)
    assert not ledger.exists() or ledger.read_text() == ""


def _small_run(out: Path) -> dict:
    return run_lab(out, seeds=[2030], worlds=ALL_WORLDS[::120], ordinals=[1, 8])


def test_verify_run_accepts_and_replays_an_untouched_run(tmp_path: Path):
    report = _small_run(tmp_path)
    assert report["world_ids"] == [w.id for w in ALL_WORLDS[::120]]
    check = verify_run(tmp_path, replay=True)
    assert check.valid and check.failures == () and check.records == 6


def test_verify_run_detects_ocel_edit(tmp_path: Path):
    _small_run(tmp_path)
    path = sorted((tmp_path / "ocel").iterdir())[0]
    doc = json.loads(path.read_bytes())
    doc["events"] = doc["events"][:-1]
    path.write_text(json.dumps(doc))
    assert verify_ledger(tmp_path / "ledger.jsonl").valid  # the chain cannot see it
    check = verify_run(tmp_path)
    assert not check.valid
    assert any("does not match its ledger fingerprint" in f for f in check.failures)


def test_verify_run_detects_report_edit_even_with_recomputed_digest(tmp_path: Path):
    from autofde_lab.simulation.doctrine_lab.report import report_body
    from autofde_lab.simulation.fortune5_safe.model import stable_digest

    _small_run(tmp_path)
    path = tmp_path / "report.json"
    report = json.loads(path.read_text())
    report["frontiers"] = {w: [] for w in report["frontiers"]}
    path.write_text(json.dumps(report))
    check = verify_run(tmp_path)
    assert not check.valid and any("report_digest" in f for f in check.failures)

    report["report_digest"] = stable_digest(report_body(report))
    path.write_text(json.dumps(report))
    rehashed = verify_run(tmp_path)  # the unkeyed digest alone no longer suffices
    assert rehashed.failures == (
        "report_signature does not bind report body to the ledger key",
    )
    # a forger holding the PUBLISHED fixture key can re-sign; that key attests no
    # writer (attests_writer False), so only replay can refuse this forgery
    fixture = seal.signer_from_env({})
    anchor = report["ledger"]
    anchor["report_signature"] = seal.report_signature(
        fixture, report["report_digest"], anchor["records"], anchor["tail_digest"]
    )
    path.write_text(json.dumps(report))
    assert anchor["attests_writer"] is False
    assert verify_run(tmp_path).valid  # self-consistent fixture-key forgery
    replayed = verify_run(tmp_path, replay=True)
    assert not replayed.valid
    assert "replay: report body differs from re-execution" in replayed.failures


def test_verify_run_detects_ledger_tail_truncation(tmp_path: Path):
    _small_run(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[:-1]) + "\n")
    assert verify_ledger(ledger).valid  # a prefix of a chain is still a chain
    check = verify_run(tmp_path)
    assert not check.valid
    assert any("report anchor" in f for f in check.failures)
    assert any("not bound by any ledger record" in f for f in check.failures)


_SRC = Path(doctrine_lab.__file__).resolve().parents[3]
_KEY_HEX = "ab" * 32


def _cli_run(out: Path, *, key_hex: str | None = None) -> dict:
    """Run the lab CLI in a fresh interpreter (real process, real import time).

    The child puts this test's own ``src`` first on ``sys.path`` (ahead of any
    editable-install finder) and asserts it imported the lab from there, so the
    run exercises the tree under test.
    """
    env = {k: v for k, v in os.environ.items() if k != seal.KEY_ENV}
    if key_hex is not None:
        env[seal.KEY_ENV] = key_hex
    prelude = (
        "import sys, runpy; src = sys.argv.pop(1); sys.path.insert(0, src); "
        "sys.meta_path[:] = [f for f in sys.meta_path "
        "if 'editable' not in type(f).__module__]; "
        "import autofde_lab.simulation.doctrine_lab as d; "
        "assert d.__file__.startswith(src), d.__file__; "
        "sys.argv[0] = 'doctrine_lab'; "
        "runpy.run_module('autofde_lab.simulation.doctrine_lab', run_name='__main__')"
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            prelude,
            str(_SRC),
            "--out",
            str(out),
            "--seeds",
            "2030",
            "--worlds",
            "2",
            "--ordinals",
            "1",
            "8",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _ledger_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ledger_and_report_bytes_are_identical_across_processes(tmp_path: Path):
    assert seal.OBSERVED_AT == 0.0
    first = _cli_run(tmp_path / "p1")
    second = _cli_run(tmp_path / "p2")
    assert first["verify_run"]["valid"] and second["verify_run"]["valid"]
    for name in ("ledger.jsonl", "report.json"):
        a = hashlib.sha256((tmp_path / "p1" / name).read_bytes()).hexdigest()
        b = hashlib.sha256((tmp_path / "p2" / name).read_bytes()).hexdigest()
        assert a == b, name
    rows = _ledger_rows(tmp_path / "p1" / "ledger.jsonl")
    assert len(rows) == 4
    for row in rows:
        assert row["signed_attestation"]["attestation"]["observed_at"] == 0.0


def test_every_artifact_carries_authority_none_and_ceiling_construct(tmp_path: Path):
    catalog = load_catalog()
    report = _small_run(tmp_path)
    assert report["authority"] == "NONE"
    assert report["authority_ceiling"] == "CONSTRUCT"
    assert report["evidence_ceiling"] == EVIDENCE_CEILING
    assert report["catalog"]["sha256"] == catalog.sha256
    for row in _ledger_rows(tmp_path / "ledger.jsonl"):
        assert row["signed_attestation"]["attestation"]["owner"] == (
            "authority=NONE;ceiling=CONSTRUCT"
        )
    episode = run_strategy_episode(
        7, catalog.get(2), MIRROR, catalog_sha256=catalog.sha256
    )
    assert (episode.receipt.authority, episode.receipt.authority_ceiling) == (
        "NONE",
        "CONSTRUCT",
    )
    forged = tmp_path / "forged"
    _small_run(forged)
    doc = json.loads((forged / "report.json").read_text())
    doc["authority"] = "DO"
    (forged / "report.json").write_text(json.dumps(doc))
    assert not verify_run(forged).valid


def test_report_anchor_names_the_sealing_key(tmp_path: Path):
    fixture = _small_run(tmp_path / "fixture")["ledger"]
    assert fixture["key_id"] == seal.FIXTURE_KEY_ID
    assert fixture["key_kind"] == "fixture" and fixture["attests_writer"] is False

    keyed = _cli_run(tmp_path / "env", key_hex=_KEY_HEX)
    assert keyed["verify_run"]["valid"]
    env_signer = seal.signer_from_env({seal.KEY_ENV: _KEY_HEX})
    anchor = json.loads((tmp_path / "env" / "report.json").read_text())["ledger"]
    assert anchor["key_kind"] == "env" and anchor["attests_writer"] is True
    assert anchor["key_id"] == env_signer.key_id != seal.FIXTURE_KEY_ID
    assert verify_run(tmp_path / "env", signer=env_signer).valid
    wrong = verify_run(tmp_path / "env")  # fixture key: HMACs and anchor both refuse
    assert not wrong.valid
    assert any("key_id" in f for f in wrong.failures)

    relabelled = json.loads((tmp_path / "env" / "report.json").read_text())
    relabelled["ledger"]["key_kind"] = "fixture"
    (tmp_path / "env" / "report.json").write_text(json.dumps(relabelled))
    check = verify_run(tmp_path / "env", signer=env_signer)
    assert not check.valid and any("key_kind" in f for f in check.failures)


def test_verify_run_refuses_a_resealed_ledger_with_wall_clock_observed_at(
    tmp_path: Path,
):
    """A re-sealed ledger (valid chain + HMAC, anchor updated) still refuses a
    non-pinned ``observed_at``: ledger bytes must be a pure function of episodes."""
    from autofde_lab._cache.provenance import CacheAttestation, ProvenanceLedger

    _small_run(tmp_path)
    ledger_path = tmp_path / "ledger.jsonl"
    rows = _ledger_rows(ledger_path)
    ledger_path.unlink()
    ledger = ProvenanceLedger(ledger_path, signer=seal.signer_from_env({}), fsync=False)
    for row in rows:
        att = dict(row["signed_attestation"]["attestation"], observed_at=time.time())
        ledger.append(CacheAttestation(**att))
    chain = ledger.verify()
    assert chain.valid
    report_path = tmp_path / "report.json"
    report = json.loads(report_path.read_text())
    report["ledger"].update(
        records=chain.records,
        tail_digest=chain.tail_digest,
        report_signature=seal.report_signature(
            seal.signer_from_env({}),
            report["report_digest"],
            chain.records,
            chain.tail_digest,
        ),
    )
    report_path.write_text(json.dumps(report))
    check = verify_run(tmp_path)
    assert not check.valid
    assert all("observed_at is not pinned" in f for f in check.failures)
    assert len(check.failures) == len(rows)
