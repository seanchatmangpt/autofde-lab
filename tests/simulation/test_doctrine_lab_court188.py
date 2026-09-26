"""Falsifiers from the PR #188 court at ec3087a1 (verdict REFUSED, admission_vacuous).

Each test pins one guard the court showed was unpinned or open:

* forged rounds: an episode executed with a foreign composition, relabelled as
  the admitted Strategy with every digest recomputed, was admitted and sealed;
* stub ordinal: the seal and ``verify_run(replay=False)`` stub guards could be
  removed together with the suite green (mutants K11, K19);
* receipt world/seed/rounds lie and foreign schema/evidence ceiling had no
  witness (mutants K15, K17);
* the seal accepted any catalog admitted in-process, not the pinned one;
* ``verify_run`` did not validate the report's scope fields and raised on a
  malformed scope during replay;
* the catalog's free-text ``provenance``/``non_claim`` were unbounded.

Real collaborators only: the fortune5_safe engine, the real ProvenanceLedger on
disk and the real catalog. Ledger forgeries are written with the PUBLISHED
fixture key, i.e. with exactly the power an attacker of a fixture-keyed run has.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from autofde_lab.simulation.doctrine_lab import (
    CATALOG_SHA256,
    ProvenanceRefused,
    admit_for_seal,
    episode_log,
    load_catalog,
    log_sha256,
    ocel_filename,
    run_strategy_episode,
    seal_episodes,
    verify_run,
    world_by_id,
)
from autofde_lab.simulation.doctrine_lab.catalog import (
    CATALOG_PATH,
    MAX_FREE_TEXT,
    CatalogIntegrityError,
)
from autofde_lab.simulation.doctrine_lab.matrix import receipt_body
from autofde_lab.simulation.doctrine_lab.seal import outcome_digest_of
from autofde_lab.simulation.fortune5_safe.model import stable_digest

from test_doctrine_lab_hardening import _reseal, _rewrite_report, _rows, _run

PARITY = world_by_id("static/full/solo/mid/parity")
MIRROR = world_by_id("mirror/deceptive/fracturing/late/inferior")


def _ocel(episode) -> str:
    return log_sha256(episode_log(episode))


def _relabel(episode, admitted, *, relabel_rounds: bool):
    """Relabel an episode as ``admitted`` and recompute every digest.

    With ``relabel_rounds`` the per-round engine receipts are also rewritten to
    carry the admitted policy digest, so only re-execution can tell.
    """
    rounds = episode.rounds
    if relabel_rounds:
        rounds = tuple(
            dataclasses.replace(
                rr,
                receipt=dataclasses.replace(
                    rr.receipt, policy_digest=admitted.policy.digest
                ),
            )
            for rr in rounds
        )
    staged = dataclasses.replace(
        episode,
        strategy=admitted,
        rounds=rounds,
        receipt=dataclasses.replace(
            episode.receipt,
            strategy_ordinal=admitted.ordinal,
            strategy_signature=admitted.signature,
            policy_digest=admitted.policy.digest,
        ),
    )
    outcome = outcome_digest_of(staged)
    r = staged.receipt
    return dataclasses.replace(
        staged,
        receipt=dataclasses.replace(
            r,
            outcome_digest=outcome,
            episode_digest=stable_digest(
                receipt_body(
                    r.catalog_sha256, admitted.ordinal, admitted.signature, outcome
                )
            ),
        ),
    )


# --- forged rounds ---------------------------------------------------------------


def test_seal_refuses_foreign_rounds_relabelled_as_the_admitted_strategy(tmp_path):
    """The court's exact probe: rounds ran withdraw>delay, label says ordinal 1."""
    catalog = load_catalog()
    admitted = catalog.get(1)
    foreign = dataclasses.replace(admitted, primitives=("withdraw", "delay"))
    assert foreign.policy.digest != admitted.policy.digest
    ran = run_strategy_episode(7, foreign, PARITY, catalog_sha256=catalog.sha256)
    forged = _relabel(ran, admitted, relabel_rounds=False)
    # every label-level digest recomputes: only the round binding can refuse
    assert forged.receipt.outcome_digest == outcome_digest_of(forged)
    with pytest.raises(
        ProvenanceRefused, match="ran a policy that is not the admitted"
    ):
        admit_for_seal(forged, _ocel(forged))
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(
        ProvenanceRefused, match="ran a policy that is not the admitted"
    ):
        seal_episodes([(forged, _ocel(forged))], ledger)
    assert not ledger.exists() or ledger.read_text() == ""


def test_seal_refuses_foreign_rounds_even_with_round_receipts_relabelled():
    """Round receipts rewritten to the admitted policy digest: re-execution refuses."""
    catalog = load_catalog()
    admitted = catalog.get(1)
    foreign = dataclasses.replace(admitted, primitives=("withdraw", "delay"))
    ran = run_strategy_episode(7, foreign, PARITY, catalog_sha256=catalog.sha256)
    forged = _relabel(ran, admitted, relabel_rounds=True)
    with pytest.raises(ProvenanceRefused, match="differ from re-execution"):
        admit_for_seal(forged, _ocel(forged))


def test_seal_refuses_a_receipt_that_differs_from_re_execution():
    """Opponent digest edited (not part of outcome/episode digests): re-execution
    compares the whole receipt."""
    catalog = load_catalog()
    episode = run_strategy_episode(
        7, catalog.get(3), MIRROR, catalog_sha256=catalog.sha256
    )
    forged = dataclasses.replace(
        episode,
        receipt=dataclasses.replace(episode.receipt, opponent_digest="0" * 64),
    )
    with pytest.raises(ProvenanceRefused, match="receipt differs from re-execution"):
        admit_for_seal(forged, _ocel(forged))
    admit_for_seal(episode, _ocel(episode))  # anti-vacuity


# --- stub ordinal ----------------------------------------------------------------


def test_seal_refuses_a_stub_ordinal_with_recomputed_digests():
    catalog = load_catalog()
    stub = catalog.get(15)
    assert stub.status == "stub"
    episode = run_strategy_episode(
        7, catalog.get(1), PARITY, catalog_sha256=catalog.sha256
    )
    r = episode.receipt
    forged = dataclasses.replace(
        episode,
        strategy=stub,
        receipt=dataclasses.replace(
            r,
            strategy_ordinal=15,
            strategy_signature=stub.signature,
            episode_digest=stable_digest(
                receipt_body(r.catalog_sha256, 15, stub.signature, r.outcome_digest)
            ),
        ),
    )
    with pytest.raises(ProvenanceRefused, match="ordinal 15 is a stub"):
        admit_for_seal(forged, _ocel(forged))


def _append_stub_record(out: Path, *, extend_scope: bool) -> None:
    """Court exploit adv_k19: a stub-ordinal record with every digest recomputed."""
    catalog = load_catalog()
    stub = catalog.get(15)
    source = dict(_rows(out)[0]["signed_attestation"]["attestation"])
    subject = source["subject_id"].replace("sd-01@", f"{stub.id}@")
    name = ocel_filename(subject.split(":", 1)[1])
    body = (
        out / "ocel" / ocel_filename(source["subject_id"].split(":", 1)[1])
    ).read_bytes()
    (out / "ocel" / name).write_bytes(body)

    if extend_scope:
        _rewrite_report(
            out,
            lambda r: (
                r.__setitem__("strategy_ids", [*r["strategy_ids"], stub.id]),
                r.__setitem__("episode_count", r["episode_count"] + 1),
            ),
        )

    def forge(atts):
        att = dict(source)
        att["subject_id"] = subject
        att["policy_digest"] = stub.policy.digest
        att["value_digest"] = stable_digest(
            receipt_body(catalog.sha256, 15, stub.signature, str(att["key_digest"]))
        )
        att["data_fingerprint"] = "ocel:" + hashlib.sha256(body).hexdigest()
        return [*atts, att]

    _reseal(out, forge)


@pytest.mark.parametrize("extend_scope", [True, False])
def test_verify_run_without_replay_refuses_a_stub_ordinal_record(
    tmp_path, extend_scope
):
    _run(tmp_path, ordinals=(1,))
    _append_stub_record(tmp_path, extend_scope=extend_scope)
    check = verify_run(tmp_path)
    assert not check.valid
    # the record-level guard itself, not only the scope check, must fire
    assert any("names stub ordinal 15" in f for f in check.failures), check.failures
    if extend_scope:
        assert "report strategy_id sd-15 is not operationalized" in check.failures
    replayed = verify_run(tmp_path, replay=True)
    assert not replayed.valid


# --- receipt field lies -----------------------------------------------------------


@pytest.mark.parametrize(
    "field_value",
    [("seed", 8), ("world_id", MIRROR.id), ("rounds", 2)],
)
def test_seal_refuses_a_receipt_world_seed_rounds_lie(field_value):
    field, value = field_value
    catalog = load_catalog()
    episode = run_strategy_episode(
        7, catalog.get(1), PARITY, catalog_sha256=catalog.sha256
    )
    forged = dataclasses.replace(
        episode, receipt=dataclasses.replace(episode.receipt, **{field: value})
    )
    # episode_digest does not commit to these fields: only the scope check refuses
    with pytest.raises(ProvenanceRefused, match="world/seed/rounds mismatch"):
        admit_for_seal(forged, _ocel(forged))


@pytest.mark.parametrize(
    "changes",
    [
        {"schema": "attacker/v9"},
        {"evidence_ceiling": "PRODUCTION"},
        {"schema": "attacker/v9", "evidence_ceiling": "PRODUCTION"},
    ],
)
def test_seal_refuses_a_foreign_schema_or_evidence_ceiling(changes):
    catalog = load_catalog()
    episode = run_strategy_episode(
        7, catalog.get(1), PARITY, catalog_sha256=catalog.sha256
    )
    forged = dataclasses.replace(
        episode, receipt=dataclasses.replace(episode.receipt, **changes)
    )
    with pytest.raises(ProvenanceRefused, match="schema/ceiling"):
        admit_for_seal(forged, _ocel(forged))


# --- pinned catalog ---------------------------------------------------------------


def _repinned(tmp_path: Path, mutate) -> tuple[Path, str]:
    doc = json.loads(CATALOG_PATH.read_bytes())
    mutate(doc)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(doc))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_seal_refuses_a_schema_valid_catalog_admitted_from_another_path(tmp_path):
    """Court input A4: a rewritten composition admitted via load_catalog(path, sha)."""
    path, digest = _repinned(
        tmp_path,
        lambda doc: doc["strategies"][0].__setitem__(
            "primitives", ["withdraw", "delay"]
        ),
    )
    attacker = load_catalog(path, expected_sha256=digest)
    assert digest != CATALOG_SHA256
    episode = run_strategy_episode(7, attacker.get(1), PARITY, catalog_sha256=digest)
    with pytest.raises(ProvenanceRefused, match="is not the pinned catalog"):
        admit_for_seal(episode, _ocel(episode))
    pinned = load_catalog()
    genuine = run_strategy_episode(
        7, pinned.get(1), PARITY, catalog_sha256=pinned.sha256
    )
    admit_for_seal(genuine, _ocel(genuine))  # anti-vacuity


# --- report scope -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "refusal"),
    [
        (
            "strategy_ids",
            ["sd-01", "sd-15"],
            "report strategy_id sd-15 is not operationalized",
        ),
        (
            "strategy_ids",
            ["sd-01", "sd-99"],
            "report strategy_id sd-99 is not in the catalog",
        ),
        (
            "strategy_ids",
            "sd-01",
            "report strategy_ids 'sd-01' is not a non-empty list",
        ),
        ("world_ids", ["no/such/world"], "is not a lab world"),
        ("rounds", 0, "report rounds 0 is not a positive integer"),
        ("rounds", True, "report rounds True is not a positive integer"),
        ("seeds", "2030", "report seeds '2030' is not a non-empty list"),
        ("seeds", ["2030"], "report seed '2030' is not an integer"),
        ("seeds", [2030, 2030], "report seeds are not distinct"),
        ("episode_count", 99, "report episode_count 99 != strategies x worlds x seeds"),
    ],
)
@pytest.mark.parametrize("replay", [False, True])
def test_verify_run_validates_report_scope_without_raising(
    tmp_path, field, value, refusal, replay
):
    _run(tmp_path, ordinals=(1,))
    _rewrite_report(tmp_path, lambda r: r.__setitem__(field, value))
    check = verify_run(tmp_path, replay=replay)  # must not raise
    assert not check.valid
    assert any(refusal in f for f in check.failures), check.failures


def test_verify_run_refuses_a_ledger_missing_part_of_the_scope(tmp_path):
    _run(tmp_path, ordinals=(1, 8))
    _reseal(tmp_path, lambda atts: atts[:-1])
    check = verify_run(tmp_path)
    assert not check.valid
    assert any("ledger subjects are not the report scope" in f for f in check.failures)


@pytest.mark.parametrize("replay", [False, True])
def test_verify_run_reports_an_unreadable_ocel_file_without_raising(tmp_path, replay):
    _run(tmp_path, ordinals=(1,))
    victim = sorted((tmp_path / "ocel").iterdir())[0]
    victim.unlink()
    victim.mkdir()  # exists() is True, read_bytes() raises IsADirectoryError
    check = verify_run(tmp_path, replay=replay)
    assert not check.valid
    assert any(f"ocel/{victim.name} is unreadable" in f for f in check.failures)


def test_replay_refuses_a_forged_outcome_the_fixture_key_can_seal(tmp_path):
    """Limit witness: an outcome no execution produced, sealed under the fixture key
    with value_digest recomputed, is refused by replay."""
    _run(tmp_path, ordinals=(1,))
    catalog = load_catalog()
    strategy = catalog.get(1)

    def forge(atts):
        att = atts[0]
        att["key_digest"] = "1" * 64
        att["value_digest"] = stable_digest(
            receipt_body(catalog.sha256, 1, strategy.signature, att["key_digest"])
        )
        return atts

    _reseal(tmp_path, forge)
    replayed = verify_run(tmp_path, replay=True)
    assert not replayed.valid
    assert any("episode digest differs" in f for f in replayed.failures)


# --- catalog free text --------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "refusal"),
    [
        (
            lambda d: d.__setitem__("provenance", d["provenance"] + " x" * 12000),
            "provenance is not a single-line string",
        ),
        (
            lambda d: d.__setitem__("non_claim", d["non_claim"] + "\nsecond line"),
            "non_claim is not a single-line string",
        ),
        (
            lambda d: d.__setitem__(
                "non_claim", "no text reproduced" + "y" * MAX_FREE_TEXT
            ),
            "non_claim is not a single-line string",
        ),
        (
            lambda d: d.__setitem__("provenance", ["list"]),
            "provenance is not a single-line",
        ),
        (lambda d: d.__setitem__("schema", "attacker/v9"), "catalog schema"),
    ],
)
def test_catalog_free_text_is_bounded_under_a_repinned_digest(
    tmp_path, mutate, refusal
):
    path, digest = _repinned(tmp_path, mutate)
    with pytest.raises(CatalogIntegrityError, match=refusal):
        load_catalog(path, expected_sha256=digest)
