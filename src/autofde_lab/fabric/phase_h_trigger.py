# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Phase H: the self-triggering outer MAPE-K loop.

Plan reference: docs/2026-08-11-autofde-lab-togaf-autonomic-architecture-plan.md
section 13, "Phase H Becomes the Outer AutoFDE-Lab Loop" --

    Phase H is the actual autonomic trigger: `new observation/OCEL ->
    process inference -> conformance/drift analysis -> trigger evaluation`.
    If the admitted trigger fires, start a new architecture experiment
    cycle ... No human prompt required.

This module is a minimal, real implementation of that closure, scoped to
one concrete drift signal: the content hash of
``ontology/autofde-lab-capabilities.ttl`` versus a stored baseline hash.
When the live hash diverges from the baseline, that is drift -- the
capability ontology changed since the baseline was captured -- and the
trigger fires an unattended, in-process solve+falsify (via
``fabric.solve_and_falsify``) against the known-working PDDLDomain/Astar
blocksworld fixture (``tests/domains/python/pddl_domains/blocks``), with
zero interactive input, and returns both the real trajectory receipt
(``trajectory_sha256``) AND a real falsification standing as evidence the
outer loop closed -- not just "it solved," but "the solve's result was
checked against its own postconditions immediately, automatically."

This is a narrow instance of Phase H, not the full
conformance/drift-analysis pipeline the plan describes (OCEL process
inference is out of scope here) -- it demonstrates the specific claim in
question: that a trigger can fire, invoke a solve, and falsify the result,
with no human in the loop and no separate manual invocation required.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autofde_lab.fabric.solve_and_falsify import solve_and_falsify

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WATCH_FILE = REPO_ROOT / "ontology" / "autofde-lab-capabilities.ttl"
DEFAULT_BASELINE_FILE = REPO_ROOT / "src" / "autofde_lab" / "fabric" / ".phase_h_baseline.json"

XAAS_REPO_ROOT = Path.home() / "xaas"
DEFAULT_COVERAGE_STATE_FILE = (
    REPO_ROOT / "src" / "autofde_lab" / "fabric" / ".phase_h_coverage_state.json"
)

# `mix xaas.close_coverage_gap` (see ~/xaas/lib/mix/tasks/xaas.close_coverage_gap.ex)
# has NO internal guard: its `least_exercised/1` always Enum.min_by's the 5
# aacm: class counts and unconditionally Acts on whichever class comes out
# lowest -- even when all 5 counts are already equal (gap == 0), confirmed
# by a real run on 2026-08-20 against the live xaas Postgres rows, all at 2
# each, which still picked PlannerCandidate and attempted to Act on it. So
# calling the mix task itself is NOT naturally idempotent/self-limiting --
# every invocation Acts, win or not, and a live gap==0 tick would spend a
# real cnv-deploy call for no coverage reason. The guard below is therefore
# real and additive: before invoking the mix task, autofde-lab consults the
# LAST real before/after counts it observed from the previous invocation
# (persisted locally in DEFAULT_COVERAGE_STATE_FILE) and only invokes again
# once that last-observed gap (max count - min count) exceeds
# COVERAGE_GAP_THRESHOLD. Rationale for the threshold value: a single Act
# call moves exactly one class's count by +1 (confirmed in the ex source --
# one Ash.create per run), so immediately after any Act the freshly-created
# imbalance is exactly gap==1 relative to the other four classes -- that is
# the *expected*, not-yet-actionable state right after closing a gap, so
# threshold must be > 1 to avoid re-triggering on every single tick chasing
# its own last Act. COVERAGE_GAP_THRESHOLD = 1 means "skip while gap <= 1,
# invoke once gap >= 2" -- the smallest threshold that does not fire on the
# task's own immediate self-perturbation. The very first tick, with no
# persisted state yet, always invokes once so a real gap baseline exists to
# compare against.
COVERAGE_GAP_THRESHOLD = 1

FIXTURE_DOMAIN = REPO_ROOT / "tests" / "domains" / "python" / "pddl_domains" / "blocks" / "domain.pddl"
FIXTURE_PROBLEM = (
    REPO_ROOT / "tests" / "domains" / "python" / "pddl_domains" / "blocks" / "probBLOCKS-3-0.pddl"
)


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class DriftResult:
    drifted: bool
    watch_file: str
    baseline_sha256: str | None
    current_sha256: str


def read_baseline(baseline_file: Path = DEFAULT_BASELINE_FILE) -> str | None:
    """Return the stored baseline sha256, or None if no baseline exists yet."""
    if not baseline_file.exists():
        return None
    return json.loads(baseline_file.read_text())["sha256"]


def write_baseline(watch_file: Path = DEFAULT_WATCH_FILE, baseline_file: Path = DEFAULT_BASELINE_FILE) -> str:
    """Snapshot the current hash of watch_file as the new baseline."""
    digest = _sha256_of(watch_file)
    baseline_file.write_text(json.dumps({"watch_file": str(watch_file), "sha256": digest}, indent=2))
    return digest


def check_drift(
    watch_file: Path = DEFAULT_WATCH_FILE,
    baseline_file: Path = DEFAULT_BASELINE_FILE,
) -> DriftResult:
    """Compare the live ontology hash against the stored baseline."""
    current = _sha256_of(watch_file)
    baseline = read_baseline(baseline_file)
    return DriftResult(
        drifted=(baseline is not None and baseline != current),
        watch_file=str(watch_file),
        baseline_sha256=baseline,
        current_sha256=current,
    )


def unattended_solve() -> dict:
    """Invoke the real, in-process solve+falsify step with zero human input.

    Calls `fabric.solve_and_falsify.solve_and_falsify()` directly (no
    subprocess, no CLI re-invocation) against the real, already-working
    blocksworld fixture, and returns both the real trajectory receipt AND
    a real falsification standing -- the automatic trigger path now closes
    both halves of the loop (solve, then check the solve) in one call.
    """
    domain_arguments = {"domain_path": str(FIXTURE_DOMAIN), "problem_path": str(FIXTURE_PROBLEM)}
    result, falsification = solve_and_falsify(
        domain="PDDLDomain",
        domain_arguments=domain_arguments,
        solver="Astar",
    )
    return {
        "domain": "PDDLDomain",
        "standing": result.standing.value,
        "terminal": result.terminal,
        "steps": len(result.steps),
        "trajectory_sha256": result.receipt_sha256,
        "falsification": {
            "candidate_id": falsification.candidate_id,
            "standing": falsification.standing.value,
            "rationale": falsification.rationale,
            "receipt_refs": falsification.receipt_refs,
            "violated_constraints": falsification.violated_constraints,
        },
    }


def _read_coverage_state(state_file: Path = DEFAULT_COVERAGE_STATE_FILE) -> dict | None:
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text())


def _write_coverage_state(state: dict, state_file: Path = DEFAULT_COVERAGE_STATE_FILE) -> None:
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True))


def _parse_coverage_gap_output(stdout: str) -> dict:
    """Parse the real `mix xaas.close_coverage_gap` stdout.

    Pulls the "before" per-class counts (`  aacm:<Class> -> <n>` lines,
    the first block printed under "Monitor: real K graph (before)") and
    the real "Closed-loop result: <Class> before=<n> after=<n>
    (delta=<n>)" line the task prints only once it reaches its own final
    Monitor step. If the task's Act step raised (e.g. a real downstream
    cnv-deploy error) the Closed-loop line is absent, which is captured
    honestly as closed=False rather than assumed to have happened.
    """
    before_counts: dict[str, int] = {}
    for match in re.finditer(r"aacm:(\w+)\s*->\s*(\d+)", stdout):
        cls, n = match.group(1), int(match.group(2))
        if cls not in before_counts:
            before_counts[cls] = n

    closed_match = re.search(
        r"Closed-loop result:\s*(\w+)\s*before=(\d+)\s*after=(\d+)\s*\(delta=(-?\d+)\)",
        stdout,
    )
    closed = closed_match is not None
    gap = (max(before_counts.values()) - min(before_counts.values())) if before_counts else 0
    result = {
        "before_counts": before_counts,
        "gap": gap,
        "closed": closed,
    }
    if closed_match:
        result["closed_class"] = closed_match.group(1)
        result["before"] = int(closed_match.group(2))
        result["after"] = int(closed_match.group(3))
        result["delta"] = int(closed_match.group(4))
    return result


def check_coverage_gap(
    xaas_repo_root: Path = XAAS_REPO_ROOT,
    state_file: Path = DEFAULT_COVERAGE_STATE_FILE,
    threshold: int = COVERAGE_GAP_THRESHOLD,
    timeout_seconds: int = 180,
) -> dict:
    """Second real Phase H trigger: the xaas real-SPARQL K-graph coverage gap.

    Real, additive READ-then-invoke call from autofde-lab into xaas -- no
    code is copied or duplicated; `mix xaas.close_coverage_gap` itself
    remains the sole owner of the SPARQL count / least-exercised / Act
    logic (~/xaas/lib/mix/tasks/xaas.close_coverage_gap.ex, untouched).

    Guarded by COVERAGE_GAP_THRESHOLD (see module docstring above) using
    the last real gap this function itself observed, persisted in
    `state_file`, since the mix task has no internal guard of its own.
    """
    last_state = _read_coverage_state(state_file)
    last_gap = last_state.get("gap") if last_state else None

    if last_state is not None and last_gap is not None and last_gap <= threshold:
        return {
            "invoked": False,
            "reason": f"last observed gap={last_gap} <= threshold={threshold}",
            "last_state": last_state,
        }

    try:
        proc = subprocess.run(
            ["mix", "xaas.close_coverage_gap"],
            cwd=str(xaas_repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {"invoked": True, "error": f"{type(exc).__name__}: {exc}"}

    stdout = (proc.stdout or "") + (proc.stderr or "")
    parsed = _parse_coverage_gap_output(stdout)
    parsed["invoked"] = True
    parsed["returncode"] = proc.returncode
    _write_coverage_state(parsed, state_file)
    return parsed


def run_once(
    watch_file: Path = DEFAULT_WATCH_FILE,
    baseline_file: Path = DEFAULT_BASELINE_FILE,
) -> dict:
    """The Phase H tick: check drift; if triggered, solve unattended.

    Returns a dict describing what happened -- always includes the drift
    result; includes the solve receipt only if the trigger actually fired.
    """
    drift = check_drift(watch_file, baseline_file)
    result: dict = {
        "phase": "H",
        "drift": {
            "drifted": drift.drifted,
            "watch_file": drift.watch_file,
            "baseline_sha256": drift.baseline_sha256,
            "current_sha256": drift.current_sha256,
        },
        "triggered": False,
    }
    if drift.drifted:
        receipt = unattended_solve()
        result["triggered"] = True
        result["architecture_change_trigger"] = {
            "evidence": "ontology sha256 diverged from stored baseline",
            "detected_drift": {
                "watch_file": drift.watch_file,
                "baseline_sha256": drift.baseline_sha256,
                "current_sha256": drift.current_sha256,
            },
            "trigger_policy": "sha256-baseline-diff",
        }
        result["solve_receipt"] = receipt
        # Absorb the drift: new baseline is the current hash, so the same
        # unresolved drift does not re-trigger on the next tick.
        write_baseline(watch_file, baseline_file)

    coverage = check_coverage_gap()
    result["coverage_gap"] = coverage
    result["coverage_triggered"] = bool(coverage.get("invoked") and coverage.get("closed"))
    return result


def main() -> None:
    result = run_once()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
