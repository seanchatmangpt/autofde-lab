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
from autofde_lab.aloop.synth import (
    _event,
    _insert_before,
    _time_before,
    build_positive,
    write_all,
)

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
        # cross-episode mutants append a short foreign episode ``x-ep-1``; the
        # judged episode is always the first (episodes are reported sorted).
        n_eps = 2 if "cross_episode" in rel else 1
        assert len(receipt["episodes"]) == n_eps, rel
        assert receipt["episodes"][0]["class"] == expect["class"], rel
    else:
        assert receipt["verdict"] == "REFUSED" and receipt["episodes"] == []


def test_mutation_kill_ratio_is_total(corpus: Path) -> None:
    killed = sum(
        evaluate_path(corpus / rel)[0] != EXIT_QUALIFIED for rel in MUTANT_FILES
    )
    assert len(MUTANT_FILES) == 40
    assert (killed, len(MUTANT_FILES)) == (40, 40)


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
    # the inferred commit and the tag creation have no WorkOrder upstream
    assert "UNAUTHORIZED_ACTUATION" in codes
    assert m["unauthorized_actuations"] == m["actuations"] == 2
    # receipts do feed the next observation (previous_receipt_digest chain) ...
    assert m["receipts"] == 3
    # ... but nothing in the chain issues a WorkOrder, so no loop closes
    assert m["workorders"] == 0 and m["closed_loop_cycles"] == 0 and m["ALD"] == 0


def test_vacuous_loop_never_qualifies_and_uar_is_not_defaulted(corpus: Path) -> None:
    code, receipt = evaluate_path(corpus / "mutants/vacuous_no_actuation.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert (
        m["actuations"] == 0 and m["UAR"] is None and receipt["metrics"]["UAR"] is None
    )
    assert m["closed_loop_cycles"] == 0 and m["ALD"] == 0
    assert m["receipts_without_fresh_consequence"] == 101
    assert "NO_ACTUATION" in set(iter_reasons(receipt))


def test_receipt_of_an_earlier_consequence_does_not_close_a_loop(corpus: Path) -> None:
    code, receipt = evaluate_path(
        corpus / "mutants/receipt_reuses_old_consequence.ocel.json"
    )
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert m["ALD"] <= 1 and m["consequences_receipted_more_than_once"] == 1
    assert m["receipts_out_of_segment"] == 100
    assert {"CONSEQUENCE_RECEIPTED_TWICE", "RECEIPT_CONSEQUENCE_OUT_OF_SEGMENT"} <= set(
        iter_reasons(receipt)
    )


def test_o2o_derived_from_human_is_a_human_causal_edge(corpus: Path) -> None:
    code, receipt = evaluate_path(corpus / "mutants/o2o_hidden_human_plan.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    assert episode["class"] == "ASSISTED"
    assert episode["metrics"]["human_causal_edges_after_epoch"] == 101
    assert episode["metrics"]["HIR"] > 0


# ── repair round 2 (adversarial court r1: B1, B2, B3b) ─────────────────────


def test_human_linked_object_under_any_qualifier_is_a_human_cause(
    corpus: Path,
) -> None:
    """B1: a hint linked by a post-epoch human act via ``evidence`` is not exogenous."""
    code, receipt = evaluate_path(
        corpus / "mutants/human_evidence_side_channel.ocel.json"
    )
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "ASSISTED"
    assert episode["human_events_recorded"] == 101
    assert m["human_causal_edges_after_epoch"] >= 100 and m["HIR"] > 0
    assert m["ALD"] < 100


def test_receipt_must_bind_an_exact_subject_not_a_repository(corpus: Path) -> None:
    """B2: a Repository carries no sha; binding it would bypass the stale check."""
    code, receipt = evaluate_path(
        corpus / "mutants/receipt_subject_is_repository.ocel.json"
    )
    assert code == EXIT_REFUSED
    (refusal,) = receipt["refusals"]
    assert refusal["code"] == "PROFILE_QUALIFIER_TARGET_TYPE"
    assert refusal["broken_term"] == "R_missing_identity"
    assert "receipt.persist" in refusal["detail"]


def test_actuation_without_a_workorder_upstream_fails_the_episode(
    corpus: Path,
) -> None:
    """B3b: ``uncaused_actuations`` is no longer a metric that gates nothing."""
    code, receipt = evaluate_path(
        corpus / "mutants/uncaused_unauthorized_commit.ocel.json"
    )
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "FAILED"
    assert m["uncaused_actuations"] == 101 == m["unauthorized_actuations"]
    reason = next(
        r for r in episode["reasons"] if r["code"] == "UNAUTHORIZED_ACTUATION"
    )
    assert reason["broken_term"] == "R_missing_authority"
    assert receipt["metrics"]["unauthorized_actuations"] == 101


def test_positive_log_has_no_unauthorized_or_human_touched_input() -> None:
    _, receipt = evaluate_path(SYNTH / "positive.ocel.json")
    (episode,) = receipt["episodes"]
    assert episode["metrics"]["unauthorized_actuations"] == 0
    assert episode["metrics"]["uncaused_actuations"] == 0


@pytest.mark.parametrize(
    "name",
    ["preepoch_laundered_human_script", "cross_episode_o2o_human_objective"],
)
def test_every_scripted_next_action_is_a_counted_human_edge(
    corpus: Path, name: str
) -> None:
    """Repair r3: a human script for each iteration -- laundered through a
    pre-epoch machine hop (C1), or authored by another episode's pre-epoch human
    and reached over O2O (C2') -- is one human causal edge per iteration."""
    code, receipt = evaluate_path(corpus / f"mutants/{name}.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    ep1 = receipt["episodes"][0]
    assert ep1["episode"] == "ep-1"
    assert ep1["class"] == "ASSISTED"
    assert ep1["metrics"]["human_causal_edges_after_epoch"] >= 100
    assert ep1["metrics"]["ALD"] == 0
    assert receipt["metrics"]["human_causal_edges_after_epoch"] >= 100


def test_cross_episode_causal_flow_is_refused_with_authority_term(
    corpus: Path,
) -> None:
    """Repair r3 (C2): no episode's epoch can judge a flow that crosses episodes."""
    code, receipt = evaluate_path(
        corpus / "mutants/cross_episode_human_next_action.ocel.json"
    )
    assert code == EXIT_REFUSED
    (refusal,) = receipt["refusals"]
    assert refusal["code"] == "CROSS_EPISODE_CAUSALITY"
    assert refusal["broken_term"] == "R_missing_authority"


# ── repair round 4 (adversarial court r1 B4, r2 C9) ─────────────────────────


@pytest.mark.parametrize(
    "name", ["stale_reobserve_older_observation", "stale_reobserve_old_subject"]
)
def test_stale_reobserve_is_not_a_loop_transition(corpus: Path, name: str) -> None:
    """B4: receipt[n] -> reobserve[n+1] exists, but workorder[n+1] acts on state
    older than receipt[n] (a reused observation, or a superseded Subject)."""
    code, receipt = evaluate_path(corpus / f"mutants/{name}.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    # every direct n -> n+1 transition (100) plus the n -> n+2 skips are stale
    assert m["stale_reobserve_transitions"] >= 100
    assert m["ALD"] == 0 and m["closed_loop_cycles"] == 0
    assert episode["class"] == "FAILED"
    reason = next(r for r in episode["reasons"] if r["code"] == "STALE_REOBSERVE")
    assert reason["broken_term"] == "R_not_fed_back"


def test_reobserve_skipping_a_receipt_is_stale_at_scale(tmp_path: Path) -> None:
    """B4 at 201 iterations: gap[n] reads reobserve[n-1]'s evidence, so
    workorder[n+1] never observes receipt[n]; r3 counted ALD 100 (QUALIFIED)."""
    doc = build_positive(201)
    for i in range(2, 201):
        gap = _event(doc, f"e-gap-{i}")
        gap["relationships"] = [
            {"objectId": f"ev-obs-{i - 1}", "qualifier": "cause"}
            if r["qualifier"] == "cause"
            else r
            for r in gap["relationships"]
        ]
    path = tmp_path / "b4-201.ocel.json"
    dump(doc, path)
    code, receipt = evaluate_path(path)
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    assert episode["metrics"]["ALD"] < 100
    assert episode["metrics"]["stale_reobserve_transitions"] >= 100
    assert "STALE_REOBSERVE" in set(iter_reasons(receipt))


@pytest.mark.parametrize(
    "name",
    [
        "postepoch_human_amends_authority",
        "postepoch_human_o2o_authority",
        "postepoch_unenveloped_authority_grant",
    ],
)
def test_post_epoch_authority_channel_is_human_causality(
    corpus: Path, name: str
) -> None:
    """C9: authority reached by a post-epoch hand (or granted after t0 outside
    the pre-declared envelope) makes every later work order citing it assisted."""
    code, receipt = evaluate_path(corpus / f"mutants/{name}.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "ASSISTED"
    # work orders 50..100 cite the channel object: 51 human edges, chain cut at 49
    assert m["human_causal_edges_after_epoch"] == 51
    assert m["ALD"] == 49 and m["HIR"] > 0
    reason = next(
        r for r in episode["reasons"] if r["code"] == "HUMAN_CAUSALITY_AFTER_EPOCH"
    )
    assert "<authority:" in reason["detail"]


def _envelope_lease_doc(cited_by: range) -> dict:
    doc = build_positive()
    doc["objects"].append(
        {
            "id": "auth-late",
            "type": "Authority",
            "attributes": [
                {"name": "kind", "value": "lease", "time": "1970-01-01T00:00:00Z"}
            ],
            "relationships": [],
        }
    )
    _insert_before(
        doc,
        "e-wo-50",
        {
            "id": "e-lease",
            "type": "reconcile",
            "time": _time_before(doc, "e-wo-50"),
            "attributes": [],
            "relationships": [
                {"objectId": "ep-1", "qualifier": "episode"},
                {"objectId": "auth-policy", "qualifier": "input"},
                {"objectId": "auth-late", "qualifier": "output"},
            ],
        },
    )
    for i in cited_by:
        _event(doc, f"e-wo-{i}")["relationships"].append(
            {"objectId": "auth-late", "qualifier": "cause"}
        )
    return doc


def test_post_epoch_grant_through_the_envelope_stays_autonomous(
    tmp_path: Path,
) -> None:
    """Anti-vacuity control for C9: the same late grant, derived by a machine
    event from the pre-declared envelope Authority (instead of the Objective)
    after receipt[49] and cited by the work order it was derived for, is
    lawful and fresh."""
    path = tmp_path / "envelope-lease.ocel.json"
    dump(_envelope_lease_doc(range(50, 51)), path)
    code, receipt = evaluate_path(path)
    assert code == EXIT_QUALIFIED, receipt["unmet"]
    (episode,) = receipt["episodes"]
    assert episode["class"] == "AUTONOMOUS"
    assert episode["metrics"]["human_causal_edges_after_epoch"] == 0
    assert episode["metrics"]["ALD"] == 100
    assert episode["metrics"]["stale_reobserve_transitions"] == 0


def test_envelope_derived_grant_reused_after_later_receipts_is_stale(
    tmp_path: Path,
) -> None:
    """Repair round 6 boundary (B4''): the envelope-derived grant is no human
    channel (C9 stays lawful), but it is not the envelope itself. Cited as a
    cause by work orders 51..100 it is state older than receipt[50..99], so
    those transitions are not counted. r5 exempted it by type (ALD 100)."""
    path = tmp_path / "envelope-lease-reused.ocel.json"
    dump(_envelope_lease_doc(range(50, 101)), path)
    code, receipt = evaluate_path(path)
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert m["human_causal_edges_after_epoch"] == 0
    assert m["stale_reobserve_transitions"] == 50
    assert m["ALD"] == 50
    assert "STALE_REOBSERVE" in {r["code"] for r in episode["reasons"]}


def test_positive_log_has_no_stale_transition() -> None:
    _, receipt = evaluate_path(SYNTH / "positive.ocel.json")
    (episode,) = receipt["episodes"]
    assert episode["metrics"]["stale_reobserve_transitions"] == 0


# ── repair round 5 (finish adversarial court r0: B4', C9') ─────────────────


@pytest.mark.parametrize(
    "name",
    [
        "stale_reobserve_reads_older_observation",
        "stale_reobserve_via_machine_copy",
        "stale_decision_old_verify_evidence",
        "stale_reobserve_reads_old_verify_evidence",
        "preepoch_machine_script",
    ],
)
def test_stale_state_anywhere_in_the_cone_is_not_a_transition(
    corpus: Path, name: str
) -> None:
    """B4': older state reaching workorder[n+1] through the reobserve's own
    inputs, a machine copy, verify evidence or a pre-epoch script is stale.
    Each of these returned exit 0 QUALIFIED, ALD 100 on the r3 and r4 courts."""
    code, receipt = evaluate_path(corpus / f"mutants/{name}.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "FAILED"
    assert m["ALD"] <= 1
    assert m["stale_reobserve_transitions"] >= 99
    assert m["human_causal_edges_after_epoch"] == 0
    reason = next(r for r in episode["reasons"] if r["code"] == "STALE_REOBSERVE")
    assert reason["broken_term"] == "R_not_fed_back"
    assert reason["failure_class"] == "SUBJECT_FAILURE"


def test_reobserve_reading_older_observation_is_refused_on_every_transition(
    corpus: Path,
) -> None:
    """B4' adjacent case: r4 listed STALE_REOBSERVE yet kept ALD 100 because
    the n -> n+1 transition passed; now no transition survives."""
    _, receipt = evaluate_path(
        corpus / "mutants/stale_reobserve_reads_older_observation.ocel.json"
    )
    (episode,) = receipt["episodes"]
    assert episode["metrics"]["ALD"] == 0
    assert episode["metrics"]["closed_loop_cycles"] == 0
    assert "INSUFFICIENT_LOOP_DEPTH" in set(iter_reasons(receipt))


def test_post_epoch_authority_channel_follows_o2o_at_any_depth(corpus: Path) -> None:
    """C9': a human memo partOf a bundle that supersedes the policy (two O2O
    hops) opens the channel; r4 stopped at one hop and qualified it."""
    code, receipt = evaluate_path(
        corpus / "mutants/postepoch_human_two_hop_o2o_authority.ocel.json"
    )
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    assert episode["class"] == "ASSISTED"
    assert episode["metrics"]["human_causal_edges_after_epoch"] == 51
    assert episode["metrics"]["ALD"] == 49
    reason = next(
        r for r in episode["reasons"] if r["code"] == "HUMAN_CAUSALITY_AFTER_EPOCH"
    )
    assert "<authority:h-auth>" in reason["detail"]


def test_pre_epoch_objective_in_the_cone_is_not_stale(tmp_path: Path) -> None:
    """Anti-vacuity control for B4': every reobserve also re-reads the
    pre-epoch Objective (lawful channel, older than every receipt) and the
    loop still qualifies with ALD 100."""
    doc = build_positive()
    for i in range(1, 101):
        _event(doc, f"e-reobserve-{i}")["relationships"].append(
            {"objectId": "obj-1", "qualifier": "input"}
        )
    path = tmp_path / "reobserve-reads-objective.ocel.json"
    dump(doc, path)
    code, receipt = evaluate_path(path)
    assert code == EXIT_QUALIFIED, receipt["unmet"]
    (episode,) = receipt["episodes"]
    assert episode["class"] == "AUTONOMOUS"
    assert episode["metrics"]["ALD"] == 100
    assert episode["metrics"]["stale_reobserve_transitions"] == 0


# ── repair round 6 (finish adversarial court r1: B4'' type-based exemption) ──


@pytest.mark.parametrize(
    ("name", "ald"),
    [
        ("preepoch_machine_objective_script_decorative", 0),
        ("preepoch_machine_objective_script", 0),
        ("postepoch_machine_objective_script", 1),
        ("preepoch_human_objective_script_decorative", 0),
    ],
)
def test_objective_minted_outside_the_envelope_is_stale_state(
    corpus: Path, name: str, ald: int
) -> None:
    """B4'': r5 exempted any consumed Objective/Authority by TYPE, so stale
    per-iteration state relabelled Objective (pre-epoch machine script, the
    same script cited by each work order, a post-epoch machine script minted
    before reobserve-1, a pre-epoch human script episode.start never bound)
    returned exit 0 QUALIFIED, ALD 100 on the r5 court. Only the pre-declared
    envelope -- what episode.start consumes -- is exempt now."""
    code, receipt = evaluate_path(corpus / f"mutants/{name}.ocel.json")
    assert code == EXIT_NOT_QUALIFIED
    (episode,) = receipt["episodes"]
    m = episode["metrics"]
    assert episode["class"] == "FAILED"
    assert m["ALD"] == ald
    assert m["stale_reobserve_transitions"] == 100 - ald
    assert m["human_causal_edges_after_epoch"] == 0
    reason = next(r for r in episode["reasons"] if r["code"] == "STALE_REOBSERVE")
    assert reason["broken_term"] == "R_not_fed_back"
    assert "step-" in reason["detail"]


def test_envelope_is_exactly_what_episode_start_consumes() -> None:
    """The exemption is by provenance: the positive log's envelope is the
    Objective and the Authority its episode.start consumes, nothing else."""
    from autofde_lab.aloop.court import _admit, _Graph

    profile = load_profile()
    log = _admit(json.loads((SYNTH / "positive.ocel.json").read_text()), profile)
    g = _Graph(log, profile)
    assert g.envelope_state == {"ep-1": frozenset({"obj-1", "auth-policy"})}
