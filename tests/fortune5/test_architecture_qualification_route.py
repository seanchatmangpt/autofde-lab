"""CI route court for the architecture qualification step in pr-ci.yml.

Chicago style: reads the real workflow file, extracts the real ``archq`` route pattern
and runs the real ``grep -E`` (the same matcher the workflow's ``route`` function uses)
over the court's own subject paths. No test double.

Hole guarded (PR #203 audit, head 0dcf14c9): the court step was gated on the
``fortune5`` route, whose pattern matched none of the court module, its benchmark or
its bench receipt, so a PR changing only the court skipped the court (vacuous gate).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-ci.yml"

SUBJECTS = (
    "src/autofde_lab/enterprise_architecture.py",
    "benchmarks/architecture_qualification.py",
    "receipts/v26.9.26/architecture-qualification-bench.json",
    "tests/fortune5/test_architecture_qualification_court.py",
    "tests/fortune5/test_architecture_qualification_adversarial.py",
    "tests/fortune5/test_architecture_qualification_bench.py",
    "tests/fortune5/test_architecture_qualification_category.py",
    "tests/fortune5/test_architecture_qualification_route.py",
    "docs/rfc/v26.9.26/abb-sbb-implementation.md",
    ".github/workflows/pr-ci.yml",
)
NON_SUBJECTS = (
    "src/autofde_lab/fortune5/enterprise_architecture.py",
    "src/autofde_lab/enterprise_architecture.pyc",
    "README.md",
    "tests/fortune5/test_space.py",
)


def _route_pattern(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"route {name} \\\n\s*'([^']+)'", text)
    assert match, f"route {name} not declared in {WORKFLOW}"
    return match.group(1)


def _grep_matches(pattern: str, path: str) -> bool:
    proc = subprocess.run(
        ["grep", "-Eq", pattern], input=path + "\n", text=True, check=False
    )
    assert proc.returncode in (0, 1), proc
    return proc.returncode == 0


def test_archq_route_matches_every_court_subject():
    pattern = _route_pattern("archq")
    missed = [path for path in SUBJECTS if not _grep_matches(pattern, path)]
    assert missed == []


def test_archq_route_is_not_a_catch_all():
    pattern = _route_pattern("archq")
    leaked = [path for path in NON_SUBJECTS if _grep_matches(pattern, path)]
    assert leaked == []


def test_every_committed_court_test_is_a_route_subject_and_is_run_by_the_step():
    pattern = _route_pattern("archq")
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text.split("- name: Architecture qualification court / Python 3.12", 1)[1]
    step = step.split("\n      - ", 1)[0]
    assert "if: steps.routes.outputs.archq == 'true'" in step
    tests = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests" / "fortune5").glob(
            "test_architecture_qualification_*.py"
        )
    )
    assert len(tests) >= 5
    for test in tests:
        assert _grep_matches(pattern, test), test
        assert test in step, f"{test} not run by the court step"


def test_workflow_dispatch_enables_the_archq_route():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "fortune5=true\\narchq=true\\n" in text
