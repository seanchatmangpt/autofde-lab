# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test suite for Closed-Loop Auto-Dev Engine.

Validates:
1. End-to-end loop: pystackt Git Extraction -> FOND x HDDL Planning -> CMCA -> GymAct -> OCEL 2.0 -> Conformance.
2. Defect repair auto-dev cycle when initial repo state has test failures.
3. Feature delivery auto-dev cycle when initial repo state is clean.
4. Conformance verification and cryptographic receipt generation.
"""

from __future__ import annotations

import pytest

from autofde_lab.agent.autodev_loop import run_autodev_cycle
from autofde_lab.cmca.bcinr_bridge import find_bcinr_cli
from autofde_lab.cmca.contracts import ResourceBudget
from autofde_lab.ocel.lifecycle_pystackt import GitCommitRecord

# The default CMCA engine delegates to the vendored bcinr-cmca crate (see
# src/autofde_lab/cmca/bcinr_bridge.py): this suite exercises that real
# engine and therefore requires the built `cmca_rank_cli` binary.
pytestmark = pytest.mark.skipif(
    find_bcinr_cli() is None,
    reason="no built 'cmca_rank_cli' binary found -- build with "
    "'cargo build --release -p bcinr-cmca' inside vendor/bcinr",
)


def test_autodev_loop_feature_delivery():
    """Verify clean feature delivery auto-dev cycle on a software repository."""
    commits = [
        GitCommitRecord(
            commit_sha="a1b2c3d4e5",
            author="lead_dev",
            timestamp_iso="2026-09-15T00:00:00Z",
            message="initial clean commit",
            affected_files=("src/module.py",),
            verification_status="PASSED",
        )
    ]
    budget = ResourceBudget(
        total_ticks=4000,
        memory_bytes=32768,
        max_verification_depth=5,
        consequence_risk_budget=0.2,
        concurrency_lanes=4,
    )

    result = run_autodev_cycle(
        repo_name="ash_pplan_sample",
        commits=commits,
        goal_task="deliver_feature",
        budget=budget,
    )

    assert result.is_success is True
    assert len(result.final_state.tau) == 0
    assert "cycle_receipted" in result.final_state.world
    assert "repo_clean" in result.final_state.world

    # Check executed trace matches HDDL decomposition methods
    assert "refine:tdd_delivery" in result.executed_trace
    assert "inspect_code" in result.executed_trace
    assert "write_failing_test" in result.executed_trace
    assert "apply_patch" in result.executed_trace
    assert "refine:test_and_receipt" in result.executed_trace
    assert "run_tests" in result.executed_trace
    assert "commit_receipt" in result.executed_trace

    # Verify OCEL 2.0 log generation
    assert len(result.execution_ocel.events) == len(result.executed_trace)

    # Verify Cryptographic Receipt
    assert result.receipt.is_conforming is True
    assert result.receipt.standing == "ALIVE"
    assert result.receipt.cmca_allocated_ticks == 4000
    assert result.receipt.receipt_id.startswith("rcpt_autodev_")


def test_autodev_loop_defect_repair():
    """Verify defect repair auto-dev cycle triggered by failing repository state."""
    commits = [
        GitCommitRecord(
            commit_sha="f9e8d7c6b5",
            author="ci_bot",
            timestamp_iso="2026-09-15T01:00:00Z",
            message="broken build commit",
            affected_files=("src/broken.py",),
            verification_status="FAILED",  # Triggers test_failing world state
        )
    ]

    result = run_autodev_cycle(
        repo_name="ash_r2rml_defect",
        commits=commits,
        goal_task="repair_defect",
    )

    assert result.is_success is True
    assert len(result.final_state.tau) == 0
    assert "cycle_receipted" in result.final_state.world

    # Repair defect should use direct_patch_repair
    assert "refine:direct_patch_repair" in result.executed_trace
    assert "inspect_code" in result.executed_trace
    assert "apply_patch" in result.executed_trace
    assert "commit_receipt" in result.executed_trace
    assert result.receipt.standing == "ALIVE"
