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
trigger fires an unattended ``python -m autofde_lab.fabric solve``
invocation against the known-working PDDLDomain/Astar blocksworld fixture
(``tests/domains/python/pddl_domains/blocks``), with zero interactive
input, and returns the parsed receipt (including ``trajectory_sha256``)
as evidence the outer loop closed.

This is a narrow instance of Phase H, not the full
conformance/drift-analysis pipeline the plan describes (OCEL process
inference is out of scope here) -- it demonstrates the specific claim in
question: that a trigger can fire and invoke a solve with no human in the
loop.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WATCH_FILE = REPO_ROOT / "ontology" / "autofde-lab-capabilities.ttl"
DEFAULT_BASELINE_FILE = REPO_ROOT / "src" / "autofde_lab" / "fabric" / ".phase_h_baseline.json"

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
    """Invoke the real fabric CLI solve command with zero human input.

    Runs `python -m autofde_lab.fabric solve PDDLDomain --solver Astar`
    against the real, already-working blocksworld fixture, and returns the
    parsed JSON receipt (including trajectory_sha256).
    """
    domain_arguments = json.dumps(
        {"domain_path": str(FIXTURE_DOMAIN), "problem_path": str(FIXTURE_PROBLEM)}
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autofde_lab.fabric",
            "solve",
            "PDDLDomain",
            "--solver",
            "Astar",
            "--domain-arguments",
            domain_arguments,
            "--no-cache",
        ],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,  # no interactive input possible
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    stdout = completed.stdout
    # The PDDL parser logs informational lines to stdout ahead of the
    # JSON receipt (e.g. "[info] Parsing ...pddl"); the receipt itself is
    # the final top-level JSON object in the stream, so decode from its
    # first '{' rather than assuming stdout is pure JSON.
    start = stdout.rfind("\n{\n")
    if start == -1 and stdout.startswith("{"):
        start = -1
    payload = stdout[start + 1 :] if start != -1 else stdout
    return json.loads(payload)


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
    return result


def main() -> None:
    result = run_once()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
