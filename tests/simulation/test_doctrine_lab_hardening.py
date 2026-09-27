"""Adversarial falsifiers for the doctrine lab's admission and run verifier.

Court findings on PR #188 (d6becb59) turned into permanent guards:

* forged origin: a receipt/ledger record that brings its own primitive
  composition under an admitted ordinal was sealed and ``verify_run(replay=False)``
  reported it valid;
* authority: ``verify_run`` without replay did not enforce authority NONE, a
  SELECT/CONSTRUCT ceiling, ``selection`` None, or the evidence ceiling once the
  unkeyed ``report_digest`` was recomputed;
* revert-mutants M9 (tail-digest anchor check) and M10 (``concealed`` constant
  False) survived the suite;
* duplicate delivery, reordering, stale catalog, malformed artifacts and short
  or non-hex seal keys had no falsifier.

Real collaborators only: the fortune5_safe engine, the real ProvenanceLedger on
disk and the real catalog. Forgeries are written with the PUBLISHED fixture key,
i.e. with exactly the power an attacker of a fixture-keyed run holds.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from autofde_lab._cache.provenance import CacheAttestation, ProvenanceLedger
from autofde_lab.simulation.doctrine_lab import (
    ALL_WORLDS,
    ProvenanceRefused,
    SealKeyRefused,
    admit_for_seal,
    episode_log,
    load_catalog,
    log_bytes,
    log_sha256,
    ocel_filename,
    run_lab,
    run_strategy_episode,
    seal,
    seal_episodes,
    verify_run,
    world_by_id,
)
from autofde_lab.simulation.doctrine_lab.matrix import receipt_body
from autofde_lab.simulation.doctrine_lab.opponent import Opponent
from autofde_lab.simulation.doctrine_lab.primitives import concealed
from autofde_lab.simulation.doctrine_lab.report import report_body
from autofde_lab.simulation.fortune5_safe.model import stable_digest

MIRROR = world_by_id("mirror/deceptive/fracturing/late/inferior")
PARITY = world_by_id("static/full/solo/mid/parity")
FIXTURE = seal.signer_from_env({})


def _run(out: Path, ordinals=(1, 8)) -> dict:
    return run_lab(out, seeds=[2030], worlds=ALL_WORLDS[::120], ordinals=list(ordinals))


def _rows(out: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (out / "ledger.jsonl").read_text().splitlines()
        if line.strip()
    ]


def _resign(report: dict, records: int, tail: str | None) -> None:
    """Forger with the published fixture key: re-digest and re-sign the report."""
    report["report_digest"] = stable_digest(report_body(report))
    report["ledger"].update(
        records=records,
        tail_digest=tail,
        report_signature=seal.report_signature(
            FIXTURE, report["report_digest"], records, tail
        ),
    )


def _rewrite_report(out: Path, mutate) -> None:
    path = out / "report.json"
    report = json.loads(path.read_text())
    mutate(report)
    anchor = report["ledger"]
    _resign(report, anchor["records"], anchor["tail_digest"])
    path.write_text(json.dumps(report))


def _reseal(out: Path, mutate, *, update_anchor: bool = True) -> None:
    """Rewrite the ledger with mutated attestations under the fixture key."""
    atts = [dict(r["signed_attestation"]["attestation"]) for r in _rows(out)]
    atts = mutate(atts)
    ledger_path = out / "ledger.jsonl"
    ledger_path.unlink()
    ledger = ProvenanceLedger(ledger_path, signer=FIXTURE, fsync=False)
    for att in atts:
        ledger.append(CacheAttestation(**att))
    chain = ledger.verify()
    assert chain.valid  # every forgery below is a VALID chain under the key
    if update_anchor:
        path = out / "report.json"
        report = json.loads(path.read_text())
        _resign(report, chain.records, chain.tail_digest)
        path.write_text(json.dumps(report))


# --- forged origin -----------------------------------------------------------


def test_seal_refuses_a_receipt_that_brings_its_own_composition():
    catalog = load_catalog()
    forged = dataclasses.replace(catalog.get(1), primitives=("withdraw", "delay"))
    episode = run_strategy_episode(7, forged, PARITY, catalog_sha256=catalog.sha256)
    # the receipt is internally consistent: episode_digest recomputes
    r = episode.receipt
    assert r.episode_digest == stable_digest(
        receipt_body(r.catalog_sha256, 1, "withdraw>delay", r.outcome_digest)
    )
    with pytest.raises(ProvenanceRefused, match="not the admitted catalog's"):
        admit_for_seal(episode, log_sha256(episode_log(episode)))


def test_seal_refuses_a_forged_signature_on_the_admitted_strategy():
    """The episode ran the admitted Strategy, but its receipt names another
    composition (episode_digest recomputed): only the signature binding refuses."""
    catalog = load_catalog()
    episode = run_strategy_episode(
        7, catalog.get(1), PARITY, catalog_sha256=catalog.sha256
    )
    r = episode.receipt
    forged = dataclasses.replace(
        episode,
        receipt=dataclasses.replace(
            r,
            strategy_signature="withdraw>delay",
            episode_digest=stable_digest(
                receipt_body(r.catalog_sha256, 1, "withdraw>delay", r.outcome_digest)
            ),
        ),
    )
    with pytest.raises(ProvenanceRefused, match="signature 'withdraw>delay' is not"):
        admit_for_seal(forged, log_sha256(episode_log(forged)))


@pytest.mark.parametrize(
    ("authority", "ceiling"), [("DO", "CONSTRUCT"), ("NONE", "DO"), ("NONE", "")]
)
def test_seal_refuses_receipt_authority_above_construct(authority, ceiling):
    catalog = load_catalog()
    episode = run_strategy_episode(
        7, catalog.get(1), PARITY, catalog_sha256=catalog.sha256
    )
    forged = dataclasses.replace(
        episode,
        receipt=dataclasses.replace(
            episode.receipt, authority=authority, authority_ceiling=ceiling
        ),
    )
    with pytest.raises(ProvenanceRefused, match="receipt authority"):
        admit_for_seal(forged, log_sha256(episode_log(forged)))
    admit_for_seal(episode, log_sha256(episode_log(episode)))  # anti-vacuity


def test_seal_refuses_a_policy_collision_relabel():
    """sd-13 and sd-14 share one policy; only the signature separates them."""
    catalog = load_catalog()
    s13, s14 = catalog.get(13), catalog.get(14)
    assert s13.policy.digest == s14.policy.digest and s13.signature != s14.signature
    episode = run_strategy_episode(7, s13, PARITY, catalog_sha256=catalog.sha256)
    r = episode.receipt
    relabelled = dataclasses.replace(
        episode,
        receipt=dataclasses.replace(
            r,
            strategy_ordinal=14,
            strategy_signature=s14.signature,
            episode_digest=stable_digest(
                receipt_body(r.catalog_sha256, 14, s14.signature, r.outcome_digest)
            ),
        ),
    )
    with pytest.raises(ProvenanceRefused, match="strategy/policy is not the admitted"):
        admit_for_seal(relabelled, log_sha256(episode_log(relabelled)))


def test_seal_refuses_an_outcome_that_does_not_recompute_from_rounds():
    catalog = load_catalog()
    episode = run_strategy_episode(
        7, catalog.get(2), MIRROR, catalog_sha256=catalog.sha256
    )
    r = episode.receipt
    outcome = "0" * 64
    forged = dataclasses.replace(
        episode,
        receipt=dataclasses.replace(
            r,
            outcome_digest=outcome,
            episode_digest=stable_digest(
                receipt_body(r.catalog_sha256, 2, r.strategy_signature, outcome)
            ),
        ),
    )
    with pytest.raises(ProvenanceRefused, match="outcome does not recompute"):
        admit_for_seal(forged, log_sha256(episode_log(forged)))


def test_verify_run_without_replay_refuses_a_forged_composition(tmp_path: Path):
    """The court's exact hole: a directly-written ledger record (valid chain,
    valid HMAC, anchor re-signed) whose value_digest commits to a composition the
    admitted catalog does not carry."""
    _run(tmp_path)
    catalog = load_catalog()

    def forge(atts):
        att = atts[0]
        att["value_digest"] = stable_digest(
            receipt_body(catalog.sha256, 1, "withdraw>delay", att["key_digest"])
        )
        return atts

    _reseal(tmp_path, forge)
    check = verify_run(tmp_path)
    assert not check.valid
    assert check.failures == (
        f"doctrine-lab:sd-01@{ALL_WORLDS[0].id}#s2030 value_digest does not bind "
        "the catalog signature 'probe>concentrate'",
    )


def test_verify_run_refuses_a_foreign_policy_digest(tmp_path: Path):
    _run(tmp_path)
    other = load_catalog().get(8).policy.digest

    def forge(atts):
        atts[0]["policy_digest"] = other
        return atts

    _reseal(tmp_path, forge)
    check = verify_run(tmp_path)
    assert not check.valid
    assert any(
        "policy_digest is not the catalog strategy's" in f for f in check.failures
    )


# --- authority without replay --------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "refusal"),
    [
        ("authority", "DO", "report authority 'DO' is not NONE"),
        ("authority_ceiling", "DO", "report authority_ceiling 'DO'"),
        ("selection", "sd-01", "report selection is not None"),
        ("evidence_ceiling", "PRODUCTION", "report evidence_ceiling 'PRODUCTION'"),
    ],
)
def test_verify_run_enforces_authority_without_replay(
    tmp_path: Path, field, value, refusal
):
    _run(tmp_path)
    _rewrite_report(tmp_path, lambda r: r.__setitem__(field, value))
    check = verify_run(tmp_path)  # digest and signature both recompute
    assert not check.valid
    assert any(refusal in f for f in check.failures), check.failures


@pytest.mark.parametrize(
    "owner", ["authority=DO;ceiling=DO", "authority=NONE;ceiling=DO", "", "NONE"]
)
def test_verify_run_refuses_a_record_owner_above_construct(tmp_path: Path, owner):
    _run(tmp_path)

    def forge(atts):
        atts[-1]["owner"] = owner
        return atts

    _reseal(tmp_path, forge)
    check = verify_run(tmp_path)
    assert not check.valid
    assert any("is not authority NONE <= CONSTRUCT" in f for f in check.failures)


def test_select_ceiling_record_is_admitted(tmp_path: Path):
    _run(tmp_path)

    def select(atts):
        for att in atts:
            att["owner"] = "authority=NONE;ceiling=SELECT"
        return atts

    _reseal(tmp_path, select)
    assert verify_run(tmp_path).valid  # anti-vacuity: the gate is not refuse-all


# --- anchor, reordering, duplicate delivery (M9) --------------------------------


def test_reordered_ledger_is_refused_by_the_tail_anchor(tmp_path: Path):
    """Kills M9: same records, same count, valid chain, only order differs."""
    _run(tmp_path)
    _reseal(tmp_path, lambda atts: list(reversed(atts)), update_anchor=False)
    check = verify_run(tmp_path)
    assert not check.valid
    assert "ledger tail digest != report anchor" in check.failures
    assert not any("ledger records" in f for f in check.failures)


def test_tail_anchor_alone_refuses_a_substituted_digest(tmp_path: Path):
    _run(tmp_path)
    path = tmp_path / "report.json"
    report = json.loads(path.read_text())
    report["ledger"]["tail_digest"] = "0" * 64
    path.write_text(json.dumps(report))
    check = verify_run(tmp_path)
    assert "ledger tail digest != report anchor" in check.failures


def test_seal_refuses_duplicate_delivery_in_batch_and_across_calls(tmp_path: Path):
    catalog = load_catalog()
    episode = run_strategy_episode(
        1, catalog.get(3), PARITY, catalog_sha256=catalog.sha256
    )
    item = (episode, log_sha256(episode_log(episode)))
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(ProvenanceRefused, match="duplicate delivery"):
        seal_episodes([item, item], ledger)
    assert not ledger.exists() or ledger.read_text() == ""
    assert seal_episodes([item], ledger).records == 1
    before = ledger.read_bytes()
    with pytest.raises(ProvenanceRefused, match="duplicate delivery"):
        seal_episodes([item], ledger)
    assert ledger.read_bytes() == before


def test_verify_run_refuses_a_duplicated_record(tmp_path: Path):
    _run(tmp_path)
    _reseal(tmp_path, lambda atts: atts[:-1] + [atts[0]])
    check = verify_run(tmp_path)
    assert not check.valid
    assert any(f.startswith("duplicate delivery of") for f in check.failures)


# --- stale subject / scope ------------------------------------------------------


def test_verify_run_refuses_a_stale_catalog_digest(tmp_path: Path):
    _run(tmp_path)
    _rewrite_report(tmp_path, lambda r: r["catalog"].__setitem__("sha256", "1" * 64))
    check = verify_run(tmp_path)
    assert not check.valid
    assert any(
        "report catalog is not the admitted catalog" in f for f in check.failures
    )


@pytest.mark.parametrize(
    ("field", "value", "refusal"),
    [
        ("seeds", [2031], "seed is not in the report's seeds"),
        ("world_ids", [], "world is not in the report's world_ids"),
        ("strategy_ids", ["sd-08"], "strategy is not in the report's strategy_ids"),
    ],
)
def test_verify_run_refuses_records_outside_report_scope(
    tmp_path: Path, field, value, refusal
):
    _run(tmp_path)
    _rewrite_report(tmp_path, lambda r: r.__setitem__(field, value))
    check = verify_run(tmp_path)
    assert not check.valid
    assert any(refusal in f for f in check.failures)


# --- malformed input ------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("report.json", b"{not json"),
        ("report.json", b"[1, 2]"),
        ("ledger.jsonl", b"{not json\n"),
        ("ledger.jsonl", b"[]\n"),
    ],
)
def test_verify_run_reports_malformed_artifacts_without_raising(
    tmp_path: Path, name, payload
):
    _run(tmp_path)
    (tmp_path / name).write_bytes(payload)
    check = verify_run(tmp_path)
    assert not check.valid and check.failures


@pytest.mark.parametrize(
    ("raw", "refusal"),
    [("zz" * 32, "is not hex"), ("ab" * 16, "carries 16 bytes"), ("abc", "not hex")],
)
def test_seal_key_is_typed_refused(raw, refusal):
    with pytest.raises(SealKeyRefused, match=refusal):
        seal.signer_from_env({seal.KEY_ENV: raw})
    assert seal.signer_from_env({seal.KEY_ENV: "ab" * 32}).key_id.startswith(
        "doctrine-lab-env-"
    )


# --- concealment (M10) ----------------------------------------------------------


def test_concealed_is_the_last_conceal_or_reveal():
    assert concealed(("conceal",)) is True
    assert concealed(("reveal", "conceal")) is True
    assert concealed(("conceal", "reveal")) is False
    assert concealed(("probe", "concentrate")) is False
    catalog = load_catalog()
    flags = {s.id: s.concealed for s in catalog.operationalized}
    assert flags["sd-02"] is True and flags["sd-01"] is False


def _moves(strategy, world, seed, *, hidden: bool):
    opponent = Opponent(seed, strategy.signature, world, concealed=hidden)
    scenario = world.to_scenario()
    moves = []
    for index in (1, 2, 3):
        scenario, move = opponent.respond(index, strategy.policy, scenario)
        moves.append(move)
    return moves


def test_concealment_reaches_the_opponent_and_changes_its_moves():
    """Kills M10: the episode's opponent must play the concealed branch."""
    catalog = load_catalog()
    strategy = catalog.get(2)
    episode = run_strategy_episode(7, strategy, MIRROR, catalog_sha256=catalog.sha256)
    played = [r.move for r in episode.rounds]
    assert played == _moves(strategy, MIRROR, 7, hidden=True)
    exposed = _moves(strategy, MIRROR, 7, hidden=False)
    assert played != exposed
    adapted = [(p, e) for p, e in zip(played, exposed) if p.adapted]
    assert adapted and all(abs(p.delta) < abs(e.delta) for p, e in adapted)


def test_ocel_file_name_is_bound_to_the_subject(tmp_path: Path):
    _run(tmp_path)
    first = _rows(tmp_path)[0]["signed_attestation"]["attestation"]["subject_id"]
    name = ocel_filename(first.split(":", 1)[1])
    path = tmp_path / "ocel" / name
    assert path.read_bytes().startswith(b"{")
    catalog = load_catalog()
    episode = run_strategy_episode(
        2030, catalog.get(1), ALL_WORLDS[0], catalog_sha256=catalog.sha256
    )
    assert path.read_bytes() == log_bytes(episode_log(episode))
