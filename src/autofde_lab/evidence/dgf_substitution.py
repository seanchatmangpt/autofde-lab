"""DGF-Bench deterministic substitution and retirement accounting.

This module intentionally reuses the DGF-Bench repository's executable
`evaluator.py` as the policy kernel.  It does not copy governance policy into
AutoFDE and it performs no model calls.

A local DGF-Bench checkout provides:
- generated case directories containing 01_route_manifest.json and
  99_hidden_ground_truth.json;
- evaluator.py, the executable reference policy.

The harness re-evaluates the canonical facts through that policy and compares
the produced route to the stored reference route.  This is a direct
reproduction surface for the benchmark's deterministic-control experiment.
"""

from __future__ import annotations

import importlib.util
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Sequence


@dataclass(frozen=True, slots=True)
class DGFCaseScore:
    case_id: str
    case_dir: str
    gate_total: int
    gate_matches: int
    route_match: bool

    @property
    def gate_success_rate(self) -> float:
        return self.gate_matches / self.gate_total if self.gate_total else 0.0


@dataclass(frozen=True, slots=True)
class DGFSubstitutionSummary:
    cases: int
    routes_passed: int
    gates: int
    gates_passed: int

    @property
    def route_success_rate(self) -> float:
        return self.routes_passed / self.cases if self.cases else 0.0

    @property
    def gate_success_rate(self) -> float:
        return self.gates_passed / self.gates if self.gates else 0.0

    def to_dict(self) -> dict[str, int | float]:
        return {
            **asdict(self),
            "route_success_rate": self.route_success_rate,
            "gate_success_rate": self.gate_success_rate,
        }


@dataclass(frozen=True, slots=True)
class ResidualWorkInputs:
    """Normalized recurring-work terms from the paper's retirement equation."""

    exception_share: float
    exception_effort_multiplier: float
    ordinary_review_multiplier: float
    rework: float
    automation_support: float
    baseline_overhead: float = 0.0


def residual_work_ratio(inputs: ResidualWorkInputs) -> float:
    """Compute remaining recurring work relative to the original baseline.

    rho = (phi*eta + (1-phi)*mu + r + b_A) / (1 + b_H)
    """
    values = asdict(inputs)
    if not 0.0 <= inputs.exception_share <= 1.0:
        raise ValueError("exception_share must be in [0, 1]")
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("residual-work inputs must be finite")
    for name, value in values.items():
        if name != "exception_share" and value < 0:
            raise ValueError(f"{name} must be non-negative")

    numerator = (
        inputs.exception_share * inputs.exception_effort_multiplier
        + (1.0 - inputs.exception_share) * inputs.ordinary_review_multiplier
        + inputs.rework
        + inputs.automation_support
    )
    return numerator / (1.0 + inputs.baseline_overhead)


def _load_evaluator(dgf_root: Path) -> ModuleType:
    evaluator_path = dgf_root / "evaluator.py"
    if not evaluator_path.is_file():
        raise FileNotFoundError(f"DGF evaluator not found: {evaluator_path}")

    spec = importlib.util.spec_from_file_location(
        "autofde_lab_dgf_reference_evaluator", evaluator_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load DGF evaluator: {evaluator_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "evaluate_route", None)):
        raise AttributeError("DGF evaluator.py must expose evaluate_route(case, occurrences)")
    return module


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def run_dgf_case(case_dir: Path, *, dgf_root: Path) -> DGFCaseScore:
    """Re-run one DGF case through its executable deterministic policy."""
    hidden = _read_json(case_dir / "99_hidden_ground_truth.json")
    manifest = _read_json(case_dir / "01_route_manifest.json")

    evaluator = _load_evaluator(dgf_root)
    actual = evaluator.evaluate_route(
        hidden["canonical_truth"],
        manifest["occurrences"],
    )
    expected = hidden["reference_decisions"]

    gate_total = max(len(actual), len(expected))
    gate_matches = sum(
        1
        for got, want in zip(actual, expected, strict=False)
        if _canonical(got) == _canonical(want)
    )
    route_match = (
        len(actual) == len(expected)
        and gate_matches == gate_total
    )

    return DGFCaseScore(
        case_id=str(hidden.get("case_id", case_dir.name)),
        case_dir=str(case_dir),
        gate_total=gate_total,
        gate_matches=gate_matches,
        route_match=route_match,
    )


def discover_dgf_cases(dataset_root: Path) -> tuple[Path, ...]:
    """Discover generated DGF cases without depending on a manifest dialect."""
    cases = {
        path.parent
        for path in dataset_root.rglob("99_hidden_ground_truth.json")
        if (path.parent / "01_route_manifest.json").is_file()
    }
    return tuple(sorted(cases))


def summarize_dgf_scores(scores: Iterable[DGFCaseScore]) -> DGFSubstitutionSummary:
    rows = tuple(scores)
    return DGFSubstitutionSummary(
        cases=len(rows),
        routes_passed=sum(int(row.route_match) for row in rows),
        gates=sum(row.gate_total for row in rows),
        gates_passed=sum(row.gate_matches for row in rows),
    )


def run_dgf_dataset(
    dataset_root: Path,
    *,
    dgf_root: Path,
    case_dirs: Sequence[Path] | None = None,
) -> tuple[tuple[DGFCaseScore, ...], DGFSubstitutionSummary]:
    """Run every discovered case through the deterministic reference kernel."""
    cases = tuple(case_dirs) if case_dirs is not None else discover_dgf_cases(dataset_root)
    scores = tuple(run_dgf_case(case_dir, dgf_root=dgf_root) for case_dir in cases)
    return scores, summarize_dgf_scores(scores)
