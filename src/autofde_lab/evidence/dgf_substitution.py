"""DGF-Bench deterministic substitution and retirement accounting.

The harness reuses DGF-Bench's executable evaluator.py as the policy kernel.
It performs no model calls and receipts both policy bytes and corpus bytes.
"""

from __future__ import annotations

import hashlib
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
class DGFRunReceipt:
    kernel_digest: str
    dataset_digest: str
    case_count: int
    gate_count: int
    routes_passed: int
    gates_passed: int
    llm_calls: int = 0

    @property
    def standing(self) -> str:
        return (
            "ALIVE"
            if self.case_count > 0
            and self.gate_count > 0
            and self.routes_passed == self.case_count
            and self.gates_passed == self.gate_count
            else "PARTIAL_ALIVE"
        )

    def to_dict(self) -> dict[str, str | int]:
        return {**asdict(self), "standing": self.standing}


@dataclass(frozen=True, slots=True)
class ResidualWorkInputs:
    exception_share: float
    exception_effort_multiplier: float
    ordinary_review_multiplier: float
    rework: float
    automation_support: float
    baseline_overhead: float = 0.0


def residual_work_ratio(inputs: ResidualWorkInputs) -> float:
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


def dgf_evaluator_digest(dgf_root: Path) -> str:
    evaluator_path = dgf_root / "evaluator.py"
    if not evaluator_path.is_file():
        raise FileNotFoundError(f"DGF evaluator not found: {evaluator_path}")
    return "sha256:" + hashlib.sha256(evaluator_path.read_bytes()).hexdigest()


def assert_evaluator_digest(dgf_root: Path, expected: str) -> str:
    actual = dgf_evaluator_digest(dgf_root)
    if actual != expected:
        raise ValueError(
            f"DGF_EVALUATOR_DIGEST_MISMATCH:expected={expected}:actual={actual}"
        )
    return actual


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
    hidden = _read_json(case_dir / "99_hidden_ground_truth.json")
    manifest = _read_json(case_dir / "01_route_manifest.json")
    occurrences = manifest.get("occurrences")
    expected = hidden.get("reference_decisions")

    if not isinstance(occurrences, list) or not occurrences:
        raise ValueError(f"DGF_CASE_HAS_NO_GATE_OCCURRENCES:{case_dir}")
    if not isinstance(expected, list) or not expected:
        raise ValueError(f"DGF_CASE_HAS_NO_REFERENCE_DECISIONS:{case_dir}")
    if len(occurrences) != len(expected):
        raise ValueError(
            f"DGF_CASE_CONTRACT_COUNT_MISMATCH:{case_dir}:"
            f"occurrences={len(occurrences)}:reference={len(expected)}"
        )

    evaluator = _load_evaluator(dgf_root)
    actual = evaluator.evaluate_route(hidden["canonical_truth"], occurrences)

    gate_total = max(len(actual), len(expected))
    gate_matches = sum(
        1
        for got, want in zip(actual, expected, strict=False)
        if _canonical(got) == _canonical(want)
    )
    route_match = len(actual) == len(expected) and gate_matches == gate_total

    return DGFCaseScore(
        case_id=str(hidden.get("case_id", case_dir.name)),
        case_dir=str(case_dir),
        gate_total=gate_total,
        gate_matches=gate_matches,
        route_match=route_match,
    )


def discover_dgf_cases(dataset_root: Path) -> tuple[Path, ...]:
    cases = {
        path.parent
        for path in dataset_root.rglob("99_hidden_ground_truth.json")
        if (path.parent / "01_route_manifest.json").is_file()
    }
    return tuple(sorted(cases))


def dgf_dataset_digest(
    case_dirs: Sequence[Path],
    *,
    dataset_root: Path | None = None,
) -> str:
    if not case_dirs:
        raise ValueError("DGF_EMPTY_DATASET")

    root = dataset_root.resolve() if dataset_root is not None else None
    digest = hashlib.sha256()
    for case_dir in sorted((path.resolve() for path in case_dirs), key=str):
        label = (
            case_dir.relative_to(root).as_posix()
            if root is not None and case_dir.is_relative_to(root)
            else case_dir.name
        )
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        for filename in ("01_route_manifest.json", "99_hidden_ground_truth.json"):
            path = case_dir / filename
            if not path.is_file():
                raise FileNotFoundError(path)
            digest.update(filename.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


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
    cases = tuple(case_dirs) if case_dirs is not None else discover_dgf_cases(dataset_root)
    if not cases:
        raise ValueError("DGF_EMPTY_DATASET")
    scores = tuple(run_dgf_case(case_dir, dgf_root=dgf_root) for case_dir in cases)
    return scores, summarize_dgf_scores(scores)


def run_receipted_dgf_dataset(
    dataset_root: Path,
    *,
    dgf_root: Path,
    case_dirs: Sequence[Path] | None = None,
    expected_evaluator_digest: str | None = None,
) -> tuple[tuple[DGFCaseScore, ...], DGFSubstitutionSummary, DGFRunReceipt]:
    cases = tuple(case_dirs) if case_dirs is not None else discover_dgf_cases(dataset_root)
    if not cases:
        raise ValueError("DGF_EMPTY_DATASET")

    kernel_digest = (
        assert_evaluator_digest(dgf_root, expected_evaluator_digest)
        if expected_evaluator_digest is not None
        else dgf_evaluator_digest(dgf_root)
    )
    scores, summary = run_dgf_dataset(
        dataset_root,
        dgf_root=dgf_root,
        case_dirs=cases,
    )
    receipt = DGFRunReceipt(
        kernel_digest=kernel_digest,
        dataset_digest=dgf_dataset_digest(cases, dataset_root=dataset_root),
        case_count=summary.cases,
        gate_count=summary.gates,
        routes_passed=summary.routes_passed,
        gates_passed=summary.gates_passed,
    )
    return scores, summary, receipt
