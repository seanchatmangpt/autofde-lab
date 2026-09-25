# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP-001 court -- Chicago style: real OCEL files on disk, real subprocesses.

No test doubles: every verdict below is computed by the real court over the
exact committed bytes of a fixture, and the CLI is exercised as a real child
process so exit codes are observed, not assumed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autofde_lab.aloop import (
    EXIT_NOT_QUALIFIED,
    EXIT_QUALIFIED,
    EXIT_REFUSED,
    AloopRefusal,
    evaluate_path,
    load_profile,
)
from autofde_lab.aloop.chatman_trace import convert
from autofde_lab.aloop.court import REPO_ROOT, iter_reasons
from autofde_lab.aloop.ocel_builder import dump
from autofde_lab.aloop.synth import write_all

HERE = Path(__file__).resolve().parent
SYNTH = HERE / "fixtures" / "synthetic"
REAL = HERE / "fixtures" / "chatman_root_crown_v26_9_25"
REAL_LOG = REAL / "chatman-root-crown-v26.9.25.ocel.json"
REAL_RECEIPT = (
    REPO_ROOT / "docs" / "rfcs" / "aloop" / "ALOOP-001-chatman-root-crown-v26.9.25.json"
)
MANIFEST = json.loads((SYNTH / "MANIFEST.json").read_text())
MUTANT_FILES = sorted(k for k in MANIFEST["files"] if k.startswith("mutants/"))


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "autofde_lab.aloop", *args],
        capture_output=True,
        text=True,
        env=_env(),
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The full synthetic corpus, regenerated as real files on disk."""
    out = tmp_path_factory.mktemp("aloop-corpus")
    write_all(out)
    return out


def test_synthetic_corpus_regenerates_byte_identical(corpus: Path) -> None:
    assert json.loads((corpus / "MANIFEST.json").read_text()) == MANIFEST
    assert (corpus / "positive.ocel.json").read_bytes() == (
        SYNTH / "positive.ocel.json"
    ).read_bytes()
    for rel, entry in MANIFEST["files"].items():
        data = (corpus / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], rel


def test_positive_closed_loop_qualifies() -> None:
    code, receipt = evaluate_path(SYNTH / "positive.ocel.json")
    assert code == EXIT_QUALIFIED
    assert receipt["verdict"] == "QUALIFIED"
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "AUTONOMOUS"
    assert m["consecutive_self_generated_transitions"] >= 100
    assert m["ALD"] == 100
    assert m["HIR"] == 0.0 and m["UAR"] == 0.0
    assert m["PSR"] == 1.0 and m["RR"] == 1.0
    assert m["human_causal_edges_after_epoch"] == 0
    # the pre-epoch human goal/policy grant is recorded, not hidden
    assert episode["human_events_recorded"] == 1
    assert receipt["standing"] == "PARTIAL_ALIVE"


@pytest.mark.parametrize("rel", MUTANT_FILES)
def test_each_mutant_is_refused_or_downgraded(corpus: Path, rel: str) -> None:
    expect = MANIFEST["files"][rel]["expect"]
    code, receipt = evaluate_path(corpus / rel)
    assert code == expect["exit"], (rel, receipt.get("refusals"), receipt.get("unmet"))
    assert code != EXIT_QUALIFIED
    assert expect["code"] in set(iter_reasons(receipt)), rel
    if expect["class"] is not None:
        assert [ep["class"] for ep in receipt["episodes"]] == [expect["class"]]
    else:
        assert receipt["verdict"] == "REFUSED" and receipt["episodes"] == []


def test_mutation_kill_ratio_is_total(corpus: Path) -> None:
    killed = sum(
        evaluate_path(corpus / rel)[0] != EXIT_QUALIFIED for rel in MUTANT_FILES
    )
    assert (killed, len(MUTANT_FILES)) == (14, 14)


def test_empty_log_is_refused_not_vacuously_qualified(tmp_path: Path) -> None:
    empty = tmp_path / "empty.ocel.json"
    dump({"objectTypes": [], "eventTypes": [], "objects": [], "events": []}, empty)
    code, receipt = evaluate_path(empty)
    assert code == EXIT_REFUSED
    assert receipt["refusals"][0]["code"] == "OCEL_ADMISSION:EmptyEventObjectLinks"


def test_non_json_bytes_are_refused(tmp_path: Path) -> None:
    junk = tmp_path / "junk.ocel.json"
    junk.write_bytes(b"\x00not json")
    code, receipt = evaluate_path(junk)
    assert code == EXIT_REFUSED
    assert receipt["refusals"][0]["code"] == "OCEL2_SCHEMA_VIOLATION"


def test_profile_pin_mismatch_is_refused(tmp_path: Path) -> None:
    profile = json.loads(
        (REPO_ROOT / "schemas/aloop/ocel2-aloop-profile.json").read_text()
    )
    profile["base_schema"]["sha256"] = "0" * 64
    tampered = tmp_path / "profile.json"
    tampered.write_text(json.dumps(profile))
    with pytest.raises(AloopRefusal) as info:
        load_profile(tampered)
    assert info.value.code == "BASE_SCHEMA_PIN_MISMATCH"


def test_cli_exit_codes_and_cold_replay_are_byte_identical(
    corpus: Path, tmp_path: Path
) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    first = _cli(str(SYNTH / "positive.ocel.json"), "--out", str(a))
    second = _cli(str(SYNTH / "positive.ocel.json"), "--out", str(b))
    assert (first.returncode, second.returncode) == (0, 0), first.stderr
    assert a.read_bytes() == b.read_bytes()
    assert (
        _cli(
            str(corpus / "mutants/fixed_task_cron.ocel.json"), "--out", str(a)
        ).returncode
        == 3
    )
    assert (
        _cli(
            str(corpus / "mutants/cause_from_future.ocel.json"), "--out", str(a)
        ).returncode
        == 2
    )


def test_real_trace_sources_are_the_committed_bytes() -> None:
    sources = json.loads((REAL / "SOURCES.json").read_text())["files"]
    assert len(sources) == 9
    for rel, entry in sources.items():
        assert (
            hashlib.sha256((REAL / rel).read_bytes()).hexdigest() == entry["sha256"]
        ), rel
        assert entry["locator"].startswith(
            "git:seanchatmangpt/chatman-ecosystem@c599667a84ec79d832bb779bce1730b33b43fdd4:"
        )


def test_real_trace_conversion_is_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "trace.ocel.json"
    dump(convert(REAL), out)
    assert out.read_bytes() == REAL_LOG.read_bytes()


def test_real_trace_committed_receipt_replays() -> None:
    committed = json.loads(REAL_RECEIPT.read_text())
    code, receipt = evaluate_path(REAL_LOG, log_locator=committed["log"]["locator"])
    assert receipt == committed
    assert code == EXIT_NOT_QUALIFIED == committed["exit_code"]


def test_real_trace_verdict_is_automation_not_autonomy() -> None:
    _, receipt = evaluate_path(REAL_LOG)
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "FAILED"
    codes = [r["code"] for r in episode["reasons"]]
    assert "AUTOMATION_NOT_AUTONOMY" in codes
    assert "UNRECEIPTED_ACTUATION" in codes
    assert "HUMAN_CAUSALITY_AFTER_EPOCH" in codes
    # receipts do feed the next observation (previous_receipt_digest chain) ...
    assert m["receipts"] == 3
    # ... but nothing in the chain issues a WorkOrder, so no loop closes
    assert m["workorders"] == 0 and m["closed_loop_cycles"] == 0 and m["ALD"] == 0
