# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago suites closing AFDE-2601 and AFDE-2602 (docs/jira/v26.9.15).

AFDE-2601: initial product state must derive from the *latest* CI
verification evidence, not from failure-anywhere-in-history -- an old
failure followed by a green verification must yield ``repo_clean``.

AFDE-2602: ``run_tests`` declares both FOND successors (``tests_pass`` /
``tests_fail``); the simulator's outcome selection is an explicit
``outcome_oracle`` parameter, and the fail successor must actually be
reachable (adversarial + alternate modes), never a hidden sort bias.
"""

from __future__ import annotations

import pytest
from gymact.models import ActuationIntent

from autofde_lab.agent.autodev_domain import (
    build_autodev_hddl_domain,
    extract_initial_product_state,
)
from autofde_lab.agent.autodev_gymact_env import AutoDevGymActEnvironment
from autofde_lab.cmca.bcinr_bridge import find_bcinr_cli
from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import OcelEvent
from autofde_lab.planning.fond_hddl_product import ProductState


def _log(activities_with_ts: list[tuple[str, int]]) -> OcelLog:
    return OcelLog(
        events=tuple(
            OcelEvent(id=f"e{i}", activity=a, timestamp_ns=ts)
            for i, (a, ts) in enumerate(activities_with_ts)
        )
    )


class TestAFDE2601LatestEvidence:
    def test_old_failure_then_green_verification_is_clean(self):
        """The ticket's falsifier: one historical failure must not poison
        the state once newer evidence is green."""
        log = _log(
            [
                ("git_commit", 1),
                ("ci_verification_failed", 2),
                ("git_commit", 3),
                ("ci_verification_passed", 4),
            ]
        )
        state = extract_initial_product_state(log)
        assert "repo_clean" in state.world
        assert "test_failing" not in state.world

    def test_latest_failure_when_failure_is_newest_evidence(self):
        log = _log(
            [
                ("ci_verification_passed", 1),
                ("ci_verification_failed", 2),
            ]
        )
        state = extract_initial_product_state(log)
        assert "test_failing" in state.world
        assert "repo_clean" not in state.world

    def test_timestamps_order_evidence_not_log_position(self):
        """Later timestamp wins even when it appears earlier in the tuple."""
        log = _log(
            [
                ("ci_verification_failed", 90),
                ("ci_verification_passed", 10),
            ]
        )
        state = extract_initial_product_state(log)
        assert "test_failing" in state.world

    def test_no_verification_evidence_presumes_clean(self):
        state = extract_initial_product_state(_log([("git_commit", 1)]))
        assert "repo_clean" in state.world


class TestAFDE2602OutcomeOracle:
    """Environment-level FOND successor reachability proofs."""

    @staticmethod
    def _run_tests_env(oracle: str) -> AutoDevGymActEnvironment:
        domain = build_autodev_hddl_domain()
        initial = ProductState(world=frozenset({"code_modified"}), tau=("run_tests",))
        env = AutoDevGymActEnvironment(
            domain=domain, initial_state=initial, outcome_oracle=oracle
        )
        cap = next(c for c in env.capabilities() if c.binding == "run_tests")
        env.actuate(ActuationIntent(capability=cap.iri, episode_id=env.episode_id))
        return env

    def test_reference_oracle_takes_pass_successor(self):
        env = self._run_tests_env("reference")
        assert "tests_pass" in env.current_state.world

    def test_adversarial_oracle_reaches_fail_successor(self):
        """The ticket's falsifier: the declared fail edge is reachable."""
        env = self._run_tests_env("adversarial")
        assert "tests_fail" in env.current_state.world
        assert "test_failing" in env.current_state.world

    def test_alternate_oracle_reaches_both_declared_successors(self):
        """Alternate mode rotates through every declared successor: the
        first visit takes the declared-first outcome, the second visit the
        other. tau consumes the action head per execution, so the second
        visit is materialized as a fresh episode whose per-action cycle is
        seeded to 1 -- exactly the state a repeated execution reaches."""
        domain = build_autodev_hddl_domain()
        initial = ProductState(world=frozenset({"code_modified"}), tau=("run_tests",))

        seen: set[str] = set()
        for cycle_seed in (0, 1):
            env = AutoDevGymActEnvironment(
                domain=domain, initial_state=initial, outcome_oracle="alternate"
            )
            env._outcome_cycle["run_tests"] = cycle_seed
            cap = next(c for c in env.capabilities() if c.binding == "run_tests")
            env.actuate(ActuationIntent(capability=cap.iri, episode_id=env.episode_id))
            seen |= {
                "tests_pass"
                if "tests_pass" in env.current_state.world
                else "tests_fail"
            }
        assert seen == {"tests_pass", "tests_fail"}

    def test_unknown_oracle_is_refused(self):
        domain = build_autodev_hddl_domain()
        initial = ProductState(world=frozenset({"code_modified"}), tau=("run_tests",))
        with pytest.raises(ValueError, match="outcome_oracle"):
            AutoDevGymActEnvironment(
                domain=domain, initial_state=initial, outcome_oracle="hidden-bias"
            )


@pytest.mark.skipif(
    find_bcinr_cli() is None,
    reason="autodev cycles allocate through the vendored bcinr engine; "
    "build 'cmca_rank_cli' with 'cargo build --release -p bcinr-cmca' "
    "inside vendor/bcinr",
)
class TestAFDE2601RecoveryThroughLoop:
    def test_loop_recovers_when_latest_evidence_is_green_after_failure(self):
        """End-to-end: a repo whose last CI verification passed (despite an
        earlier failure) starts a delivery cycle, not a repair cycle."""
        from autofde_lab.agent.autodev_loop import run_autodev_cycle
        from autofde_lab.ocel.lifecycle_pystackt import GitCommitRecord

        result = run_autodev_cycle(
            repo_name="afde_2601_probe",
            commits=[
                GitCommitRecord(
                    commit_sha="f0000001",
                    author="dev",
                    timestamp_iso="2026-09-15T00:00:00Z",
                    message="broken commit",
                    affected_files=("src/x.py",),
                    verification_status="FAILED",
                ),
                GitCommitRecord(
                    commit_sha="f0000002",
                    author="dev",
                    timestamp_iso="2026-09-15T01:00:00Z",
                    message="fixed commit",
                    affected_files=("src/x.py",),
                    verification_status="PASSED",
                ),
            ],
            goal_task="deliver_feature",
        )
        assert result.is_success is True
        assert "cycle_receipted" in result.final_state.world
