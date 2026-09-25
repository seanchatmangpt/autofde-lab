# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP sealed-recorder profile (court r9) -- Chicago style.

Real collaborators only: a real git repository built in ``tmp_path`` with
real commits (the commit completeness witness is real ``git rev-list``), a
real append-only ``ProvenanceLedger`` on disk signed with a random recorder
key that never enters the log, and the real CLI as a child process for exit
codes. No test doubles.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autofde_lab._cache.provenance import (
    AttestationKeyring,
    AttestationSigner,
    CacheAttestation,
    ProvenanceLedger,
)
from autofde_lab.aloop import (
    CONSISTENT,
    EXIT_NOT_QUALIFIED,
    EXIT_QUALIFIED,
    EXIT_REFUSED,
    evaluate_path,
)
from autofde_lab.aloop.court import REPO_ROOT
from autofde_lab.aloop.ocel_builder import dump
from autofde_lab.aloop.seal import SealInputs, git_rev_list, seal_document
from autofde_lab.aloop.synth import (
    MUTANTS,
    POSITIVE_ITERATIONS,
    SECOND,
    T0,
    bind_commits,
    build_positive,
)
from autofde_lab.ocel.model import format_ns

KEY_ID = "aloop-recorder-test"


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=aloop-recorder",
            "-c",
            "user.email=aloop@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout.strip()


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, list[str]]:
    """A real repository: a base commit plus one commit per loop iteration."""
    path = tmp_path_factory.mktemp("aloop-repo")
    _git(path, "init", "-q")
    _git(path, "commit", "-q", "--allow-empty", "-m", "base")
    base = _git(path, "rev-parse", "HEAD")
    for i in range(POSITIVE_ITERATIONS):
        _git(path, "commit", "-q", "--allow-empty", "-m", f"iteration {i}")
    shas = git_rev_list(path, f"{base}..HEAD")
    assert len(shas) == POSITIVE_ITERATIONS
    return path, base, shas


@pytest.fixture
def signer() -> AttestationSigner:
    return AttestationSigner(os.urandom(32), key_id=KEY_ID)


def _keyring(signer: AttestationSigner) -> AttestationKeyring:
    return AttestationKeyring((signer,))


def _key(signer: AttestationSigner) -> bytes:
    return signer._key  # the recorder's own key, held by the verifier here


def _write(tmp: Path, doc: dict, signer: AttestationSigner) -> tuple[Path, Path]:
    log = tmp / "log.ocel.json"
    dump(doc, log)
    ledger = seal_document(json.loads(log.read_bytes()), tmp / "log.seal.jsonl", signer)
    return log, ledger


def _inputs(
    ledger: Path,
    signer: AttestationSigner,
    commits: dict | None,
    humans: list | None = None,
) -> SealInputs:
    return SealInputs(
        ledger=ledger,
        keyring=_keyring(signer),
        commits=commits,
        human_messages=humans if humans is not None else [],
        key_material=(_key(signer),),
    )


def _bound(repo: tuple[Path, str, list[str]]) -> dict:
    _path, base, shas = repo
    return bind_commits(build_positive(), base, shas)


def _codes(receipt: dict) -> set[str]:
    return {r["code"] for r in receipt["refusals"]}


def test_sealed_complete_positive_qualifies(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_QUALIFIED, (receipt.get("refusals"), receipt.get("unmet"))
    assert receipt["verdict"] == "QUALIFIED" and receipt["rules_consistent"]
    (episode,) = receipt["episodes"]
    assert episode["class"] == "AUTONOMOUS" and episode["metrics"]["ALD"] == 100
    s = receipt["sealing"]
    assert s["sealed"] is True and s["complete"] is True
    assert s["records"] == len(json.loads(log.read_text())["events"]) + 1
    assert s["witnesses"] == {"commits": {"repo-1": 101}, "human_messages": 0}


def test_cli_sealed_complete_exits_zero_unsealed_exits_three(
    tmp_path, repo, signer
) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    key_file = tmp_path / "recorder.key"
    key_file.write_text(_key(signer).hex())
    humans = tmp_path / "humans.json"
    humans.write_text("[]")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    def cli(*extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "autofde_lab.aloop", str(log), *extra],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
            check=False,
        )

    sealed = cli(
        "--out", str(tmp_path / "sealed.json"),
        "--seal", str(ledger),
        "--key-file", str(key_file),
        "--key-id", KEY_ID,
        "--git", f"repo-1={repo[0]}:{repo[1]}..HEAD",
        "--human-ledger", str(humans),
    )  # fmt: skip
    assert sealed.returncode == 0, sealed.stderr
    assert json.loads((tmp_path / "sealed.json").read_text())["verdict"] == "QUALIFIED"
    unsealed = cli("--out", str(tmp_path / "unsealed.json"))
    assert unsealed.returncode == 3, unsealed.stderr
    receipt = json.loads((tmp_path / "unsealed.json").read_text())
    assert receipt["verdict"] == CONSISTENT
    assert receipt["episodes"][0]["class"] == CONSISTENT
    # sealed, but no completeness witness: still only consistent
    unwitnessed = cli(
        "--out", str(tmp_path / "unwitnessed.json"),
        "--seal", str(ledger), "--key-file", str(key_file), "--key-id", KEY_ID,
    )  # fmt: skip
    assert unwitnessed.returncode == 3, unwitnessed.stderr
    r = json.loads((tmp_path / "unwitnessed.json").read_text())
    assert r["verdict"] == CONSISTENT
    assert r["sealing"]["sealed"] is True and r["sealing"]["complete"] is None
    assert "complete against external witnesses" in r["claim"]


def test_omitted_human_event_is_refused(tmp_path, repo, signer) -> None:
    """The out-of-band human ledger has a message after t0; the sealed log has
    no human.intervene carrying it -- the omission is observed, not assumed."""
    log, ledger = _write(tmp_path, _bound(repo), signer)
    humans = [{"id": "msg-7", "time": format_ns(T0 + 50 * SECOND)}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans)
    )
    assert code == EXIT_REFUSED and receipt["verdict"] == "REFUSED"
    assert _codes(receipt) == {"SEAL_INCOMPLETE_HUMAN"}
    assert receipt["refusals"][0]["broken_term"] == "mu_on_O"
    # a message before t0 is the lawful goal channel: not required in the log
    early = [{"id": "msg-0", "time": format_ns(T0 + SECOND)}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, early)
    )
    assert code == EXIT_QUALIFIED, receipt["refusals"]


def test_recorded_human_event_is_sealed_but_assisted(tmp_path, repo, signer) -> None:
    """Control: when the post-t0 human message IS sealed in the log, the seal
    is complete and the rules judge it -- ASSISTED, not QUALIFIED."""
    doc = _bound(repo)
    MUTANTS["human_after_epoch"][0](doc)
    human = next(e for e in doc["events"] if e["id"] == "h-post-50")
    human["attributes"].append({"name": "messageId", "value": "msg-7"})
    log, ledger = _write(tmp_path, doc, signer)
    humans = [{"id": "msg-7", "time": human["time"]}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans)
    )
    assert code == EXIT_NOT_QUALIFIED, receipt["refusals"]
    assert receipt["sealing"]["complete"] is True
    assert receipt["episodes"][0]["class"] == "ASSISTED"


def test_event_deleted_after_sealing_is_refused(tmp_path, repo, signer) -> None:
    doc = _bound(repo)
    MUTANTS["human_after_epoch"][0](doc)
    log, ledger = _write(tmp_path, doc, signer)
    edited = json.loads(log.read_text())
    edited["events"] = [e for e in edited["events"] if e["id"] != "h-post-50"]
    dump(edited, log)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_BIJECTION"}


def test_object_edited_after_sealing_is_refused(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    edited = json.loads(log.read_text())
    goal = next(o for o in edited["objects"] if o["id"] == "obj-1")
    goal.setdefault("attributes", []).append(
        {"name": "description", "value": "rewritten", "time": format_ns(0)}
    )
    dump(edited, log)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert "close digest" in receipt["refusals"][0]["detail"]


def test_forged_chain_is_refused(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    lines = ledger.read_text().splitlines()
    record = json.loads(lines[10])
    record["previous_digest"] = "0" * 64
    lines[10] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    ledger.write_text("\n".join(lines) + "\n")
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}
    assert "hash chain is broken" in receipt["refusals"][0]["detail"]


def test_dropped_ledger_record_is_refused(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[:5] + lines[6:]) + "\n")
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}


def test_wrong_key_is_refused(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    other = AttestationSigner(os.urandom(32), key_id=KEY_ID)
    code, receipt = evaluate_path(log, seal=_inputs(ledger, other, {"repo-1": repo[2]}))
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}
    assert "signature mismatch" in receipt["refusals"][0]["detail"]


def test_resealed_by_author_with_other_key_is_refused(tmp_path, repo, signer) -> None:
    """The judged author re-seals an edited log under its own key: the
    verifier's recorder key does not verify it."""
    doc = _bound(repo)
    MUTANTS["human_after_epoch"][0](doc)
    doc["events"] = [e for e in doc["events"] if e["id"] != "h-post-50"]
    author = AttestationSigner(os.urandom(32), key_id=KEY_ID)
    log, ledger = _write(tmp_path, doc, author)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}


def test_missing_commit_event_is_refused(tmp_path, repo, signer) -> None:
    """git has a commit no sealed actuate/commit/merge event produced."""
    path, base, shas = repo
    log, ledger = _write(tmp_path, _bound(repo), signer)
    extra = shas + ["f" * 40]
    code, receipt = evaluate_path(log, seal=_inputs(ledger, signer, {"repo-1": extra}))
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_INCOMPLETE_COMMIT"}
    assert receipt["refusals"][0]["broken_term"] == "R_missing_consequence"


def test_missing_commit_event_real_git_is_refused(tmp_path, signer) -> None:
    """Same, witnessed by real git: one commit more than sealed events."""
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "commit", "-q", "--allow-empty", "-m", "base")
    base = _git(path, "rev-parse", "HEAD")
    for i in range(POSITIVE_ITERATIONS + 1):
        _git(path, "commit", "-q", "--allow-empty", "-m", f"c{i}")
    shas = git_rev_list(path, f"{base}..HEAD")
    doc = bind_commits(build_positive(), base, shas[:POSITIVE_ITERATIONS])
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log,
        seal=_inputs(ledger, signer, {"repo-1": git_rev_list(path, f"{base}..HEAD")}),
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_INCOMPLETE_COMMIT"}
    assert shas[-1] in receipt["refusals"][0]["detail"]


def test_duplicated_commit_event_is_refused(tmp_path, repo, signer) -> None:
    doc = _bound(repo)
    i = next(n for n, e in enumerate(doc["events"]) if e["id"] == "e-commit-50")
    dup = copy.deepcopy(doc["events"][i])
    dup["id"] = "e-commit-50-dup"
    doc["events"].insert(i + 1, dup)
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_INCOMPLETE_COMMIT"}
    assert "2 sealed commit events" in receipt["refusals"][0]["detail"]


def test_commit_claim_outside_witnessed_range_is_refused(
    tmp_path, repo, signer
) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2][:-1]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_UNWITNESSED_COMMIT"}


def test_recorder_key_inside_the_log_is_refused(tmp_path, repo, signer) -> None:
    doc = _bound(repo)
    goal = next(o for o in doc["objects"] if o["id"] == "obj-1")
    goal.setdefault("attributes", []).append(
        {"name": "description", "value": _key(signer).hex(), "time": format_ns(0)}
    )
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_KEY_DISCLOSED"}


@pytest.mark.parametrize(
    "mutant",
    [
        "envelope_human_script_into_actuate",
        "envelope_multikey_script",
        "attribute_change_after_human",
        "unattributed_attribute_change",
    ],
)
def test_sealed_k_mutant_still_fails_the_rules(tmp_path, repo, signer, mutant) -> None:
    """Sealing certifies recorder authorship and completeness, not the rules:
    a sealed, complete K-mutant is still NOT_QUALIFIED."""
    doc = _bound(repo)
    MUTANTS[mutant][0](doc)
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]})
    )
    assert code == EXIT_NOT_QUALIFIED, receipt["refusals"]
    assert receipt["sealing"]["complete"] is True
    assert receipt["rules_consistent"] is False


def test_provenance_ledger_default_record_type_unchanged(tmp_path, signer) -> None:
    """The generalization keeps the cache ledger's own record type working."""
    ledger = ProvenanceLedger(tmp_path / "cache.jsonl", signer=signer, fsync=False)
    att = CacheAttestation(
        subject_id="s", namespace="n", method="m", key_digest="k",
        value_digest=None, disposition="hit", policy_digest="p",
        release_id="r", model_fingerprint="mf", data_fingerprint="df",
        rollout_reason="x", rollout_cohort=None, observed_at=1.5, owner="o",
    )  # fmt: skip
    ledger.append(att)
    ledger.append(att)
    check = ledger.verify()
    assert check.valid and check.records == 2
