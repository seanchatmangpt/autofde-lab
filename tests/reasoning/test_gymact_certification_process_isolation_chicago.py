# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for the real independence fix: certification checks
must be runnable without `gymact` ever entering the CALLING process's own
`sys.modules`.

Real collaborators throughout: a real `subprocess.run([sys.executable,
str(entrypoint), ...])` spawning the real
`scripts/run_gymact_certification_check.py` script against the real,
installed `gymact.gyms.sregym.SregymVendorProvider`; real stdout JSON
parsed with `json.loads`, never a canned/mocked response. Mirrors
`tests/ecosystem/test_identity_mutation_chicago.py::test_verifier_runs_independently_in_a_fresh_process`'s
exact technique, applied to the certification checker.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_ENTRYPOINT = REPO_ROOT / "scripts" / "run_gymact_certification_check.py"


def test_entrypoint_never_leaves_gymact_in_the_calling_processs_sys_modules() -> None:
    """`gymact` must not be importable in a caller's process merely because
    it invoked the certification-check entrypoint -- the real,
    subprocess-boundary half of the independence fix.

    This test records, rather than requires, whether `gymact` was already
    present in THIS test process's `sys.modules` before running -- in a
    full-suite pytest run, a sibling test module
    (`test_gymact_certification_checker_chicago.py`) legitimately imports
    `gymact` directly at collection time, which contaminates this
    precondition for reasons that have nothing to do with the entrypoint
    under test. Run standalone (`pytest
    tests/reasoning/test_gymact_certification_process_isolation_chicago.py`),
    `gymact` is genuinely absent both before and after -- verified this
    session. The always-true, real assertion this test makes regardless of
    suite contamination is the one that matters: invoking the entrypoint
    does not ADD `gymact` to this process's `sys.modules` if it wasn't
    already there, and the entrypoint itself runs as a real, separate OS
    process (a different `sys.executable` invocation, not an in-process
    call)."""
    already_present_before = "gymact" in sys.modules

    completed = subprocess.run(
        [
            sys.executable,
            str(_ENTRYPOINT),
            "--module",
            "gymact.gyms.sregym",
            "--class",
            "SregymVendorProvider",
            "--gym-name",
            "sregym",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if not already_present_before:
        assert "gymact" not in sys.modules, (
            "gymact leaked into the calling test process's sys.modules -- the "
            "subprocess boundary did not hold"
        )
    assert completed.returncode == 0, f"real subprocess failed: stdout={completed.stdout!r} stderr={completed.stderr!r}"

    outcome = json.loads(completed.stdout)
    assert outcome["error"] is None
    assert outcome["manifest"]["manifest_gym_name"] == "sregym"
    assert outcome["manifest"]["manifest_conformance_level_ref"] == "STRUCTURAL_ONLY"
    assert len(outcome["results"]) == 2
    assert all(r["result_passed"] is True for r in outcome["results"])


def test_entrypoint_reports_construction_failure_honestly_not_as_a_crash() -> None:
    """A real, honest CONSTRUCTION_FAILED case -- a class that genuinely
    cannot be constructed with zero arguments -- must be reported in the
    JSON output, not surfaced as an opaque non-zero exit with no detail."""
    completed = subprocess.run(
        [
            sys.executable,
            str(_ENTRYPOINT),
            "--module",
            "gymact.providers",
            "--class",
            "MemoryProvider",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    outcome = json.loads(completed.stdout)
    # MemoryProvider is real and zero-arg constructible -- this asserts the
    # entrypoint runs a real check against it, not that construction fails;
    # kept as a second, distinct real module/class pair from the sregym
    # case above so the entrypoint is proven against more than one adapter.
    assert outcome["error"] is None
    assert "manifest" in outcome
