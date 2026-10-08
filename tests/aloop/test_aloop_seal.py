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
from autofde_lab.aloop.seal import (
    CommitClock,
    SealInputs,
    git_rev_list,
    git_witness,
    seal_document,
)
from autofde_lab.aloop.synth import (
    MUTANTS,
    POSITIVE_ITERATIONS,
    SECOND,
    T0,
    _event,
    _insert_before,
    _time_before,
    bind_commits,
    build_positive,
)
from autofde_lab.ocel.model import format_ns, parse_ns

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


def _commit_at(repo: Path, message: str, epoch_s: int) -> None:
    """A real commit whose committer (and author) clock is ``epoch_s``."""
    stamp = f"@{epoch_s} +0000"
    env = dict(
        os.environ,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_COMMITTER_DATE=stamp,
        GIT_AUTHOR_DATE=stamp,
    )
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=aloop-recorder",
            "-c", "user.email=aloop@example.invalid",
            "-c", "commit.gpgsign=false",
            "commit", "-q", "--allow-empty", "-m", message,
        ],
        capture_output=True, text=True, check=True, env=env,
    )  # fmt: skip


def _commit_event_seconds() -> list[int]:
    """Epoch seconds of the positive's commit events, in iteration order: the
    recorder dated each one by the commit it produced."""
    doc = build_positive()
    return [
        parse_ns(e["time"]) // SECOND for e in doc["events"] if e["type"] == "commit"
    ]


@pytest.fixture(scope="module")
def repo(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str, list[str], CommitClock]:
    """A real repository: a base commit at the synthetic epoch plus one commit
    per loop iteration, each committed at its commit event's time, and the git
    clock read back through :func:`git_witness`."""
    path = tmp_path_factory.mktemp("aloop-repo")
    _git(path, "init", "-q")
    _commit_at(path, "base", T0 // SECOND)
    base = _git(path, "rev-parse", "HEAD")
    seconds = _commit_event_seconds()
    assert len(seconds) == POSITIVE_ITERATIONS
    for i, when in enumerate(seconds):
        _commit_at(path, f"iteration {i}", when)
    shas, clock = git_witness(path, f"{base}..HEAD")
    assert shas == git_rev_list(path, f"{base}..HEAD")
    assert len(shas) == POSITIVE_ITERATIONS and clock.floor == T0 // SECOND
    assert [clock.times[s] for s in shas] == seconds
    return path, base, shas, clock


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
    clock: CommitClock | None = None,
) -> SealInputs:
    return SealInputs(
        ledger=ledger,
        keyring=_keyring(signer),
        commits=commits,
        human_messages=humans if humans is not None else [],
        key_material=(_key(signer),),
        commit_clock={"repo-1": clock} if clock is not None else None,
    )


def _bound(repo: tuple[Path, str, list[str]]) -> dict:
    _path, base, shas, _clock = repo
    return bind_commits(build_positive(), base, shas)


def _codes(receipt: dict) -> set[str]:
    return {r["code"] for r in receipt["refusals"]}


def test_sealed_complete_positive_qualifies(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans, clock=repo[3])
    )
    assert code == EXIT_REFUSED and receipt["verdict"] == "REFUSED"
    assert _codes(receipt) == {"SEAL_INCOMPLETE_HUMAN"}
    assert receipt["refusals"][0]["broken_term"] == "mu_on_O"
    # a pre-epoch message is still witnessed: omitting it is refused too (the
    # pre-t0 filter read t0 from the author's bytes -- court r9 repair, C2)
    early = [{"id": "msg-0", "time": format_ns(T0 + SECOND)}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, early, clock=repo[3])
    )
    assert code == EXIT_REFUSED and _codes(receipt) == {"SEAL_INCOMPLETE_HUMAN"}


def test_pre_epoch_goal_message_sealed_on_h_pre_qualifies(
    tmp_path, repo, signer
) -> None:
    """Control: the lawful goal channel -- a witnessed pre-t0 message sealed as
    the pre-epoch human.intervene at its witnessed time -- qualifies."""
    doc = _bound(repo)
    h_pre = _event(doc, "h-pre")
    h_pre["attributes"].append({"name": "messageId", "value": "msg-0"})
    log, ledger = _write(tmp_path, doc, signer)
    early = [{"id": "msg-0", "time": h_pre["time"]}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, early, clock=repo[3])
    )
    assert code == EXIT_QUALIFIED, receipt["refusals"]
    assert receipt["sealing"]["clock_anchored"] is True
    assert receipt["sealing"]["witnesses"]["human_messages"] == 1


def _shift_clock(doc: dict, delta_ns: int) -> dict:
    """Court attack C2: move every event time and every post-epoch attribute
    time by ``delta_ns`` -- the recorder signs whatever times it is handed."""
    for e in doc["events"]:
        e["time"] = format_ns(parse_ns(e["time"]) + delta_ns)
    for o in doc["objects"]:
        for a in o.get("attributes", ()):
            if "time" in a and parse_ns(a["time"]) > 0:
                a["time"] = format_ns(parse_ns(a["time"]) + delta_ns)
    return doc


DAY = 86_400 * SECOND


def test_clock_shift_hiding_mid_loop_message_is_refused(tmp_path, repo, signer) -> None:
    """C2: the whole log clock is shifted one day forward so a genuine mid-loop
    human message (omitted from the log) falls before the declared t0. The
    commit events no longer match git's committer clock: refused."""
    doc = _shift_clock(_bound(repo), DAY)
    log, ledger = _write(tmp_path, doc, signer)
    humans = [{"id": "m-mid", "time": format_ns(T0 + 50 * SECOND)}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans, clock=repo[3])
    )
    assert code == EXIT_REFUSED and receipt["verdict"] == "REFUSED", receipt
    assert {"SEAL_CLOCK_MISMATCH", "SEAL_INCOMPLETE_HUMAN"} <= _codes(receipt)
    assert receipt["sealing"]["complete"] is False
    assert receipt["sealing"]["clock_anchored"] is False
    # without the git clock the same log cannot be complete: never exit 0
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans)
    )
    assert code != EXIT_QUALIFIED and receipt["verdict"] != "QUALIFIED"


def test_clock_shift_with_message_sealed_pre_epoch_is_refused(
    tmp_path, repo, signer
) -> None:
    """C2 variant: the shifted log does seal the mid-loop message, at its true
    time, as a pre-epoch act -- the git clock still refuses the epoch."""
    doc = _shift_clock(_bound(repo), DAY)
    _decoy_human(doc, "e-start", "h-mid", "m-mid", "note-mid")
    _event(doc, "h-mid")["time"] = format_ns(T0 + 50 * SECOND)
    log, ledger = _write(tmp_path, doc, signer)
    humans = [{"id": "m-mid", "time": format_ns(T0 + 50 * SECOND)}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans, clock=repo[3])
    )
    assert code == EXIT_REFUSED, receipt
    assert "SEAL_CLOCK_MISMATCH" in _codes(receipt)


def test_epoch_declared_after_first_commit_is_refused(tmp_path, repo, signer) -> None:
    """Only episode.start moves (commit events keep git's clock): t0 later than
    the first witnessed commit is refused."""
    doc = _bound(repo)
    first = _event(doc, "e-commit-0")["time"]
    _event(doc, "e-start")["time"] = format_ns(parse_ns(first) + 1)
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, [], clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert "SEAL_CLOCK_MISMATCH" in _codes(receipt)


def test_epoch_before_base_commit_is_refused(tmp_path, repo, signer) -> None:
    doc = _bound(repo)
    _event(doc, "h-pre")["time"] = format_ns(T0 - 3 * SECOND)
    _event(doc, "e-start")["time"] = format_ns(T0 - 2 * SECOND)
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, [], clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert "SEAL_CLOCK_MISMATCH" in _codes(receipt)


def test_commit_event_off_git_clock_by_one_second_is_refused(
    tmp_path, repo, signer
) -> None:
    doc = _bound(repo)
    ev = _event(doc, "e-commit-50")
    ev["time"] = format_ns(parse_ns(ev["time"]) + SECOND)
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, [], clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert "SEAL_CLOCK_MISMATCH" in _codes(receipt)
    assert all(
        r["broken_term"] == "R_missing_identity"
        for r in receipt["refusals"]
        if r["code"] == "SEAL_CLOCK_MISMATCH"
    )


def test_human_ledger_over_unanchored_clock_is_never_complete(
    tmp_path, repo, signer
) -> None:
    """A non-empty human ledger with no git clock: the messages cannot be
    placed relative to an author-chosen t0, so the seal is not complete."""
    doc = _bound(repo)
    h_pre = _event(doc, "h-pre")
    h_pre["attributes"].append({"name": "messageId", "value": "msg-0"})
    log, ledger = _write(tmp_path, doc, signer)
    early = [{"id": "msg-0", "time": h_pre["time"]}]
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, early)
    )
    assert code == EXIT_NOT_QUALIFIED and receipt["verdict"] == CONSISTENT
    assert receipt["sealing"]["complete"] is None
    assert receipt["sealing"]["clock_anchored"] is False


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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans, clock=repo[3])
    )
    assert code == EXIT_NOT_QUALIFIED, receipt["refusals"]
    assert receipt["sealing"]["complete"] is True
    assert receipt["episodes"][0]["class"] == "ASSISTED"


def _decoy_human(doc: dict, before: str, eid: str, mid: str, out: str) -> None:
    """Insert a sealed human.intervene carrying ``mid`` just before ``before``,
    producing one unconsumed Evidence object (court attack A1b shape)."""
    doc["objects"].append(
        {"id": out, "type": "Evidence", "attributes": [], "relationships": []}
    )
    _insert_before(
        doc,
        before,
        {
            "id": eid,
            "type": "human.intervene",
            "time": _time_before(doc, before),
            "attributes": [
                {"name": "messageId", "value": mid},
                {"name": "basis", "value": "x"},
            ],
            "relationships": [
                {"objectId": "ep-1", "qualifier": "episode"},
                {"objectId": "hum-operator", "qualifier": "originAuthority"},
                {"objectId": out, "qualifier": "output"},
            ],
        },
    )


def _assert_human_relabel_refused(tmp_path, repo, signer, doc, humans) -> None:
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, humans, clock=repo[3])
    )
    assert code == EXIT_REFUSED and receipt["verdict"] == "REFUSED", receipt
    assert "SEAL_INCOMPLETE_HUMAN" in _codes(receipt)
    assert receipt["sealing"]["complete"] is False
    assert all(
        r["broken_term"] == "mu_on_O"
        for r in receipt["refusals"]
        if r["code"] == "SEAL_INCOMPLETE_HUMAN"
    )


def test_post_t0_message_on_inserted_pre_epoch_event_is_refused(
    tmp_path, repo, signer
) -> None:
    """A1b: a mid-loop human message is carried by a new human.intervene placed
    before episode.start (pre-epoch time) -- relabelled as goal supply."""
    doc = _bound(repo)
    _decoy_human(doc, "e-start", "h-decoy", "msg-7", "note-x")
    humans = [{"id": "msg-7", "time": format_ns(T0 + 50 * SECOND)}]
    _assert_human_relabel_refused(tmp_path, repo, signer, doc, humans)


def test_post_t0_message_relabelled_onto_h_pre_is_refused(
    tmp_path, repo, signer
) -> None:
    """A3: the existing pre-epoch goal act h-pre carries the messageId of a
    human message the external ledger dates inside the episode."""
    doc = _bound(repo)
    _event(doc, "h-pre")["attributes"].append({"name": "messageId", "value": "m1"})
    mid_time = _event(doc, "e-reobserve-50")["time"]
    _assert_human_relabel_refused(
        tmp_path, repo, signer, doc, [{"id": "m1", "time": mid_time}]
    )


def test_two_post_t0_messages_absorbed_by_h_pre_are_refused(
    tmp_path, repo, signer
) -> None:
    """A4: two post-t0 messages absorbed as extra messageIds on h-pre."""
    doc = _bound(repo)
    attrs = _event(doc, "h-pre")["attributes"]
    attrs.append({"name": "messageId", "value": "msg-a"})
    attrs.append({"name": "messageId", "value": "msg-b"})
    humans = [
        {"id": "msg-a", "time": format_ns(T0 + 50 * SECOND)},
        {"id": "msg-b", "time": format_ns(T0 + 70 * SECOND)},
    ]
    _assert_human_relabel_refused(tmp_path, repo, signer, doc, humans)


def test_post_t0_message_with_mismatched_time_is_refused(
    tmp_path, repo, signer
) -> None:
    """The sealed post-t0 human event exists but its time differs from the
    externally witnessed message time (backdated by one nanosecond)."""
    doc = _bound(repo)
    MUTANTS["human_after_epoch"][0](doc)
    human = _event(doc, "h-post-50")
    human["attributes"].append({"name": "messageId", "value": "msg-7"})
    witnessed = format_ns(parse_ns(human["time"]) + 1)
    _assert_human_relabel_refused(
        tmp_path, repo, signer, doc, [{"id": "msg-7", "time": witnessed}]
    )


def test_message_exactly_at_t0_must_be_sealed(tmp_path, repo, signer) -> None:
    """A5: a human message witnessed at exactly t0 is not pre-epoch goal
    supply; omitting it from the sealed log is refused."""
    doc = _bound(repo)
    t0 = next(e for e in doc["events"] if e["type"] == "episode.start")["time"]
    _assert_human_relabel_refused(
        tmp_path, repo, signer, doc, [{"id": "m2", "time": t0}]
    )


def test_commit_event_naming_unwitnessed_repository_is_refused(
    tmp_path, repo, signer
) -> None:
    """A4_unnamed_repo: every sealed commit event names a repository outside
    the witnessed set, and the witnessed range is empty -- the commits escape
    the rev-list bijection unless unwitnessed repositories are refused."""
    doc = _bound(repo)
    for o in doc["objects"]:
        if o["type"] == "Subject":
            for a in o["attributes"]:
                if a["name"] == "repository":
                    a["value"] = "repo-unnamed"
    log, ledger = _write(tmp_path, doc, signer)
    code, receipt = evaluate_path(log, seal=_inputs(ledger, signer, {"repo-1": []}))
    assert code == EXIT_REFUSED and receipt["verdict"] == "REFUSED"
    assert _codes(receipt) == {"SEAL_UNWITNESSED_COMMIT"}
    assert receipt["sealing"]["complete"] is False


def test_event_deleted_after_sealing_is_refused(tmp_path, repo, signer) -> None:
    doc = _bound(repo)
    MUTANTS["human_after_epoch"][0](doc)
    log, ledger = _write(tmp_path, doc, signer)
    edited = json.loads(log.read_text())
    edited["events"] = [e for e in edited["events"] if e["id"] != "h-post-50"]
    dump(edited, log)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}
    assert "hash chain is broken" in receipt["refusals"][0]["detail"]


def test_dropped_ledger_record_is_refused(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[:5] + lines[6:]) + "\n")
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}


def test_wrong_key_is_refused(tmp_path, repo, signer) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    other = AttestationSigner(os.urandom(32), key_id=KEY_ID)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, other, {"repo-1": repo[2]}, clock=repo[3])
    )
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_CHAIN_INVALID"}


def test_missing_commit_event_is_refused(tmp_path, repo, signer) -> None:
    """git has a commit no sealed actuate/commit/merge event produced."""
    path, base, shas, _clock = repo
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
    )
    assert code == EXIT_REFUSED
    assert _codes(receipt) == {"SEAL_INCOMPLETE_COMMIT"}
    assert "2 sealed commit events" in receipt["refusals"][0]["detail"]


def test_commit_claim_outside_witnessed_range_is_refused(
    tmp_path, repo, signer
) -> None:
    log, ledger = _write(tmp_path, _bound(repo), signer)
    code, receipt = evaluate_path(
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2][:-1]}, clock=repo[3])
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
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
        log, seal=_inputs(ledger, signer, {"repo-1": repo[2]}, clock=repo[3])
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


def test_cli_clock_shift_hiding_mid_loop_message_exits_two(
    tmp_path, repo, signer
) -> None:
    """C2 through the real CLI: ``--git`` reads the committer clock, so the
    shifted log is refused (exit 2), not QUALIFIED (exit 0 on f9a1fcd9)."""
    log, ledger = _write(tmp_path, _shift_clock(_bound(repo), DAY), signer)
    key_file = tmp_path / "recorder.key"
    key_file.write_text(_key(signer).hex())
    humans = tmp_path / "humans.json"
    humans.write_text(
        json.dumps([{"id": "m-mid", "time": format_ns(T0 + 50 * SECOND)}])
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    out = tmp_path / "receipt.json"
    proc = subprocess.run(
        [
            sys.executable, "-m", "autofde_lab.aloop", str(log),
            "--out", str(out),
            "--seal", str(ledger),
            "--key-file", str(key_file),
            "--key-id", KEY_ID,
            "--git", f"repo-1={repo[0]}:{repo[1]}..HEAD",
            "--human-ledger", str(humans),
        ],
        capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False,
    )  # fmt: skip
    assert proc.returncode == 2, proc.stderr
    receipt = json.loads(out.read_text())
    assert receipt["verdict"] == "REFUSED"
    assert "SEAL_CLOCK_MISMATCH" in _codes(receipt)
