# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP metrics calculator -- Chicago style: real logs, real subprocesses.

Every verdict below comes from the real court over real bytes on disk; the
CLI is exercised as a child process so exit codes are observed, not assumed.
The mutant battery is regenerated per :func:`autofde_lab.aloop.synth.write_all`
(the mutants are never committed) and every fixture's sha256 is checked
against ``SOURCES.json`` before use -- a silently edited fixture must fail
here, not pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autofde_lab.aloop.metrics import (
    load_document,
    score_corpus,
    score_log,
    semantic_divergence,
    semantic_signature,
    to_ndjson,
    wilson,
)
from autofde_lab.aloop.ocel_builder import dump
from autofde_lab.aloop.stats import add_stats, run_trials
from autofde_lab.aloop.synth import build_positive

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SYNTH_POSITIVE = HERE / "fixtures" / "synthetic" / "positive.ocel.json"
FIXTURES = REPO_ROOT / "benchmarks" / "aloop" / "fixtures"
SCENARIOS = REPO_ROOT / "benchmarks" / "aloop" / "scenarios"
SOURCES = json.loads((FIXTURES / "SOURCES.json").read_text())


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "autofde_lab.aloop.score", *args],
        capture_output=True,
        text=True,
        env=_env(),
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(scope="module", autouse=True)
def _fixtures_intact() -> None:
    """The RECONSTRUCTED corpus must be byte-identical to its SOURCES.json."""
    for name, meta in SOURCES["files"].items():
        data = (FIXTURES / name).read_bytes()
        assert (
            hashlib.sha256(data).hexdigest() == meta["sha256"]
        ), f"{name} was edited; regenerate with generate_fixtures.py"
        assert meta.get("note", "").endswith("RECONSTRUCTED") or "RECONSTRUCTED" in meta.get("note", "")


def test_positive_fixture_invariants() -> None:
    score = score_log(SYNTH_POSITIVE)
    assert score["verdict"] == "QUALIFIED"
    m = score["metrics"]
    assert m["HIR"] == 0.0
    assert m["ALD"] >= 100
    assert m["UAR"] == 0.0
    assert m["DCR"] == 0.0
    assert m["OCR"] == 0.0
    assert m["CRR"] == 1.0  # the crash window at iteration 40 is machine-reconciled
    assert m["PSR"] == 1.0  # provider extinction at 70 is machine-substituted
    assert m["RPR"] == 1.0  # cold replay: same bytes -> same sealed verdict


def test_ndjson_roundtrip_metric_equivalence(tmp_path: Path) -> None:
    doc, fmt, raw = load_document(SYNTH_POSITIVE)
    assert fmt == "ocel2-json"
    nd = tmp_path / "positive.ocel.ndjson"
    nd.write_bytes(to_ndjson(doc))
    a = score_log(SYNTH_POSITIVE, cold_replay=False)
    b = score_log(nd, cold_replay=False)
    assert b["format"] == "ocel2-ndjson"
    for key in ("HIR", "ALD", "LCR", "RR", "UAR", "PSR", "CRR", "DCR", "OCR"):
        assert a["metrics"][key] == b["metrics"][key], key


def test_committed_fixture_classes() -> None:
    positive = score_log(FIXTURES / "positive-60.ocel.ndjson")
    human = score_log(FIXTURES / "human-after-epoch-60.ocel.ndjson")
    cron = score_log(FIXTURES / "fixed-task-cron-30.ocel.ndjson")
    assert positive["episodes"][0]["class"] == "AUTONOMOUS"
    assert positive["metrics"]["CRR"] == 1.0
    # negative controls, witnessed on the committed bytes:
    assert human["episodes"][0]["class"] == "ASSISTED"
    assert human["metrics"]["HIR"] > 0.0
    assert cron["episodes"][0]["class"] == "FAILED"
    assert "AUTOMATION_NOT_AUTONOMY" in cron["episodes"][0]["reason_codes"]


def test_corpus_mutation_battery_and_controls() -> None:
    report = score_corpus()  # regenerated into a temp dir, never committed
    assert report["MKR"]["executed"] == 15
    assert report["MKR"]["value"] == 1.0, [
        k for k, v in report["files"].items() if not v["killed"]
    ]
    assert all(report["negative_controls"].values())


def test_pdr_provider_invariance_and_sensitivity(tmp_path: Path) -> None:
    renamed = score_log(FIXTURES / "provider-renamed-20.ocel.ndjson")
    plain_path = tmp_path / "plain-20.ocel.json"
    dump(build_positive(iterations=20), plain_path)
    plain = score_log(plain_path)
    assert semantic_divergence(semantic_signature(renamed), semantic_signature(plain)) == 0.0

    human_doc = build_positive(iterations=60)
    from autofde_lab.aloop.synth import m_human_after_epoch

    m_human_after_epoch(human_doc)
    human_path = tmp_path / "human-60.ocel.json"
    dump(human_doc, human_path)
    human = score_log(human_path)
    positive = score_log(FIXTURES / "positive-60.ocel.ndjson")
    assert semantic_divergence(semantic_signature(positive), semantic_signature(human)) > 0.0


def test_trials_report_distributions_and_standing() -> None:
    board = add_stats(run_trials([20260925, 20260926]))
    assert board["standing"] == "ALIVE"
    assert all(board["invariants"].values())
    assert all(board["negative_controls"].values())
    ald = board["statistics"]["ALD"]["across_logs"]
    assert ald["n"] == 2
    assert all(v >= 100 for v in ald["values"])  # court qualification floor
    assert board["statistics"]["MKR"]["wilson95"] is not None
    assert board["statistics"]["MKR"]["wilson95"][0] > 0.0


def test_wilson_interval_sanity() -> None:
    assert wilson(0, 0) is None
    lo, hi = wilson(0, 100)
    assert lo < 0.001 and hi < 0.05
    lo, hi = wilson(100, 100)
    assert lo > 0.95 and hi == 1.0
    assert wilson(7, 15)[0] < 7 / 15 < wilson(7, 15)[1]


def test_cli_validate_manifests() -> None:
    proc = _cli("validate-manifests", str(SCENARIOS))
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["all_valid"] is True
    assert len(report["manifests"]) == 10


def test_cli_score_and_corpus_exit_codes(tmp_path: Path) -> None:
    # corpus battery: all invariants hold -> exit 0
    out_corpus = tmp_path / "corpus.json"
    proc = _cli("corpus", "--out", str(out_corpus))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out_corpus.read_text())["MKR"]["value"] == 1.0
    # the 60-iteration demo fixture scores but cannot qualify ALOOP-001
    # (ALD 59 < 100) and carries no mutant battery -> typed exit 1
    out_score = tmp_path / "score.json"
    proc = _cli("score", str(FIXTURES / "positive-60.ocel.ndjson"), "--no-corpus",
                "--out", str(out_score))
    assert proc.returncode == 1
    board = json.loads(out_score.read_text())
    assert board["log_results"][0]["episodes"][0]["class"] == "AUTONOMOUS"
    assert board["invariants"]["UAR_zero"] and board["invariants"]["DCR_zero"]
